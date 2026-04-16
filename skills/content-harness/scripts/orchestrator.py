#!/usr/bin/env python3
"""
Content Harness Orchestrator
每个 Stage 的执行保障层。Claude 负责内容生成，这个脚本负责：
1. 验证每个 Stage 的输出确实存在且格式正确
2. 强制 Stage 8 知识库更新（不更新就报错）
3. 记录 pipeline 执行状态，断点可恢复

用法（由 Claude 在 pipeline 运行中调用）：
  python3 orchestrator.py init --inspiration "灵感文字" --article-type opinion
  python3 orchestrator.py verify --stage 3 --article /tmp/article_draft.txt
  python3 orchestrator.py verify --stage 4 --scan-result /tmp/scan_result.json
  python3 orchestrator.py verify --stage 6.5 --images /tmp/cover_A.png,/tmp/cover_B.png,/tmp/cover_C.png
  python3 orchestrator.py verify --stage 8 --kb-before /tmp/kb_before.md
  python3 orchestrator.py status
  python3 orchestrator.py complete
"""

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / ".pipeline_state.json"
KB_PATH = SKILL_DIR / "references" / "knowledge-base.md"
PROJECT_DIR = Path.home() / "Documents/Claude/Projects/AI工具/content-harness"
ARTICLES_DIR = PROJECT_DIR / "articles"
IMAGES_DIR = PROJECT_DIR / "images"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


# ─── init: 开始新的 pipeline ───────────────────────────────────────────────

def archive_active_run(reason="new_init"):
    """将当前活跃的 pipeline 归档（如果存在）。返回被归档的 run id 或 None。"""
    state = load_state()
    if not state:
        return None

    state["archived_reason"] = reason
    state["archived_at"] = datetime.now().isoformat()

    archive_dir = SKILL_DIR / ".pipeline_archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / f"run_{state['id']}.json"
    archive_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.unlink()

    run_id = state["id"]
    print(f"[归档] 活跃 pipeline {run_id} 已归档 → {archive_path.name}（原因：{reason}）")
    return run_id


def cmd_init(args):
    if not args.inspiration:
        print("错误：必须提供 --inspiration", file=sys.stderr)
        sys.exit(1)

    # 检测并归档已有的活跃 pipeline
    archived = archive_active_run(reason="被新 init 覆盖")
    if archived:
        print(f"⚠ 上一次运行 {archived} 未完成，已自动归档")

    state = {
        "id": datetime.now().strftime("%Y%m%d_%H%M"),
        "started": datetime.now().isoformat(),
        "inspiration": args.inspiration,
        "article_type": args.article_type or "pending",
        "stages_completed": [],
        "current_stage": "0",
        "article_path": None,
        "images": [],
        "scan_result": None,
        "kb_hash_before": md5(KB_PATH),
        "errors": [],
    }
    save_state(state)
    print(f"Pipeline {state['id']} 已初始化")
    print(f"灵感：{args.inspiration}")
    print(f"知识库 hash (before): {state['kb_hash_before']}")
    return state


# ─── verify: 验证某个 Stage 的输出 ────────────────────────────────────────

