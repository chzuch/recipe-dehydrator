"""端口抽象（Ports）：domain 只依赖这些接口，具体实现都在 infrastructure。

依赖方向：application 依赖本模块，infrastructure 实现本模块。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models import Recipe, SubtitleLine


class VideoInfo(Protocol):
    url: str
    title: str
    uploader: str | None
    duration_sec: float | None


class Fetcher(Protocol):
    """抓取视频元数据与字幕（yt-dlp 实现）。"""

    async def fetch(self, url: str, with_video: bool = False) -> tuple[VideoInfo, list[SubtitleLine]]:
        """返回 (视频信息, 预处理后字幕行)。with_video=True 时额外下载低清视频用于抽帧。"""

    async def video_path(self) -> str | None:
        """最近一次 fetch 下载的视频本地路径（供抽帧使用），未下载返回 None。"""

    async def cleanup(self) -> None:
        """清理临时下载产物（视频文件等），抽帧完成后由用例调用。"""


class LLMClient(Protocol):
    """LLM 结构化输出客户端（DeepSeek/Qwen/Kimi 实现）。"""

    provider_name: str
    model: str

    async def complete_json(self, system: str, prompt: str) -> dict[str, Any] | str:
        """调用 LLM 并要求返回 JSON 对象（也可能是不可解析文本）；失败抛 LLMError。"""


class FrameExtractor(Protocol):
    """从视频抽帧（ffmpeg 实现）。"""

    async def extract(self, video_path: str, timestamps: list[float], out_dir: str) -> list[str]:
        """在给定时间点各抽一帧，返回截图文件名列表（与 timestamps 顺序一致）。"""


class CardStore(Protocol):
    """菜谱卡持久化（SQLite 实现）。"""

    async def save(self, recipe: Recipe) -> str: ...
    async def get(self, card_id: str) -> Recipe | None: ...
    async def list_all(self) -> list[tuple[str, Recipe]]: ...
    async def update(self, card_id: str, recipe: Recipe) -> None: ...
    async def delete(self, card_id: str) -> None: ...
