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
