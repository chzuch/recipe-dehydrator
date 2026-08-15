"""配图选帧逻辑：静态图抽帧时间点选择 + GIF 步骤筛选。"""

from __future__ import annotations

from app.domain.models import Step, SubtitleLine

# 步骤区间允许的最大重叠（秒）：与 validation 保持一致
_MAX_OVERLAP_SEC = 2.0
# GIF 片段时长（秒）
GIF_DURATION_SEC = 2.0
# 步骤数超过此阈值时，GIF 只给中间阶段的步骤（首尾通常是备料/装盘，手法信息少）
GIF_STEP_THRESHOLD = 8


def pick_frame_time(step: Step, lines: list[SubtitleLine]) -> float:
    """关键句对齐抽帧：在步骤区间内找含烹饪动作的字幕行，取该行中点。

    说「倒入料酒」时画面大概率正在倒——比区间中点靠谱得多。
    找不到则回退区间中点。
    """
    in_range = [
        line
        for line in lines
        if line.start >= step.start_sec - _MAX_OVERLAP_SEC and line.end <= step.end_sec + _MAX_OVERLAP_SEC
    ]
    for line in in_range:
        if any(
            v in line.text
            for v in ("切", "炒", "炖", "煮", "焯", "炸", "煎", "加", "倒", "放", "翻炒", "搅拌", "收汁")
        ):
            return (line.start + line.end) / 2
    return step.start_sec + (step.end_sec - step.start_sec) / 2


def select_gif_steps(steps: list[Step]) -> list[Step]:
    """选择生成 GIF 的步骤：≤阈值全选；超过则只选中间阶段（跳首尾备料/装盘阶段）。"""
    if len(steps) <= GIF_STEP_THRESHOLD:
        return list(steps)
    phases: list[str] = []
    for s in steps:
        if s.phase not in phases:
            phases.append(s.phase)
    if len(phases) <= 2:
        return list(steps)  # 阶段太少无法区分首尾，全选
    middle_phases = set(phases[1:-1])
    return [s for s in steps if s.phase in middle_phases]
