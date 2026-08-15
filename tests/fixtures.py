"""测试共享 fixtures：构造器与样例数据（集中管理，各测试文件从此导入）。"""

from __future__ import annotations

from typing import Any

from app.domain.models import Ingredient, Recipe, Step, SubtitleLine


def make_recipe(*steps: Step, ingredients: list[Ingredient] | None = None) -> Recipe:
    return Recipe(title="测试菜", steps=list(steps), ingredients=ingredients or [])


def make_ing(name: str, amount: str | None = None, note: str | None = None) -> Ingredient:
    """测试食材构造器：category/essential 用占位值。"""
    return Ingredient(name=name, amount=amount, note=note, category="调味料", essential=True)


def make_step(index: int, start: float, end: float, text: str = "") -> Step:
    return Step(
        index=index,
        title=text or f"步骤{index}",
        phase="烹饪",
        description=text or f"做{index}",
        start_sec=start,
        end_sec=end,
    )


# 标准菜谱样例（LLM 切分输出）
SAMPLE_RECIPE: dict[str, Any] = {
    "title": "红烧牛肉",
    "difficulty": "中等",
    "servings": "2人份",
    "total_time": "40分钟",
    "ingredients": [{"name": "牛腩肉", "amount": "500克", "note": None, "category": "主料", "essential": True}],
    "tools": ["锅"],
    "steps": [
        {
            "index": 1,
            "title": "切牛肉",
            "phase": "备料",
            "description": "牛腩肉切成稍大的块",
            "done_when": None,
            "tip": "切稍大的块",
            "start_sec": 0.5,
            "end_sec": 5.0,
        },
        {
            "index": 2,
            "title": "焯水去腥",
            "phase": "预处理",
            "description": "冷水下锅焯水",
            "done_when": "煮出浮沫",
            "tip": "冷水下锅",
            "start_sec": 5.0,
            "end_sec": 20.0,
        },
    ],
    "tips": [],
}

# 步骤 1、2 时间区间重叠（STEP_OVERLAP）的错误输出
OVERLAP_RECIPE: dict[str, Any] = {
    **SAMPLE_RECIPE,
    "steps": [
        {**SAMPLE_RECIPE["steps"][0], "end_sec": 12.0},
        {**SAMPLE_RECIPE["steps"][1], "start_sec": 8.0},
    ],
}

# 字幕样例
LINES = [
    SubtitleLine(start=0.5, end=5.0, text="牛腩肉切成稍大的块"),
    SubtitleLine(start=5.0, end=20.0, text="冷水下锅焯水，煮出浮沫"),
]
