# 下一轮任务 Spec：打通「真实方案 → Skill → 看图规划 → 采用到草稿」

> 合并来源：`docs/kimi-suggestion.txt` + `docs/minimax-suggestion.txt`
> 评审基线：`feat/image-plan-skill` @ `1221e29`（master @ `65a0dff`，Skill 未合入）
> 面向：可直接交给开发者的实现规格。范围严格限 `main` 族。

---

## 1. 目标（一句话）

让「看图规划」真实发生一次：**图片像素进入模型请求**，输出可落库可采纳，并留下可复现的运行记录。

达成状态：

```
草稿方案 → 点「AI 生成方案」→ 后端读库组装请求（含图片像素）
         → 调用规划模型 → 解析四段输出 → 落运行记录
         → 用户审阅 → 「采纳到草稿」写入 prompt / designNotes / openQuestions
```

## 2. 范围

### 本轮做

| # | 任务 | 一句话 |
|---|------|--------|
| T1 | `family` 成为方案一等字段 | 落库 + API + 仅放开 `main` |
| T2 | 图片真正进入模型请求 | base64/content 数组，顺序=`referenceUsage` |
| T3 | 规划模型调用点 | 薄客户端，只规划不生图 |
| T4 | 运行记录 `plan_runs` | 快照内联正文+规则哈希；顺带修 `now_iso` 秒精度 |
| T5 | `designNotes` / `openQuestions` 入库 + 采纳流程 | 结果进 run，采纳才改草稿 |
| T6 | 「基于此方案再生成」 | 前端补齐 `basedOnPlanId` 复制链路 |
| 附 | `load_plan_case` | 真实数据与 case 夹具同构校验 |

### 本轮明确不做

- 生图 API 接入 / 生图模型
- 其余五族（wear / scene / compare / handheld / texture）规则补全与创建入口
- 养成器、四桶归因、自动提案、自动改规则
- 回归评测集自动跑、黄金集
- 知识 Markdown → 结构化格式迁移
- 类目 / 材质 / 平台知识检索轴（`products` 表尚无这些字段）
- family 选择 UI 的完整六族放开（本轮只 `main`）
- 多 provider 抽象、队列、重试、计费

## 3. 现状基线（实现时对照）

数据流：

```
文件夹 → 商品(name/market/facts)
       → 参考图(url/desc/productRelation/aiStatus/sortOrder)
       → 图片方案(imageUsage/drawingRequest/prompt/referenceUsage[]/status: draft→confirmed)
```

关键事实：

| 事实 | 位置 |
|------|------|
| `image_plans` 无 `family` / `designNotes` / `openQuestions` 列 | `db.py:46-60` |
| `based_on_plan_id` 列已存在，前端未接 | `db.py:55`，`schemas.py:100`，`routers.py:706-712` |
| `model_request` 只有两段纯文本，`images_resolved` 硬编码 `False` | `assemble.py:151-157, 184` |
| `model: "TBD-next-round"`，无 provider / HTTP 客户端 | 全库；依赖仅 fastapi / python-multipart / uvicorn |
| 缺 `primary` 不得生成——只写在 markdown，代码不拦 | `main.md:18`；`validate_case` 不检查 |
| `now_iso()` 分钟精度 | `db.py:195-196` |
| `usageSummary` 前后端两份实现（技术债，本轮不修） | `routers.py:77` / `ImagePlansPanel.jsx:23` |
| 迁移模式：`_ensure_column` 幂等加列 | `db.py:82-84` |
| 角色枚举、primary≤1、归属校验已落地 | `routers.py:150-194` `_normalize_usage` |
| 顺序语义：`referenceUsage` 数组序 = 使用序，A/B/C 仅展示标签 | `assemble.py:31,44-75` `_ref_map` |

命名注意（防撞车）：`roles` 已被「参考图角色」占用。将来货架位置 role 落库时必须改名（如 `slot` / `position`），本轮不涉及。

---

## 4. 任务规格

### T1. `family` 成为方案的一等字段

**动机**：Skill 体系以 family 为主轴路由，但 family 只活在 CLI 参数（`__main__.py`），方案里没有，真实数据无法路由到规则。

**改哪里**

