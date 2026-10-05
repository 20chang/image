---
feature: skill-planner
status: in-progress
updated: 2026-10-05
branch: feat/skill-planner
commits:
---

# Skill Planner（真实方案 → 看图规划 → 采用到草稿）

## Report

## [S1] Problem

图片方案 Skill 第一轮只做到 dry_run 组装（`image-plan-skill` @ `1221e29`）：`family` 不落库、图片像素从不进入模型请求、无模型调用层、无运行记录、`designNotes`/`openQuestions` 只存在于 IO 契约。真实方案数据与 Skill 是两条不相交的线，「看图规划」从未真实发生。

本轮目标：草稿方案可点「AI 生成方案」→ 从库读真实数据组装请求（含图片像素）→ 调用规划模型 → 解析四段输出 → 落运行记录 → 用户审阅后「采用到草稿」。范围严格限 `main` 族。合并评审见 `docs/next-round-spec.md`。

## [S2] Design

### [S2.1] 数据模型

`image_plans` 增列（一律走 `db._ensure_column` 幂等迁移）：

| 列 | 类型 | 说明 |
|----|------|------|
| `family` | `TEXT NOT NULL DEFAULT 'main'` | 规则路由主轴；本轮仅接受 `main` |
| `design_notes` | `TEXT NOT NULL DEFAULT ''` | 设计说明 |
| `open_questions` | `TEXT NOT NULL DEFAULT '[]'` | JSON 字符串数组 |

新增表 `plan_runs`：

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | TEXT PK | `new_id("run")` |
| `plan_id` | TEXT NOT NULL | → `image_plans(id)` |
| `status` | TEXT NOT NULL | `success` \| `failed` |
| `planner_model` | TEXT NOT NULL | 规划模型名（生图模型另列，本轮无） |
| `system_prompt` | TEXT NOT NULL | **正文内联快照** |
| `user_prompt` | TEXT NOT NULL | 同上 |
| `input_ref_ids` | TEXT NOT NULL | `referenceUsage` 顺序 JSON |
| `rules_snapshot` | TEXT NOT NULL | 规则文件路径 + sha256 JSON |
| `raw_output` | TEXT | 模型原始返回 |
| `design_notes` | TEXT | 解析后 |
| `open_questions` | TEXT | JSON 数组 |
| `generated_prompt` | TEXT | 解析后 |
| `ref_usage_notes` | TEXT | 解析后（可空） |
| `error` | TEXT | 失败原因 |
| `created_at` | TEXT NOT NULL | 秒精度 |
| `adopted_at` | TEXT | 采纳时间，可空 |

`now_iso()` 改秒精度（`%Y-%m-%d %H:%M:%S`）。查询一律 `ORDER BY created_at, id`。

API 字段名跟 `schemas.py` 现有 camelCase：`family` / `designNotes` / `openQuestions` / `basedOnPlanId` / `referenceUsage`。

### [S2.2] 图片进入模型请求

`skill_preview/assemble.py`：

- 复用 `_ref_map` 顺序语义（`referenceUsage` 序 = 使用序 = A/B/C 标签序）。
- 新增 `_image_part(row)`：`UPLOAD_DIR` 本地文件 → base64 data URL。`url` 为 `/uploads/...` 相对路径时以**仓库根**为基准解析（同 `loader.py` 的 `parents[4]`），不依赖 CWD。
- `messages[1].content` 改为 content 数组：`[{"type":"text",...}, {"type":"image_url",...}, ...]`，图片物理顺序严格等于 `referenceUsage`。文字行与图片行共用同一次 `ref_rows` 迭代。
- 文件缺失**整次失败**，错误含 `refImageId` 与绝对路径；禁止静默跳过。
- `assembly_status.images_resolved` 实算；部分失败暴露 `images_missing`（refImageId 列表）。
- 测试占位路径（`/static/fixtures/`、`fixture:`）仍走原分支，报「测试占位」不崩溃，`images_resolved=False` 且不算错误。

`skill_preview/loader.py` 新增 `load_plan_case(conn, plan_id)`：从库读商品+方案+参考图，产出与 case JSON **同构** dict，复用 `validate_case`。

### [S2.3] 规划模型客户端（薄，不抽象）

新增 `backend/src/backend/planner/__init__.py`、`planner/client.py`；依赖 `httpx`。

职责边界：

| 做 | 不做 |
|----|------|
| messages（含图片）→ 文本/JSON | 生图 |
| 结构化失败（超时/HTTP/解析） | 多 provider 抽象、队列、重试、计费 |

配置走 `os.environ`：`PLANNER_MODEL`、`PLANNER_BASE_URL`、`PLANNER_API_KEY`。缺 key 在启动或首次调用前明确报错。

规划与生图必须分模块——出烂图时才能区分「方案错了」vs「生图没听话」。生图是下一轮另一个模块。

失败行为：**绝不写半截 prompt 到方案**；方案保持 `draft`；失败也落 `plan_runs`（`status=failed`，`raw_output`/`error` 保留）。

模型输出固定 JSON：

```json
{
  "designNotes": "…（设计选择须标注依据：facts / refImageId / 规则条文）",
  "prompt": "…",
  "openQuestions": ["…"],
  "refUsageNotes": "…"
}
```

解析失败即 run 失败，不允许自由文本入库。

### [S2.4] 生成与采纳流程

```
POST /api/plans/{id}/skill-run     (仅 draft)
  → 前置检查（见下）
  → load_plan_case + assemble（含图片）+ planner.client
  → 解析 → 落 plan_runs → 返回 run
  → 不改方案字段

POST /api/plans/{id}/adopt         body: { "runId": "..." }
  → 校验 run 属于该 plan、status=success、方案仍为 draft
  → 写 image_plans.prompt / design_notes / open_questions
  → 记 plan_runs.adopted_at

GET  /api/plans/{id}/runs          倒序，confirmed 也可查
```

