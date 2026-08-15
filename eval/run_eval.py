"""评估脚本：批量脱水 + 客观评分 + 稳定性对比。

手动评估工具（调真实 B站/LLM API），不属于测试套件（CLAUDE.md §4 禁止测试触网）。
用法：uv run python eval/run_eval.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.config import Settings
from app.application.dehydrate import DehydrateUseCase
from app.domain.exceptions import DehydratorError
from app.domain.scorer import score_recipe
from app.infrastructure.bilibili_fetcher import BilibiliFetcher
from app.infrastructure.ffmpeg_frames import FFmpegFrameExtractor
from app.infrastructure.llm_providers import create_llm_client
from app.infrastructure.sqlite_store import SQLiteCardStore

URLS = [
    "https://www.bilibili.com/video/BV1jD4y1o77r",
    "https://www.bilibili.com/video/BV1CX4y137uY",
    "https://www.bilibili.com/video/BV1hh411N7Qo",
    "https://www.bilibili.com/video/BV1v92xYRE9d",  # 28 分钟 6 菜合集（应被拒）
    "https://www.bilibili.com/video/BV1hvnizoEfw",
    "https://www.bilibili.com/video/BV1HV411e7Uq",
    "https://www.bilibili.com/video/BV1sM4y1C7Me",
]


def _make_usecase(settings: Settings, store: SQLiteCardStore) -> DehydrateUseCase:
    env = {
        "DEEPSEEK_API_KEY": settings.deepseek_api_key,
        "DEEPSEEK_BASE_URL": settings.deepseek_base_url,
        "DEEPSEEK_MODEL": settings.deepseek_model,
        "QWEN_API_KEY": settings.qwen_api_key,
        "QWEN_BASE_URL": settings.qwen_base_url,
        "QWEN_MODEL": settings.qwen_model,
        "KIMI_API_KEY": settings.kimi_api_key,
        "KIMI_BASE_URL": settings.kimi_base_url,
        "KIMI_MODEL": settings.kimi_model,
    }
    return DehydrateUseCase(
        fetcher=BilibiliFetcher(
            cookiefile=str(settings.bilibili_cookie_file) if settings.bilibili_cookie_file else None
        ),
        llm=create_llm_client(settings.llm_provider, env),
        frames=FFmpegFrameExtractor(),
        store=store,
        frames_dir=settings.frames_dir,
        with_frames=False,  # 评估不抽帧，节省时间
    )


def _time_iou(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """两次输出的步骤时间区间平均 IoU（按较短列表对齐）。"""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    ious = []
    for i in range(n):
        (s1, e1), (s2, e2) = a[i], b[i]
        inter = max(0.0, min(e1, e2) - max(s1, s2))
        union = max(e1, e2) - min(s1, s2)
        ious.append(inter / union if union > 0 else 0.0)
    return sum(ious) / len(ious)


async def eval_one(usecase: DehydrateUseCase, url: str) -> dict:
    try:
        _, recipe = await usecase.run(url)
        report = score_recipe(recipe)
        return {
            "url": url,
            "ok": True,
            "title": recipe.title,
            "steps": len(recipe.steps),
            "score": report.total,
            "dimensions": {d.name: f"{d.score}/{d.max_score}" for d in report.dimensions},
            "details": {d.name: d.details for d in report.dimensions if d.details},
            "warnings": recipe.warnings,
            "step_ranges": [(s.start_sec, s.end_sec) for s in recipe.steps],
        }
    except DehydratorError as exc:
        return {"url": url, "ok": False, "rejected": str(exc)}
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def main() -> None:
    settings = Settings()
    store = SQLiteCardStore(settings.db_path)
    usecase = _make_usecase(settings, store)

    results = []
    for url in URLS:
        print(f"\n=== 脱水 {url} ===")
        r1 = await eval_one(usecase, url)
        if not r1["ok"]:
            print(f"  拒绝/失败: {r1.get('rejected') or r1.get('error')}")
            results.append({"url": url, "first": r1})
            continue
        r2 = await eval_one(usecase, url)  # 第二次：稳定性
        iou = _time_iou(r1["step_ranges"], r2["step_ranges"]) if r2["ok"] else 0.0
        stable = {
            "steps_diff": abs(r1["steps"] - r2["steps"]),
            "title_same": r1["title"] == r2["title"],
            "time_iou": round(iou, 2),
            "score_diff": abs(r1["score"] - r2["score"]),
        }
        results.append({"url": url, "first": r1, "second": r2, "stability": stable})
        print(f"  {r1['title']}  分数 {r1['score']}/{r2['score']}  稳定性: {stable}")

    out = Path("eval/report.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已存 {out}")


if __name__ == "__main__":
    asyncio.run(main())
