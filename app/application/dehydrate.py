"""用例：视频链接 → 菜谱卡（SCOPE §3 全链路编排）。

流程：抓取字幕(L1 已在 fetcher 内预处理) → 切分(L2) → 结构化 → 校验(L3，失败重试一次)
→ 抽帧(可选) → 持久化 → 清理临时视频。
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.application.prompts import (
    SYSTEM_SPLIT,
    build_retry_prompt,
    build_split_prompt,
)
from app.domain.exceptions import LLMError, SubtitleNotFoundError, ValidationFailedError
from app.domain.models import Recipe, SubtitleLine
from app.domain.ports import CardStore, Fetcher, FrameExtractor, LLMClient
from app.domain.rules import validate_recipe

logger = logging.getLogger(__name__)

MAX_LLM_ATTEMPTS = 2


class DehydrateUseCase:
    def __init__(
        self,
        fetcher: Fetcher,
        llm: LLMClient,
        frames: FrameExtractor,
        store: CardStore,
        frames_dir: str | Path,
        with_frames: bool = True,
    ) -> None:
        self._fetcher = fetcher
        self._llm = llm
        self._frames = frames
        self._store = store
        self._frames_dir = Path(frames_dir)
        self._with_frames = with_frames
        self._last_error_messages: list[str] = []

    async def run(self, url: str, with_frames: bool | None = None) -> tuple[str, Recipe]:
        """执行脱水，返回 (card_id, recipe)。with_frames=None 时用构造默认值。"""
        want_frames = self._with_frames if with_frames is None else with_frames
        video, lines = await self._fetcher.fetch(url, with_video=want_frames)
        if not lines:
            raise SubtitleNotFoundError("字幕预处理后为空，无法脱水")

        recipe = await self._split_with_retry(lines)
        recipe.source_url = url
        recipe.source_title = video.title
        recipe.uploader = video.uploader

        issues = validate_recipe(recipe, video.duration_sec)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            # 重试仍失败 → 阻断入库
            messages = [i.message for i in errors]
            raise ValidationFailedError("；".join(messages))

        recipe.warnings = [i.message for i in issues if i.severity == "warning"]

        if want_frames:
            await self._attach_frames(recipe)

        card_id = await self._store.save(recipe)
        await self._fetcher.cleanup()
        logger.info("dehydrated %s → card %s (%d 步骤)", url, card_id, len(recipe.steps))
        return card_id, recipe

    async def _split_with_retry(self, lines: list[SubtitleLine]) -> Recipe:
        """调用 LLM 切分；输出无法解析或校验失败时，携带问题重试一次。"""
        prompt = build_split_prompt(lines)
        last_json = ""
        for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
            try:
                if attempt == 1:
                    raw = await self._llm.complete_json(SYSTEM_SPLIT, prompt)
                else:
                    raw = await self._llm.complete_json(
                        SYSTEM_SPLIT,
                        build_retry_prompt(lines, last_json, self._last_error_messages),
                    )
                last_json = raw if isinstance(raw, str) else repr(raw)
                recipe = Recipe.model_validate(raw)
            except LLMError:
                # LLM 调用失败（网络/限流）不重试，直接冒泡 → api 层映射 502
                raise
            except (ValidationError, ValueError) as exc:
                # 输出不可解析：携带问题重试一次
                self._last_error_messages = [f"无法解析 LLM 输出: {exc}"]
                if attempt == MAX_LLM_ATTEMPTS:
                    raise ValidationFailedError("；".join(self._last_error_messages)) from exc
                continue

            issues = validate_recipe(recipe)
            errors = [i for i in issues if i.severity == "error"]
            if not errors:
                return recipe
            self._last_error_messages = [i.message for i in errors]
            if attempt == MAX_LLM_ATTEMPTS:
                raise ValidationFailedError("；".join(self._last_error_messages))

        msg = "切分失败（不应到达）"
        raise ValidationFailedError(msg)

    async def _attach_frames(self, recipe: Recipe) -> None:
        """为每个步骤在时间区间中点抽一帧；失败不阻断整张卡。"""
        video_path = await self._fetcher.video_path()
        if not video_path:
            return
        timestamps = [s.start_sec + (s.end_sec - s.start_sec) / 2 for s in recipe.steps]
        try:
            names = await self._frames.extract(video_path, timestamps, str(self._frames_dir))
        except (RuntimeError, OSError) as exc:
            logger.warning("抽帧失败，跳过（不影响卡片）: %s", exc)
            return
        for step, name in zip(recipe.steps, names, strict=True):
            step.frame_path = name
