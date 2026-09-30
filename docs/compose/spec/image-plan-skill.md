---
feature: image-plan-skill
status: delivered
updated: 2026-09-30
branch: feat/image-plan-skill
commits: 65a0dff..HEAD
---

# 图片方案 Skill 第一轮（结构 + main 样板 + 请求预览）

## Report

**What was built** — 建立 `skills/` 规则体系：`common/` 通用流程与 IO 契约（读商品事实 → 理解参考图与使用范围 → 处理资料冲突 → 组织方案与提示词；字段映射含 `designNotes`/`openQuestions` 缺口记录），六族文件统一六节（main 完整实现，wear/handheld/scene/texture/compare 标注边界与待实现）。main 族配车灯案例：`car-light-main.case.json`（TEST FIXTURE）+ `car-light-main.sample.md`（人工编写）。新增 `backend.skill_preview` CLI，组装 system+user messages 并打印规则加载列表、A/B/C ↔ refImageId 对照、字段映射；不调用模型。

**Verification** — 命令与结果：

- `uv run python -m backend.skill_preview --family main --case ../skills/cases/car-light-main.case.json` — PASS。输出摘录：
  ```
  1. 加载的规则文件
    - skills/common/00-overview.md
    - skills/common/10-io-contract.md
    - skills/families/main.md
  2. 参考图顺序对照（顺序=使用顺序）
    A  ↔  ref-A
    B  ↔  ref-B
    C  ↔  ref-C
  3. 组装后的模型请求 (messages)  # system=通用+IO+main 规则，user=商品资料+方案+参考范围
  4. 与方案字段的映射说明          # 含 [gap] designNotes / openQuestions
  ```
- `--case missing.case.json` → `[error] case 文件不存在`，exit 1 — PASS
- `--family wear`（case 为 main）→ family 不一致报错，exit 1 — PASS
- `uv run ruff check src/` / `ruff format --check src/` — PASS
- `uv run pyright src/` — PASS（0 errors）
- `uv run pytest tests/ -q` — PASS（14 passed）

**Journey log** —
1. Review 指出 T5「留下输出摘录」未落在文档 — 本 Report 的 Verification 摘录即补齐；交付前务必把 dry_run 证据写进 spec。
2. `loader.loaded_paths` 混用 `str`/`Path`、`references` 缺 `id` 抛裸 `KeyError` — review 后已修。
3. `paste.txt` 为任务简报，保持 untracked，不入库。
4. `designNotes`/`openQuestions` 本轮只文档化；下一轮入库时可直接按 IO 契约加列。

## [S1] Problem

图片方案已有结构化数据（商品事实、参考图角色/采纳忽略、制图要求），但缺少把它们组织成模型指令的**规则体系**。需要：通用流程 + 六族边界 + main 族样板，并在本地预览「最终交给模型的内容」，确认规则加载与参考图顺序正确。模型调用与出图留到下一轮。

## [S2] Design

### 目录结构（根目录 `skills/`）

```
skills/
  README.md                 # 总览：通用 + 六族 + 案例；如何 dry_run
  common/
    00-overview.md          # 通用流程：读事实→理解参考图→处理冲突→组织提示词
    10-io-contract.md       # 输入输出契约与方案字段映射
  families/
    main.md                 # 完整样板（目标/必要输入/设计选择/约束/检查标准/案例）
    wear.md                 # 边界 + 待实现
    handheld.md
    scene.md
    texture.md
    compare.md
  cases/
    car-light-main.case.json   # 测试样例输入（标明 TEST FIXTURE）
    car-light-main.sample.md   # 人工编写样例输出（标注「人工编写」）
backend/src/backend/skill_preview/
  __init__.py
  __main__.py               # python -m backend.skill_preview
  loader.py                 # 读 skills/ 规则与 case
  assemble.py               # 组装模型请求
```

### 六族边界（各族文件统一六节）

| 族 | 主要任务 | 本轮 |
|----|----------|------|
| main | 清楚展示商品及本次售卖内容 | **完整实现** |
| wear | 穿戴、安装或操作关系 | 边界 + 待实现 |
| handheld | 握持方式与相对比例 | 边界 + 待实现 |
| scene | 使用环境与情境 | 边界 + 待实现 |
| texture | 有依据的材质与结构细节 | 边界 + 待实现 |
| compare | 有事实依据的差异对照 | 边界 + 待实现 |

每族统一六节：**目标、必要输入、设计选择、约束、检查标准、案例**。