- `db.py`：`_SCHEMA` 的 `image_plans` 表补列定义；`_migrate` 用 `_ensure_column` 迁移
- `schemas.py`：`ImagePlanCreate` / `ImagePlanUpdate` / `ImagePlanOut` 增加 `family`
- `routers.py`：`create_image_plan` / `update_image_plan` / `_plan_row_to_out`
- `ImagePlansPanel.jsx`：硬编码 `imageUsage: '商品主图'` 改为读 `plan.family`；新建入口增加族下拉

**新增字段**

```
family TEXT NOT NULL DEFAULT 'main'
```

**行为约定**

- `ImagePlanCreate.family` 省略 → 取 `main`；`PATCH` 可改
- **本轮只接受 `family == "main"`**。传 `scene` / `wear` / `compare` / `handheld` / `texture` 一律 **422**
- 前端族下拉：`main` 可选，其余五项置灰并标「待实现」（与 `skills/README.md` 状态表一致）
- `imageUsage` 与 `family` 解耦：`family` 决定规则路由，`imageUsage` 仍是自由文本用途描述

**为什么只放开 main**：`skills/families/` 里 5/6 族的「设计选择/约束/检查标准」全是「（待实现）」，放开等于让 Agent 拿空规则出图。

**验收**

1. 旧库启动后 `image_plans` 出现 `family` 列，历史行值为 `main`
2. `POST` 省略 `family` → 200，响应 `family="main"`
3. `POST` 传 `family="scene"` → 422
4. `PATCH` 可改 `family`（仍仅允许 `main`）
5. 现有 38 测试全绿（fixture 补 `ImagePlanOut.family`）

---

### T2. 图片真正进入模型请求

**动机**：项目定位是「看图规划」，但当前 Agent 只看到 `desc` 文字 + 路径字符串，从未收到像素。这是最严重断点。

**改哪里**

- `skill_preview/assemble.py`：`model_request` 构造段（`:151-157`）与 `_image_status`（`:35-41`）
- 复用 `_ref_map`（`:44`）——它已按 `referenceUsage` 顺序产出 `url`，**顺序语义正确，不要重写**

**新增**

- `_image_part(row) -> dict`：从 `UPLOAD_DIR` 读本地文件 → base64 data URL（或 provider 等价图片块）
- `messages[1].content` 由字符串改为 **content 数组**：

```python
{"role": "user", "content": [
    {"type": "text", "text": user_prompt},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},  # A
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},  # B
    ...
]}
```

**约束（必须遵守）**

1. **图片在 API 中的物理顺序严格等于 `referenceUsage` 数组顺序**（即 A/B/C 标签序）。建议 `_image_part` 与 `_usage_line` 共用同一次 `ref_rows` 迭代，避免两处各自排序后漂移。
2. `url` 是 `/uploads/xxx.jpg` 相对路径，**必须以仓库根为基准解析**（参考 `loader.py` 的 `parents[4]` 锚点），不能依赖 CWD。
3. **文件缺失要报错，不能静默跳过**。宁可整次调用失败，也不要让模型在缺 A 图的情况下拿到 A 的文字说明——那会产出「看起来有依据、实际是编的」方案。错误信息须含 `refImageId` 与解析后的绝对路径。
4. `assembly_status.images_resolved` 改为**实算**：全部图片成功读入才 `True`；部分失败单独暴露 `images_missing: list[str]`（refImageId 列表）。
5. 测试占位路径（`/static/fixtures/`、`fixture:`）仍走原分支，报「测试占位」而不是崩溃；占位场景 `images_resolved=False` 但不算错误。

**验收**

1. 用 `UPLOAD_DIR` 下真实文件组装：`model_request.messages[1].content` 是数组，且图片顺序 = `[A, B, C]`
2. 删掉 B 对应文件 → 抛明确错误，消息含 `ref-B`（或对应 refImageId）和路径
3. 真实图片下 `images_resolved=True`（当前硬编码 `False`）
4. `car-light-main.case.json` 占位路径仍可 dry-run，不崩溃

---

### T3. 规划模型调用点（薄客户端，不做抽象层）

**动机**：`model` 字段是 `"TBD-next-round"`，图片没进 messages。在这两件事修好之前，Skill 组装做得再干净也只是「格式正确」。

**新增**

- `backend/src/backend/planner/__init__.py`
- `backend/src/backend/planner/client.py`
- 依赖：`httpx`（加入 `pyproject.toml`）

**职责边界（写死，不得越界）**

