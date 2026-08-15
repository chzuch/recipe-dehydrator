"""字幕解析与 L1 预处理（SCOPE §4）：格式解析 + 断句合并 + 闲话过滤 + 去重。

所有函数为纯函数，不依赖网络与文件系统，便于单测。
"""

from __future__ import annotations

import json
import re

from app.domain.models import SubtitleLine

# B站字幕常见语言（优先级从高到低）
PREFERRED_LANGS: tuple[str, ...] = (
    "zh-Hans",
    "zh-CN",
    "zh",
    "zh-Hans-CN",
    "ai-zh",
    "ai-zh-CN",
    "ai-zh-Hans",
)

# 闲话信号：寒暄开场 / 求三连 / 广告口播（子串匹配；语气词不在此列，见 _FILLER_LINES）
_FLAFFY_RE = re.compile(
    r"(点赞|投币|收藏|三连|一键三连|关注|订阅|记得.{0,6}(关注|点赞|投币|三连)"
    r"|本期视频|这期视频|下期视频|视频里|视频中|欢迎大家|给大家|分享一道|大厨"
    r"|喜欢.{0,6}(视频|记得)|每天更新|感谢.{0,8}观看|我们下次|再见|拜拜)",
)
# 整句就是语气词的才过滤；禁止子串匹配（「好香啊」会被「啊」误伤）
_FILLER_LINES = {"嗯", "呃", "啊", "哦", "好的", "那好", "对", "嗯嗯", "对对", "好嘞", "对啦"}
# B站 AI 字幕用音符符号标记背景音乐（BGM）歌词行，必须过滤
_BGM_RE = re.compile(r"[♪♫♬]")
_ENDING_RE = re.compile(r"[。！？!?…]$")
_MERGE_GAP_SEC = 0.5  # 相邻字幕 gap 小于此值视为断句，可合并
_MERGE_MAX_PREV_LEN = 10  # 前句短于此字数才允许合并：AI 字幕无标点，长句合并会吞掉时间分辨率
_STRIP_RE = re.compile(r"[\s\u3000]+")


def parse_subtitle(raw: str, fmt: str) -> list[SubtitleLine]:
    """按格式解析字幕文本为 SubtitleLine 列表。fmt: json | json3 | vtt | srt。"""
    if fmt in {"json", "json3"}:
        return parse_bilibili_json(raw)
    if fmt == "vtt":
        return parse_vtt(raw)
    if fmt == "srt":
        return parse_srt(raw)
    msg = f"不支持的字幕格式: {fmt}"
    raise ValueError(msg)


def parse_bilibili_json(raw: str) -> list[SubtitleLine]:
    """B站 JSON 字幕（含 json3 的 events 结构）。"""
    data = json.loads(raw)
    lines: list[SubtitleLine] = []

    if isinstance(data, dict) and isinstance(data.get("body"), list):
        for item in data["body"]:
            start = float(item.get("from", 0))
            end = float(item.get("to", start))
            content = str(item.get("content", "")).strip()
            if content:
                lines.append(SubtitleLine(start=start, end=end, text=content))
        return lines

    if isinstance(data, dict) and isinstance(data.get("events"), list):
        for ev in data["events"]:
            t_start = float(ev.get("tStartMs", 0)) / 1000.0
            duration = float(ev.get("dDurationMs", 0)) / 1000.0
            segs = ev.get("segs") or []
            content = "".join(s.get("utf8", "") for s in segs if isinstance(s, dict)).strip()
            if content:
                lines.append(SubtitleLine(start=t_start, end=t_start + duration, text=content))
        return lines

    msg = "无法识别的字幕 JSON 结构"
    raise ValueError(msg)


def _parse_timestamp(ts: str) -> float:
    parts = [float(p) for p in ts.replace(",", ".").split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def parse_vtt(raw: str) -> list[SubtitleLine]:
    lines: list[SubtitleLine] = []
    blocks = re.split(r"\n\s*\n", raw)
    for block in blocks:
        m = re.search(r"(\d{1,2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{1,2}:\d{2}:\d{2}\.\d{3})", block)
        if not m:
            continue
        text = _STRIP_RE.sub("", "\n".join(block.splitlines()[1:])).strip()
        if text:
            lines.append(SubtitleLine(start=_parse_timestamp(m.group(1)), end=_parse_timestamp(m.group(2)), text=text))
    return lines


def parse_srt(raw: str) -> list[SubtitleLine]:
    lines: list[SubtitleLine] = []
    for block in re.split(r"\n\s*\n", raw):
        lines_in_block = block.splitlines()
        if len(lines_in_block) < 2:
            continue
        m = re.search(r"(\d{1,2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{1,2}:\d{2}:\d{2},\d{3})", lines_in_block[1])
        if not m:
            continue
        text = _STRIP_RE.sub("", "\n".join(lines_in_block[2:])).strip()
        if text:
            lines.append(SubtitleLine(start=_parse_timestamp(m.group(1)), end=_parse_timestamp(m.group(2)), text=text))
    return lines


def _is_flaffy(text: str) -> bool:
    return bool(_FLAFFY_RE.search(text)) or len(text) <= 1 or text in _FILLER_LINES


def _is_bgm(text: str) -> bool:
    return bool(_BGM_RE.search(text))


def preprocess_lines(lines: list[SubtitleLine]) -> list[SubtitleLine]:
    """L1 预处理：按时间顺序 过滤闲话 → 去重 → 合并断句。"""
    ordered = sorted(lines, key=lambda line: (line.start, line.end))
    filtered = [line for line in ordered if not _is_flaffy(line.text) and not _is_bgm(line.text)]

    # 去重：连续重复（UP主强调）只保留第一条，必须在合并之前做
    deduped: list[SubtitleLine] = []
    for line in filtered:
        if not deduped or deduped[-1].text != line.text:
            deduped.append(line)

    merged: list[SubtitleLine] = []
    for line in deduped:
        if not merged:
            merged.append(line)
            continue
        prev = merged[-1]
        gap = line.start - prev.end
        # 只合并「短残片」（前后两句都短）：AI 字幕无标点，长句合并会吞掉时间分辨率
        if (
            gap <= _MERGE_GAP_SEC
            and not _ENDING_RE.search(prev.text)
            and len(prev.text) < _MERGE_MAX_PREV_LEN
            and len(line.text) < _MERGE_MAX_PREV_LEN
        ):
            merged[-1] = SubtitleLine(
                start=prev.start,
                end=line.end,
                text=prev.text + line.text,
            )
        else:
            merged.append(line)
    return merged
