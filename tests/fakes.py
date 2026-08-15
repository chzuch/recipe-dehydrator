"""测试替身（Test Doubles）：LLM/Fetcher/FrameExtractor/CardStore 的 fake 实现。

原则：测试不得调用真实 API、不得依赖网络（CLAUDE.md §4）。
"""

from __future__ import annotations

from typing import Any

from app.domain.models import Recipe, SubtitleLine
from pydantic import BaseModel


class FakeVideoInfo(BaseModel):
    url: str
    title: str
    uploader: str | None = None
    duration_sec: float | None = None


class FakeLLMClient:
    """按调用顺序返回预置响应的 LLM fake（dict 为合法 JSON 对象，str 模拟不可解析输出）。"""

    provider_name = "fake"
    model = "fake-model"

    def __init__(self, responses: list[dict[str, Any] | str]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete_json(self, system: str, prompt: str) -> dict[str, Any] | str:
        self.calls.append((system, prompt))
        if not self._responses:
            msg = "FakeLLMClient 没有更多预置响应"
            raise AssertionError(msg)
        return self._responses.pop(0)


class FakeFetcher:
    """返回预置视频信息与字幕行的 fetcher fake。"""

    def __init__(self, video: FakeVideoInfo, lines: list[SubtitleLine], video_path: str | None = None) -> None:
        self._video = video
        self._lines = lines
        self._video_path = video_path
        self.urls: list[str] = []

    async def fetch(self, url: str, with_video: bool = False) -> tuple[FakeVideoInfo, list[SubtitleLine]]:
        self.urls.append(url)
        return self._video, list(self._lines)

    async def video_path(self) -> str | None:
        return self._video_path

    async def cleanup(self) -> None:
        self._video_path = None


class FakeFrameExtractor:
    """为每个时间点生成占位截图文件名，并记录调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[float], str]] = []

    async def extract(self, video_path: str, timestamps: list[float], out_dir: str) -> list[str]:
        self.calls.append((video_path, timestamps, out_dir))
        return [f"{video_path}-{t:.0f}.jpg" for t in timestamps]


class FakeCardStore:
    """内存版 CardStore，行为与 SQLite 实现对齐。"""

    def __init__(self) -> None:
        self._cards: dict[str, Recipe] = {}
        self._seq = 0

    async def save(self, recipe: Recipe) -> str:
        self._seq += 1
        card_id = f"fake-{self._seq}"
        self._cards[card_id] = recipe
        return card_id

    async def get(self, card_id: str) -> Recipe | None:
        return self._cards.get(card_id)

    async def list_all(self) -> list[tuple[str, Recipe]]:
        return list(self._cards.items())

    async def update(self, card_id: str, recipe: Recipe) -> None:
        if card_id not in self._cards:
            msg = f"card {card_id} 不存在"
            raise KeyError(msg)
        self._cards[card_id] = recipe

    async def delete(self, card_id: str) -> None:
        self._cards.pop(card_id, None)
