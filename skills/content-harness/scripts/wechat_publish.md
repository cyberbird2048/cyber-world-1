# 微信公众号发布操作手册（内部 API 方式）

> **2026-04-15 重写**：全流程压缩为 **2 次授权**（Block A + Block B），减少权限弹窗。
> 作者固定为 **cyber brid**（阿泽账号），不可变更。
> 放弃 CDP 编辑器 UI 操作，全程走微信内部 API。

## 前置条件

1. CDP Proxy 运行中（`curl -s http://localhost:3456/health`）
2. 用户已在 Chrome 中登录公众号后台（至少有一个 `mp.weixin.qq.com` 标签页）
3. 图片文件已准备好：封面图（cover.png）+ 可选插图（illus.png）

---

## Block A（1次授权）— 环境检查 + Token + 上传所有图片

将封面图和插图一次性全部上传，获取所有 CDN URL 和 media_id。

```bash
#!/bin/bash
# === 环境检查 ===
curl -s http://localhost:3456/health || { echo "CDP 未运行"; exit 1; }

# === 找已登录的 MP 标签页 ===
TARGET=$(curl -s http://localhost:3456/targets | python3 -c "
import sys, json
for t in json.load(sys.stdin):
    if 'mp.weixin.qq.com' in t.get('url',''):
        print(t['targetId']); break
")
if [ -z "$TARGET" ]; then
    TARGET=$(curl -s "http://localhost:3456/new?url=https%3A%2F%2Fmp.weixin.qq.com" | \
        python3 -c "import sys,json; print(json.load(sys.stdin)['targetId'])")
    sleep 3
fi

# === 获取 token（从当前 URL 提取）===
TOKEN=$(curl -s "http://localhost:3456/info?target=$TARGET" | python3 -c "
import sys, json, re
m = re.search(r'token=(\d+)', json.load(sys.stdin).get('url',''))
print(m.group(1) if m else '')
")
[ -z "$TOKEN" ] && { echo "Token 为空，请确认已登录 mp.weixin.qq.com"; exit 1; }
echo "TARGET=$TARGET  TOKEN=$TOKEN"

# === 上传封面图 ===
COVER_PATH="/path/to/cover.png"   # ← 替换为实际路径
COVER_B64=$(base64 -i "$COVER_PATH" | tr -d '\n')

python3 - <<PYEOF > /tmp/cover_upload.js
b64 = "$COVER_B64"
tok = "$TOKEN"
print(f"""(async () => {{
  const b = atob('{b64}');
  const ab = new ArrayBuffer(b.length);
  const ia = new Uint8Array(ab);
  for (let i = 0; i < b.length; i++) ia[i] = b.charCodeAt(i);
  const fd = new FormData();
  fd.append('file', new Blob([ab], {{type: 'image/png'}}), 'cover.png');
  const r = await fetch('/cgi-bin/filetransfer?action=upload_material&f=json&scene=1&writetype=doublewrite&groupid=1&token={tok}&lang=zh_CN', {{method:'POST',body:fd}});
  return JSON.stringify(await r.json());
}})()""")
PYEOF

COVER_RESULT=$(curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary @/tmp/cover_upload.js)
COVER_MEDIA_ID=$(echo "$COVER_RESULT" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); r=json.loads(d.get('result','{}') if isinstance(d,dict) else d); print(r.get('content',''))")
COVER_CDN_URL=$(echo "$COVER_RESULT" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); r=json.loads(d.get('result','{}') if isinstance(d,dict) else d); print(r.get('cdn_url',''))")
echo "封面 media_id: $COVER_MEDIA_ID"
echo "封面 cdn_url: $COVER_CDN_URL"

# === 上传插图（可选，有插图才执行）===
ILLUS_PATH="/path/to/illus.png"   # ← 替换为实际路径，无插图则跳过
ILLUS_CDN_URL=""
if [ -f "$ILLUS_PATH" ]; then
    ILLUS_B64=$(base64 -i "$ILLUS_PATH" | tr -d '\n')
    python3 - <<PYEOF2 > /tmp/illus_upload.js
b64 = "$ILLUS_B64"
tok = "$TOKEN"
print(f"""(async () => {{
  const b = atob('{b64}');
  const ab = new ArrayBuffer(b.length);
  const ia = new Uint8Array(ab);
  for (let i = 0; i < b.length; i++) ia[i] = b.charCodeAt(i);
  const fd = new FormData();
  fd.append('file', new Blob([ab], {{type: 'image/png'}}), 'illus.png');
  const r = await fetch('/cgi-bin/filetransfer?action=upload_material&f=json&scene=1&writetype=doublewrite&groupid=1&token={tok}&lang=zh_CN', {{method:'POST',body:fd}});
  return JSON.stringify(await r.json());
}})()""")
PYEOF2
    ILLUS_RESULT=$(curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
        -H "Content-Type: text/plain" \
        --data-binary @/tmp/illus_upload.js)
    ILLUS_CDN_URL=$(echo "$ILLUS_RESULT" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); r=json.loads(d.get('result','{}') if isinstance(d,dict) else d); print(r.get('cdn_url',''))")
    echo "插图 cdn_url: $ILLUS_CDN_URL"
fi

# 保存变量供 Block B 使用
cat > /tmp/wechat_vars.sh <<EOF
TARGET="$TARGET"
TOKEN="$TOKEN"
COVER_MEDIA_ID="$COVER_MEDIA_ID"
COVER_CDN_URL="$COVER_CDN_URL"
ILLUS_CDN_URL="$ILLUS_CDN_URL"
EOF
echo "Block A 完成。变量已保存到 /tmp/wechat_vars.sh"
```