| 做 | 不做 |
|----|------|
| 读商品资料 + 参考图（含像素）+ 规则 system prompt | 生图 |
| 调用规划模型，返回文本/JSON | 多 provider 抽象 |
| 结构化失败（超时 / HTTP 错 / 解析失败） | 队列、重试、计费、限流 |

**为什么规划与生图必须分模块**：混在一起时，出一张烂图无法区分是「方案错了」还是「生图模型没听话」——两者要修的地方完全不同。这是四桶归因的最小版本，必须从第一轮就分开，否则后续所有归因都不可靠。生图是下一轮的**另一个模块**。

**实现口径**

- **一个函数 + 一个模型名字符串 + 环境变量配置** 即可。不要建 provider 抽象层——现在建是在给不存在的多态性写接口。
- 配置项（`os.environ` 读取，不引 pydantic-settings）：
  - `PLANNER_MODEL`（模型名）
  - `PLANNER_BASE_URL`
  - `PLANNER_API_KEY`
- 配套函数 `assemble.py` → `load_plan_case(conn, plan_id)`（可放 `loader.py`）：从库读商品+方案+参考图，组装成与 case JSON **同构**的 dict，然后**复用现有 `validate_case`** 校验——保证夹具和真实数据走同一套闸门。

**失败行为**

- 超时 / HTTP 错误 / JSON 解析失败 → 返回结构化失败，**绝不写入半截 prompt 到方案**
- 方案保持 `draft`，UI 显示可读错误
- **失败也必须落运行记录**（T4），否则不知道失败在哪个环节

**验收**

1. `PLANNER_API_KEY` 缺失 → 启动或首次调用前报明确错误，不等到半路
2. 端点返回 5xx → 方案 `prompt` 字段**保持原值不变**，返回可读原因
3. 模型返回非预期 JSON → 报错 + 原始输出存进 run 的 `raw_output`
4. 同一输入连续两次组装，system prompt 逐字节相同（确定性）
5. `load_plan_case` 产出的 dict 能通过 `validate_case`，与 `car-light-main.case.json` 同构

---

### T4. 运行记录 `plan_runs`（案例快照的真身）

**动机**：没有运行记录，模型实测结果无法回放；且 `skills/*.md` 是会变的 git 文件，只记 `rules_version: "HEAD@xxx"` 事后无法重建当时喂了什么。

**新增表 `plan_runs`**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | TEXT PK | `run` + 12 hex（复用 `new_id("run")`） |
| `plan_id` | TEXT NOT NULL | → `image_plans(id)` |
| `status` | TEXT NOT NULL | `success` \| `failed` |
| `planner_model` | TEXT NOT NULL | 规划模型名；与生图模型分开记，下一轮再加 `generator_model` |
| `system_prompt` | TEXT NOT NULL | **正文内联快照**，不记 git 引用 |
| `user_prompt` | TEXT NOT NULL | 同上 |
| `input_ref_ids` | TEXT NOT NULL | `referenceUsage` 顺序的 JSON 快照 |
| `rules_snapshot` | TEXT NOT NULL | 已加载规则文件路径 + 各自 sha256（JSON） |
| `raw_output` | TEXT | 模型原始返回；解析失败时唯一可查的东西 |
| `design_notes` | TEXT | 解析后 |
| `open_questions` | TEXT | JSON 数组 |
| `generated_prompt` | TEXT | 解析后 |
| `ref_usage_notes` | TEXT | 解析后（可选，参考图使用说明） |
| `error` | TEXT | 失败原因 |
| `created_at` | TEXT NOT NULL | — |
| `adopted_at` | TEXT | 被采纳时间（可空） |

**快照口径（两份评审的合并结论）**

- **内联规则正文**（`system_prompt` / `user_prompt` 已含）**+ 规则文件路径与 sha256**（`rules_snapshot`）
- 只记指针 / git commit 不够——规则文件可变，事后无法重建

**顺带修复（必须本轮做）**

`db.py:195-196` `now_iso()` 改为**秒精度**：

```python
def now_iso() -> str:
    return datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")
```

否则同一分钟内多次运行无法定序（`ORDER BY created_at, id` 会落到随机 id 上）。查询统一 `ORDER BY created_at, id`。

**接口**

- `GET /api/plans/{planId}/runs` → 该方案全部运行记录，倒序
- 确认后的方案（`confirmed`）仍可查看其全部运行记录

**验收**

