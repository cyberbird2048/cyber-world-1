#!/usr/bin/env python3
"""
封面图生成脚本
支持多个后端：
  doubao   — 即梦 (jimeng.jianying.com) CDP 桌面操作，画质最高（需 CDP Proxy + 已登录）
  minimax  — MiniMax API（注册送额度，需 API key）
  pollinations — 完全免费，无需 key，画质中等

用法：
  python3 generate_cover.py --prompt "极简深色背景，代码与自然融合" --out cover.png
  python3 generate_cover.py --prompt "..." --backend doubao
  python3 generate_cover.py --prompt "..." --backend minimax --api-key YOUR_KEY
  python3 generate_cover.py --article /tmp/article_draft.txt

后端自动选择优先级（无 --backend 时）:
  1. doubao  — CDP Proxy 可用（localhost:3456/health）
  2. minimax — 环境变量有 MINIMAX_API_KEY
  3. pollinations — 兜底
"""

import argparse
import sys
import os
import urllib.request
import urllib.parse
import json
import time
from pathlib import Path

# 自动加载 .env 文件（按优先级查找多个位置）
_ENV_CANDIDATES = [
    Path.home() / ".config/content-harness/.env",  # 本地独立配置（不同步）
    Path(__file__).parent.parent / ".env",           # skill 目录内（可能在 Obsidian 同步中）
]
for _ENV_FILE in _ENV_CANDIDATES:
    if _ENV_FILE.exists():
        for _line in _ENV_FILE.read_text().splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break

# 公众号封面图推荐尺寸
COVER_WIDTH = 900
COVER_HEIGHT = 500


# ─── CDP 可用性检测 ──────────────────────────────────────────────────────────

