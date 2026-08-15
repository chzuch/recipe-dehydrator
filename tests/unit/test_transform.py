"""domain.transform 单元测试。"""

from __future__ import annotations

from app.domain.transform import merge_duplicate_ingredients

from tests.fixtures import make_ing


class TestMergeDuplicateIngredients:
    def test_merges_same_name_keeping_order(self) -> None:
        merged = merge_duplicate_ingredients(
            [
                make_ing(name="花生油", amount="50克"),
                make_ing(name="蚝油", amount="100克"),
                make_ing(name="花生油", amount="700克"),
                make_ing(name="花生油", amount="150克", note="炒鸡用"),
            ]
        )
        assert [i.name for i in merged] == ["花生油", "蚝油"]
        assert merged[0].amount == "50克；700克；150克"

    def test_merges_notes(self) -> None:
        merged = merge_duplicate_ingredients(
            [
                make_ing(name="姜片", amount="100克", note="老油用"),
                make_ing(name="姜片", amount="50克", note="炒鸡用"),
            ]
        )
        assert merged[0].amount == "100克；50克"
        assert merged[0].note is not None
        assert "老油用" in merged[0].note and "炒鸡用" in merged[0].note

    def test_unique_ingredients_untouched(self) -> None:
        merged = merge_duplicate_ingredients([make_ing(name="鸡腿", amount="2根"), make_ing(name="辣椒")])
        assert len(merged) == 2

    def test_name_with_spaces_merged(self) -> None:
        merged = merge_duplicate_ingredients(
            [make_ing(name="花 生 油"), make_ing(name="花生油", amount="100克")]
        )
        assert len(merged) == 2  # 不 trim 内部空格，仅去重同名（含空格视为不同，保守）
