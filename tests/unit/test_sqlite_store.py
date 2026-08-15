"""SQLiteCardStore 单元测试（真实 SQLite，内存/临时文件，无网络）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.domain.models import Ingredient, Recipe, Step
from app.infrastructure.sqlite_store import SQLiteCardStore


def _recipe(title: str = "测试菜") -> Recipe:
    return Recipe(
        title=title,
        ingredients=[Ingredient(name="鸡肉", amount="500克", category="主料", essential=True)],
        steps=[Step(index=1, title="切", phase="备料", description="切肉", start_sec=0, end_sec=10)],
    )


@pytest.fixture
async def store(tmp_path: Path) -> SQLiteCardStore:
    return SQLiteCardStore(tmp_path / "cards.db")


class TestCRUD:
    async def test_save_and_get(self, store: SQLiteCardStore) -> None:
        card_id = await store.save(_recipe("红烧肉"))
        loaded = await store.get(card_id)
        assert loaded is not None and loaded.title == "红烧肉"

    async def test_get_missing_returns_none(self, store: SQLiteCardStore) -> None:
        assert await store.get("不存在") is None

    async def test_update_and_delete(self, store: SQLiteCardStore) -> None:
        card_id = await store.save(_recipe("番茄蛋"))
        updated = _recipe("番茄蛋（改良）")
        await store.update(card_id, updated)
        assert (await store.get(card_id)).title == "番茄蛋（改良）"  # type: ignore[union-attr]
        await store.delete(card_id)
        assert await store.get(card_id) is None

    async def test_list_all_returns_all(self, store: SQLiteCardStore) -> None:
        await store.save(_recipe("菜一"))
        await store.save(_recipe("菜二"))
        assert len(await store.list_all()) == 2


class TestCorruptedData:
    async def test_corrupted_card_skipped_in_list(self, store: SQLiteCardStore, tmp_path: Path) -> None:
        """单张卡片数据损坏（schema 不符）→ 跳过，不拖垮整个历史列表（真实事故回归）。"""
        good_id = await store.save(_recipe("好卡片"))
        # 直接写一条 category 非法的坏数据
        bad_recipe = _recipe("坏卡片").model_dump()
        bad_recipe["ingredients"][0]["category"] = "配菜"  # 旧枚举值
        import sqlite3

        with sqlite3.connect(store._db_path) as conn:
            conn.execute(
                "INSERT INTO cards (id, recipe_json) VALUES (?, ?)",
                ("bad-card", json.dumps(bad_recipe, ensure_ascii=False)),
            )
        result = await store.list_all()
        ids = [cid for cid, _ in result]
        assert good_id in ids
        assert "bad-card" not in ids
        assert len(result) == 1
