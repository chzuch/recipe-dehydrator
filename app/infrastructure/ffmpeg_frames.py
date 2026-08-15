"""视频抽帧：ffmpeg 实现 FrameExtractor 端口。

每个时间点抽一帧（-ss 精确到秒前 seek + -frames:v 1），输出 JPG。
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class FFmpegFrameExtractor:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg_path

    async def extract(self, video_path: str, timestamps: list[float], out_dir: str) -> list[str]:
        out = Path(out_dir)
        await asyncio.to_thread(out.mkdir, parents=True, exist_ok=True)
        names: list[str] = []
        for ts in timestamps:
            name = f"frame_{ts:07.1f}.jpg"
            await asyncio.to_thread(self._extract_one, video_path, ts, out / name)
            names.append(name)
        return names

    async def extract_gif(self, video_path: str, start_sec: float, duration_sec: float, out_dir: str) -> str:
        """截取片段生成循环 GIF（480p、10fps，调色板两步法保证质量）。"""
        out = Path(out_dir)
        await asyncio.to_thread(out.mkdir, parents=True, exist_ok=True)
        name = f"clip_{start_sec:07.1f}.gif"
        dest = out / name
        palette = out / f"palette_{start_sec:07.1f}.png"
        try:
            await asyncio.to_thread(self._gif_palette, video_path, start_sec, duration_sec, palette)
            await asyncio.to_thread(self._gif_render, video_path, start_sec, duration_sec, palette, dest)
        finally:
            palette.unlink(missing_ok=True)
        if not dest.exists():
            msg = f"ffmpeg 未生成 GIF at {start_sec:.1f}s"
            raise RuntimeError(msg)
        return name

    def _gif_palette(self, video_path: str, start: float, dur: float, palette: Path) -> None:
        cmd = [
            self._ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.2f}", "-i", video_path,
            "-vf", "fps=10,scale=480:-1:flags=lanczos,palettegen",
            str(palette),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            msg = f"ffmpeg 调色板生成失败 at {start:.1f}s: {proc.stderr.strip()[:200]}"
            raise RuntimeError(msg)

    def _gif_render(self, video_path: str, start: float, dur: float, palette: Path, dest: Path) -> None:
        cmd = [
            self._ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.2f}", "-i", video_path,
            "-i", str(palette),
            "-lavfi", "fps=10,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse",
            str(dest),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            msg = f"ffmpeg GIF 生成失败 at {start:.1f}s: {proc.stderr.strip()[:200]}"
            raise RuntimeError(msg)

    def _extract_one(self, video_path: str, ts: float, dest: Path) -> None:
        cmd = [
            self._ffmpeg,
            "-y",
            "-ss",
            f"{ts:.3f}",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.warning("ffmpeg 抽帧失败 at %s: %s", ts, proc.stderr.strip()[:300])
        if not dest.exists():
            msg = f"ffmpeg 未生成截图 at {ts:.1f}s: {proc.stderr.strip()[:200]}"
            raise RuntimeError(msg)
