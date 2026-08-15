# CLAUDE.md — 项目开发规范与 Agent 约束

> 本文件是**硬性约束**，对开发者（含 AI 编码 agent）同等生效。
> 两个事实来源的分工：**SCOPE.md** 管"做什么"（范围、验收、边界）；**本文件**管"怎么改代码"（规范、纪律、流程）。
> 冲突时：范围问题听 SCOPE.md，变更纪律问题听本文件；涉及取舍分歧，先问人，不自行拍板。

## 0. 项目身份

- 项目：视频脱水机 v0.1（B站视频 → 图文菜谱卡）
- 语言：Python 3.14；包管理：uv
- 架构：分层架构（api → application → domain ← infrastructure），详见 SCOPE.md §9
- 测试框架：pytest；质量工具：ruff（lint+format）、mypy（type check）

---

## 1. 通用纪律（任何修改都适用）

1. **先读再改**：动任何文件前，先读 SCOPE.md、CLAUDE.md、目标模块及其全部调用方，理解设计意图
2. **遵循既有模式**：新代码沿用项目里已有的范式（分层、端口抽象、异常分层、测试风格）。引入新范式必须先说明理由并获得确认
3. **最小改动**：只改解决当前问题必需的代码；不做顺手重构、不美化无关代码
4. **禁止破坏性操作**：不改公共接口签名/语义；改数据库 schema 必须走迁移并单独说明
5. **禁止冗余逻辑**：新功能优先复用现有模块与函数；发现重复代码 → 先抽公共实现再复用，禁止复制粘贴
6. **不确定就问**：涉及范围、接口设计、行为取舍的分歧，提问而非猜测
7. **改动必须带测试**：无测试的改动不算完成（见 §4）

---

## 2. Python 编码规范

- **风格**：PEP 8；ruff 默认规则集（E/F/W/I/UP/B 等），零告警才可提交
- **命名**：类 `PascalCase`；函数/变量 `snake_case`；常量 `UPPER_SNAKE_CASE`；私有成员 `_` 前缀；模块名短小名词
- **类型注解**：所有函数签名必须注解（含返回值）；模块首行 `from __future__ import annotations`；mypy 严格模式无错误
- **禁止**：`print()`（一律用 logging）；裸 `except:` / `except Exception` 吞异常；`*` 通配导入；可变对象作默认参数；手写字符串拼接（用 f-string）
- **数据模型**：用 Pydantic v2（字段校验 + 序列化），不用裸 dataclass 充当领域模型
- **import 顺序**：stdlib → 第三方 → 本地（由 ruff/isort 强制）
- **函数职责**：单一职责，短小；超过 ~50 行考虑拆分

---

## 3. 依赖与配置

- 依赖只用 **uv** 管理（`uv add` / `uv remove`），锁定版本提交
- 新增任何依赖必须说明理由（写在 commit message 里）；能用标准库/pydantic 解决的不要引框架
- 配置统一走 `app/config.py`（pydantic-settings）；**密钥只存 `.env`，绝不入代码、日志、commit**
- 新增配置项必须同步更新 `.env.example`

---

## 4. 测试规范

- 框架 pytest；测试放 `tests/`，目录结构镜像 `app/`
- 命名：`test_<被测对象>_<行为>`；**一个用例只验证一件事**，断言显式（`pytest.raises` / `assert`），禁止无断言测试
- **LLM 一律用 fake**（`tests/fakes.py` 的 `FakeLLMClient`）：单元/集成测试不得调用真实 API，不得依赖网络
- 新功能必须带测试；修 bug 先写**能复现该 bug 的失败测试**（红）再修复（绿），防止回归
- 交付前必须：全量 `pytest` 通过 + `ruff check` 零告警 + `mypy` 零错误
- 测试代码也是代码：同样遵守命名、lint、类型规范

---

## 5. 错误处理与日志

- **错误分层**：
  - domain：定义业务异常（如 `SubtitleNotFound`、`ValidationFailed`）
  - infrastructure：把外部错误（yt-dlp/ffmpeg/LLM/网络）翻译成领域异常
  - api：统一把领域异常映射为 HTTP 错误（FastAPI exception handler）
- 不允许静默吞异常；预期情况显式 raise，非预期情况向上冒泡
- 日志用 `logging`，按级别分级：LLM 调用记录 model/token/耗时（debug）；外部失败（warning）；流程关键节点（info）
- 用户可见错误必须可理解（中文、指出怎么修），不抛裸堆栈

---

## 6. 变更流程（新增功能 / 修 bug）

1. 先写/更新测试（红）
2. 最小实现使测试变绿
3. （可选）重构，保持全绿
4. 检查重复：引入新逻辑时确认无既有实现可复用；有重复则先抽象
5. 全量验证：`uv run pytest` + `uv run ruff check .` + `uv run mypy app`
6. 更新受影响文档（README / SCOPE.md 相关节）
7. 提交：conventional commits（`feat:` `fix:` `refactor:` `test:` `docs:` `chore:`），一次提交一个逻辑变更

---

## 7. Git 与协作

- Conventional Commits；message 写清"为什么"，不只写"做了什么"
- 个人项目至少做 self-review：提交前重读自己的 diff
- 不入库：`.env`、`data/` 运行产物、任何密钥/令牌

---

## 8. 与 LLM 相关的工程约束

- **LLM 输出不可信**：一切 LLM 返回必须先过 validator（SCOPE §4 的 L3 校验）再入库/展示；校验失败要可观测、可重试
- **provider 是策略**：端口 `LLMClient` 定义在 domain.ports；新增模型/厂商只新增 infrastructure 策略类，禁止改动上层
- **prompt 是代码**：prompt 模板放独立模块并版本化；改 prompt = 改代码，必须过测试
- 每次脱水记录 provider/model/耗时/校验结果，便于复盘与调优

---

## 9. 禁止事项速查

- ❌ 绕过测试直接改领域逻辑
- ❌ 把 API key / secret 写进代码、日志、commit、报错信息
- ❌ 全局可变状态 / 隐式依赖（一律构造注入）
- ❌ 在 domain 层 import 第三方库
- ❌ 复制粘贴既有实现（应抽取公共函数）
- ❌ 未经讨论修改 SCOPE.md 的范围、验收标准、边界
- ❌ 为了"快"引入与现有架构冲突的写法（如新模块绕过分层直接调外部 SDK）

---

## 10. 与工具链兼容说明

- 本文件遵循 CLAUDE.md / AGENTS.md 通用约定：若使用支持 `AGENTS.md` 的工具，本文件可整体作为其内容使用（保持单一来源，勿另存漂移副本）。
