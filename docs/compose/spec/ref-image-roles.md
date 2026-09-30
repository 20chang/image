---
feature: ref-image-roles
status: delivered
updated: 2026-09-30
branch: feat/ref-image-roles
commits: f79d155..WORKTREE
---

# 参考图属性重设 + 方案内角色

## Report

**What was built** — 参考图属性拆为独立的 `productRelation` / `aiStatus`（可存「不确定」），备注仍用 `desc`；方案内新增 `referenceUsage`（角色 / 参考什么 / 忽略什么），顺序即使用顺序，至多一张「主体依据」；`refImageIds` 与 usage 由后端保持一致；确认前必须补齐选中图角色，已确认方案冻结。「本次参考说明」由结构化数据生成预览。启动时幂等迁移旧 `source`，`attrs_migrated` 哨兵保证用户主动存的「不确定」不被改写。前端接通参考图新属性面板与图片方案页（列表 / 选图 / 角色 / 保存 / 确认 / 只读）。

**Verification** — `uv run pytest tests/ -v` → 14 passed；`uv run ruff check` / `pyright` → clean；`npm run build` → PASS；`python backend/tests/smoke_live.py` 真实 API 冒烟 → PASS（三张图角色说明、双方案不同角色、排序不扰动、非法 422、删引用 409、确认后 409）。

**Journey log**
- 默认值哨兵会与合法的「不确定/不确定」冲突；用 `attrs_migrated` 标记「已迁移/用户已写」比用列默认值安全。
- `refImageIds` 与 `referenceUsage` 双字段兼容：usage 为真源，ids 由后端派生，避免界面勾选与落库不一致。
- FastAPI 出参/入参用 `str = ""` 默认会在省略字段时抹掉旧值；PATCH 半更新要用 `| None = None`。

## [S1] Problem

参考图资料页目前把「同款/其他商品/AI 生成/未知」混在单一 `source` 里，又用 `purposes` 兼作永久用途。实际工作流需要拆开两件事：**图片自身是什么**（是否同款、是否经 AI）与**这次方案里怎么用它**（主体依据/细节补充/…）。方案页也尚未接通，无法选图、写「参考什么/忽略什么」并回读。需要重设属性模型、引入方案内角色、接通页面，并可重复迁移旧数据。

## [S2] Design

### 范围

后端数据模型 + 迁移 + 校验 + 接口扩展；前端参考图编辑面板与图片方案页接通；「本次参考说明」由结构化数据生成预览。本轮不接模型、不识别图片内容。

### 参考图属性（图片自身）

`ref_images` 新增列，**保留**旧列 `source` / `purposes` 不删：

| 列 | 类型 | 说明 |
|----|------|------|
| product_relation | TEXT NOT NULL DEFAULT `'unknown'` | `same_product` \| `other_product` \| `no_product` \| `unknown` |
| ai_status | TEXT NOT NULL DEFAULT `'unknown'` | `yes` \| `no` \| `unknown` |

- 与现有 `desc`（备注）并列；`id` / `asset_id` / 文件 / `sort_order` 不变。
- 允许保存「不确定」；卡片如实显示。两字段相互独立（可同时「同款」+「经 AI」）。
- API 出参 camelCase：`productRelation`、`aiStatus`；入参同名可选字段，只覆盖提交项。
- 旧 `PATCH /references/{id}` 的 `source` / `purposes` 继续可写（兼容），但 UI 改用新字段。

### 方案内角色（本次怎么用）

`image_plans` 新增列 `reference_usage` TEXT NOT NULL DEFAULT `'[]'`：

```json
[
  {
    "refImageId": "r…",
    "roles": ["primary"],
    "useFor": "灯身外观",
    "ignore": "背景、促销文案"
  }
]
```

- **数组顺序 = 本次使用顺序**；素材列表 `sort_order` 变化不得改写已保存方案的顺序或角色。
- `roles` 多选枚举：

| 值 | 显示 | 含义 |
|----|------|------|
| primary | 主体依据 | 决定商品整体外观 |
| detail | 细节补充 | 接口、支架、线束等指定部位 |
| usage | 安装与使用 | 安装位置、朝向、使用关系 |
| composition | 构图参考 | 位置、角度、大小和布局 |
| style | 视觉风格 | 背景、光线和氛围 |

- 一份方案 **最多一张** `primary`；一张图可兼任其他角色。
- `useFor` / `ignore` 为自由文本；选角色后可填入建议文案（前端模板），用户可改。
- 不自动推荐「其他商品 / AI 处理 / 关系不确定」的图为事实依据（primary/detail/usage）；用户坚持选时前端提示核对参考范围。后端不阻止（只拦非法枚举、重复主体、越权引用）。

### refImageIds 一致性

- 继续接受/返回现有 `refImageIds`。
- 后端统一维护：任一写入路径下，`refImageIds = [u.refImageId for u in referenceUsage]`（按 usage 顺序）；若只传 `refImageIds` 不传 `referenceUsage`，则 `referenceUsage` 按该 id 顺序生成骨架（`roles: []`, `useFor: ''`, `ignore: ''`）。
- 校验：每张图属于当前商品；`refImageId` 不得在同一方案重复；`roles ⊆` 枚举；`primary` 计数 ≤ 1。
- **草稿**允许角色未填完；**确认前**若存在 `roles` 为空的选中项 → 422（前端先提示补齐）。已确认方案不可 PATCH / 再 confirm（沿用既有 409）。

### 「本次参考说明」

由 `referenceUsage` 生成只读预览（不入库），示例：

> A图提供灯身外观；B图只补充接口；C图只参考构图，忽略其中的商品、文字和Logo。

