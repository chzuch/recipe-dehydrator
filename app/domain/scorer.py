"""脱水卡片质量评分器：无需「理想答案」的客观规则打分（100 分制）。

维度：
- 时间质量 30：步骤区间无重叠、时间跨度覆盖率合理、无大空隙
- 食材质量 25：食材闭环率、分类合规（词表校验）、无重复
- 步骤质量 25：数量在 5-12、done_when 覆盖率、phase 分组合理
- 内容相关性 20：烹饪动词占比、无歌词/无关内容特征

用于 prompt 迭代的量化对比，分数本身不代表「能不能吃」。
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.models import Ingredient, Recipe

# 词表：命中词的食材必须归到对应分类（校验 LLM 分类是否准确）
CONDIMENT_WORDS = frozenset(
    {
        "油", "花生油", "盐", "酱油", "生抽", "老抽", "醋", "香醋", "陈醋",
        "白糖", "糖", "淀粉", "蚝油", "料酒", "鸡精", "味精", "白胡椒", "黑胡椒", "豆瓣酱", "甜面酱",
    }
)
SPICE_WORDS = frozenset(
    {"八角", "桂皮", "花椒", "香叶", "白芷", "小茴香", "草果", "干辣椒", "山奈", "肉蔻", "丁香", "陈皮"}
)
AROMATIC_WORDS = frozenset(
    {
        "葱", "大葱", "小葱", "姜", "生姜", "姜片", "蒜", "大蒜",
        "洋葱", "青蒜", "香菜", "青椒", "小米椒", "鲜辣椒", "蒜苗",
    }
)

COOKING_VERBS = (
    "切", "剁", "拍", "洗", "泡", "焯", "腌", "炸", "煎", "炒", "爆", "煸", "炖", "煮", "蒸", "焖", "烧",
    "烤", "卤", "拌", "调", "熬", "收汁", "勾芡", "上色", "下锅", "翻炒", "调味", "装盘", "出锅", "焯水",
)
_LYRIC_MARKERS = ("♪", "♫", "♬", "词：", "曲：", "演唱")


class DimensionScore(BaseModel):
    name: str
    score: int
    max_score: int
    details: list[str]


class ScoreReport(BaseModel):
    total: int
    dimensions: list[DimensionScore]


def _score_time(recipe: Recipe, video_duration_sec: float | None) -> DimensionScore:
    details: list[str] = []
    score = 0
    steps = sorted(recipe.steps, key=lambda s: s.index)

    # 1. 无重叠（10 分）
    overlap = any(
        steps[i].end_sec - steps[i + 1].start_sec > 2.0 for i in range(len(steps) - 1)
    ) if len(steps) > 1 else False
    if not overlap:
        score += 10
    else:
        details.append("步骤时间区间存在重叠")

    # 2. 覆盖率（15 分）：跨度/时长。覆盖率高是好的；只有过低（漏步骤）才扣分
    if video_duration_sec and video_duration_sec > 0 and steps:
        coverage = (steps[-1].end_sec - steps[0].start_sec) / video_duration_sec
        if coverage >= 0.65:
            score += 15
        elif coverage >= 0.45:
            score += 8
            details.append(f"时间覆盖率 {coverage:.0%} 偏低，可能漏步骤")
        else:
            score += 3
            details.append(f"时间覆盖率 {coverage:.0%} 过低，很可能漏步骤")
    else:
        score += 8
        details.append("无视频时长，覆盖率无法评估")

    # 3. 无大空隙（5 分）
    big_gap = any(
        steps[i + 1].start_sec - steps[i].end_sec > 30 for i in range(len(steps) - 1)
    ) if len(steps) > 1 else False
    if not big_gap:
        score += 5
    else:
        details.append("相邻步骤存在 >30s 空隙")

    return DimensionScore(name="时间质量", score=score, max_score=30, details=details)


def _check_category(name: str, category: str) -> bool:
    """命中词表时校验分类正确性。"""
    if name in SPICE_WORDS:
        return category == "香料"
    if name in AROMATIC_WORDS:
        return category == "配料"
    for w in CONDIMENT_WORDS:
        if w in name:
            return category == "调味料"
    return True  # 未命中词表不校验


def _score_ingredients(recipe: Recipe) -> DimensionScore:
    details: list[str] = []
    score = 0
    ings = recipe.ingredients
    if not ings:
        return DimensionScore(name="食材质量", score=0, max_score=25, details=["无食材"])

    # 1. 闭环率（10 分）：食材出现在步骤文本中的比例
    step_text = " ".join(
        " ".join(filter(None, (s.title, s.description, s.done_when, s.tip))) for s in recipe.steps
    ).replace(" ", "")
    hit = sum(1 for i in ings if i.name.replace(" ", "") in step_text)
    closure = hit / len(ings)
    score += round(closure * 10)
    if closure < 1:
        details.append(f"食材闭环率 {closure:.0%}（{hit}/{len(ings)} 出现在步骤中）")

    # 2. 分类合规（10 分）：命中词表的食材分类正确比例
    def _in_wordlist(ing: Ingredient) -> bool:
        return (
            ing.name in SPICE_WORDS
            or ing.name in AROMATIC_WORDS
            or any(w in ing.name for w in CONDIMENT_WORDS)
        )

    checked = [i for i in ings if _in_wordlist(i)]
    if checked:
        ok = sum(1 for i in checked if _check_category(i.name, i.category))
        ratio = ok / len(checked)
        score += round(ratio * 10)
        if ratio < 1:
            wrong = [f"{i.name}→{i.category}" for i in checked if not _check_category(i.name, i.category)]
            details.append(f"分类错误：{'、'.join(wrong)}")
    else:
        score += 10

    # 3. 无重复（5 分）
    names = [i.name for i in ings]
    if len(names) == len(set(names)):
        score += 5
    else:
        details.append("食材存在重复条目")

    return DimensionScore(name="食材质量", score=score, max_score=25, details=details)


def _score_steps(recipe: Recipe) -> DimensionScore:
    details: list[str] = []
    score = 0
    steps = recipe.steps

    # 1. 数量（10 分）
    n = len(steps)
    if 5 <= n <= 12:
        score += 10
    elif 3 <= n <= 15:
        score += 5
        details.append(f"步骤数 {n} 偏离理想区间（5-12）")
    else:
        details.append(f"步骤数 {n} 异常")

    # 2. done_when 覆盖率（10 分）
    if steps:
        with_done = sum(1 for s in steps if s.done_when)
        ratio = with_done / len(steps)
        score += round(ratio * 10)
        if ratio < 1:
            details.append(f"done_when 覆盖率 {ratio:.0%}")

    # 3. phase 分组（5 分）：全部有 phase + 每阶段 2-4 步为主
    if steps and all(s.phase for s in steps):
        score += 3
        phases: dict[str, int] = {}
        for s in steps:
            phases[s.phase] = phases.get(s.phase, 0) + 1
        reasonable = sum(1 for c in phases.values() if 1 <= c <= 4)
        if reasonable == len(phases):
            score += 2
        else:
            details.append(f"部分阶段步骤数异常：{phases}")
    else:
        details.append("存在无 phase 的步骤")

    return DimensionScore(name="步骤质量", score=score, max_score=25, details=details)


def _score_content(recipe: Recipe) -> DimensionScore:
    details: list[str] = []
    score = 0
    steps = recipe.steps
    if not steps:
        return DimensionScore(name="内容相关性", score=0, max_score=20, details=["无步骤"])

    # 1. 烹饪动词占比（12 分）
    with_verb = sum(1 for s in steps if any(v in (s.title + s.description) for v in COOKING_VERBS))
    ratio = with_verb / len(steps)
    score += round(ratio * 12)
    if ratio < 1:
        details.append(f"烹饪动词覆盖率 {ratio:.0%}")

    # 2. 无歌词/无关内容（8 分）
    text = " ".join(s.title + s.description for s in steps)
    if not any(m in text for m in _LYRIC_MARKERS):
        score += 8
    else:
        details.append("步骤描述含歌词/无关内容标记")

    return DimensionScore(name="内容相关性", score=score, max_score=20, details=details)


def score_recipe(recipe: Recipe, video_duration_sec: float | None = None) -> ScoreReport:
    """对脱水卡片打分（100 分制，四维度）。"""
    dims = [
        _score_time(recipe, video_duration_sec),
        _score_ingredients(recipe),
        _score_steps(recipe),
        _score_content(recipe),
    ]
    return ScoreReport(total=sum(d.score for d in dims), dimensions=dims)