通用流程职责（不写死商品资料）：
1. 读取商品事实（每次调用作为输入）
2. 理解参考图及使用范围（`referenceUsage`: roles / useFor / ignore）
3. 处理资料冲突（产品关系/AI 状态 vs 主张的事实；图与文字矛盾时以标注）
4. 组织方案与提示词（设计说明、参考安排、生图提示词、待确认问题）

### 输入 / 输出契约

**输入**（组装请求的 payload，兼容现有 API 实体）：

| 输入 | 来源字段 | 说明 |
|------|----------|------|
| 商品资料 | `ProductOut.name/market/facts` | 每次调用输入，不进通用规则 |
| 参考图身份 | `ReferenceOut.id/url/productRelation/aiStatus/desc` | 保留 ID 与顺序 |
| 角色与范围 | `ImagePlanOut.referenceUsage[]` | roles/useFor/ignore，顺序=使用顺序 |
| 用户制图要求 | `ImagePlanOut.drawingRequest` | 原文保留 |
| 方案名/用途 | `name` / `imageUsage` | |

**建议输出**（Skill 组装结果，映射到方案字段）：

| 输出 | 对应字段 | 本轮是否入库 |
|------|----------|--------------|
| 设计说明 | 建议新增 `designNotes`（待定） | 否，仅预览/文档 |
| 参考图使用安排 | 已有 `referenceUsage` + 派生 `usageSummary` | 已有 |
| 生图提示词 | 已有 `prompt` | 已有 |
| 待确认问题 | 建议新增 `openQuestions`（待定） | 否，仅预览/文档 |

**缺口记录**：`designNotes` / `openQuestions` 尚未入 `image_plans`；本轮不改库，预览 JSON 中以 `designNotes` / `openQuestions` 字段给出，文档列出建议列。

参考图角色改造**已落地**（`productRelation`/`aiStatus`/`referenceUsage`），本 Skill 直接消费这些字段；无缺失约定时用 `cases/*.case.json` 测试数据验证。

### main 样板（车灯案例）

测试输入 `car-light-main.case.json`（标注 TEST FIXTURE）：
- A：主体依据（primary）— 同款整体图，用「灯身外观」，忽略「背景」
- B：细节补充（detail）— 同款接口特写，用「接口形状」
- C：构图参考（composition）— 其他商品海报，用构图，忽略「其中的商品、文字和 Logo」

样例输出 `car-light-main.sample.md` 必须展示（标注 **人工编写**）：
1. 为何采用该构图与光影（白底、正面偏 45°、柔光防过曝、完整轮廓）
2. A/B/C 各自使用与忽略
3. 最终生图提示词
4. 事实不足需用户确认处（如 IP 等级、附件清单、真实光效参数）

### 请求预览（dry_run）

```bash
cd backend
uv run python -m backend.skill_preview --family main --case ../skills/cases/car-light-main.case.json
```

或 `--plan-id`（可选，若本地库有方案则读真实方案；本轮默认走 case 文件）。

预览输出须包含：
- 加载的规则文件路径列表（证明 common + family 被加载）
- 组装后的 messages/system+user（或等价 model request）
- 参考图条目顺序与 `refImageId` 对照表（A/B/C ↔ id）
- 与方案字段的映射说明

**本轮验证**：规则确实加载；参考图 ID 与传入顺序一致。不调用模型、不出图。

## [S3] Out of Scope

- 实际调用文本/生图模型、生成图片
- wear/handheld/scene/texture/compare 五族完整规则
- `designNotes` / `openQuestions` 入库与 UI
- 「AI 生成提示词」按钮接线
- 前端 Skill 预览页

## Tasks

- [x] T1: skills/ 通用流程与 IO 契约 — acceptance: `skills/common/*.md` 覆盖读事实/参考图/冲突/组织提示词与字段映射、缺口列表 (covers: S2)
- [x] T2: 六族文件 — acceptance: 六族均含统一六节；main 完整，其余标「待实现」且边界清晰 (covers: S2; depends: T1)
- [x] T3: main 车灯案例 — acceptance: case JSON 为标明的测试数据；sample.md 含构图光影理由、A/B/C 使用与忽略、提示词、待确认事实，标注「人工编写」 (covers: S2; depends: T2)
- [x] T4: skill_preview dry_run — acceptance: `python -m backend.skill_preview --family main --case …` 打印规则加载列表、组装请求、ref 顺序对照；错误 case 有明确报错 (covers: S2; depends: T2)
- [x] T5: 验证与说明 — acceptance: dry_run 实际跑通并留下输出摘录；README/功能说明记录用法；`ruff`/`pyright` 通过 (covers: S2; depends: T3, T4)
