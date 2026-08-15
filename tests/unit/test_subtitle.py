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

    def test_unsorted_input_sorted(self) -> None:
        lines = [
            SubtitleLine(start=10, end=12, text="后发生的"),
            SubtitleLine(start=0, end=2, text="先发生的"),
        ]
        out = preprocess_lines(lines)
        assert out[0].text == "先发生的"
