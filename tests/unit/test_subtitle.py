"""app.infrastructure.subtitle 单元测试（纯函数，无网络依赖）。"""

from __future__ import annotations

import pytest
from app.domain.models import SubtitleLine
from app.infrastructure.subtitle import (
    parse_bilibili_json,
    parse_srt,
    parse_subtitle,
    parse_vtt,
    preprocess_lines,
)


class TestParseBilibiliJson:
    def test_body_structure(self) -> None:
        raw = '{"body": [{"from": 1.0, "to": 3.0, "content": "今天做红烧肉"}, {"from": 3.0, "to": 5.0, "content": "先切肉"}]}'
        lines = parse_bilibili_json(raw)
        assert len(lines) == 2
        assert lines[0].start == 1.0
        assert lines[0].text == "今天做红烧肉"

    def test_events_structure(self) -> None:
        raw = '{"events": [{"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "切"}, {"utf8": "肉"}]}]}'
        lines = parse_bilibili_json(raw)
        assert len(lines) == 1
        assert lines[0].text == "切肉"
        assert lines[0].start == pytest.approx(1.0)
        assert lines[0].end == pytest.approx(3.0)

    def test_invalid_structure_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_bilibili_json('{"foo": 1}')

    def test_empty_content_skipped(self) -> None:
        raw = '{"body": [{"from": 1.0, "to": 2.0, "content": "  "}]}'
        assert parse_bilibili_json(raw) == []


class TestParseVttSrt:
    def test_vtt(self) -> None:
        raw = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n今天做红烧肉\n\n00:00:03.500 --> 00:00:05.000\n先切肉\n"
        lines = parse_vtt(raw)
        assert len(lines) == 2
        assert lines[0].start == pytest.approx(1.0)
        assert lines[1].text == "先切肉"

    def test_srt(self) -> None:
        raw = "1\n00:00:01,000 --> 00:00:03,000\n今天做红烧肉\n\n2\n00:00:03,500 --> 00:00:05,000\n先切肉\n"
        lines = parse_srt(raw)
        assert len(lines) == 2
        assert lines[1].end == pytest.approx(5.0)

    def test_parse_subtitle_dispatch(self) -> None:
        raw = '{"body": [{"from": 0, "to": 1, "content": "x"}]}'
        assert parse_subtitle(raw, "json")[0].text == "x"
        with pytest.raises(ValueError):
            parse_subtitle(raw, "txt")


class TestPreprocessLines:
    def test_flaffy_lines_filtered(self) -> None:
        lines = [
            SubtitleLine(start=0, end=2, text="今天给大家分享一道菜"),
            SubtitleLine(start=2, end=4, text="记得点赞投币收藏"),
            SubtitleLine(start=4, end=6, text="切牛腩肉"),
        ]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["切牛腩肉"]

    def test_merge_split_sentences(self) -> None:
        lines = [
            SubtitleLine(start=0, end=1, text="把牛肉切"),
            SubtitleLine(start=1.2, end=2, text="成稍大的块"),
        ]
        out = preprocess_lines(lines)
        assert len(out) == 1
        assert out[0].text == "把牛肉切成稍大的块"
        assert out[0].start == 0
        assert out[0].end == 2

    def test_no_merge_across_sentence_end(self) -> None:
        lines = [
            SubtitleLine(start=0, end=1, text="把牛肉切好。"),
            SubtitleLine(start=2, end=3, text="起锅烧油"),
        ]
        out = preprocess_lines(lines)
        assert len(out) == 2

    def test_dedup_repeated_lines(self) -> None:
        lines = [
            SubtitleLine(start=0, end=2, text="注意别糊了"),
            SubtitleLine(start=2, end=4, text="注意别糊了"),
            SubtitleLine(start=4, end=6, text="出锅"),
        ]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["注意别糊了", "出锅"]

    def test_single_char_noise_filtered(self) -> None:
        lines = [SubtitleLine(start=0, end=1, text="嗯"), SubtitleLine(start=1, end=2, text="好")]
        assert preprocess_lines(lines) == []

    def test_bgm_lyric_lines_filtered(self) -> None:
        """B站 AI 字幕用 ♪ 标记背景音乐歌词，必须过滤（真实事故回归）。"""
        lines = [
            SubtitleLine(start=0, end=4, text="♪我循声而去♪"),
            SubtitleLine(start=4, end=7, text="♪叶黄退入长何桥♪"),
            SubtitleLine(start=7, end=10, text="切好的鸡肉下锅"),
        ]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["切好的鸡肉下锅"]

    def test_music_note_variants_filtered(self) -> None:
        lines = [
            SubtitleLine(start=0, end=2, text="♫ 副歌部分 ♬"),
            SubtitleLine(start=2, end=4, text="加生抽翻炒"),
        ]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["加生抽翻炒"]

    def test_unsorted_input_sorted(self) -> None:
        lines = [
            SubtitleLine(start=10, end=12, text="后发生的"),
            SubtitleLine(start=0, end=2, text="先发生的"),
        ]
        out = preprocess_lines(lines)
        assert out[0].text == "先发生的"

    def test_long_sentence_not_merged(self) -> None:
        """AI 字幕无标点：长句不得合并，否则时间分辨率被吞（真实事故回归）。"""
        lines = [
            SubtitleLine(start=0, end=2, text="整只鸡或者半只鸡都可以"),
            SubtitleLine(start=2, end=4, text="大小按自己喜好来就行"),
        ]
        out = preprocess_lines(lines)
        assert len(out) == 2
        assert out[0].text == "整只鸡或者半只鸡都可以"
        assert out[1].start == 2.0

    def test_filler_word_substring_not_filtered(self) -> None:
        """「啊」等语气词只能整句过滤，不能子串匹配（「好香啊」会被误伤）。"""
        lines = [SubtitleLine(start=0, end=2, text="好香啊，出锅了")]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["好香啊，出锅了"]

    def test_filler_whole_line_filtered(self) -> None:
        lines = [SubtitleLine(start=0, end=2, text="好的"), SubtitleLine(start=2, end=4, text="下锅")]
        out = preprocess_lines(lines)
        assert [line.text for line in out] == ["下锅"]

    def test_short_fragment_merged_but_long_sentence_stops(self) -> None:
        """短残片合并后形成长句，后续不再吞并后面的长句。"""
        lines = [
            SubtitleLine(start=0, end=1, text="买两根"),
            SubtitleLine(start=1, end=2, text="大鸡腿"),
            SubtitleLine(start=2, end=4, text="买的时候可以让老板帮你剁一下"),
        ]
        out = preprocess_lines(lines)
        assert len(out) == 2
        assert out[0].text == "买两根大鸡腿"
        assert out[1].text == "买的时候可以让老板帮你剁一下"
