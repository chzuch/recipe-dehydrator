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

from app.domain.models import Recipe

# 相邻步骤间允许的最大闲话间隙（秒）：超过视为「可能漏了步骤」
MAX_GAP_SEC = 30.0
# 步骤区间允许的最大重叠（秒）：轻微重叠可接受（字幕边界模糊）
MAX_OVERLAP_SEC = 2.0
# 总跨度与视频时长的最大相对偏差
MAX_DURATION_DRIFT = 0.2


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
