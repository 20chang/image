---
feature: image-plans
status: delivered
updated: 2026-09-30
branch: master
commits: # implementation reviewed as uncommitted working tree on master (base c6f2adb)
---

# 商品图片方案（Day-1 后端）

## Report

**What was built** — 商品「图片方案」Day-1 后端：新增 `image_plans` 表（稳定 `pl` ID、JSON 参考图列表、`draft`/`confirmed` 状态、可选 `basedOnPlanId` 血缘），以及 5 个 REST 接口——列表、详情、创建草稿、更新草稿、确认。参考图强制归属当前商品；已确认方案内容不可变；确认仅记录认可，不调用生图。方案通过 `product_id` 跟随商品，移动文件夹不影响。

**Verification** — `uv run pytest tests/ -v` → 4 passed（生命周期含重启后可读、外键/血缘校验、确认后不可变、未知 id 404）；`uv run ruff check src/ tests/` → PASS；`uv run ruff format --check src/ tests/` → PASS；`uv run pyright src/` → 0 errors。独立审查确认 T1–T6 全部满足，无 CRITICAL。

**Journey log**
- 需求里「后续修改通过新草稿」用 `basedOnPlanId` 指针实现，不建版本表——保持 Day-1 简单，血缘仅作记录。
- 参考图关联沿用 `ref_images.purposes` 的 JSON 数组风格，不建 join 表；服务端校验归属即可。
- `now_iso()` 分钟精度会让同一分钟内创建的方案排序落到随机 id 上；若后续需要严格创建序，再升级时间戳精度。
- 测试里 `from backend.main import app` 会在 fixture monkeypatch 之前触发真实 `init_db()`；隔离要求高时再改。

## [S1] Problem

商品详情的「图片方案」标签目前只有占位空态。运营需要为商品创建**主图方案**：填写方案名称、图片用途、选用的参考图、制图要求、生图提示词，保存草稿并在认可后确认。确认只表示认可制图要求，不调用生图。后端需提供稳定的持久化与接口，使内容在页面刷新和后端重启后仍完整可读。

## [S2] Design

### 范围角色

本轮只做后端。前端交互由后续/他人对接；验收例子中的页面操作通过本 API 完成。

### 数据模型

新表 `image_plans`（沿用现有 `db.py` 的 `CREATE TABLE IF NOT EXISTS` 风格）：

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | 稳定 ID，前缀 `pl` + 12 hex（沿用 `new_id`） |
| product_id | TEXT NOT NULL → products(id) ON DELETE CASCADE | 方案跟随商品；商品移动文件夹不影响 |
| name | TEXT NOT NULL | 方案名称 |
| image_usage | TEXT NOT NULL DEFAULT `'商品主图'` | 图片用途（本轮固定） |
| ref_image_ids | TEXT NOT NULL DEFAULT `'[]'` | JSON 数组，元素为 `ref_images.id` |
| drawing_request | TEXT NOT NULL DEFAULT `''` | 制图要求（短意图） |
| prompt | TEXT NOT NULL DEFAULT `''` | 生图提示词（可多行） |
| status | TEXT NOT NULL DEFAULT `'draft'` | `draft` \| `confirmed` |
| based_on_plan_id | TEXT NULL | 可选血缘，指向同商品的另一方案 |
| created_at / updated_at | TEXT NOT NULL | 沿用 `now_iso()` |
| confirmed_at | TEXT NULL | 确认时间 |

索引：`idx_image_plans_product ON image_plans(product_id, created_at)`。

参考图关联存 JSON 数组（与现有 `ref_images.purposes` 一致），不建 join 表。服务端校验每个 id 且必须属于 `product_id`。

### 状态机与不变式

