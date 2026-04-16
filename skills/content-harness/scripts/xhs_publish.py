#!/usr/bin/env python3
"""
小红书创作中心半自动发布脚本（CDP方式）

用法：
  python3 xhs_publish.py \
    --title "标题（≤20字）" \
    --body "正文内容" \
    --tags "AI工具,Claude使用教程,办公效率" \
    --images "/path/cover.png,/path/illus.png"

流程：
  1. 找到/打开 creator.xiaohongshu.com 标签页
  2. 导航到发布页
  3. 上传图片
  4. 注入标题、正文、话题标签
  5. 暂停 → 等用户手动点"发布"

注意：最后一步发布由用户手动操作，脚本不自动点击。
"""

import argparse
import sys
import json
import time
import base64
import urllib.request
import urllib.parse
from pathlib import Path

CDP_BASE = "http://localhost:3456"

# ─── CDP 基础操作 ──────────────────────────────────────────────────────────────

def cdp_get(path):
    with urllib.request.urlopen(f"{CDP_BASE}{path}", timeout=10) as r:
        raw = r.read()
        return json.loads(raw)

def cdp_get_raw(path):
    """返回原始字节（用于截图等二进制响应）"""
    with urllib.request.urlopen(f"{CDP_BASE}{path}", timeout=10) as r:
        return r.read()

def cdp_post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{CDP_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw.decode("utf-8", errors="replace")}

