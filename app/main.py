"""uvicorn 入口：`uvicorn app.main:app --reload`。

正式运行需要项目根存在 .env（含 LLM API key），否则启动即失败（fail fast，CLAUDE.md §3）。
"""

from app.factory import create_app

app = create_app()