- 草稿可反复 PATCH；确认后**内容不可再改**。
- 「后续修改通过新草稿进行」= 新建独立方案，创建时可带 `basedOnPlanId` 指回来源（通常为已确认方案），字段由调用方复制。不建版本表。
- 首次「保存草稿」才创建记录（POST）；新建未保存的编辑器状态是前端本地态，取消即丢弃，后端不产生空方案。
- `basedOnPlanId` 若给出：必须存在且属于同一商品，否则 422。
- 方案不因商品移动文件夹而改变 `product_id`。

### 接口

前缀 `/api`，出参字段 camelCase（与 `schemas.py` 现状一致）。

| 方法 | 路径 | 作用 | 成功 |
|------|------|------|------|
| GET | `/products/{productId}/plans` | 列出该商品全部方案（含字段全量，按 created_at,id） | 200 list |
| GET | `/plans/{planId}` | 方案详情 | 200 |
| POST | `/products/{productId}/plans` | 创建草稿（首次保存，可含 basedOnPlanId） | 201 |
| PATCH | `/plans/{planId}` | 更新草稿字段 | 200 |
| POST | `/plans/{planId}/confirm` | 草稿 → 已确认 | 200 |

请求/响应模型：

- `ImagePlanCreate`: `name` (min 1), `imageUsage="商品主图"`, `refImageIds=[]`, `drawingRequest=""`, `prompt=""`, `basedOnPlanId=null`
- `ImagePlanUpdate`: `name` / `imageUsage` / `refImageIds` / `drawingRequest` / `prompt` 均可选，只覆盖给出的字段。`basedOnPlanId` 仅创建时设定，不提供更新。
- `ImagePlanOut`: `id`, `productId`, `name`, `imageUsage`, `refImageIds`, `drawingRequest`, `prompt`, `status`, `basedOnPlanId`, `createdAt`, `updatedAt`, `confirmedAt`

### 错误行为

| 情况 | 状态 |
|------|------|
| product / plan 不存在 | 404 |
| `name` 空白 | 422 |
| `refImageIds` 含不存在或不属于该商品的 id | 422 |
| `basedOnPlanId` 不存在或不属于该商品 | 422 |
| PATCH / confirm 目标已是 `confirmed` | 409 |
| 重复 confirm | 409 |

### 持久化边界

使用现有 `connect()`；SQLite 文件 `backend/data/app.db`。重启后内容仍可读取（验收要求）。不写上传文件、不调生图 API。

## [S3] Out of Scope

- 前端「图片方案」页签 UI 与交互
- 「AI 生成提示词」（第二轮）
- 调用生图 API / 产出图片
- 删除方案、方案列表排序选项、重命名以外的元数据
- 版本树 / 多版本方案（仅保留 `basedOnPlanId` 指针）
- 鉴权、多用户

## Tasks

- [x] T1: `image_plans` 表与初始化 — acceptance: `init_db()` 后表存在，插入的行在进程重启后仍可读取 (covers: S2)
- [x] T2: 列表与详情接口 — acceptance: `GET /products/{id}/plans` 返回该商品全部方案，`GET /plans/{id}` 返回全量字段，未知 id 为 404 (covers: S2; depends: T1)
- [x] T3: 创建草稿接口 — acceptance: `POST` 生成 `status=draft` 并关联商品；非法 `refImageIds` / `basedOnPlanId` 为 422；成功体含稳定 `id` (covers: S2; depends: T1)
- [x] T4: 更新草稿接口 — acceptance: `PATCH` 只覆盖提交字段且校验参考图归属；目标为 `confirmed` 时 409 (covers: S2; depends: T3)
- [x] T5: 确认接口 — acceptance: `POST /plans/{id}/confirm` 将 `status` 置 `confirmed` 并写 `confirmedAt`；对已确认方案再次 confirm 或 PATCH 为 409 (covers: S2; depends: T3)
- [x] T6: 回归测试跑通验收链 — acceptance: 自动化测试覆盖「创建→选参考图保存→再改再存→确认→可再读」，且 `ruff check` / `pyright` 通过 (covers: S2; depends: T2, T3, T4, T5)
