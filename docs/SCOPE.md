# recipe-dehydrator · 范围定义（SCOPE）

> 本文件是项目的**事实来源 #1**（管"做什么"：范围、验收、边界）。
> 事实来源 #2 是 [CLAUDE.md](../CLAUDE.md)（管"怎么改代码"：规范、纪律、流程）。
> 冲突时：范围问题听本文件，变更纪律问题听 CLAUDE.md；涉及取舍分歧，先问人，不自行拍板。

---

## 1. 目的（为什么做）

- **主目的**：让做饭新手不用刷视频——给一个 B站视频链接，拿到一张能照着做完的图文菜谱卡
- **副目的**：练手 LLM 结构化抽取与时间轴切分工程；沉淀个人菜谱库（视频是获取渠道，菜谱库是资产）

**一句话定位**：摘要是"内容说明"，脱水是"把信息从视频里还原成可直接使用的形态"。

---

## 2. 使用形式

- **本地服务**：FastAPI 后端 + TS/esbuild 前端，电脑当服务器（局域网）
- 手机/平板浏览器访问 `http://<电脑IP>:8000`，可 PWA「添加到主屏」像 App 使用
- 纯本地自用，不部署上线，不做账号系统（开源后他人自建实例）

---

## 3. 功能现状（已实现）

### 3.1 脱水管线
- 输入：B站视频链接（BV 号 / 完整 URL）
- 抓取：yt-dlp 抓标题/时长/字幕（官方字幕 + AI 字幕；**需要登录 cookie**，未配置时无字幕视频提示「无字幕」）
- 字幕：L1 预处理（解析/去寒暄/去 BGM 歌词/合并断句/去重）
- 预检：LLM 判断单菜/多菜/非烹饪——**多菜合集、BGM 歌词、非烹饪内容自动拒绝**
- 切分：LLM 时间轴切分 → 步骤（含阶段 phase/达成状态 done_when/易错点 tip/时间区间）
- 校验：L3 一致性（时间连续、食材闭环、顺序合理），失败自动重试一次
- 配图：关键句对齐抽帧 + 动作 GIF（**默认关**，勾选开启；>8 步只给中间阶段）

### 3.2 菜谱库（默认首页）
- 网格卡片（成品图封面）、搜索（菜名/食材）、主料分类、排序（置顶/最近做过/最新）
- 置顶📌、「今天做了」打卡（cooked_count / last_cooked_at）
- 编辑（JSON）、删除

### 3.3 卡片三模式
- **浏览**：食材五分类（主料/配料/调味料/香料/需提前自制，调味料折叠）、步骤阶段分组、页内播放器（B站 iframe + t 参数跳转）
- **做菜**：一步一屏、大字、进度条、步骤栏（桌面竖排/手机圆点条）、左右滑/键盘翻页、屏幕常亮（WakeLock）
- **买菜**：全屏清单、大勾选、调味料折叠、勾选沉底

### 3.4 工程能力
- 质量评分器（100 分制客观打分，无需人工标注）+ eval 批量评估脚本
- PWA 离线（缓存卡片/截图）、暗色模式、移动端响应式

---

## 4. 抽取策略（核心设计）

**核心原则：让 LLM「切分时间线」，而不是「抽取步骤」。** 切分有唯一性约束（连续、全覆盖），犯错空间远小于开放抽取；切出的时间区间直接复用于抽帧。

### L1 字幕预处理（代码层）
- 按时间戳合并断句（只合并短残片，避免吞掉时间分辨率）
- 过滤：寒暄/求三连/广告口播、**B站 ♪ 标记的 BGM 歌词**、语气词整句、去重

### L2 时间轴切分（LLM 主任务，prompt 版本化 split-v6）
- 先切 3-6 个阶段（phase），阶段内分步骤，总量 5-12 步
- done_when 必须是可观察状态（禁模糊词）；description ≤30 字；细节进 tip
- 食材五分类 + essential（核心/可选）由 LLM 判定
- 无烹饪内容输出空 steps（配合预检兜底）

### L3 一致性校验（代码层）
- 食材闭环（每个食材出现在某步骤中，漏的告警）
- 时间自洽（无重叠、无大空隙、跨度与时长吻合，偏差告警）
- 顺序合理（步骤 index 与时间顺序一致）
- 同名食材合并（归一化）

### L4 人机回环
- 卡片可编辑；人工修正自动沉淀为 few-shot 样本（只积累，不重训）

### 兜底认知
- LLM 输出永不 100% 准 → 校验只告警不阻断（error 级才阻断）、页面可编辑、评分器量化
- 目标：把人工从「看 20 分钟视频」降到「改两处文字」

---

## 5. 明确不做（边界）

