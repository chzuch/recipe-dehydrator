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


class TestExtractInfo:
    def test_skips_download_and_requests_subtitles(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = _fetcher_with_tmp(tmp_path)

        info = fetcher._extract_info("https://www.bilibili.com/video/BV1xx")

        assert info["title"] == "测试视频"
        assert instances[0].opts["skip_download"] is True
        assert instances[0].opts["writeautomaticsub"] is True
        assert "cookiefile" not in instances[0].opts  # 未配置 cookie 时不附加


class TestDownloadVideo:
    def test_uses_dash_combined_format(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = _fetcher_with_tmp(tmp_path)

        fetcher._download_video("https://www.bilibili.com/video/BV1xx")

        assert instances[0].opts["format"] == VIDEO_FORMAT
        assert instances[0].opts["format_sort"] == ["res:480", "res:360"]
        assert instances[0].opts["merge_output_format"] == "mp4"
        assert instances[0].opts["skip_download"] is False

    def test_cookiefile_attached_when_configured(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        instances = _patch_ydl(monkeypatch, _FakeYDL)
        fetcher = BilibiliFetcher(cookiefile="data/cookies.txt")
        fetcher._tmp_dir = tmp_path

        fetcher._download_video("https://www.bilibili.com/video/BV1xx")

        assert instances[0].opts["cookiefile"] == "data/cookies.txt"


class TestFetch:
    async def test_info_failure_translated_to_video_not_found(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fetcher = _fetcher_with_tmp(tmp_path)

        def boom(url: str) -> dict[str, object]:
            msg = "模拟 yt-dlp 失败"
            raise RuntimeError(msg)

        monkeypatch.setattr(fetcher, "_extract_info", boom)

        with pytest.raises(VideoNotFoundError):
            await fetcher.fetch("https://www.bilibili.com/video/BV1xx")

    async def test_video_download_failure_degrades_gracefully(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """视频下载失败 → 仍返回字幕（降级为无截图），不阻断脱水（真实事故回归）。"""
        fetcher = _fetcher_with_tmp(tmp_path)
        (tmp_path / "BV1xx.zh-Hans.srt").write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n切鸡肉\n", encoding="utf-8"
        )

        async def noop_cleanup() -> None:
            return None

        def fake_info(url: str) -> dict[str, object]:
            return {"id": "BV1xx", "title": "测试视频", "uploader": None, "duration": 10.0}

        def boom(url: str) -> None:
            msg = "模拟视频下载失败"
            raise RuntimeError(msg)

        monkeypatch.setattr(fetcher, "cleanup", noop_cleanup)  # 避免 fetch 删除预置字幕
        monkeypatch.setattr("tempfile.mkdtemp", lambda prefix="": str(tmp_path))
        monkeypatch.setattr(fetcher, "_extract_info", fake_info)
        monkeypatch.setattr(fetcher, "_download_video", boom)

        video, lines = await fetcher.fetch("https://www.bilibili.com/video/BV1xx", with_video=True)

        assert video.title == "测试视频"
        assert len(lines) == 1
        assert lines[0].text == "切鸡肉"