- 字母 A/B/C 对应数组顺序；文案由 `roles` + `useFor` + `ignore` 拼出。
- 同一份结构化数据供后续模型调用复用；本轮不调用模型。
- 后端在方案出参提供派生字段 `usageSummary: str`（计算字段，不落库），前端预览直接展示，保证与未来模型输入一致。

### 删除保护

被任一方案 `referenceUsage` / `refImageIds` 引用的参考图 **不可删除**（DELETE 返回 409 并说明被哪些方案引用）。解绑仅当方案中已不再引用。

### 迁移（可重复执行）

启动时 `init_db()` 内幂等迁移（已选方案）：

1. `ALTER TABLE ref_images ADD COLUMN product_relation` / `ai_status`（若缺）。
2. `ALTER TABLE image_plans ADD COLUMN reference_usage`（若缺）。
3. 回填映射（仅当新列仍为默认且旧列非空，可重复跑）：
   - `source=same` → `product_relation=same_product`, `ai_status=unknown`
   - `source=other` → `product_relation=other_product`, `ai_status=unknown`
   - `source=ai` → `product_relation=unknown`, `ai_status=yes`
   - 空/未知 → 两者 `unknown`
4. 旧 `purposes` **只作角色建议**，不写入已有方案的 `reference_usage`。
5. 已有方案：`ref_image_ids` 按序生成 `reference_usage` 骨架（roles 空）；已确认方案**不改写**内容，列表/详情如实呈现「角色未配置」。
6. 旧列保留，不删除、不回写。

### 接口变化

| 方法 | 路径 | 变化 |
|------|------|------|
| GET | `/products/{id}/references` | 出参增加 `productRelation`, `aiStatus` |
| PATCH | `/references/{id}` | 入参增加 `productRelation?`, `aiStatus?` |
| GET | `/products/{id}/plans`、`/plans/{id}` | 出参增加 `referenceUsage`, `usageSummary` |
| POST | `/products/{id}/plans` | 入参增加 `referenceUsage?` |
| PATCH | `/plans/{id}` | 入参增加 `referenceUsage?` |
| POST | `/plans/{id}/confirm` | 确认前校验角色齐全；冻结 usage（不再校验图片当前属性） |
| DELETE | `/references/{id}` | 被方案引用时 409 |

### 错误行为（新增）

| 情况 | 状态 |
|------|------|
| `referenceUsage[].roles` 含未知枚举 | 422 |
| 同一方案重复 `refImageId` | 422 |
| `primary` 超过 1 张 | 422 |
| confirm 时仍有选中图 `roles` 为空 | 422 |
| 删除被方案引用的参考图 | 409 |
| 旧规则（归属/404/确认不可变） | 不变 |

### 前端

1. **参考图编辑面板**：来源 → 「与当前商品的关系」「是否经过 AI 处理」「备注」；卡片显示新属性；允许「不确定」。
2. **图片方案页**（替换空态）：方案列表（名称 + 草稿/已确认）→ 编辑器：选参考图（多选）→ 每图角色多选 + 「参考什么」「忽略什么」→ 保存草稿 / 取消修改 / 确认方案 / 只读打开已确认方案。
3. **「本次参考说明」预览块**：由 `usageSummary` 或同逻辑前端生成。
4. 选角色时填入建议文案；对 non-same / AI / unknown 图选 primary|detail|usage 时提示核对范围。
5. 保存失败保留输入、不弹成功；被引用图不可删除。

## [S3] Out of Scope

- 调用生图 / 文本模型（含「AI 生成提示词」按钮）
- 自动识别图片内容、自动判断角色
- 版本树 / 多版本方案扩展（`basedOnPlanId` 仅沿用）
- 删除旧列 `source` / `purposes`
- 鉴权、多用户

## Tasks

- [x] T1: 参考图新列 + 幂等迁移 — acceptance: 重启后 `product_relation`/`ai_status` 存在且按映射回填；重复启动不改写已填值；旧列仍在 (covers: S2)
- [x] T2: 参考图 API 扩展 — acceptance: GET/PATCH 往返 `productRelation`/`aiStatus`，含 `unknown`；备注仍为 `desc` (covers: S2; depends: T1)
- [x] T3: `reference_usage` 存储与读写 — acceptance: POST/PATCH 接受 `referenceUsage` 并回读含 `usageSummary`；`refImageIds` 与 usage 顺序一致 (covers: S2; depends: T1)
- [x] T4: 后端校验 — acceptance: 未知枚举/重复 ref/多 primary/confirm 缺角色 422；非本商品 ref 422；删被引用图 409 (covers: S2; depends: T3)
- [x] T5: 旧方案迁移兼容 — acceptance: 旧 `ref_image_ids` 方案可读且 usage 骨架顺序正确；已确认旧方案内容不被改写 (covers: S2; depends: T3)
- [x] T6: 参考图编辑面板改造 — acceptance: 可编辑关系/AI/备注并保存回读；卡片显示新状态 (covers: S2; depends: T2)
- [x] T7: 图片方案页接通 — acceptance: 列表→选图→角色/useFor/ignore→保存→回读；确认后只读；失败保留输入 (covers: S2; depends: T3, T4)
- [x] T8: 本次参考说明预览 — acceptance: 「整体图决定外观，特写补接口，海报只借构图」类描述可由结构化配置生成 (covers: S2; depends: T3)
- [x] T9: 验收链与回归 — acceptance: 三张图七条验收（含双方案不同角色、排序不扰动、非法拒绝、旧数据可读）；`ruff`/`pyright`/前端 build 通过 (covers: S2; depends: T4, T5, T6, T7, T8)
