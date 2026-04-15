---
name: WeChat Publishing - Use Internal API Not Editor UI
description: WeChat MP article publishing must use internal API (filetransfer + operate_appmsg), never CDP editor UI interactions for file uploads or cover setting
type: feedback
originSessionId: e693bc5d-29f6-421c-bd95-99d7a5e40241
---
微信公众号发布流程必须走内部 API，禁止用 CDP eval 操作编辑器 UI。

**Why:** 2026-04-13 session 中反复尝试 CDP 编辑器 UI 操作（file input、drag-drop、图片库弹窗），导致标签页崩溃 4+ 次、正文丢失 1 次（operate_appmsg 漏传 content0）、总共浪费了大量 token 在试错上。

**How to apply:**
1. 素材上传：用 `/cgi-bin/filetransfer?action=upload_material` 在浏览器 fetch 上下文中执行
2. 草稿创建：编辑器 eval 只做标题+作者+正文注入 → 点保存
3. 封面绑定：用 `/cgi-bin/operate_appmsg?sub=update` 一次性写入 fileid0 + cdn_url0 + content0
4. **content0 必须包含完整 HTML**，否则正文被清空
5. 全流程 ~5 次 CDP 调用，不涉及弹窗、文件对话框、图片库选择器
6. 音频/配乐只能手动在编辑器中添加（QQ 音乐搜索）