def _cdp_available(cdp_base="http://localhost:3456") -> bool:
    """检查 CDP Proxy 是否在线（用于自动后端选择）"""
    try:
        with urllib.request.urlopen(f"{cdp_base}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


# ─── 后端：即梦 / 豆包（CDP 桌面操作，画质最高）─────────────────────────────

def generate_doubao_cdp(
    prompt: str,
    out_path: Path,
    cdp_base: str = "http://localhost:3456",
    width: int = COVER_WIDTH,
    height: int = COVER_HEIGHT,
    timeout: int = 90,
) -> bool:
    """
    通过 CDP Proxy 驱动浏览器，在即梦 (jimeng.jianying.com) 生成图片。

    前置条件：
      - CDP Proxy 运行中（localhost:3456）
      - Chrome 中已登录 jimeng.jianying.com（否则自动打开，需用户手动登录后重试）

    流程：
      1. 找到或打开 jimeng.jianying.com 标签页
      2. 导航到文生图页面
      3. 注入 prompt 并点击生成
      4. 轮询等待图片出现（最多 timeout 秒）
      5. 下载图片到 out_path
    """
    JIMENG_URL = "https://jimeng.jianying.com/ai-tool/image/generate"

    def cdp_get(path):
        with urllib.request.urlopen(f"{cdp_base}{path}", timeout=10) as r:
            return json.loads(r.read())

    def cdp_post_text(path, script):
        req = urllib.request.Request(
            f"{cdp_base}{path}",
            data=script.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def eval_js(target, js):
        return cdp_post_text(f"/eval?target={target}", js)

    print("[doubao/即梦] 初始化 CDP 连接...", file=sys.stderr)

    # 找到或创建即梦标签页
    targets = cdp_get("/targets")
    target_id = None
    for t in targets:
        if "jimeng.jianying.com" in t.get("url", ""):
            target_id = t["targetId"]
            break

    if not target_id:
        print("[doubao/即梦] 未找到即梦标签页，正在打开...", file=sys.stderr)
        try:
            resp = cdp_get(f"/new?url={urllib.parse.quote(JIMENG_URL)}")
            target_id = resp.get("targetId", "")
        except Exception as e:
            print(f"[doubao/即梦] 无法打开标签页: {e}", file=sys.stderr)
            return False
        time.sleep(4)

    print(f"[doubao/即梦] 使用标签页 {target_id}", file=sys.stderr)

    # 导航到文生图页面
    try:
        nav_url = urllib.parse.quote(JIMENG_URL, safe="")
        urllib.request.urlopen(
            f"{cdp_base}/navigate?target={target_id}&url={nav_url}", timeout=10
        )
        time.sleep(3)
    except Exception as e:
        print(f"[doubao/即梦] 导航失败: {e}", file=sys.stderr)

    # 注入 prompt 到输入框
    # 即梦的 prompt 输入框：textarea 或 div[contenteditable]
    import base64
    prompt_b64 = base64.b64encode(prompt.encode()).decode()

    inject_js = f"""(function() {{
  var text = decodeURIComponent(escape(atob('{prompt_b64}')));
  // 尝试 textarea
  var el = document.querySelector('textarea.generate-input, textarea[placeholder*="描述"], textarea[class*="input"]');
  // 如果没有 textarea，尝试 contenteditable div
  if (!el) el = document.querySelector('div[contenteditable="true"][class*="input"], div[contenteditable="true"][placeholder]');
  if (!el) {{
    // 最后兜底：找所有 textarea
    var tas = document.querySelectorAll('textarea');
    if (tas.length > 0) el = tas[0];
  }}
  if (el) {{
    var nativeSetter = Object.getOwnPropertyDescriptor(el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLElement.prototype, 'value');
    if (nativeSetter && nativeSetter.set) nativeSetter.set.call(el, text);
    else el.value = text;
    el.innerHTML = text;
    el.dispatchEvent(new Event('input', {{bubbles: true}}));
    el.dispatchEvent(new Event('change', {{bubbles: true}}));
    return 'injected:' + el.tagName + ':' + el.className.substring(0, 40);
  }}
  return 'no-input-found';
}})()"""

    result = eval_js(target_id, inject_js)
    inject_result = str(result.get("result", ""))
    print(f"[doubao/即梦] prompt 注入结果: {inject_result}", file=sys.stderr)

    if "no-input-found" in inject_result:
        print("[doubao/即梦] 未找到输入框。可能需要先登录或手动导航到文生图页面。", file=sys.stderr)
        # 截图保存以便调试
        try:
            with urllib.request.urlopen(f"{cdp_base}/screenshot?target={target_id}", timeout=10) as r:
                Path("/tmp/jimeng_debug.png").write_bytes(r.read())
            print("[doubao/即梦] 调试截图已保存到 /tmp/jimeng_debug.png", file=sys.stderr)
        except Exception:
            pass
        return False

    time.sleep(0.5)

    # 点击生成按钮
    click_js = """(function() {
  var btns = Array.from(document.querySelectorAll('button'));
  var gen = btns.find(b => b.textContent.includes('生成') || b.textContent.includes('Generate') || b.getAttribute('data-type') === 'generate');
  if (!gen) {
    // 尝试找包含生成文字的 div/span
    var els = Array.from(document.querySelectorAll('div[class*="generate"], div[class*="submit"], [class*="btn"][class*="generate"]'));
    gen = els[0];
  }
  if (gen) { gen.click(); return 'clicked:' + gen.textContent.trim().substring(0, 20); }
  return 'no-button-found';
})()"""

    click_result = eval_js(target_id, click_js)
    print(f"[doubao/即梦] 生成按钮: {click_result.get('result', '')}", file=sys.stderr)
    time.sleep(2)

    # 轮询等待图片生成完成
    print(f"[doubao/即梦] 等待生成（最多 {timeout} 秒）...", file=sys.stderr)
    poll_js = """(function() {
  // 找生成完成的图片：class 包含 result/output/generated 的 img
  var imgs = Array.from(document.querySelectorAll('img[class*="result"], img[class*="output"], img[class*="generated"], div[class*="result"] img, div[class*="output"] img'));
  // 过滤掉 logo、头像等小图（src 包含 avatar/logo/icon 的）
  imgs = imgs.filter(i => i.src && !i.src.includes('avatar') && !i.src.includes('logo') && !i.src.includes('icon') && i.naturalWidth > 200);
  if (imgs.length > 0) return imgs[imgs.length - 1].src;
  return '';
})()"""

    generated_url = ""
    start = time.time()
    while time.time() - start < timeout:
        poll_result = eval_js(target_id, poll_js)
        generated_url = poll_result.get("result", "")
        if generated_url and generated_url.startswith("http"):
            print(f"[doubao/即梦] 图片生成完成: {generated_url[:60]}...", file=sys.stderr)
            break
        elapsed = int(time.time() - start)
        print(f"\r[doubao/即梦] 等待中... {elapsed}s", end="", flush=True, file=sys.stderr)
        time.sleep(3)

    print("", file=sys.stderr)

    if not generated_url:
        print("[doubao/即梦] 超时未检测到生成图片。", file=sys.stderr)
        # 保存截图以便调试
        try:
            with urllib.request.urlopen(f"{cdp_base}/screenshot?target={target_id}", timeout=10) as r:
                Path("/tmp/jimeng_timeout.png").write_bytes(r.read())
            print("[doubao/即梦] 超时截图已保存到 /tmp/jimeng_timeout.png", file=sys.stderr)
        except Exception:
            pass
        return False

    # 下载图片
    try:
        req = urllib.request.Request(generated_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        print(f"[doubao/即梦] 完成 → {out_path}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[doubao/即梦] 下载失败: {e}", file=sys.stderr)
        return False


# ─── 后端：Pollinations.ai（完全免费，无需 key）─────────────────────────────

def generate_pollinations(prompt: str, out_path: Path, width=COVER_WIDTH, height=COVER_HEIGHT, max_retries=3) -> bool:
    """
    调用 pollinations.ai 生成图片。
    模型：FLUX（开源），质量中等偏上，免费无限制。
    retry=3，指数退避（2s/4s）；第2次起自动禁用 SSL 验证（应对已知证书问题）。
    """
    import ssl
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&nologo=true&model=flux"
    )
    for attempt in range(max_retries):
        if attempt > 0:
            wait = 2 ** attempt  # 2s, 4s
            print(f"[pollinations] 第{attempt + 1}次重试（等待{wait}s）...", file=sys.stderr)
            time.sleep(wait)
        print(f"[pollinations] 请求中（{attempt + 1}/{max_retries}）... ", end="", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "content-harness/1.0"})
            if attempt >= 1:
                # 第2次起禁用 SSL 验证，应对证书问题（历史上出现过 SSL handshake 失败）
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                    data = resp.read()
            else:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)
            print(f"完成 → {out_path}")
            return True
        except Exception as e:
            print(f"失败: {e}", file=sys.stderr)
    return False


