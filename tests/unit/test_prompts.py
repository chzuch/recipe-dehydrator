"""app.application.prompts 单元测试：prompt 组装是代码，必须有测试（CLAUDE.md §8）。"""

from __future__ import annotations

import pytest
from app.application.prompts import SYSTEM_SPLIT, build_retry_prompt, build_split_prompt
from app.domain.models import SubtitleLine


def _lines() -> list[SubtitleLine]:
    return [SubtitleLine(start=0.5, end=5.0, text="切牛腩肉"), SubtitleLine(start=5.0, end=20.0, text="焯水")]


class TestBuildSplitPrompt:
    def test_includes_numbered_lines(self) -> None:
        prompt = build_split_prompt(_lines())
        assert "1: 0.5-5.0 切牛腩肉" in prompt
        assert "2: 5.0-20.0 焯水" in prompt

    def test_empty_lines_raises(self) -> None:
        with pytest.raises(ValueError):
            build_split_prompt([])

    def test_system_mentions_cutting_rules(self) -> None:
        assert "连续" in SYSTEM_SPLIT
        assert "start_sec" in SYSTEM_SPLIT

    def test_system_v3_schema_fields(self) -> None:
        """split-v3：食材分类（category）与核心筛选（essential）。"""
        assert "category" in SYSTEM_SPLIT
        assert "essential" in SYSTEM_SPLIT
        assert "主料" in SYSTEM_SPLIT and "需提前自制" in SYSTEM_SPLIT

    def test_system_v5_category_boundaries(self) -> None:
        """split-v5：配料（湿）/香料（干）/调味料（成品含淀粉白糖）边界规则。"""
        assert "配料" in SYSTEM_SPLIT
        assert "鲜辣椒→配料" in SYSTEM_SPLIT
        assert "淀粉" in SYSTEM_SPLIT


class TestBuildRetryPrompt:
    def test_includes_previous_output_and_issues(self) -> None:
        prompt = build_retry_prompt(_lines(), '{"title": "x"}', ["步骤1与步骤2时间区间重叠"])
        assert '{"title": "x"}' in prompt
        assert "步骤1与步骤2时间区间重叠" in prompt
