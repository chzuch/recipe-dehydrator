"""B站视频抓取：yt-dlp 实现 Fetcher 端口。

职责：提取视频信息、下载并解析字幕（优先官方字幕，AI 字幕兜底）、
按需下载 360p 低清视频供抽帧。视频文件为临时产物，抽帧后由 cleanup 删除。
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.domain.exceptions import SubtitleNotFoundError, VideoNotFoundError
from app.domain.models import SubtitleLine
from app.infrastructure.subtitle import PREFERRED_LANGS, parse_subtitle, preprocess_lines

logger = logging.getLogger(__name__)

_SUBTITLE_EXTS = (".json3", ".json", ".vtt", ".srt")
_TMP_PREFIX = "vdh-fetch-"
# B站是 DASH 音视频分离：单格式选择器（best 等）必然失败，必须用 bv*+ba 组合语法。
# 不限制分辨率上限（部分视频没有 360p/480p），用 format_sort 偏好低分辨率控制体积。
VIDEO_FORMAT = "bv*+ba/b"
VIDEO_FORMAT_SORT = ["res:480", "res:360"]


class VideoInfoImpl(BaseModel):
    url: str
    title: str
    uploader: str | None = None
    duration_sec: float | None = None


class BilibiliFetcher:
    def __init__(self, cookiefile: str | None = None) -> None:
        self._cookiefile = cookiefile
        self._tmp_dir: Path | None = None
        self._video_file: Path | None = None
        self._subtitles: list[SubtitleLine] = []

    async def fetch(self, url: str, with_video: bool = False) -> tuple[VideoInfoImpl, list[SubtitleLine]]:
        await self.cleanup()
        self._tmp_dir = Path(tempfile.mkdtemp(prefix=_TMP_PREFIX))
        try:
            info = await asyncio.to_thread(self._extract, url, with_video)
        except Exception as exc:  # yt-dlp 的异常体系杂，统一翻译
            raise VideoNotFoundError(f"视频抓取失败: {exc}") from exc

        subtitle_file = self._find_subtitle_file(info["id"])
        if subtitle_file is None:
            raise SubtitleNotFoundError(
                "该视频没有可用字幕（官方/AI 字幕都没有）。"
                "当前版本不支持语音识别（SCOPE §5 边界）。"
                "请换一个视频：B站播放页右下角「字幕」按钮可见即可用"
            )
        raw = subtitle_file.read_text(encoding="utf-8")
        lines = parse_subtitle(raw, subtitle_file.suffix.lstrip("."))
        self._subtitles = preprocess_lines(lines)
        logger.info(
            "fetched %s: %d 字幕行（预处理后）",
            info["title"],
            len(self._subtitles),
        )

        video = VideoInfoImpl(
            url=url,
            title=str(info.get("title", "")),
            uploader=info.get("uploader"),
            duration_sec=float(info["duration"]) if info.get("duration") else None,
        )
        return video, list(self._subtitles)

    def _extract(self, url: str, with_video: bool) -> dict[str, Any]:
        from yt_dlp import YoutubeDL  # 延迟导入，避免 CLI 无 yt-dlp 时 import 失败

        assert self._tmp_dir is not None
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": not with_video,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(PREFERRED_LANGS),
            "subtitlesformat": "json3/best",
            "outtmpl": str(self._tmp_dir / "%(id)s"),
        }
        if with_video:
            opts["format"] = VIDEO_FORMAT
            opts["format_sort"] = VIDEO_FORMAT_SORT
            opts["merge_output_format"] = "mp4"
        if self._cookiefile:
            # B站字幕（含 AI 字幕）需登录 cookie 才返回（已实测确认）
            opts["cookiefile"] = self._cookiefile
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                msg = "yt-dlp 未返回视频信息"
                raise VideoNotFoundError(msg)
            return info

    def _find_subtitle_file(self, video_id: str) -> Path | None:
        if self._tmp_dir is None:
            return None
        for ext in _SUBTITLE_EXTS:
            hits = sorted(self._tmp_dir.glob(f"{video_id}.*{ext}"))
            for lang in PREFERRED_LANGS:
                for hit in hits:
                    if f".{lang}." in hit.name or hit.name.endswith(f".{lang}{ext}"):
                        return hit
            if hits:
                return hits[0]
        return None

    async def video_path(self) -> str | None:
        if self._tmp_dir is None:
            return None
        if self._video_file is None:
            hits = [p for p in self._tmp_dir.iterdir() if p.suffix.lower() in {".mp4", ".flv", ".webm", ".mkv"}]
            self._video_file = hits[0] if hits else None
        return str(self._video_file) if self._video_file else None

    async def cleanup(self) -> None:
        if self._tmp_dir is not None:
            await asyncio.to_thread(shutil.rmtree, self._tmp_dir, ignore_errors=True)
        self._tmp_dir = None
        self._video_file = None
        self._subtitles = []