---

## Block B（1次授权）— 编辑器注入 + 保存草稿 + 绑定封面 + 截图验证

接续 Block A 的变量，完成全部剩余步骤。

```bash
#!/bin/bash
# 加载 Block A 保存的变量
source /tmp/wechat_vars.sh

# ============================================================
# 配置区 — 填写文章内容
# ============================================================
TITLE="文章标题"
AUTHOR="cyber brid"   # 固定，不可改
DIGEST="摘要文字（前54字）"

# 正文 HTML（p 标签格式，内嵌插图 CDN URL）
# 插图用: <p style="text-align:center;"><img src="$ILLUS_CDN_URL" style="max-width:100%;"/></p>
read -r -d '' BODY_HTML << 'HTMLEOF'
<p style="font-size:16px;line-height:2em;color:rgb(55,53,47);margin-bottom:1.5em;">正文段落...</p>
HTMLEOF
# ============================================================

# === Step 1: 导航到新建编辑器 ===
curl -s "http://localhost:3456/navigate?target=$TARGET&url=https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2%26action=edit%26isNew=1%26type=77%26token=$TOKEN%26lang=zh_CN" > /dev/null
sleep 3

# === Step 2: 注入标题 ===
TITLE_B64=$(python3 -c "import base64; print(base64.b64encode('$TITLE'.encode()).decode())")
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary "(function(){var s=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;var el=document.querySelector('textarea#title');s.call(el,decodeURIComponent(escape(atob('$TITLE_B64'))));el.dispatchEvent(new Event('input',{bubbles:true}));})()" > /dev/null
sleep 0.3

# === Step 3: 注入作者（cyber brid）===
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary "(function(){var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;var el=document.querySelector('input#author');if(el){s.call(el,'cyber brid');el.dispatchEvent(new Event('input',{bubbles:true}));}})()" > /dev/null
sleep 0.3

# === Step 4: 注入正文 HTML（base64 编码避免转义问题）===
BODY_B64=$(python3 -c "import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())" <<< "$BODY_HTML")
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary "(function(){var html=decodeURIComponent(escape(atob('$BODY_B64')));var ed=document.querySelector('div.ProseMirror[contenteditable=true]');if(ed){ed.innerHTML=html;ed.dispatchEvent(new Event('input',{bubbles:true}));}})()" > /dev/null
sleep 0.5

# === Step 5: 点击"保存为草稿" ===
curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary "(function(){var btns=document.querySelectorAll('.send_wording');if(btns[2]){btns[2].click();}else{Array.from(document.querySelectorAll('button,a')).find(b=>b.textContent.includes('保存为草稿'))?.click();}})()" > /dev/null
sleep 3

# === Step 6: 获取草稿 ID（从 URL 中提取）===
DRAFT_ID=$(curl -s "http://localhost:3456/info?target=$TARGET" | python3 -c "
import sys,json,re
url = json.load(sys.stdin).get('url','')
m = re.search(r'appmsgid=(\d+)', url)
print(m.group(1) if m else '')
")
echo "草稿 ID: $DRAFT_ID"
[ -z "$DRAFT_ID" ] && { echo "草稿 ID 获取失败，请手动检查草稿箱"; exit 1; }

# === Step 7: operate_appmsg — 绑定封面 + 写完整内容 ===
FULL_HTML_B64=$(python3 -c "import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())" <<< "$BODY_HTML")

python3 - <<PYEOF > /tmp/operate_appmsg.js
import base64
full_html = open('/tmp/body.html', 'r', encoding='utf-8').read() if __import__('os').path.exists('/tmp/body.html') else ""
tok = "$TOKEN"
draft_id = "$DRAFT_ID"
title = "$TITLE"
author = "cyber brid"
digest = "$DIGEST"
cover_id = "$COVER_MEDIA_ID"
cover_cdn = "$COVER_CDN_URL"

# 将 body_html 写入临时文件
body_b64 = base64.b64encode("$BODY_HTML".encode()).decode()

print(f"""(async () => {{
  const bodyHtml = decodeURIComponent(escape(atob('{body_b64}')));
  const fd = new URLSearchParams();
  fd.append('token','{tok}'); fd.append('lang','zh_CN'); fd.append('f','json'); fd.append('ajax','1');
  fd.append('AppMsgId','{draft_id}'); fd.append('count','1'); fd.append('operate_from','Chrome'); fd.append('isnew','0');
  fd.append('title0','{title}'); fd.append('author0','{author}'); fd.append('content0',bodyHtml);
  fd.append('digest0','{digest}');
  fd.append('fileid0','{cover_id}'); fd.append('cdn_url0','{cover_cdn}');
  fd.append('cdn_235_1_url0','{cover_cdn}'); fd.append('cdn_1_1_url0','{cover_cdn}'); fd.append('cdn_3_4_url0','{cover_cdn}');
  fd.append('show_cover_pic0','0'); fd.append('need_open_comment0','1'); fd.append('only_fans_can_comment0','0');
  fd.append('originality_type0','1');
  const r = await fetch('/cgi-bin/operate_appmsg?sub=update&t=ajax-response&type=77', {{
    method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}}, body:fd.toString()
  }});
  return JSON.stringify(await r.json());
}})()""")
PYEOF

OPERATE_RESULT=$(curl -s -X POST "http://localhost:3456/eval?target=$TARGET" \
    -H "Content-Type: text/plain" \
    --data-binary @/tmp/operate_appmsg.js)
echo "operate_appmsg 结果: $OPERATE_RESULT"

# === Step 8: 截图验证 ===
sleep 1
# 导航到草稿预览
curl -s "http://localhost:3456/navigate?target=$TARGET&url=https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2%26action=edit%26isNew=0%26type=77%26appmsgid=$DRAFT_ID%26token=$TOKEN%26lang=zh_CN" > /dev/null
sleep 2
curl -s "http://localhost:3456/screenshot?target=$TARGET" > /tmp/wechat_verify.png
echo "截图已保存到 /tmp/wechat_verify.png"
echo "Block B 完成 — 草稿 ID: $DRAFT_ID"
```