# ─── 后端：MiniMax（注册送免费额度）────────────────────────────────────────

def generate_minimax(prompt: str, out_path: Path, api_key: str, max_retries=2) -> bool:
    """
    调用 MiniMax image generation API。
    需要注册并获取 API key：https://www.minimaxi.com/
    注册后有免费额度，支持中文 prompt。retry=2，指数退避（2s）。
    """
    url = "https://api.minimaxi.com/v1/image_generation"
    payload = json.dumps({
        "model": "image-01",
        "prompt": prompt,
        "aspect_ratio": "16:9",  # 最接近 900×500
        "response_format": "url",
    }).encode()

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"[minimax] 第{attempt + 1}次重试（等待2s）...", file=sys.stderr)
            time.sleep(2)
        print(f"[minimax] 请求中（{attempt + 1}/{max_retries}）... ", end="", flush=True)
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read())

            if "data" not in result or not result["data"].get("image_urls"):
                print(f"API 返回错误: {result}", file=sys.stderr)
                continue

            image_url = result["data"]["image_urls"][0]
            with urllib.request.urlopen(image_url, timeout=30) as img_resp:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(img_resp.read())
            print(f"完成 → {out_path}")
            return True
        except Exception as e:
            print(f"失败: {e}", file=sys.stderr)
    return False


# ─── 自动从文章提取封面图 prompt ──────────────────────────────────────────

