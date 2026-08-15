"""SQLite 实现 CardStore 端口。

本地单用户：每次操作用独立连接（asyncio.to_thread 执行，避免阻塞事件循环）。
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from pathlib import Path

from app.domain.models import Recipe

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    recipe_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SQLiteCardStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    async def save(self, recipe: Recipe) -> str:
        def _do() -> str:
            card_id = uuid.uuid4().hex
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO cards (id, recipe_json) VALUES (?, ?)",
                    (card_id, recipe.model_dump_json()),
                )
            return card_id

        return await asyncio.to_thread(_do)

    async def get(self, card_id: str) -> Recipe | None:
        def _do() -> Recipe | None:
            with self._connect() as conn:
                row = conn.execute("SELECT recipe_json FROM cards WHERE id = ?", (card_id,)).fetchone()
            return Recipe.model_validate_json(row["recipe_json"]) if row else None

        return await asyncio.to_thread(_do)

    async def list_all(self) -> list[tuple[str, Recipe]]:
        def _do() -> list[tuple[str, Recipe]]:
            with self._connect() as conn:
                rows = conn.execute("SELECT id, recipe_json FROM cards ORDER BY created_at DESC").fetchall()
            return [(r["id"], Recipe.model_validate_json(r["recipe_json"])) for r in rows]

        return await asyncio.to_thread(_do)

    async def update(self, card_id: str, recipe: Recipe) -> None:
        def _do() -> None:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE cards SET recipe_json = ?, updated_at = datetime('now') WHERE id = ?",
                    (recipe.model_dump_json(), card_id),
                )
                if cur.rowcount == 0:
                    msg = f"卡片不存在: {card_id}"
                    raise KeyError(msg)

        await asyncio.to_thread(_do)

    async def delete(self, card_id: str) -> None:
        def _do() -> None:
            with self._connect() as conn:
                conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

        await asyncio.to_thread(_do)