def cmd_verify(args):
    state = load_state()
    if not state:
        print("错误：没有活跃的 pipeline，先运行 init", file=sys.stderr)
        sys.exit(1)

    stage = args.stage
    errors = []

    # --- Stage 1.5: 文章类型分类 ---
    if stage == "1.5":
        if not args.article_type:
            errors.append("Stage 1.5 必须提供 --article-type")
        elif args.article_type not in ["opinion", "creator-share", "life-reflection", "news-reaction", "how-to"]:
            errors.append(f"无效的文章类型: {args.article_type}")
        else:
            state["article_type"] = args.article_type
            print(f"文章类型确认: {args.article_type}")

    # --- Stage 3: 全文写作 ---
    elif stage == "3":
        if not args.article:
            errors.append("Stage 3 必须提供 --article 文件路径")
        elif not Path(args.article).exists():
            errors.append(f"文章文件不存在: {args.article}")
        else:
            text = Path(args.article).read_text(encoding="utf-8")
            # 基础验证
            if len(text) < 500:
                errors.append(f"文章过短({len(text)}字)，最少500字")
            if len(text) > 5000:
                errors.append(f"文章过长({len(text)}字)，建议3000字以内")

            # 检查是否包含灵感关键词（至少1个）
            inspiration_words = [w for w in state["inspiration"] if len(w) > 1]
            # 简单检查：灵感中至少有一个2字以上的片段出现在文中
            found = False
            for i in range(len(state["inspiration"]) - 1):
                chunk = state["inspiration"][i:i+3]
                if len(chunk) >= 2 and chunk in text:
                    found = True
                    break
            if not found:
                errors.append("警告：文章中未发现灵感关键词，可能偏离主题")

            state["article_path"] = args.article
            word_count = len(text)
            para_count = len([p for p in text.split("\n\n") if p.strip()])
            print(f"文章验证: {word_count}字, {para_count}段")

    # --- Stage 4: 规则扫描结果 ---
    elif stage == "4":
        if not args.scan_result:
            errors.append("Stage 4 必须提供 --scan-result (JSON 文件路径)")
        elif not Path(args.scan_result).exists():
            # 如果没有 JSON 文件，检查是否至少运行了 rule_scan.py
            errors.append("规则扫描结果文件不存在，是否忘了运行 rule_scan.py？")
        else:
            result = json.loads(Path(args.scan_result).read_text(encoding="utf-8"))
            state["scan_result"] = result["summary"]
            if not result.get("all_pass"):
                failed = [r["rule"] for r in result["results"] if not r["pass"]]
                errors.append(f"规则扫描未通过: {failed}")
                print(f"FAIL: {result['summary']} — 失败项: {failed}")
            else:
                print(f"PASS: {result['summary']}")

    # --- Stage 6.5: 图片验证 ---
    elif stage == "6.5":
        if not args.images:
            errors.append("Stage 6.5 必须提供 --images (逗号分隔的图片路径)")
        else:
            paths = [p.strip() for p in args.images.split(",")]
            missing = [p for p in paths if not Path(p).exists()]
            if missing:
                errors.append(f"图片文件不存在: {missing}")
            else:
                total_size = sum(Path(p).stat().st_size for p in paths)
                state["images"] = paths
                print(f"图片验证通过: {len(paths)}张, 总大小{total_size/1024:.0f}KB")

    # --- Stage 8: 知识库更新验证 ---
    elif stage == "8":
        kb_hash_now = md5(KB_PATH)
        if kb_hash_now == state.get("kb_hash_before"):
            errors.append("Stage 8 失败：知识库 hash 未变化，knowledge-base.md 没有被更新！")
            print("FAIL: 知识库没有更新。这是不可跳过的步骤。")
        else:
            # 进一步验证：检查是否包含本次运行的记录
            kb_text = KB_PATH.read_text(encoding="utf-8")
            run_date = datetime.now().strftime("%Y-%m-%d")
            if f"Run {run_date}" not in kb_text and run_date not in kb_text:
                errors.append(f"知识库已修改但未找到今日({run_date})的运行记录")
            else:
                print(f"知识库更新验证通过 (hash: {state['kb_hash_before'][:8]} → {kb_hash_now[:8]})")

            # 检查文章是否保存到项目目录
            articles = list(ARTICLES_DIR.glob(f"{run_date}*.md"))
            if not articles:
                errors.append(f"文章未保存到项目目录: {ARTICLES_DIR}")
            else:
                print(f"文章存档验证通过: {[a.name for a in articles]}")

            # 检查图片是否保存到项目目录
            covers = list((IMAGES_DIR / "covers").glob(f"{run_date}*.png"))
            if not covers:
                errors.append(f"封面图未保存到项目目录: {IMAGES_DIR / 'covers'}")

    else:
        errors.append(f"未知的 Stage: {stage}")

    # 更新状态
    if errors:
        state["errors"].extend(errors)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
    else:
        if stage not in state["stages_completed"]:
            state["stages_completed"].append(stage)
        state["current_stage"] = stage

    save_state(state)
    sys.exit(1 if errors else 0)


# ─── status: 查看当前 pipeline 状态 ───────────────────────────────────────

def cmd_status(args):
    state = load_state()
    if not state:
        print("没有活跃的 pipeline")
        return

    all_stages = ["0", "1", "1.5", "2", "3", "4", "5", "6", "6.5", "7", "8", "9"]

    print(f"\n Pipeline {state['id']}")
    print(f" 灵感：{state['inspiration']}")
    print(f" 类型：{state['article_type']}")
    print(f" 启动：{state['started']}")
    print(f" 当前：Stage {state['current_stage']}")
    print()

    for s in all_stages:
        if s in state["stages_completed"]:
            icon = "●"
        elif s == state["current_stage"]:
            icon = "◐"
        else:
            icon = "○"
        print(f"  {icon} Stage {s}")

    if state["scan_result"]:
        print(f"\n 规则扫描: {state['scan_result']}")

    if state["errors"]:
        print(f"\n 错误({len(state['errors'])}个):")
        for e in state["errors"][-5:]:  # 只显示最近5个
            print(f"  ! {e}")

    print()


# ─── complete: 标记 pipeline 完成 ─────────────────────────────────────────

