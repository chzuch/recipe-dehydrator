"""L3 一致性校验（SCOPE §4）：LLM 输出不可信，入库/展示前必经此层。

规则：
1. 食材闭环：每个食材必须出现在某个步骤的文本中
2. 时间自洽：步骤区间不重叠、相邻间隙不异常、总跨度与视频时长吻合
3. 顺序合理：步骤 index 顺序与时间顺序一致

「error」级问题应阻止入库；「warning」级写入 recipe.warnings 展示给用户。
"""

from __future__ import annotations

import itertools
from typing import Literal

from pydantic import BaseModel

from app.domain.models import Ingredient, Recipe, Step, SubtitleLine

# 相邻步骤间允许的最大闲话间隙（秒）：超过视为「可能漏了步骤」
MAX_GAP_SEC = 30.0
# 步骤区间允许的最大重叠（秒）：轻微重叠可接受（字幕边界模糊）
MAX_OVERLAP_SEC = 2.0
# 总跨度与视频时长的最大相对偏差
MAX_DURATION_DRIFT = 0.2

# 触发 GIF 生成的动作词（这些动作静态图教不会，新手需要看手法）
GIF_ACTION_WORDS = ("翻炒", "搅拌", "颠", "淋", "搅", "翻拌", "掂", "泼", "倒入")
# GIF 片段时长（秒）
GIF_DURATION_SEC = 2.0


def pick_frame_time(step: Step, lines: list[SubtitleLine]) -> float:
    """关键句对齐抽帧：在步骤区间内找含烹饪动作的字幕行，取该行中点。

    说「倒入料酒」时画面大概率正在倒——比区间中点靠谱得多。
    找不到则回退区间中点。
    """
    in_range = [
        line
        for line in lines
        if line.start >= step.start_sec - MAX_OVERLAP_SEC and line.end <= step.end_sec + MAX_OVERLAP_SEC
    ]
    for line in in_range:
        if any(
            v in line.text
            for v in ("切", "炒", "炖", "煮", "焯", "炸", "煎", "加", "倒", "放", "翻炒", "搅拌", "收汁")
        ):
            return (line.start + line.end) / 2
    return step.start_sec + (step.end_sec - step.start_sec) / 2


def is_action_step(step: Step) -> bool:
    """该步骤是否包含需要看手法的动作（触发 GIF 生成）。"""
    text = step.title + step.description + (step.tip or "")
    return any(w in text for w in GIF_ACTION_WORDS)


def merge_duplicate_ingredients(ingredients: list[Ingredient]) -> list[Ingredient]:
    """同名食材合并（LLM 常把同一原料多次出现拆成多条，如花生油 3 次）。

    保留首次出现顺序；amount 合并展示（分号分隔），note 合并。
    """
    merged: dict[str, Ingredient] = {}
    order: list[str] = []
    for ing in ingredients:
        key = ing.name.strip()
        if key not in merged:
            merged[key] = ing.model_copy(deep=True)
            order.append(key)
            continue
        prev = merged[key]
        amounts = [a for a in (prev.amount, ing.amount) if a]
        if amounts:
            prev.amount = "；".join(amounts)
        if ing.note:
            prev.note = f"{prev.note}；{ing.note}" if prev.note else ing.note
    return [merged[key] for key in order]


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str


def _normalize_text(text: str) -> str:
    return text.replace(" ", "").replace("　", "")


def check_ingredient_closure(recipe: Recipe) -> list[ValidationIssue]:
    """每个食材必须出现在某步骤文本中。"""
    issues: list[ValidationIssue] = []
    if not recipe.ingredients:
        return issues
    step_text = _normalize_text(
        " ".join(" ".join(filter(None, (s.title, s.description, s.done_when, s.tip))) for s in recipe.steps)
    )
    for ing in recipe.ingredients:
        if _normalize_text(ing.name) not in step_text:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="INGREDIENT_NOT_IN_STEPS",
                    message=f"食材「{ing.name}」未在任何步骤中出现，请核对是否遗漏或名称不一致",
                )
            )
    return issues


def check_time_consistency(recipe: Recipe, video_duration_sec: float | None = None) -> list[ValidationIssue]:
    """步骤区间不重叠、间隙不异常、跨度与视频时长吻合。"""
    issues: list[ValidationIssue] = []
    steps = sorted(recipe.steps, key=lambda s: s.index)
    if len(steps) < 2:
        return issues

    for prev, cur in itertools.pairwise(steps):
        overlap = prev.end_sec - cur.start_sec
        if overlap > MAX_OVERLAP_SEC:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="STEP_OVERLAP",
                    message=f"步骤{prev.index}与{cur.index}时间区间重叠 {overlap:.0f} 秒，切分不可信",
                )
            )
        gap = cur.start_sec - prev.end_sec
        if gap > MAX_GAP_SEC:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="STEP_GAP",
                    message=f"步骤{prev.index}与{cur.index}之间有空隙 {gap:.0f} 秒，可能遗漏了步骤",
                )
            )

    if video_duration_sec and video_duration_sec > 0:
        span = steps[-1].end_sec - steps[0].start_sec
        drift = abs(span - video_duration_sec) / video_duration_sec
        if drift > MAX_DURATION_DRIFT:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="DURATION_DRIFT",
                    message=(
                        f"步骤时间跨度({span:.0f}s)与视频时长({video_duration_sec:.0f}s)"
                        f"偏差 {drift:.0%}，切分可能不完整"
                    ),
                )
            )
    return issues


def check_order(recipe: Recipe) -> list[ValidationIssue]:
    """步骤 index 顺序应与时间顺序一致（LLM 切分可信度信号）。"""
    issues: list[ValidationIssue] = []
    steps = sorted(recipe.steps, key=lambda s: s.index)
    if len(steps) < 2:
        return issues
    prev_end = steps[0].start_sec
    for s in steps:
        if s.start_sec < prev_end - MAX_OVERLAP_SEC:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="STEP_ORDER",
                    message=f"步骤{s.index}的时间起点早于前序步骤，切分混乱",
                )
            )
            break
        prev_end = s.end_sec
    return issues


def validate_recipe(recipe: Recipe, video_duration_sec: float | None = None) -> list[ValidationIssue]:
    """执行全部 L3 校验，返回 issues（error 级由调用方决定是否阻断）。"""
    return [
        *check_ingredient_closure(recipe),
        *check_time_consistency(recipe, video_duration_sec),
        *check_order(recipe),
    ]