1. 改 `skills/families/main.md` 后重跑，历史 `system_prompt` 内容**不变**（证明是快照不是引用）
2. 调用失败也产生 `status='failed'` 记录，`error` 非空，`raw_output` 保留
3. 一分钟内连续 3 次运行，`GET /runs` 返回顺序正确
4. 确认方案后仍可查看全部运行记录

---

### T5. `designNotes` / `openQuestions` 入库 + 输出可采纳

**动机**：IO 契约已定义这两个输出语义（`10-io-contract.md`），`assemble.py` `field_mapping` 已预留名字；本轮落库并打通「审阅 → 采纳」。

**改哪里**

- `db.py`：`image_plans` 加列（走 `_ensure_column`）
  ```
  design_notes   TEXT NOT NULL DEFAULT ''
  open_questions TEXT NOT NULL DEFAULT '[]'
  ```
- `schemas.py`：`ImagePlanOut`（`designNotes: str`、`openQuestions: list[str]`）；Create/Update 视采纳路径决定是否暴露可写
- `routers.py`：读写 + 采纳端点
- `ImagePlansPanel.jsx`：结果展示 + 「采纳到草稿」按钮

**字段命名与语义：照 `10-io-contract.md` 来，不重新设计。**

**采纳流程（核心）**

```
「AI 生成方案」按钮
  → 调 T3 → 结构化输出
  → 写入 plan_runs，不直接改方案
  → 方案页展示该次运行的 designNotes / openQuestions / generatedPrompt
  → 用户点「采纳到草稿」
  → 才把 designNotes / openQuestions / prompt 写进 image_plans
  → 记录 plan_runs.adopted_at
```

**硬性规则**

- **绝不自动确认。** AI 产出永远先进草稿；方案 `status` 保持 `draft`
- 不点采纳，`plan.prompt` / `designNotes` / `openQuestions` 保持用户原值
- 解析失败即 run 失败落记录，**不允许自由文本入库**（输出必须是固定 JSON，见下）
- 草稿之外（`confirmed`）不可采纳、不可改

**规划模型输出契约（固定 JSON）**

```json
{
  "designNotes": "…（构图/光影/视角理由，每条设计选择标注依据来源）",
  "prompt": "…（生图提示词）",
  "openQuestions": ["…"],
  "refUsageNotes": "…（可选）"
}
```

要求模型在 `designNotes` 中为每个设计选择标注依据（facts / 某 refImageId / 规则条文），学 `car-light-main.sample.md` 文风。用文字约束代替 schema 约束（槽位化等案例够多再谈）。

**`openQuestions` 非空时的行为**

- 显示醒目警示（复用 `ImagePlansPanel.jsx` 已有 `isRiskyRef` 提示样式）
- **不阻断采纳**——用户常知道答案、只想先出图；硬拦很烦
- 与「缺 primary 不得生成」区别对待：前者是**硬约束**（见下），后者是**软提示**

**硬约束前置检查（把 `main.md:18` 变成代码）**

调用规划模型**之前**检查：`main` 族方案的 `referenceUsage` 必须含 `primary` 角色。缺失则**不调用模型**，直接返回缺失清单（422 或 200+错误体，实现自定，但必须可读且不产生 run——或产生 `failed` run 并注明 `error=missing_primary`，二选一，推荐后者以保留痕迹）。

**API**

- `POST /api/plans/{id}/skill-run`：仅 `draft` 可执行；跑前置检查 → 调 T3 → 落 run → 返回 run
- `POST /api/plans/{id}/adopt`：body 含 `runId`；把该成功 run 的 `prompt` / `designNotes` / `openQuestions` 写入草稿，记 `adopted_at`
- 失败可重试（再点「AI 生成方案」产生新 run），草稿数据不丢

**验收**

1. AI 生成后方案 `status` 仍是 `draft`
2. 不点采纳，`plan.prompt` 保持用户原值
3. 采纳后 `designNotes` / `openQuestions` / `prompt` 落库，刷新和重启后仍可读
4. `openQuestions` 非空时 UI 有提示但不阻止采纳
5. 缺 `primary` 时阻断且返回缺失清单，不产生成功 run
6. 模型超时/解析失败时 run 记 `failed`、前端可重试、草稿数据不丢

**前端本轮范围**