- ❌ 语音识别（ASR）：无字幕视频提示换视频（画面花字 OCR 在二期展望）
- ❌ 多平台：只支持 B站；抖音/YouTube 以后再说
- ❌ 账号系统、多人协作、云端部署（开源后他人自建）
- ❌ 多模态选帧（Qwen-VL）：当前用关键句对齐，视觉选帧在二期展望
- ❌ 不追求还原大厨水准：标准是"新手照着做不翻车"
- ❌ 不托管下载服务、不聚合内容：纯本地工具（合规见 README 免责声明）

---

## 6. 技术栈

- Python 3.14 + uv
- 后端：FastAPI + SQLite + Pydantic v2
- 前端：TypeScript + esbuild（轻量构建，无框架）+ 原生 ES Modules；`types.ts` 与后端 schema 对齐
- 抓取：yt-dlp；抽帧/GIF：ffmpeg
- LLM：DeepSeek（默认）/ Qwen / Kimi（OpenAI 兼容协议，provider 可切换），key 存本地 `.env`
- 质量门禁四件套：`pytest` + `ruff check` + `mypy`（strict）+ `tsc --noEmit`（CI 自动跑）

---

## 7. 验收标准（Definition of Done）

| 项 | 状态 |
|---|---|
| 10 个真实 B站做饭视频 ≥8 个产出"能照做的卡片" | 🟡 已测 9 个（8 成功 + 1 正确拒绝合集），未正式走完 |
| 纯文字 ≤30 秒 / 带图 ≤90 秒 | ✅ 实测达标 |
| 页面：贴链接出卡、买菜清单、菜谱库、三模式、播放器 | ✅ 已实现 |
| **真实用一次**：用它做一顿饭记录卡壳 | ⏳ 未做（用户唯一缺口） |

---

## 8. 二期展望（只记录，不实现）

- 新闻情报局：同一管线换"新闻事件 schema"做增量关联
- Qwen-VL 多模态选帧 + 画面 OCR 补信息（解决"配料比例打在屏幕上"类字幕缺失）
- 无声视频画面花字 OCR（RapidOCR → 伪字幕 → 复用现有管线）
- 多平台支持（抖音/YouTube）+ 对应播放器
- 低置信度卡片标记（评分 <70 前端提示）
- 步骤计时器 / 语音朗读（厨房场景增强）

---

## 9. 项目结构（分层架构 / Layered Architecture）

依赖方向单向：**api → application → domain ← infrastructure**。
domain 零外部依赖；infrastructure 实现 domain 的 ports；组合根在 `app/factory.py`。

```
recipe-dehydrator/
├── README.md                  # 开源介绍（中英双语）
├── CLAUDE.md                  # 编码规范与 Agent 约束（事实来源 #2）
├── LICENSE                    # MIT
├── pyproject.toml             # uv 项目（依赖 + ruff/pytest/mypy 配置）
├── package.json               # 前端依赖 + esbuild/tsc 脚本
├── tsconfig.json              # 前端 TS 配置
├── .env.example               # LLM API key 模板（.env 不入库）
├── .gitignore
├── docs/
│   ├── SCOPE.md               # 本文件（范围定义，事实来源 #1）
│   └── frontend-design.md     # 前端设计文档（v0.2 已实施）
├── data/                      # 运行产物：SQLite、截图、few-shot 样本（gitignore）
├── eval/                      # 评估工具：评分器驱动、截图（screenshots gitignore）
├── tests/
│   ├── fixtures.py            # 共享样例与构造器
│   ├── fakes.py               # 测试替身（LLM 等，测试不触网）
│   ├── unit/                  # 纯逻辑单测
│   └── integration/           # 链路/API 测试
├── app/
│   ├── main.py                # uvicorn 入口
│   ├── factory.py             # 组合根（装配依赖，无副作用）
│   ├── api/                   # 表现层：config / routes / schemas
│   ├── application/           # 应用层：dehydrate（脱水编排）/ cards（菜谱库）/ prompts
│   ├── domain/                # 领域层：models / validation / transform / framing / scorer / ports / exceptions
│   ├── infrastructure/        # 适配层：bilibili_fetcher / llm_providers / ffmpeg_frames / sqlite_store / subtitle
│   └── static/                # 前端：index.html / css / src（TS 源）/ dist（esbuild 产物，gitignore）
└── .github/workflows/ci.yml   # CI：pytest + ruff + mypy + tsc + esbuild
```

**分层职责与禁忌**：

| 层 | 职责 | 禁止 |
|---|---|---|
| api | HTTP 契约、参数校验、序列化 | 业务逻辑、直接调用外部 SDK |
| application | 用例编排、跨端口协调 | 外部 SDK 细节、领域规则实现 |
| domain | 实体、规则、端口接口 | 任何 stdlib 以外的 import |
| infrastructure | 外部能力适配（yt-dlp/ffmpeg/LLM/SQLite） | 业务决策 |

> 详细编码规范见 `CLAUDE.md`（变更纪律以其为准，范围以本文件为准）。