---

## 群发审批（技术层门禁，不可绕过）

草稿完成后，用 AskUserQuestion 工具弹出确认：

- 问题："即将向订阅者群发《[文章标题]》，此操作发出后不可撤回。确认发布？"
- 选项：`["确认群发", "取消，先留草稿"]`
- 取消 → 立即终止，草稿保留
- 确认群发 → 在编辑器点击"发表"按钮，截图确认

**⚠️ 订阅号群发最后一步需要手机扫码二次确认，CDP 流程止步于草稿完成。**
草稿已安全保存在草稿箱，用户可手动点"发表"。

---

## HTML 内容格式（赛博禅心排版）

```javascript
// 实测最优排版参数（来自 2026-04-14 作者扫描数据）
const pStyle = 'font-size:16px;line-height:2em;color:rgb(55,53,47);margin-bottom:1.5em;';
const boldStyle = 'font-weight:bold;color:rgb(55,53,47);';
const p = text => `<p style="${pStyle}">${text}</p>`;
const bold = text => `<strong style="${boldStyle}">${text}</strong>`;
const img = url => `<p style="text-align:center;margin:2em 0;"><img src="${url}" style="max-width:100%;border-radius:4px;" /></p>`;
// 段落分节用空白段，不用 <hr>
const spacer = `<p style="margin:2em 0;">&nbsp;</p>`;
```

插图嵌入：使用 Block A 上传后返回的 `ILLUS_CDN_URL` 作为 `<img src>`。

---

## 注意事项

- **作者固定为 `cyber brid`**，所有 operate_appmsg 调用中 `author0` 字段不可修改
- 公众号后台 session 约 2 小时过期
- 订阅号每天群发上限 1 次
- `operate_appmsg` 的 `content0` 字段**必须包含完整 HTML**，缺失则正文被清空
- 上传素材的 `filetransfer` 接口无频率限制，但单次最大 10MB
- 音频/配乐需要在编辑器 UI 中手动添加（"音频"工具栏按钮 → QQ 音乐搜索）

## 推荐工作流（2次授权）

```
Block A（1次授权）:
  1. CDP health check + 找 MP tab + 提取 token
  2. 上传封面图 → 获取 COVER_MEDIA_ID + COVER_CDN_URL
  3. 上传插图（如有）→ 获取 ILLUS_CDN_URL
  4. 保存变量到 /tmp/wechat_vars.sh

Block B（1次授权）:
  5. 导航到新建编辑器
  6. 注入标题 + 作者(cyber brid) + 正文 HTML
  7. 点击"保存为草稿"
  8. 提取草稿 ID（从 URL）
  9. operate_appmsg 绑定封面 + 写完整内容
  10. 截图验证

群发（用户确认后）:
  11. AskUserQuestion 确认
  12. 点击"发表"按钮（用户手机扫码）
```
