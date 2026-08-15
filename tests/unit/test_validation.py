"""domain.validation（L3 校验）单元测试。"""

from __future__ import annotations

from app.domain.validation import (
    check_ingredient_closure,
    check_order,
    check_time_consistency,
    validate_recipe,
)

from tests.fixtures import make_ing, make_recipe, make_step


class TestIngredientClosure:
    def test_ingredient_mentioned_in_step_is_ok(self) -> None:
        recipe = make_recipe(
            make_step(1, 0, 10, "切牛腩肉"),
            ingredients=[make_ing(name="牛腩肉")],
        )
        assert check_ingredient_closure(recipe) == []

    def test_missing_ingredient_reports_warning(self) -> None:
        recipe = make_recipe(
            make_step(1, 0, 10, "切牛腩肉"),
            ingredients=[make_ing(name="土豆")],
        )
        issues = check_ingredient_closure(recipe)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].code == "INGREDIENT_NOT_IN_STEPS"

    def test_ingredient_name_ignores_spaces(self) -> None:
        recipe = make_recipe(
            make_step(1, 0, 10, "放入 生抽"),
            ingredients=[make_ing(name="生抽")],
        )
        assert check_ingredient_closure(recipe) == []


class TestTimeConsistency:
    def test_overlapping_steps_report_error(self) -> None:
        recipe = make_recipe(make_step(1, 0, 30), make_step(2, 20, 50))
        issues = check_time_consistency(recipe)
        assert any(i.code == "STEP_OVERLAP" and i.severity == "error" for i in issues)

    def test_small_overlap_tolerated(self) -> None:
        recipe = make_recipe(make_step(1, 0, 10), make_step(2, 9.5, 20))
        issues = check_time_consistency(recipe)
        assert not any(i.code == "STEP_OVERLAP" for i in issues)

    def test_large_gap_reports_warning(self) -> None:
        recipe = make_recipe(make_step(1, 0, 10), make_step(2, 100, 120))
        issues = check_time_consistency(recipe)
        assert any(i.code == "STEP_GAP" and i.severity == "warning" for i in issues)

    def test_duration_drift_reports_warning(self) -> None:
        recipe = make_recipe(make_step(1, 0, 10), make_step(2, 10, 20))
        issues = check_time_consistency(recipe, video_duration_sec=600)
        assert any(i.code == "DURATION_DRIFT" for i in issues)

    def test_single_step_no_time_checks(self) -> None:
        recipe = make_recipe(make_step(1, 0, 60))
        assert check_time_consistency(recipe, video_duration_sec=60) == []


class TestOrder:
    def test_consistent_order_no_issues(self) -> None:
        recipe = make_recipe(make_step(1, 0, 10), make_step(2, 10, 20), make_step(3, 20, 30))
        assert check_order(recipe) == []

    def test_out_of_order_times_report_error(self) -> None:
        recipe = make_recipe(make_step(1, 30, 40), make_step(2, 10, 20), make_step(3, 20, 30))
        issues = check_order(recipe)
        assert any(i.code == "STEP_ORDER" and i.severity == "error" for i in issues)


class TestValidateRecipe:
    def test_aggregates_all_rules(self) -> None:
        recipe = make_recipe(
            make_step(1, 0, 10, "切牛腩肉"),
            make_step(2, 50, 60, "炖"),
            ingredients=[make_ing(name="土豆")],
        )
        issues = validate_recipe(recipe, video_duration_sec=600)
        codes = {i.code for i in issues}
        assert "INGREDIENT_NOT_IN_STEPS" in codes
        assert "STEP_GAP" in codes
