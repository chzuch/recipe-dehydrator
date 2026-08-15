"""domain.scorer 单元测试。"""

from __future__ import annotations

from app.domain.models import Ingredient, Recipe, Step
from app.domain.scorer import score_recipe


def _step(index: int, start: float, end: float, title: str, desc: str = "", done: str | None = "完成") -> Step:
    return Step(
        index=index,
        title=title,
        phase="烹饪",
        description=desc or title,
        done_when=done,
        start_sec=start,
        end_sec=end,
    )


def _good_recipe() -> Recipe:
    """高质量卡片：6 步连续、食材闭环、分类正确、done_when 齐全。"""
    steps = [
        _step(1, 0, 30, "切鸡肉", "鸡肉切块"),
        _step(2, 30, 60, "焯水", "鸡肉下锅焯水", "煮出浮沫"),
        _step(3, 60, 120, "爆香", "下姜片翻炒"),
        _step(4, 120, 180, "炒鸡肉", "翻炒鸡肉", "表面微黄"),
        _step(5, 180, 220, "加八角调味", "加八角和盐调味"),
        _step(6, 220, 240, "收汁出锅", "大火收汁"),
    ]
    return Recipe(
        title="炒鸡",
        ingredients=[
            Ingredient(name="鸡肉", amount="500克", category="主料", essential=True),
            Ingredient(name="姜片", category="配料", essential=True),
            Ingredient(name="八角", category="香料", essential=True),
            Ingredient(name="盐", category="调味料", essential=True),
        ],
        steps=steps,
    )


class TestScoreRecipe:
    def test_good_recipe_scores_high(self) -> None:
        report = score_recipe(_good_recipe(), video_duration_sec=260)
        assert report.total >= 85
        assert all(d.score > 0 for d in report.dimensions)

    def test_perfect_coverage_full_marks(self) -> None:
        report = score_recipe(_good_recipe(), video_duration_sec=250)
        time_dim = next(d for d in report.dimensions if d.name == "时间质量")
        assert time_dim.score == 30

    def test_wrong_category_penalized(self) -> None:
        recipe = _good_recipe()
        recipe.ingredients[2] = Ingredient(name="八角", category="调味料", essential=True)  # 应为香料
        report = score_recipe(recipe)
        ings_dim = next(d for d in report.dimensions if d.name == "食材质量")
        good = next(d for d in score_recipe(_good_recipe()).dimensions if d.name == "食材质量")
        assert ings_dim.score < good.score
        assert any("八角" in d for d in ings_dim.details)

    def test_duplicate_ingredients_penalized(self) -> None:
        recipe = _good_recipe()
        recipe.ingredients.append(Ingredient(name="盐", category="调味料", essential=True))
        report = score_recipe(recipe)
        ings_dim = next(d for d in report.dimensions if d.name == "食材质量")
        assert any("重复" in d for d in ings_dim.details)

    def test_overlap_penalized(self) -> None:
        recipe = _good_recipe()
        recipe.steps[1] = _step(2, 25, 60, "焯水")  # 与步骤 1 (0-30) 重叠
        report = score_recipe(recipe)
        time_dim = next(d for d in report.dimensions if d.name == "时间质量")
        assert time_dim.score < 30

    def test_missing_done_when_penalized(self) -> None:
        recipe = _good_recipe()
        for s in recipe.steps:
            s.done_when = None
        report = score_recipe(recipe)
        steps_dim = next(d for d in report.dimensions if d.name == "步骤质量")
        good = next(d for d in score_recipe(_good_recipe()).dimensions if d.name == "步骤质量")
        assert steps_dim.score < good.score

    def test_lyrics_penalized(self) -> None:
        recipe = _good_recipe()
        recipe.steps[0] = _step(1, 0, 30, "♪我循声而去♪", "♪歌词内容♪")
        report = score_recipe(recipe)
        content_dim = next(d for d in report.dimensions if d.name == "内容相关性")
        assert any("歌词" in d for d in content_dim.details)