- 草稿态加「AI 生成方案」按钮
- 展示运行结果四段（`designNotes` / `prompt` / `openQuestions` / `refUsageNotes`），openQuestions 醒目
- 「采纳到草稿」按钮；失败可重试
- `family` 本轮 UI 固定 main，不加六族选择器（见 T1）

---

### T6. 「基于此方案再生成」

**动机**：已确认方案不可变（`update_image_plan` 对非 draft 返回 409）。需要「同一个 prompt 改了规则之后再跑一次」来对比效果，`basedOnPlanId` 是唯一血缘载体。不做这个，评估闭环断在这里。

**现状核实**

- 后端已有：`based_on_plan_id` 列、`ImagePlanCreate.basedOnPlanId`、跨商品校验（`routers.py:706-712`）
- 前端缺失：`PlanEditor.saveDraft` 的 body 无此字段；列表页无复制按钮

**拟新增**

- 列表页每个已确认方案旁「基于此生成新草稿」
- → `POST /products/{id}/plans`，body 带 `basedOnPlanId` + 复制 `name` / `family` / `drawingRequest` / `referenceUsage`（及 `imageUsage`）
- `prompt` / `designNotes` / `openQuestions` **一并复制**还是清空：**一并复制**（对比实验需要原 prompt 作基线）；`status` 必为 `draft`

**验收**

1. 从已确认方案复制出新草稿，`basedOnPlanId` 正确指向来源
2. 两者 `status` 分别为 `confirmed` / `draft`
3. 修改新草稿**不影响**原方案
4. 省略 `basedOnPlanId` 创建时行为不变（回归）

---

## 5. 横切约束

1. **规划 ≠ 生图**：本轮零生图代码。规划失败与（未来的）生图失败必须能分开归因。
2. **确定性组装**：同一输入 → 相同 system prompt（逐字节）。规则过滤（按 family）+ 资料组装已有雏形（`assemble.py`），本轮只接真数据与图片，不改知识格式。
3. **快照内联**：凡是「事后要能回答当时喂了什么」的，一律存正文+哈希，不存指针。
4. **失败不写半截**：任何异常路径不得污染 `image_plans.prompt` 等用户字段。
5. **顺序语义单一来源**：`referenceUsage` 数组序 = 使用序 = 图片传入序 = 文字说明序；A/B/C 只是 `_ref_label` 派生标签。
6. **迁移模式**：新列一律 `_ensure_column`，禁止手写破坏性迁移；参考 `attrs_migrated` 哨兵思路（防迁移覆盖用户写入）。
7. **技术债（记账不修）**：`usageSummary` / `ROLE_SUGGESTIONS` 前后端重复实现——本轮不动，下次动相关代码时收编。已在欠账清单。

## 6. 测试策略

**保持通过**：现有 38 个（`test_image_plans.py` 4 + `test_ref_image_roles.py` 10 + `test_skill_preview.py` 24）。

**新增测试（按任务）**

| 任务 | 测试点 |
|------|--------|
| T1 | 迁移后有 `family` 列且历史值 `main`；省略→`main`；`scene`→422 |
| T2 | content 数组图片顺序 = A/B/C；缺文件抛错含 refImageId+路径；`images_resolved` 实算；占位路径不崩 |
| T3 | 缺 API key 明确报错；失败不改 `prompt`；非预期 JSON 进 `raw_output`；组装确定性；`load_plan_case` 与夹具同构 |
| T4 | 改规则后历史快照不变；失败也落 run；分钟内多 run 定序正确；confirmed 可查 runs |
| T5 | 生成后仍 draft；不采纳不改字段；采纳落库持久化；openQuestions 软提示；缺 primary 阻断；parse 失败路径 |
| T6 | 复制出草稿、`basedOnPlanId` 指向、互不影响、省略行为回归 |

**人工抽查（验收项，非自动化）**

- 输出 prompt 中不含输入无依据的商品结构描述（对照 `car-light-main.sample.md` 的「已删除的无依据细节」标准）
- 设计选择带依据标注（facts / ref-ID / 规则），可溯源

## 7. 完成后的后续两步（仅路线，不在本轮）

### 第二步：用真实图片判断知识有没有价值（不做自动化）

进入条件：T1–T6 验收全过，`main` 族能真实调出规划模型、输出能落库能采纳。

