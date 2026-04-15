---
name: WeChat Publish Defaults
description: 微信公众号发布的默认配置（作者名等）
type: project
originSessionId: 0357821f-f69c-4c00-9b44-b84ab09eae6c
---
微信公众号文章的默认作者名是 **cyber brid**（不是"月下蝶舞"）。

**Why:** 用户在 2026-04-13 明确指定。

**How to apply:** 每次调用 wechat_publish.md 流程，`input#author` 字段写 "cyber brid"。operate_appmsg 的 `author0` 字段同样写 "cyber brid"。
