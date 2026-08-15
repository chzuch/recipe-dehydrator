"""切分 prompt 模板（SCOPE §4 L2）。

prompt 是代码：修改本文件视为代码变更，必须同步更新/新增测试（CLAUDE.md §8）。
"""

from __future__ import annotations

from app.domain.models import SubtitleLine

# 版本号：prompt 语义变更时递增，便于复盘哪版 prompt 产出哪批卡片
PROMPT_VERSION = "split-v6"

SYSTEM_SPLIT = """你是一个中文美食视频字幕的结构化分析器。
任务：把一段按时间顺序排列的视频字幕，切成连续的烹饪步骤，并抽取结构化菜谱信息。
目标读者是完全不会做菜的新手，要能照着你的输出把菜做出来。

切分规则（必须严格遵守）：
1. 步骤必须按时间顺序、连续地覆盖整条字幕时间线；每句字幕只能属于一个步骤，不得跳过、不得重叠。
2. 步骤边界信号：衔接词（下一步 / 接下来 / 然后 / 最后 / 起锅烧油）、动作动词（切、焯、腌、炒、炖、蒸、收汁）、状态达成。
3. 每个步骤的「达成状态」（done_when）必须是可观察的具体状态，
   例如「炖 10 分钟」「煮到变色」「用筷子能扎透」「水分炒干只剩油」；
   禁止模糊词（如「炒好」「差不多」「行了」），没有明确状态就写 null。
4. 步骤标题（title）用 2-6 字的动宾短语，例如「切牛肉」「焯水去腥」。
5. 步骤描述（description）**不超过 30 字**，一句话说清核心动作（做什么+怎么做）；
   细节、原因、注意事项全部放进 tip，不要堆在 description 里。
6. 只抽取视频里实际出现的内容，禁止编造食材、用量或步骤。
7. start_sec / end_sec 必须来自字幕时间戳（单位：秒，1 位小数）。
8. 步骤的 index 从 1 开始递增。
9. 字幕里未出现的工具不要写进 tools。
10. 步骤粒度与阶段化：先把视频切成 3-6 个「阶段」（phase），再在阶段内分步骤：
    - 阶段名由你给（如「备料」「预处理」「熬制酱料」「炒制」「调味」「收汁装盘」），
      不同菜阶段不同，但都是 2-4 个步骤为一组；
    - 把同属一个阶段的连续动作合并为一个步骤，整个视频的步骤数量控制在 5-12 个；
    - 不要把一个动作拆成多个步骤；超过 90 秒的持续动作（如炖煮）保留为一步。
11. 食材清单（ingredients）只列「需要购买」的原料，每项必须带 category 与 essential：
    - category 五选一：主料 | 配料 | 调味料 | 香料 | 需提前自制
      「主料」= 食材主体（肉、水产、蛋、豆制品、蔬菜主体等），没有它就没有这道菜；
      「配料」= 湿的提味配头：葱、姜、蒜、洋葱、青蒜、香菜、鲜辣椒（青椒/小米椒等）；
      「调味料」= 成品：油、盐、酱、醋、糖、白糖、淀粉、蚝油、料酒、鸡精、味精、白胡椒等；
      「香料」= 干料：八角、桂皮、花椒、香叶、白芷、小茴香、草果、干辣椒等；
      「需提前自制」= 视频里自制出来的中间产物（自制酱料、香料粉、老油、花椒水等）。
      边界规则：鲜辣椒→配料，干辣椒→香料；葱姜蒜→配料（不是香料）；
      淀粉、白糖等成品粉末→调味料（不是香料）。
    - essential：必不可少为 true，可选/锦上添花为 false。
      判断标准：没有它这道菜就做不成的（主料、关键调味料、主要配料）为 true；
      可省略的香料、提鲜剂（味精/鸡精）、备选替代品为 false。
    - 同一种原料多次出现（如不同阶段都用到花生油）必须合并为一条，amount 汇总或按用途标注。
12. 如果这段字幕**没有任何烹饪步骤信息**（例如全部是背景音乐歌词、纯闲聊、无任何烹饪动作），
   请输出：{"title": "", "steps": [], "ingredients": [], "tools": [], "tips": []}，
   不要编造任何步骤。

输出必须是合法 JSON 对象，结构如下（字段不可增减，没有的值用 null）：
{
  "title": "菜名",
  "difficulty": "简单 | 中等 | 困难",
  "servings": "份量或 null",
  "total_time": "总耗时或 null",
  "ingredients": [
    {"name": "食材名", "amount": "用量或 null", "note": "备注或 null",
     "category": "主料 | 配料 | 调味料 | 香料 | 需提前自制", "essential": true}
  ],
  "tools": ["工具"],
  "steps": [
    {"index": 1, "title": "步骤标题", "phase": "阶段名", "description": "做了什么", "done_when": "达成状态或 null", "tip": "新手易错点或 null", "start_sec": 0.0, "end_sec": 0.0}
  ],
  "tips": ["小贴士"]
}

示例（仅用于说明输出格式，勿照抄内容）：
输入字幕：
1: 0.5-5.0 牛腩肉切成稍大的块
2: 5.0-20.0 冷水下锅焯水 煮出浮沫
3: 20.0-60.0 加冰糖炒出糖色 下牛肉翻炒上色

输出：
{"title": "红烧牛肉", "difficulty": "中等", "servings": null, "total_time": null,
 "ingredients": [
   {"name": "牛腩肉", "amount": null, "note": "切稍大的块", "category": "主料", "essential": true},
   {"name": "冰糖", "amount": null, "note": null, "category": "调味料", "essential": true}
 ],
 "tools": ["锅"], "steps": [
   {"index": 1, "title": "切牛肉", "phase": "备料", "description": "牛腩肉切成稍大的块", "done_when": null, "tip": null, "start_sec": 0.5, "end_sec": 5.0},
   {"index": 2, "title": "焯水去腥", "phase": "预处理", "description": "冷水下锅焯水", "done_when": "煮出浮沫", "tip": "冷水下锅", "start_sec": 5.0, "end_sec": 20.0},
   {"index": 3, "title": "炒糖色", "phase": "炒制", "description": "加冰糖炒出糖色，下牛肉翻炒上色", "done_when": "牛肉均匀上色", "tip": null, "start_sec": 20.0, "end_sec": 60.0}
 ], "tips": []}
"""

