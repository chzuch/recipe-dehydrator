"""食材/菜谱的归一化变换（LLM 输出后的代码层兜底）。"""

from __future__ import annotations

from app.domain.models import Ingredient


def merge_duplicate_ingredients(ingredients: list[Ingredient]) -> list[Ingredient]:
    """同名食材合并（LLM 常把同一原料多次出现拆成多条，如花生油 3 次）。

    保留首次出现顺序；amount 合并展示（分号分隔），note 合并。
    """
    merged: dict[str, Ingredient] = {}
    order: list[str] = []
    for ing in ingredients:
        key = ing.name.strip()
        if key not in merged:
            merged[key] = ing.model_copy(deep=True)
            order.append(key)
            continue
        prev = merged[key]
        amounts = [a for a in (prev.amount, ing.amount) if a]
        if amounts:
            prev.amount = "；".join(amounts)
        if ing.note:
            prev.note = f"{prev.note}；{ing.note}" if prev.note else ing.note
    return [merged[key] for key in order]