def auto_prompt_from_article(article_path: Path) -> str:
    """
    读取文章，基于标题和核心类比生成封面图 prompt。
    支持 YAML frontmatter 和 # 标题两种格式。
    """
    import re as _re
    text = article_path.read_text(encoding="utf-8")

    # 提取 YAML frontmatter 中的 title
    title = ""
    fm_match = _re.match(r"^---\s*\n(.*?)\n---", text, _re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if line.startswith("title:"):
                title = line[6:].strip().strip('"').strip("'")
                break

    # 没有 frontmatter 则找 # 标题
    if not title:
        for line in text.split("\n"):
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break

    # 提取正文段落（跳过 frontmatter 和元数据行）
    body = text[fm_match.end():] if fm_match else text
    paragraphs = []
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-") and not line.startswith(":") and len(line) > 20:
            paragraphs.append(line)
        if len(paragraphs) >= 2:
            break

    context = f"标题：{title}\n内容摘要：{''.join(paragraphs[:2])[:200]}"
    print(f"[auto-prompt] 基于文章内容生成 prompt：\n{context}\n")

    # 固定视觉风格，用文章关键词填充主体
    # 这里用规则生成，实际运行时 Claude 会在 Stage 6.5 生成更精准的 prompt
    prompt = (
        f"minimalist digital art cover image, dark navy background, "
        f"single abstract geometric object glowing softly, "
        f"inspired by concept: {title[:40]}, "
        f"no text, no words, ultra clean, high contrast, "
        f"cinematic lighting, 16:9 ratio, professional editorial style"
    )
    return prompt


# ─── 主入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="公众号封面图生成器")
    parser.add_argument("--prompt", "-p", help="图片生成提示词（英文效果更好）")
    parser.add_argument("--article", help="文章文件路径，自动提取 prompt")

    # 自动后端选择优先级: doubao(CDP可用) > minimax(有key) > pollinations(兜底)
    if _cdp_available():
        _default_backend = "doubao"
    elif os.environ.get("MINIMAX_API_KEY"):
        _default_backend = "minimax"
    else:
        _default_backend = "pollinations"

    parser.add_argument(
        "--backend",
        choices=["doubao", "pollinations", "minimax"],
        default=_default_backend,
        help=f"图片生成后端（默认 {_default_backend}，优先级: doubao > minimax > pollinations）",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("MINIMAX_API_KEY"),
        help="MiniMax API key（自动从 .env 读取）",
    )
    parser.add_argument(
        "--cdp",
        default="http://localhost:3456",
        help="CDP Proxy 地址（doubao 后端使用）",
    )
    _default_img_dir = Path(__file__).parent.parent.parent.parent.parent / \
        "Documents/Claude/Projects/AI工具/content-harness/images/covers"
    parser.add_argument(
        "--out", "-o",
        default=str(_default_img_dir / "cover.png"),
        help="输出文件路径",
    )
    parser.add_argument("--width", type=int, default=COVER_WIDTH)
    parser.add_argument("--height", type=int, default=COVER_HEIGHT)
    args = parser.parse_args()

    out_path = Path(args.out)

    # 确定 prompt
    if args.article:
        prompt = auto_prompt_from_article(Path(args.article))
    elif args.prompt:
        prompt = args.prompt
    else:
        print("错误：需要 --prompt 或 --article 参数", file=sys.stderr)
        sys.exit(1)

    print(f"Prompt: {prompt}\n")
    print(f"后端: {args.backend}\n")

    # 调用对应后端
    success = False
    if args.backend == "doubao":
        success = generate_doubao_cdp(prompt, out_path, cdp_base=args.cdp,
                                       width=args.width, height=args.height)
    elif args.backend == "minimax":
        if not args.api_key:
            print("错误：使用 minimax 后端需要 --api-key 参数", file=sys.stderr)
            print("注册地址：https://www.minimaxi.com/ （注册送免费额度）", file=sys.stderr)
            sys.exit(1)
        success = generate_minimax(prompt, out_path, args.api_key)
    else:
        success = generate_pollinations(prompt, out_path, args.width, args.height)

    # 主后端失败后，自动 fallback 降级
    if not success:
        if args.backend == "doubao":
            print("[fallback] 即梦 CDP 失败，尝试 minimax...", file=sys.stderr)
            if args.api_key:
                success = generate_minimax(prompt, out_path, args.api_key)
            if not success:
                print("[fallback] minimax 失败，尝试 pollinations...", file=sys.stderr)
                success = generate_pollinations(prompt, out_path, args.width, args.height)
        elif args.backend == "minimax":
            print("[fallback] minimax 失败，尝试 pollinations...", file=sys.stderr)
            success = generate_pollinations(prompt, out_path, args.width, args.height)
        elif args.backend == "pollinations" and args.api_key:
            print("[fallback] pollinations 失败，尝试 minimax...", file=sys.stderr)
            success = generate_minimax(prompt, out_path, args.api_key)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
