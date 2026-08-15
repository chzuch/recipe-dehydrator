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
from app.domain.rules import validate_recipe

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