- 选 8–12 个商品覆盖材质差异（金属反光 / 塑料哑光 / 透明半透明 / 深色 / 多部件带线束）。别只挑最好做的——车灯恰好是金属+浅色+结构清晰，是最不需要经验的一类。
- 每商品 2–3 张参考图，按 `referenceUsage` 配角色。
- **出图在系统外手动做**（可灵/即梦/SD），参数固定。本轮不接生图 API——避免计费/超时/重试/失败补偿复杂度。
- 人工只记三个数：商品是否准确、任务是否完成、返工几次才可用。
- **真正产出是失败清单**，不是分数。纪律：不要用「跑通了一次」当结论；失败样本密度才有价值。

进入第三步条件：至少 6 条具体、可复述的失败描述，且能对应到 `main.md` / `common/` 的某条规则或某个缺失。

### 第三步：建设养成器（只建四分之一）

进入条件：失败清单成型，且能看出失败是「知识错了」还是「模型没听话」。

- 失败记录进案例 schema：`(商品属性, 族, 决策, 最终 prompt, 结果图, 评分, 失败类型, 证据)`。注意：`car-light-main.sample.md` 是**设计意图文档**，不是案例——它没绑定任何运行、没有失败、没有分数。真正案例必须来自 `plan_runs`。
- 只做四桶归因（知识错缺 / 未检索到 / 模型不听话 / 转译丢失），**人工判定，不写代码**。
- 看指标：`bucket 3+4` 占比应随时间下降；`bucket 1` 先升后降。若 `bucket 3` 一直高，瓶颈在 prompt 结构与转译，加多少规则都没用。
- 明确不做：自动提案、自动改规则、自动回归、规则退役。
- 长期债（案例 30+ 后）：记每条规则「被调用 / 被修正」次数，准备退役。知识库只增不减，第二年就没人敢动。

## 8. 值得保留的设计资产（实现时不要破坏）

1. **参考图身份与顺序分离**——`refImageId` 稳定，A/B/C 只是数组位置派生的展示标签；文字说明与图片输入共用同一个 `ref_rows` 迭代。T2 直接复用，不要重写。
2. **`attrs_migrated` 哨兵**（`db.py:101`）——用标记位而不是列默认值防止迁移覆盖用户写入。新迁移若涉及数据回填，沿用此思路。
3. **「已删除的无依据细节」类负向知识**（`car-light-main.sample.md`）——比正向规则值钱。养成器建成后，每条失败都应能落成同样形式。

## 9. 欠账清单（本轮不修，登记备查）

| 项 | 位置 | 备注 |
|----|------|------|
| `usageSummary` 前后端两份实现 | `routers.py:77` / `ImagePlansPanel.jsx:23` | 下次动相关代码时收编 |
| `ROLE_SUGGESTIONS` 硬编码在前端 | `ImagePlansPanel.jsx` | 与上条同类；角色知识散落 |
| 货架位置 role 命名与参考图 `roles` 撞车 | — | 落库时改用 `slot` / `position` |
| 五族规则补全 | `skills/families/*.md` | 等失败清单，知道该填什么再填 |
| `car-light-main.sample.md` 对照评审 | `skills/cases/` | 模型实测后补一轮：人工预期 vs 实测差距本身就是第一批知识 |
| 规则退役机制 | — | 案例 30+ 后再议 |
| 类目 / 材质 / 平台字段与检索 | `products` 表 | 依赖字段先于检索；spec 只记录依赖关系 |

## 10. 验收总清单（合并可勾选）

- [ ] 旧库迁移出 `family` / `design_notes` / `open_questions` 列，历史行为不回归
- [ ] 仅 `main` 可创建；其余族 422
- [ ] 真实图片按 `referenceUsage` 顺序进入 `messages` content 数组
- [ ] 缺文件 / 缺 primary 分别报错 / 阻断，信息可读
- [ ] `images_resolved` 实算
- [ ] 规划模型可调通一次；失败不污染草稿字段
- [ ] 每次运行（成功与失败）落 `plan_runs`，含正文快照 + 规则 sha256 + `raw_output`
- [ ] `now_iso` 秒精度；分钟内多 run 定序正确
- [ ] 采纳流程：生成 → 审阅 → 采纳落库；不自动确认
- [ ] `openQuestions` 软提示不阻断；缺 `primary` 硬阻断
- [ ] 「基于此生成新草稿」血缘正确、互不影响
- [ ] 38 个既有测试全绿 + 上表新增测试
- [ ] 人工抽查：无无依据细节；设计选择可溯源