# 预检：切分前的快速判断（单菜/多菜/非烹饪），token 极少
PRECHECK_SYSTEM = """你是一个视频内容预检器。根据视频标题和字幕片段，判断这个视频是否值得做「菜谱脱水」。

判断规则：
1. is_cooking：视频是否包含烹饪教学内容（讲怎么做菜）。背景音乐歌词、纯吃播、探店等非教学内容 → false。
2. dish_count：视频里教了几道菜。只教一道菜 → 1；教多道不同的菜（合集/盘点类）→ 实际数量。
3. dishes：每道菜的名字（按出现顺序）。
4. summary：一句话概括视频内容。

输出必须是合法 JSON 对象：
{"is_cooking": true, "dish_count": 1, "dishes": ["菜名"], "summary": "一句话概括"}
"""


def build_precheck_prompt(title: str, lines: list[SubtitleLine]) -> str:
    """预检请求：标题 + 首尾字幕片段（不用全量，控制 token）。"""
    head = lines[:15]
    tail = lines[-10:] if len(lines) > 15 else []
    snippet = "\n".join(f"{line.text}" for line in head)
    if tail:
        snippet += "\n...\n" + "\n".join(f"{line.text}" for line in tail)
    return (
        f"视频标题：{title}\n"
        f"字幕总行数：{len(lines)}\n\n"
        f"字幕片段（开头 + 结尾）：\n{snippet}\n\n"
        f"按系统提示的 JSON 结构输出判断结果，不要输出任何其他文字。"
    )


def build_split_prompt(lines: list[SubtitleLine]) -> str:
    """组装切分请求：字幕行 → user prompt。"""
    if not lines:
        msg = "没有可用于切分的字幕"
        raise ValueError(msg)
    numbered = "\n".join(f"{i}: {line.start:.1f}-{line.end:.1f} {line.text}" for i, line in enumerate(lines, 1))
    return (
        f"请把下面这段视频字幕切成连续步骤，并抽取菜谱信息。\n\n"
        f"字幕（编号: 开始秒-结束秒 文本）：\n{numbered}\n\n"
        f"按系统提示中的 JSON 结构输出，不要输出任何其他文字。"
    )


def build_retry_prompt(
    lines: list[SubtitleLine],
    previous_json: str,
    error_messages: list[str],
) -> str:
    """L3 校验失败后的重试 prompt：附带上次结果与具体问题，要求修正。"""
    numbered = "\n".join(f"{i}: {line.start:.1f}-{line.end:.1f} {line.text}" for i, line in enumerate(lines, 1))
    issues = "\n".join(f"- {m}" for m in error_messages)
    return (
        f"上次的切分结果没有通过一致性校验，请修正后重新输出完整 JSON。\n\n"
        f"字幕（编号: 开始秒-结束秒 文本）：\n{numbered}\n\n"
        f"上次输出的 JSON：\n{previous_json}\n\n"
        f"校验发现的问题：\n{issues}\n\n"
        f"请针对上述问题修正（尤其是步骤时间区间必须连续不重叠、"
        f"index 按时间顺序递增），按系统提示中的 JSON 结构重新输出，不要输出任何其他文字。"
    )
