"""切分 prompt 模板（SCOPE §4 L2）。

prompt 是代码：修改本文件视为代码变更，必须同步更新/新增测试（CLAUDE.md §8）。
"""

from __future__ import annotations

from app.domain.models import SubtitleLine

# 版本号：prompt 语义变更时递增，便于复盘哪版 prompt 产出哪批卡片
PROMPT_VERSION = "split-v1"

SYSTEM_SPLIT = """你是一个中文美食视频字幕的结构化分析器。
任务：把一段按时间顺序排列的视频字幕，切成连续的烹饪步骤，并抽取结构化菜谱信息。

切分规则（必须严格遵守）：
1. 步骤必须按时间顺序、连续地覆盖整条字幕时间线；每句字幕只能属于一个步骤，不得跳过、不得重叠。
2. 步骤边界信号：衔接词（下一步 / 接下来 / 然后 / 最后 / 起锅烧油）、动作动词（切、焯、腌、炒、炖、蒸、收汁）、状态达成。
3. 每个步骤的「达成状态」（done_when）必须写出来，例如「炖 10 分钟」「煮到变色」「用筷子能扎透」；没有明确状态就写 null。
4. 步骤标题（title）用 2-6 字的动宾短语，例如「切牛肉」「焯水去腥」。
5. 只抽取视频里实际出现的内容，禁止编造食材、用量或步骤。
6. start_sec / end_sec 必须来自字幕时间戳（单位：秒，1 位小数）。
7. 步骤的 index 从 1 开始递增。
8. 字幕里未出现的工具不要写进 tools。
9. 如果这段字幕**没有任何烹饪步骤信息**（例如全部是背景音乐歌词、纯闲聊、无任何烹饪动作），
   请输出：{"title": "", "steps": [], "ingredients": [], "tools": [], "tips": []}，
   不要编造任何步骤。

输出必须是合法 JSON 对象，结构如下（字段不可增减，没有的值用 null）：
{
  "title": "菜名",
  "difficulty": "简单 | 中等 | 困难",
  "servings": "份量或 null",
  "total_time": "总耗时或 null",
  "ingredients": [{"name": "食材名", "amount": "用量或 null", "note": "备注或 null"}],
  "tools": ["工具"],
  "steps": [
    {"index": 1, "title": "步骤标题", "description": "做了什么", "done_when": "达成状态或 null", "tip": "新手易错点或 null", "start_sec": 0.0, "end_sec": 0.0}
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
 "ingredients": [{"name": "牛腩肉", "amount": null, "note": "切稍大的块"}],
 "tools": ["锅"], "steps": [
   {"index": 1, "title": "切牛肉", "description": "牛腩肉切成稍大的块", "done_when": null, "tip": null, "start_sec": 0.5, "end_sec": 5.0},
   {"index": 2, "title": "焯水去腥", "description": "冷水下锅焯水", "done_when": "煮出浮沫", "tip": "冷水下锅", "start_sec": 5.0, "end_sec": 20.0},
   {"index": 3, "title": "炒糖色", "description": "加冰糖炒出糖色，下牛肉翻炒上色", "done_when": "牛肉均匀上色", "tip": null, "start_sec": 20.0, "end_sec": 60.0}
 ], "tips": []}
"""


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
