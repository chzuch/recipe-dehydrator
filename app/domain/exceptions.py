"""领域异常：跨层传递业务失败信号，infrastructure/api 负责翻译。"""

from __future__ import annotations


class DehydratorError(Exception):
    """项目内所有业务异常的基类。"""


class VideoNotFoundError(DehydratorError):
    """视频无法获取（链接无效、区域限制、页面不存在）。"""


class SubtitleNotFoundError(DehydratorError):
    """视频没有可用字幕（当前不支持 ASR，见 SCOPE §5）。"""


class LLMError(DehydratorError):
    """LLM 调用失败（网络、限流、格式解析）。"""


class ValidationFailedError(DehydratorError):
    """LLM 输出未通过 L3 一致性校验，且无法自动修复。"""


class NoCookingContentError(DehydratorError):
    """字幕不含烹饪步骤信息（疑似全部为背景音乐歌词/无效内容），无法脱水。"""
