"""domain.rules（L3 校验）单元测试。"""

from __future__ import annotations

from app.domain.models import Ingredient, Recipe, Step, SubtitleLine
from app.domain.rules import (
    check_ingredient_closure,
    check_order,
    check_time_consistency,
    is_action_step,
    merge_duplicate_ingredients,
    pick_frame_time,
    validate_recipe,
)


def _recipe(*steps: Step, ingredients: list[Ingredient] | None = None) -> Recipe:
    return Recipe(title="测试菜", steps=list(steps), ingredients=ingredients or [])


def _ing(name: str, amount: str | None = None, note: str | None = None) -> Ingredient:
    """测试食材构造器：category/essential 用占位值。"""
    return Ingredient(name=name, amount=amount, note=note, category="调味料", essential=True)


def _step(index: int, start: float, end: float, text: str = "") -> Step:
    return Step(
        index=index,
        title=text or f"步骤{index}",
        phase="烹饪",
        description=text or f"做{index}",
        start_sec=start,
        end_sec=end,
    )


class TestIngredientClosure:
    def test_ingredient_mentioned_in_step_is_ok(self) -> None:
        recipe = _recipe(
            _step(1, 0, 10, "切牛腩肉"),
            ingredients=[_ing(name="牛腩肉")],
        )
        assert check_ingredient_closure(recipe) == []

    def test_missing_ingredient_reports_warning(self) -> None:
        recipe = _recipe(
            _step(1, 0, 10, "切牛腩肉"),
            ingredients=[_ing(name="土豆")],
        )
        issues = check_ingredient_closure(recipe)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].code == "INGREDIENT_NOT_IN_STEPS"

    def test_ingredient_name_ignores_spaces(self) -> None:
        recipe = _recipe(
            _step(1, 0, 10, "放入 生抽"),
            ingredients=[_ing(name="生抽")],
        )
        assert check_ingredient_closure(recipe) == []


class TestTimeConsistency:
    def test_overlapping_steps_report_error(self) -> None:
        recipe = _recipe(_step(1, 0, 30), _step(2, 20, 50))
        issues = check_time_consistency(recipe)
        assert any(i.code == "STEP_OVERLAP" and i.severity == "error" for i in issues)

    def test_small_overlap_tolerated(self) -> None:
        recipe = _recipe(_step(1, 0, 10), _step(2, 9.5, 20))
        issues = check_time_consistency(recipe)
        assert not any(i.code == "STEP_OVERLAP" for i in issues)

    def test_large_gap_reports_warning(self) -> None:
        recipe = _recipe(_step(1, 0, 10), _step(2, 100, 120))
        issues = check_time_consistency(recipe)
        assert any(i.code == "STEP_GAP" and i.severity == "warning" for i in issues)

    def test_duration_drift_reports_warning(self) -> None:
        recipe = _recipe(_step(1, 0, 10), _step(2, 10, 20))
        issues = check_time_consistency(recipe, video_duration_sec=600)
        assert any(i.code == "DURATION_DRIFT" for i in issues)

    def test_single_step_no_time_checks(self) -> None:
        recipe = _recipe(_step(1, 0, 60))
        assert check_time_consistency(recipe, video_duration_sec=60) == []


class TestOrder:
    def test_consistent_order_no_issues(self) -> None:
        recipe = _recipe(_step(1, 0, 10), _step(2, 10, 20), _step(3, 20, 30))
        assert check_order(recipe) == []

    def test_out_of_order_times_report_error(self) -> None:
        recipe = _recipe(_step(1, 30, 40), _step(2, 10, 20), _step(3, 20, 30))
        issues = check_order(recipe)
        assert any(i.code == "STEP_ORDER" and i.severity == "error" for i in issues)


class TestValidateRecipe:
    def test_aggregates_all_rules(self) -> None:
        recipe = _recipe(
            _step(1, 0, 10, "切牛腩肉"),
            _step(2, 50, 60, "炖"),
            ingredients=[_ing(name="土豆")],
        )
        issues = validate_recipe(recipe, video_duration_sec=600)
        codes = {i.code for i in issues}
        assert "INGREDIENT_NOT_IN_STEPS" in codes
        assert "STEP_GAP" in codes


class TestMergeDuplicateIngredients:
    def test_merges_same_name_keeping_order(self) -> None:
        merged = merge_duplicate_ingredients(
            [
                _ing(name="花生油", amount="50克"),
                _ing(name="蚝油", amount="100克"),
                _ing(name="花生油", amount="700克"),
                _ing(name="花生油", amount="150克", note="炒鸡用"),
            ]
        )
        assert [i.name for i in merged] == ["花生油", "蚝油"]
        assert merged[0].amount == "50克；700克；150克"

    def test_merges_notes(self) -> None:
        merged = merge_duplicate_ingredients(
            [
                _ing(name="姜片", amount="100克", note="老油用"),
                _ing(name="姜片", amount="50克", note="炒鸡用"),
            ]
        )
        assert merged[0].amount == "100克；50克"
        assert merged[0].note is not None
        assert "老油用" in merged[0].note and "炒鸡用" in merged[0].note

    def test_unique_ingredients_untouched(self) -> None:
        merged = merge_duplicate_ingredients([_ing(name="鸡腿", amount="2根"), _ing(name="辣椒")])
        assert len(merged) == 2

    def test_name_with_spaces_merged(self) -> None:
        merged = merge_duplicate_ingredients(
            [_ing(name="花 生 油"), _ing(name="花生油", amount="100克")]
        )
        assert len(merged) == 2  # 不 trim 内部空格，仅去重同名（含空格视为不同，保守）


class TestPickFrameTime:
    def test_aligns_to_action_line(self) -> None:
        """步骤区间内含动作的字幕行中点优先（而非区间中点）。"""
        step = _step(1, 100, 140, "翻炒")
        lines = [
            SubtitleLine(start=100, end=110, text="现在我们把鸡肉准备好"),
            SubtitleLine(start=120, end=126, text="下锅翻炒至变色"),
        ]
        t = pick_frame_time(step, lines)
        assert t == 123.0  # (120+126)/2

    def test_fallback_to_midpoint(self) -> None:
        step = _step(1, 100, 140, "静置")
        lines = [SubtitleLine(start=100, end=140, text="什么都不做静静等待")]
        assert pick_frame_time(step, lines) == 120.0


class TestIsActionStep:
    def test_action_word_triggers(self) -> None:
        step = Step(index=1, title="翻炒鸡肉", phase="炒制", description="下锅快速翻炒", start_sec=0, end_sec=10)
        assert is_action_step(step) is True

    def test_static_step_not_triggered(self) -> None:
        step = Step(index=1, title="切牛肉", phase="备料", description="牛腩肉切成稍大的块", start_sec=0, end_sec=10)
        assert is_action_step(step) is False
