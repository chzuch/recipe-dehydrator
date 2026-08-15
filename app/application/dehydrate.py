"""用例：视频链接 → 菜谱卡（SCOPE §3 全链路编排）。

流程：抓取字幕(L1 已在 fetcher 内预处理) → 切分(L2) → 结构化 → 校验(L3，失败重试一次)
→ 抽帧(可选) → 持久化 → 清理临时视频。
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.application.prompts import (
    PRECHECK_SYSTEM,
    SYSTEM_SPLIT,
    build_precheck_prompt,
    build_retry_prompt,
    build_split_prompt,
)
from app.domain.exceptions import (
    LLMError,
    MultiDishError,
    NoCookingContentError,
    SubtitleNotFoundError,
    ValidationFailedError,
)
from app.domain.models import Recipe, SubtitleLine
from app.domain.ports import CardStore, Fetcher, FrameExtractor, LLMClient
from app.domain.rules import (
    GIF_DURATION_SEC,
    merge_duplicate_ingredients,
    pick_frame_time,
    select_gif_steps,
    validate_recipe,
)

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
        with_gif: bool = False,
    ) -> None:
        self._fetcher = fetcher
        self._llm = llm
        self._frames = frames
        self._store = store
        self._frames_dir = Path(frames_dir)
        self._with_frames = with_frames
        self._with_gif = with_gif
        self._last_error_messages: list[str] = []

    async def run(
        self,
        url: str,
        with_frames: bool | None = None,
        with_gif: bool | None = None,
    ) -> tuple[str, Recipe]:
        """执行脱水，返回 (card_id, recipe)。开关为 None 时用构造默认值。"""
        want_frames = self._with_frames if with_frames is None else with_frames
        want_gif = self._with_gif if with_gif is None else with_gif
        # GIF 也需要视频文件：开 GIF 隐含下载视频
        video, lines = await self._fetcher.fetch(url, with_video=want_frames or want_gif)
        if not lines:
            raise SubtitleNotFoundError("字幕预处理后为空，无法脱水")

        await self._precheck(video.title, lines)

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

        if want_frames or want_gif:
            await self._attach_frames(recipe, lines, want_frames=want_frames, want_gif=want_gif)

        card_id = await self._store.save(recipe)
        await self._fetcher.cleanup()
        logger.info("dehydrated %s → card %s (%d 步骤)", url, card_id, len(recipe.steps))
        return card_id, recipe

    async def _precheck(self, title: str, lines: list[SubtitleLine]) -> None:
        """预检：非烹饪内容 / 多菜合集直接拒绝（token 极少的一次性判断）。"""
        raw = await self._llm.complete_json(PRECHECK_SYSTEM, build_precheck_prompt(title, lines))
        if not isinstance(raw, dict):
            return  # 预检输出异常不阻断，交给切分阶段兜底
        if raw.get("is_cooking") is False:
            raise NoCookingContentError("该视频不是烹饪教学（可能是吃播/探店/纯音乐），无法脱水")
        dish_count = raw.get("dish_count") or 1
        if isinstance(dish_count, int) and dish_count > 1:
            dishes = [str(d) for d in (raw.get("dishes") or [])][:6]
            detail = "、".join(dishes) if dishes else "多道菜"
            raise MultiDishError(
                f"该视频包含 {dish_count} 道菜（{detail}）。当前只支持单菜视频，请提供只教一道菜的视频"
            )

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
                if isinstance(raw, dict) and not raw.get("steps"):
                    # LLM 判定字幕无烹饪内容（如全是 BGM 歌词），不重试
                    raise NoCookingContentError(
                        "该视频字幕疑似为背景音乐歌词或无效内容，没有可提取的烹饪步骤"
                    )
                recipe = Recipe.model_validate(raw)
                # 归一化：合并 LLM 拆散的同名食材（花生油×3 → 1 条），
                # 在 L3 校验前做，让食材闭环检查基于合并后的清单
                recipe.ingredients = merge_duplicate_ingredients(recipe.ingredients)
            except LLMError:
                # LLM 调用失败（网络/限流）不重试，直接冒泡 → api 层映射 502
                raise
            except NoCookingContentError:
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

    async def _attach_frames(
        self, recipe: Recipe, lines: list[SubtitleLine], want_frames: bool, want_gif: bool
    ) -> None:
        """步骤配图：静态图关键句对齐抽帧 + GIF（可选）；失败不阻断整张卡。"""
        video_path = await self._fetcher.video_path()
        if not video_path:
            return
        if want_frames:
            timestamps = [pick_frame_time(s, lines) for s in recipe.steps]
            try:
                names = await self._frames.extract(video_path, timestamps, str(self._frames_dir))
            except (RuntimeError, OSError) as exc:
                logger.warning("抽帧失败，跳过（不影响卡片）: %s", exc)
                names = []
            for step, name in zip(recipe.steps, names, strict=False):
                step.frame_path = name

        if want_gif:
            # 每步都生成；步骤过多时只选中间阶段（首尾备料/装盘手法信息少）
            for step in select_gif_steps(recipe.steps):
                duration = min(GIF_DURATION_SEC, max(0.5, step.end_sec - step.start_sec))
                start = max(step.start_sec, pick_frame_time(step, lines) - 0.5)
                try:
                    step.gif_path = await self._frames.extract_gif(
                        video_path, start, duration, str(self._frames_dir)
                    )
                except (RuntimeError, OSError) as exc:
                    logger.warning("步骤%d GIF 生成失败，跳过: %s", step.index, exc)
