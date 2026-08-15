"""BilibiliFetcher 单元测试：mock yt-dlp，不触网（CLAUDE.md §4）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.exceptions import VideoNotFoundError
from app.infrastructure.bilibili_fetcher import VIDEO_FORMAT, BilibiliFetcher


class _FakeYDL:
    """记录 opts 并返回假 info 的 YoutubeDL 替身。"""

    def __init__(self, opts: dict[str, object]) -> None:
        self.opts = opts
        self.info: dict[str, object] = {"id": "BV1xx", "title": "测试视频"}

    def __enter__(self) -> _FakeYDL:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict[str, object]:
        return self.info


def _patch_ydl(monkeypatch: pytest.MonkeyPatch, cls: type[_FakeYDL]) -> list[_FakeYDL]:
    """替换 yt_dlp.YoutubeDL，捕获每次创建的实例。"""
    instances: list[_FakeYDL] = []

    def factory(opts: dict[str, object]) -> _FakeYDL:
        inst = cls(opts)
        instances.append(inst)
        return inst

    monkeypatch.setattr("yt_dlp.YoutubeDL", factory)
    return instances


def _fetcher_with_tmp(tmp_path: Path) -> BilibiliFetcher:
    fetcher = BilibiliFetcher()
    fetcher._tmp_dir = tmp_path
    return fetcher


class TestExtractFormat:
    def test_with_video_uses_dash_combined_format(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = _fetcher_with_tmp(tmp_path)

        info = fetcher._extract("https://www.bilibili.com/video/BV1xx", with_video=True)

        assert info["title"] == "测试视频"
        assert instances[0].opts["format"] == VIDEO_FORMAT
        assert instances[0].opts["format_sort"] == ["res:480", "res:360"]
        assert instances[0].opts["merge_output_format"] == "mp4"
        assert instances[0].opts["skip_download"] is False

    def test_without_video_skips_download(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = _fetcher_with_tmp(tmp_path)

        fetcher._extract("https://www.bilibili.com/video/BV1xx", with_video=False)

        assert instances[0].opts["skip_download"] is True
        assert "format" not in instances[0].opts

    def test_cookiefile_attached_when_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = BilibiliFetcher(cookiefile="data/cookies.txt")
        fetcher._tmp_dir = tmp_path

        fetcher._extract("https://www.bilibili.com/video/BV1xx", with_video=True)

        assert instances[0].opts["cookiefile"] == "data/cookies.txt"

    def test_no_cookiefile_when_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = _fetcher_with_tmp(tmp_path)

        fetcher._extract("https://www.bilibili.com/video/BV1xx", with_video=True)

        assert "cookiefile" not in instances[0].opts

    async def test_download_error_translated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fetcher = _fetcher_with_tmp(tmp_path)

        def boom(url: str, with_video: bool) -> dict[str, object]:
            msg = "模拟 yt-dlp 失败"
            raise RuntimeError(msg)

        monkeypatch.setattr(fetcher, "_extract", boom)  # 异常翻译发生在 fetch 层

        with pytest.raises(VideoNotFoundError):
            await fetcher.fetch("https://www.bilibili.com/video/BV1xx")
