"""应用配置（pydantic-settings）：唯一配置入口，读取 .env。

新增配置项必须同步更新 .env.example（CLAUDE.md §3）。
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 默认 provider: deepseek | qwen | kimi
    llm_provider: str = "deepseek"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Qwen (DashScope 兼容模式)
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # Kimi (Moonshot)
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"

    # 数据目录（相对项目根）
    data_dir: Path = Path("data")
    frames_dir: Path = Path("data/frames")
    samples_dir: Path = Path("data/samples")
    db_path: Path = Path("data/cards.db")

    # 是否默认给步骤抽帧
    with_frames: bool = True