def eval_js(target_id, js, timeout=20):
    """CDP eval — text/plain body，支持完整 JS 表达式"""
    body = js.encode("utf-8")
    req = urllib.request.Request(
        f"{CDP_BASE}/eval?target={target_id}",
        data=body,
        headers={"Content-Type": "text/plain"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout + 5) as r:
        raw = r.read()
    try:
        result = json.loads(raw)
        if "value" in result:
            return result["value"]
        return result
    except Exception:
        return raw.decode("utf-8", errors="replace")


def click_element(target_id, selector):
    """CDP click — text/plain body，CSS 选择器"""
    body = selector.encode("utf-8")
    req = urllib.request.Request(
        f"{CDP_BASE}/click?target={target_id}",
        data=body,
        headers={"Content-Type": "text/plain"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def navigate(target_id, url):
    cdp_get(f"/navigate?target={target_id}&url={urllib.parse.quote(url, safe=':/?&=')}")
    time.sleep(3)

def screenshot(target_id, out_path="/tmp/xhs_screenshot.png"):
    try:
        raw = cdp_get_raw(f"/screenshot?target={target_id}")
        # CDP proxy 可能返回原始 PNG 字节，也可能返回 base64 JSON
        if raw[:4] == b'\x89PNG' or raw[:2] == b'\xff\xd8':
            # 直接是图片字节
            Path(out_path).write_bytes(raw)
        else:
            result = json.loads(raw)
            if "data" in result:
                Path(out_path).write_bytes(base64.b64decode(result["data"]))
            else:
                Path(out_path).write_bytes(raw)
        print(f"[截图] 已保存到 {out_path}")
    except Exception as e:
        print(f"[截图] 失败: {e}")

# ─── 查找/打开小红书标签页 ──────────────────────────────────────────────────────

def get_or_open_xhs_tab():
    targets = cdp_get("/targets")
    for t in targets:
        if "creator.xiaohongshu.com" in t.get("url", ""):
            print(f"[CDP] 找到小红书标签页: {t['targetId']}")
            return t["targetId"]

    print("[CDP] 未找到小红书标签页，打开新标签...")
    result = cdp_get("/new?url=https%3A%2F%2Fcreator.xiaohongshu.com%2Fpublish%2Fpublish")
    time.sleep(6)  # 等页面初始加载

    # 重新查询，确保拿到已加载的 target
    targets = cdp_get("/targets")
    for t in targets:
        if "xiaohongshu.com" in t.get("url", ""):
            print(f"[CDP] 已确认小红书标签页: {t['targetId']}")
            return t["targetId"]

    # fallback: 用 /new 返回的 id
    tid = result.get("targetId", "")
    print(f"[CDP] 使用新建 targetId: {tid}")
    return tid

# ─── 等待元素出现 ───────────────────────────────────────────────────────────────

def wait_for_selector(target_id, selector, timeout=15, description="元素"):
    js = f"""
    new Promise((resolve, reject) => {{
        const start = Date.now();
        const check = () => {{
            const el = document.querySelector('{selector}');
            if (el) {{ resolve(true); return; }}
            if (Date.now() - start > {timeout * 1000}) {{ reject('timeout'); return; }}
            setTimeout(check, 500);
        }};
        check();
    }})
    """
    result = eval_js(target_id, js, timeout=timeout + 5)
    if "error" in str(result).lower() or "timeout" in str(result).lower():
        print(f"[警告] 等待 {description} 超时")
        return False
    return True

# ─── 图片上传 ──────────────────────────────────────────────────────────────────

def upload_images(target_id, image_paths):
    """
    触发小红书的图片上传。
    小红书创作中心用 <input type="file"> + 拖拽区，通过 CDP 设置文件路径。
    """
    if not image_paths:
        print("[图片] 无图片，跳过")
        return

    paths_str = json.dumps(image_paths)
    js = f"""
    (async () => {{
        // 等待上传区域出现
        await new Promise(r => setTimeout(r, 1000));

        // 找到文件 input
        const fileInput = document.querySelector('input[type="file"][accept*="image"]')
            || document.querySelector('input[type="file"]');

        if (!fileInput) {{
            return 'ERROR: 未找到文件上传 input';
        }}

        // 使用 DataTransfer 设置文件（CDP 支持此方式）
        const dt = new DataTransfer();
        const paths = {paths_str};

        // 触发点击，由 CDP setFiles 处理
        fileInput.click();
        return 'READY: 请通过 CDP setFiles 设置文件路径';
    }})()
    """
    result = eval_js(target_id, js)
    print(f"[图片] 上传准备: {result}")

    # 用 CDP Input.setFiles 直接设置文件路径
    set_files_js = f"""
    (async () => {{
        const input = document.querySelector('input[type="file"][accept*="image"]')
                   || document.querySelector('input[type="file"]');
        if (!input) return 'ERROR: no input';

        // 构造 File 对象列表（CDP 方式）
        const filePaths = {paths_str};
        const dt = new DataTransfer();

        for (const p of filePaths) {{
            // 通过 fetch blob 方式加载本地文件（CDP 环境支持）
            try {{
                const resp = await fetch('file://' + p);
                const blob = await resp.blob();
                const name = p.split('/').pop();
                const file = new File([blob], name, {{type: blob.type || 'image/png'}});
                dt.items.add(file);
            }} catch(e) {{
                return 'ERROR loading ' + p + ': ' + e.message;
            }}
        }}

        Object.defineProperty(input, 'files', {{
            value: dt.files,
            writable: false,
        }});
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return 'OK: ' + dt.files.length + ' files set';
    }})()
    """
    result = eval_js(target_id, set_files_js, timeout=30)
    print(f"[图片] 设置结果: {result}")
    time.sleep(3)

# ─── 注入标题 ──────────────────────────────────────────────────────────────────

def inject_title(target_id, title):
    b64 = base64.b64encode(title.encode("utf-8")).decode()
    js = f"""
    (() => {{
        const decoded = decodeURIComponent(escape(atob('{b64}')));
        const selectors = [
            'input[placeholder*="\\u6807\\u9898"]',
            'input[placeholder*="title"]',
            '.title-input input',
            '.note-title input',
            'input[class*="title"]',
        ];
        let input = null;
        for (const s of selectors) {{
            input = document.querySelector(s);
            if (input) break;
        }}
        if (!input) return 'ERROR: no title input';
        input.focus();
        input.value = decoded;
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return 'OK:' + decoded.length;
    }})()
    """
    result = eval_js(target_id, js)
    print(f"[标题] {result}")

# ─── 注入正文（支持 Quill 富文本编辑器）─────────────────────────────────────────

def inject_body(target_id, body_text):
    b64 = base64.b64encode(body_text.encode("utf-8")).decode()
    js = f"""
    (() => {{
        const decoded = decodeURIComponent(escape(atob('{b64}')));
        const selectors = [
            '.ql-editor',
            '[contenteditable="true"]',
            'textarea[placeholder*="\\u6b63\\u6587"]',
            'textarea[placeholder*="\\u5185\\u5bb9"]',
            '.content-input',
            '.note-content',
        ];
        let editor = null;
        for (const s of selectors) {{
            editor = document.querySelector(s);
            if (editor) break;
        }}
        if (!editor) return 'ERROR: no editor';
        editor.focus();
        if (editor.tagName === 'TEXTAREA') {{
            editor.value = decoded;
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }} else {{
            const paragraphs = decoded.split('\\n');
            editor.innerHTML = paragraphs
                .map(p => p.trim() ? '<p>' + p + '</p>' : '<p><br></p>')
                .join('');
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
        return 'OK:' + decoded.length;
    }})()
    """
    result = eval_js(target_id, js)
    print(f"[正文] {result}")

# ─── 注入话题标签 ──────────────────────────────────────────────────────────────

def inject_tags(target_id, tags):
    """
    注入话题标签。小红书话题需要逐个输入后选择下拉。
    这里只注入文本到话题输入框，提示用户手动确认。
    """
    if not tags:
        return

    tags_display = "、".join(tags)
    b64 = base64.b64encode(tags[0].encode("utf-8")).decode()

    js = f"""
    (() => {{
        const firstTag = decodeURIComponent(escape(atob('{b64}')));
        const selectors = [
            'input[placeholder*="\\u8bdd\\u9898"]',
            'input[placeholder*="\\u6807\\u7b7e"]',
            'input[placeholder*="tag"]',
            '.topic-input input',
            '.tag-input input',
        ];
        let input = null;
        for (const s of selectors) {{
            input = document.querySelector(s);
            if (input) break;
        }}
        if (!input) return 'WARN: no tag input';
        input.focus();
        input.value = firstTag;
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return 'OK';
    }})()
    """
    result = eval_js(target_id, js)
    print(f"[话题] {result}")
    print(f"[话题] 建议标签: {tags_display}")

# ─── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="小红书半自动发布脚本")
    parser.add_argument("--title", required=True, help="标题（≤20字）")
    parser.add_argument("--body", required=True, help="正文内容")
    parser.add_argument("--tags", default="", help="话题标签，逗号分隔")
    parser.add_argument("--images", default="", help="图片路径，逗号分隔，第一张为封面")
    args = parser.parse_args()

    # 检查 CDP
    try:
        cdp_get("/health")
        print("[CDP] 连接正常")
    except Exception:
        print("[错误] CDP Proxy 未运行，请先启动: chrome --remote-debugging-port=9222")
        print("       或检查 CDP Proxy 是否在 localhost:3456")
        sys.exit(1)

    # 解析参数
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    images = [p.strip() for p in args.images.split(",") if p.strip()]

    print(f"\n{'='*50}")
    print(f"标题: {args.title}")
    print(f"正文: {len(args.body)} 字")
    print(f"图片: {len(images)} 张")
    print(f"话题: {tags}")
    print(f"{'='*50}\n")

    # Step 1: 找到小红书标签页
    target_id = get_or_open_xhs_tab()

    # Step 2: 确保在发布页
    print("[导航] 进入图文发布页...")
    navigate(target_id, "https://creator.xiaohongshu.com/publish/publish")
    time.sleep(2)

    # 截图确认页面状态
    screenshot(target_id, "/tmp/xhs_step1.png")

    # Step 3: 检查页面是否在发布页（未跳转到登录）
    page_check_js = "window.location.href"
    current_url = eval_js(target_id, page_check_js)
    print(f"[页面] 当前URL: {current_url}")
    if isinstance(current_url, str) and "login" in current_url:
        print("\n[错误] 检测到登录页面！")
        print("请先在 Chrome 中登录 creator.xiaohongshu.com，然后重新运行此脚本。")
        sys.exit(2)

    # Step 3: 选择图文类型（如果有类型选择器）
    select_type_js = """
    (() => {
        const tabs = Array.from(document.querySelectorAll('[class*="tab"], [class*="type"], button'));
        const found = tabs.find(t => t.textContent.includes('\u56fe\u6587'));
        if (found) { found.click(); return 'OK'; }
        return 'SKIP';
    })()
    """
    result = eval_js(target_id, select_type_js)
    print(f"[类型] {result}")
    time.sleep(1)

    # Step 4: 上传图片
    if images:
        print(f"[图片] 准备上传 {len(images)} 张...")
        upload_images(target_id, images)
        time.sleep(2)
        screenshot(target_id, "/tmp/xhs_step2_images.png")

    # Step 5: 注入标题
    print("[标题] 注入中...")
    inject_title(target_id, args.title)
    time.sleep(1)

    # Step 6: 注入正文
    print("[正文] 注入中...")
    inject_body(target_id, args.body)
    time.sleep(1)

    # Step 7: 注入话题
    if tags:
        print("[话题] 注入中...")
        inject_tags(target_id, tags)
        time.sleep(1)

    # 最终截图
    screenshot(target_id, "/tmp/xhs_final.png")

    print(f"\n{'='*50}")
    print("✓ 内容已填写完毕")
    print("")
    print("接下来请手动操作：")
    print("  1. 检查图片顺序（封面是否正确）")
    print("  2. 确认话题标签已选中（下拉选择）")
    print("  3. 点击右上角「发布」按钮")
    print("")
    print("截图已保存：")
    print("  /tmp/xhs_step1.png      — 页面初始状态")
    if images:
        print("  /tmp/xhs_step2_images.png — 图片上传后")
    print("  /tmp/xhs_final.png      — 发布前最终状态")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