硬性规则：

- **绝不自动确认**；AI 产出永远先进草稿。
- 不点采纳，方案 `prompt`/`designNotes`/`openQuestions` 保持原值。
- 草稿之外不可采纳、不可改（沿用现有 409）。

硬约束（把 `main.md:18` 变成代码）：`main` 族缺 `primary` 角色时**不调用模型**，落 `status=failed`、`error=missing_primary`（或含缺失清单），前端可读。软提示：`openQuestions` 非空显示警示但**不阻断**采纳（复用 `isRiskyRef` 样式）。

### [S2.5] 方案复制（评估闭环）

后端 `basedOnPlanId` 已有（`db.py:55`、`routers.py:706-712`）。前端补：

- 已确认方案旁「基于此生成新草稿」→ `POST` 带 `basedOnPlanId` + 复制 `name`/`family`/`imageUsage`/`drawingRequest`/`referenceUsage`/`prompt`/`designNotes`/`openQuestions`。
- 新方案 `status=draft`；修改新草稿不影响原方案。

### [S2.6] API / Schema 增量

- `ImagePlanCreate`：`family: str = "main"`；非 `main` → 422。
- `ImagePlanUpdate`：可改 `family`（仍仅 `main`）。
- `ImagePlanOut`：+ `family`、`designNotes`、`openQuestions: list[str]`。
- 运行记录 Out：对应 `plan_runs` 列的 camelCase。

### [S2.7] 前端（`ImagePlansPanel.jsx` 等）

- 族下拉：仅 `main` 可选，其余五项置灰标「待实现」；去掉硬编码 `imageUsage: '商品主图'`。
- 草稿态「AI 生成方案」→ 展示 run 四段（`designNotes`/`prompt`/`openQuestions`/`refUsageNotes`），openQuestions 醒目 →「采纳到草稿」；失败可重试。
- 「基于此生成新草稿」入口。
- 复用现有提示样式，不新造 UI 框架。

### [S2.8] 测试边界

保持 38 个既有测试全绿。新增覆盖：迁移后 `family` 默认值；`family=scene`→422；图片 content 数组顺序；缺文件报错；`images_resolved` 实算；`load_plan_case` 与夹具同构；缺 key 报错；失败不污染 `prompt`；`raw_output` 保留；组装确定性；快照改规则后历史不变；分钟内多 run 定序；adopt 仅 success+draft；缺 primary 阻断；openQuestions 不阻断；复制血缘。测试公开行为，不 mock 掉核心路径。

## [S3] Out of Scope

- 生图 API / 生图模型 / `generations` 表
- 其余五族规则补全与创建入口（`wear`/`scene`/`compare`/`handheld`/`texture`）
- 养成器、四桶归因、自动提案、自动改规则、规则退役
- 回归评测集、黄金集自动化
- 知识 Markdown → 结构化格式迁移
- 类目/材质/平台知识检索轴（`products` 尚无这些字段）
- 多 provider 抽象、队列、重试、计费
- `usageSummary` / `ROLE_SUGGESTIONS` 前后端重复实现的收编（欠账，见 `docs/next-round-spec.md` §9）
- 货架位置 role 字段（将来须用 `slot`/`position`，避免与参考图 `roles` 撞名）

## Tasks

- [ ] T1: `family` 落库并成为一等字段 — acceptance: 旧库迁移出 `family` 列且历史行为 `main`；省略创建得 `main`；`family=scene` 返回 422；38 测试全绿（covers: S2.1, S2.6）
- [ ] T2: 图片像素进入模型请求 — acceptance: 真实 `UPLOAD_DIR` 文件下 `messages[1].content` 为数组且图片序=referenceUsage；缺文件报错含 refImageId+路径；`images_resolved` 实算为 True；占位路径 dry-run 不崩（covers: S2.2）
- [ ] T3: `load_plan_case` + 薄规划客户端 — acceptance: `load_plan_case` 产出通过 `validate_case` 且与 car-light 夹具同构；缺 `PLANNER_API_KEY` 明确报错；失败不改方案 `prompt`；非预期 JSON 进 `raw_output`；两次组装 system prompt 逐字节相同（covers: S2.2, S2.3）
- [ ] T4: `plan_runs` 表 + `now_iso` 秒精度 + `GET /runs` — acceptance: 改 `main.md` 后历史 `system_prompt` 不变；失败也落 run 且 `error`/`raw_output` 非空；一分钟内 3 次 run 顺序正确；confirmed 可查 runs（covers: S2.1）
- [ ] T5: `designNotes`/`openQuestions` 入库 + skill-run/adopt 流程 + 前端 — acceptance: 生成后仍 draft 且方案字段不变；采纳后三字段落库持久化；openQuestions 有提示不阻断；缺 primary 不调模型且有可读缺失清单；parse 失败 run=failed 可重试草稿不丢（covers: S2.1, S2.4, S2.6, S2.7）
- [ ] T6: 「基于此生成新草稿」 — acceptance: 复制出 draft、`basedOnPlanId` 指向来源、改新草稿不影响原方案；省略 `basedOnPlanId` 行为不变（covers: S2.5, S2.7）
- [ ] T7: 集成验证与人工抽查 — acceptance: 38+新增测试全绿；ruff/pyright 过；人工对照 `car-light-main.sample.md` 标准：prompt 无无依据细节、设计选择可溯源（covers: S2.8）
