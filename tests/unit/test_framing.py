"""domain.framing（配图选帧）单元测试。"""

from __future__ import annotations

from app.domain.framing import pick_frame_time, select_gif_steps
from app.domain.models import Step, SubtitleLine

from tests.fixtures import make_step


class TestPickFrameTime:
    def test_aligns_to_action_line(self) -> None:
        """步骤区间内含动作的字幕行中点优先（而非区间中点）。"""
        step = make_step(1, 100, 140, "翻炒")
        lines = [
            SubtitleLine(start=100, end=110, text="现在我们把鸡肉准备好"),
            SubtitleLine(start=120, end=126, text="下锅翻炒至变色"),
        ]
        t = pick_frame_time(step, lines)
        assert t == 123.0  # (120+126)/2

    def test_fallback_to_midpoint(self) -> None:
        step = make_step(1, 100, 140, "静置")
        lines = [SubtitleLine(start=100, end=140, text="什么都不做静静等待")]
        assert pick_frame_time(step, lines) == 120.0


class TestSelectGifSteps:
    def _steps_with_phases(self, phases: list[str]) -> list[Step]:
        return [
            Step(index=i, title=f"步骤{i}", phase=p, description="做", start_sec=i * 10, end_sec=i * 10 + 10)
            for i, p in enumerate(phases, 1)
        ]

    def test_few_steps_all_selected(self) -> None:
        steps = self._steps_with_phases(["备料", "备料", "炒制", "炒制", "收尾"])
        assert select_gif_steps(steps) == steps

    def test_many_steps_skip_first_last_phase(self) -> None:
        phases = ["备料"] * 3 + ["炒制"] * 4 + ["炖煮"] * 2 + ["收尾"]  # 10 步
        steps = self._steps_with_phases(phases)
        selected = select_gif_steps(steps)
        assert len(selected) == 6
        assert all(s.phase in {"炒制", "炖煮"} for s in selected)

    def test_two_phases_all_selected(self) -> None:
        phases = ["备料"] * 5 + ["炒制"] * 5  # 10 步但只有 2 阶段
        steps = self._steps_with_phases(phases)
        assert select_gif_steps(steps) == steps
