"""用例：菜谱卡查询 / 编辑 / 删除 + L4 人工修正样本沉淀（SCOPE §4）。

用户编辑过的卡片视为「比 LLM 输出更可信」的 few-shot 样本，写入 samples 目录，
供后续 prompt 增强使用（v0.1 只做积累，不做重训）。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.domain.models import Recipe
from app.domain.ports import CardStore
from app.domain.validation import validate_recipe

logger = logging.getLogger(__name__)


class CardsUseCase:
    def __init__(self, store: CardStore, samples_dir: str | Path) -> None:
        self._store = store
        self._samples_dir = Path(samples_dir)

    async def list_cards(self) -> list[tuple[str, Recipe]]:
        return await self._store.list_all()

    async def get_card(self, card_id: str) -> Recipe | None:
        return await self._store.get(card_id)

    async def update_card(self, card_id: str, recipe: Recipe) -> Recipe:
        """更新卡片：重跑 L3 校验（仅告警不阻断，用户已人工确认），并沉淀样本。"""
        issues = validate_recipe(recipe)
        recipe.warnings = [i.message for i in issues if i.severity == "warning"]
        await self._store.update(card_id, recipe)
        self._collect_sample(card_id, recipe)
        return recipe

    async def delete_card(self, card_id: str) -> None:
        await self._store.delete(card_id)

    async def cook_card(self, card_id: str) -> Recipe | None:
        """「今天做了」打卡：cooked_count+1、更新 last_cooked_at。"""
        recipe = await self._store.get(card_id)
        if recipe is None:
            return None
        recipe.cooked_count += 1
        recipe.last_cooked_at = datetime.now(UTC).isoformat(timespec="seconds")
        await self._store.update(card_id, recipe)
        return recipe

    async def pin_card(self, card_id: str) -> Recipe | None:
        """置顶/取消置顶（toggle）。"""
        recipe = await self._store.get(card_id)
        if recipe is None:
            return None
        recipe.pinned = not recipe.pinned
        await self._store.update(card_id, recipe)
        return recipe

    @staticmethod
    def search_cards(cards: list[tuple[str, Recipe]], query: str | None = None) -> list[tuple[str, Recipe]]:
        """菜名 + 食材名模糊搜索。"""
        if not query or not query.strip():
            return cards
        q = query.strip().lower()
        hits: list[tuple[str, Recipe]] = []
        for cid, recipe in cards:
            if q in recipe.title.lower():
                hits.append((cid, recipe))
                continue
            if any(q in ing.name.lower() for ing in recipe.ingredients):
                hits.append((cid, recipe))
        return hits

    @staticmethod
    def filter_by_main_ingredient(
        cards: list[tuple[str, Recipe]], category: str | None
    ) -> list[tuple[str, Recipe]]:
        """按主料分类筛选（主料食材名匹配，如「鸡肉」「牛肉」）。"""
        if not category or not category.strip():
            return cards
        c = category.strip()
        hits: list[tuple[str, Recipe]] = []
        for cid, recipe in cards:
            main_names = [i.name for i in recipe.ingredients if i.category == "主料"]
            if any(c in name for name in main_names):
                hits.append((cid, recipe))
        return hits

    @staticmethod
    def sort_cards(cards: list[tuple[str, Recipe]], sort: str) -> list[tuple[str, Recipe]]:
        """排序：pinned（置顶优先→最近做过→最新）/ recent（最近做过）/ newest（最新创建）。"""
        if sort == "recent":
            return sorted(
                cards,
                key=lambda t: (t[1].last_cooked_at or "", t[1].pinned),
                reverse=True,
            )
        if sort == "newest":
            return list(cards)
        # 默认 pinned：置顶优先 → 最近做过 → 原顺序（最新）
        return sorted(
            cards,
            key=lambda t: (t[1].pinned, t[1].last_cooked_at or "", t[1].cooked_count),
            reverse=True,
        )

    def _collect_sample(self, card_id: str, recipe: Recipe) -> None:
        """把用户修正后的卡片存为 few-shot 样本（不阻塞主流程）。"""
        try:
            self._samples_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            payload = {
                "card_id": card_id,
                "edited_at": stamp,
                "recipe": recipe.model_dump(mode="json"),
            }
            path = self._samples_dir / f"sample_{uuid.uuid4().hex[:8]}_{stamp}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("样本沉淀失败（不影响保存卡片）: %s", exc)