def cmd_complete(args):
    state = load_state()
    if not state:
        print("没有活跃的 pipeline")
        return

    # 检查必要的 stages 是否都完成了
    required = ["3", "4", "8"]
    missing = [s for s in required if s not in state["stages_completed"]]

    if missing:
        print(f"不能完成：以下必需 Stage 未通过验证: {missing}", file=sys.stderr)
        print("必须完成 Stage 3(写作) + Stage 4(质检) + Stage 8(沉淀) 才能标记完成")
        sys.exit(1)

    state["completed"] = datetime.now().isoformat()
    state["current_stage"] = "done"

    # 归档状态文件
    archive_dir = SKILL_DIR / ".pipeline_archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / f"run_{state['id']}.json"
    archive_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # 清除当前状态
    STATE_FILE.unlink()

    duration = (datetime.fromisoformat(state["completed"]) -
                datetime.fromisoformat(state["started"]))
    minutes = duration.total_seconds() / 60

    print(f"Pipeline {state['id']} 完成")
    print(f"耗时: {minutes:.0f}分钟")
    print(f"已完成 Stage: {state['stages_completed']}")
    print(f"错误数: {len(state['errors'])}")
    print(f"归档至: {archive_path}")


# ─── list-runs: 列出活跃 + 历史 run ────────────────────────────────────────

def cmd_list_runs(args):
    archive_dir = SKILL_DIR / ".pipeline_archive"
    active = load_state()

    print("=== 活跃 Pipeline ===")
    if active:
        print(f"  {active['id']}  Stage {active['current_stage']}  {active['inspiration'][:40]}")
        print(f"    启动: {active['started']}  完成 stages: {active['stages_completed']}")
    else:
        print("  (无)")

    print("\n=== 历史归档 ===")
    if not archive_dir.exists():
        print("  (无)")
        return

    archives = sorted(archive_dir.glob("run_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    limit = int(args.limit) if hasattr(args, "limit") and args.limit else 10
    for f in archives[:limit]:
        try:
            run = json.loads(f.read_text(encoding="utf-8"))
            status = "✓ 完成" if run.get("completed") else f"✗ 归档({run.get('archived_reason', '?')})"
            stages = ",".join(run.get("stages_completed", []))
            print(f"  {run['id']}  {status}  stages=[{stages}]  {run['inspiration'][:30]}")
        except Exception:
            print(f"  {f.name}  (解析失败)")
    if len(archives) > limit:
        print(f"  ...还有 {len(archives) - limit} 个历史 run")


# ─── resume: 输出断点续跑信息 ────────────────────────────────────────────

def cmd_resume(args):
    state = load_state()
    if not state:
        print("没有活跃的 pipeline 可恢复。")
        print("使用 list-runs 查看历史 run。")
        sys.exit(1)

    all_stages = ["0", "1", "1.5", "2", "3", "4", "5", "6", "6.5", "7", "8", "9"]
    completed = set(state.get("stages_completed", []))
    current = state.get("current_stage", "0")

    # 找到下一个需要执行的 stage
    next_stage = None
    for s in all_stages:
        if s not in completed:
            next_stage = s
            break

    print("=== Pipeline 恢复信息 ===")
    print(f"Run ID: {state['id']}")
    print(f"灵感: {state['inspiration']}")
    print(f"类型: {state['article_type']}")
    print(f"启动时间: {state['started']}")
    print(f"已完成 Stages: {sorted(completed)}")
    print(f"当前 Stage: {current}")
    print(f"下一步: Stage {next_stage}" if next_stage else "所有 Stage 已完成，运行 complete")

    if state.get("article_path"):
        print(f"文章路径: {state['article_path']}")
    if state.get("images"):
        print(f"图片: {state['images']}")
    if state.get("scan_result"):
        print(f"扫描结果: {state['scan_result']}")
    if state.get("errors"):
        print(f"历史错误({len(state['errors'])}个): {state['errors'][-3:]}")

    print(f"\n→ 请从 Stage {next_stage} 继续执行 SKILL.md 中的 pipeline 流程。")


# ─── 入口 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Content Harness Orchestrator")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="初始化新 pipeline")
    p_init.add_argument("--inspiration", "-i", required=True)
    p_init.add_argument("--article-type", "-t")

    # verify
    p_verify = sub.add_parser("verify", help="验证 Stage 输出")
    p_verify.add_argument("--stage", "-s", required=True)
    p_verify.add_argument("--article", help="文章文件路径")
    p_verify.add_argument("--scan-result", help="规则扫描 JSON 结果")
    p_verify.add_argument("--images", help="逗号分隔的图片路径")
    p_verify.add_argument("--article-type", help="文章类型")

    # status
    sub.add_parser("status", help="查看当前 pipeline 状态")

    # complete
    sub.add_parser("complete", help="完成 pipeline")

    # list-runs
    p_list = sub.add_parser("list-runs", help="列出活跃和历史 pipeline")
    p_list.add_argument("--limit", "-n", default="10", help="显示最近N个历史 run")

    # resume
    sub.add_parser("resume", help="输出断点续跑恢复信息")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "complete":
        cmd_complete(args)
    elif args.command == "list-runs":
        cmd_list_runs(args)
    elif args.command == "resume":
        cmd_resume(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
