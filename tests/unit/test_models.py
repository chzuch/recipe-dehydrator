"""domain.models 单元测试。"""

from __future__ import annotations

import pytest
from app.domain.models import Ingredient, Recipe, Step, SubtitleLine
from pydantic import ValidationError


def _step(index: int, start: float, end: float, title: str = "步骤") -> Step:
    return Step(index=index, title=title, description="做", start_sec=start, end_sec=end)


class TestSubtitleLine:
    def test_requires_nonempty_text(self) -> None:
        with pytest.raises(ValidationError):
            SubtitleLine(start=0, end=1, text="")

    def test_negative_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SubtitleLine(start=-1, end=1, text="x")


class TestStep:
    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError, match="end_sec"):
            Step(index=1, title="切", description="切肉", start_sec=10, end_sec=5)

    def test_ok(self) -> None:
        step = Step(index=1, title="切", description="切肉", start_sec=5, end_sec=10)
        assert step.done_when is None


class TestRecipe:
    def test_steps_sorted_by_index_on_validation(self) -> None:
        recipe = Recipe(
            title="红烧牛肉",
            steps=[_step(3, 30, 40), _step(1, 0, 10), _step(2, 10, 30)],
        )
        assert [s.index for s in recipe.steps] == [1, 2, 3]
        assert recipe.steps[0].start_sec == 0

    def test_shopping_list_filters_have(self) -> None:
        recipe = Recipe(
            title="番茄炒蛋",
            ingredients=[Ingredient(name="番茄", amount="2个"), Ingredient(name="鸡蛋", amount="3个")],
        )
        missing = recipe.shopping_list({"番茄"})
        assert [i.name for i in missing] == ["鸡蛋"]

    def test_shopping_list_empty_have_returns_all(self) -> None:
        recipe = Recipe(
            title="番茄炒蛋",
            ingredients=[Ingredient(name="番茄")],
        )
        assert len(recipe.shopping_list()) == 1
