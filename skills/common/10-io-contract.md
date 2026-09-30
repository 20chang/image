# 输入输出契约

## 输入

组装模型请求的 payload，兼容现有 API 实体。

| 输入 | 来源字段 | 说明 |
|------|----------|------|
| 商品资料 | `ProductOut.name` / `market` / `facts` | 每次调用输入，不进通用规则 |
| 参考图身份 | `ReferenceOut.id` / `url` / `productRelation` / `aiStatus` / `desc` | 保留 ID 与顺序 |
| 角色与范围 | `ImagePlanOut.referenceUsage[]` | `roles` / `useFor` / `ignore`，顺序=使用顺序 |
| 用户制图要求 | `ImagePlanOut.drawingRequest` | 原文保留 |
| 方案名 / 用途 | `ImagePlanOut.name` / `imageUsage` | |

## 建议输出

| 输出 | 对应字段 | 本轮是否入库 |
|------|----------|--------------|
| 设计说明 | 建议新增 `designNotes`（待定） | 否，仅预览 / 文档 |
| 参考图使用安排 | 已有 `referenceUsage` + 派生 `usageSummary` | 已有 |
| 生图提示词 | 已有 `prompt` | 已有 |
| 待确认问题 | 建议新增 `openQuestions`（待定） | 否，仅预览 / 文档 |

## 字段缺口

以下字段尚未写入 `image_plans` 表，本轮不改库；dry_run 预览 JSON 中以同名字段给出，供下一轮入库时参考：

- `designNotes: str` — 设计说明（构图/光影/视角理由）
- `openQuestions: str[]` — 待用户确认的问题列表

## 映射说明

```
ProductOut          ──┐
ReferenceOut[]      ──┤
ImagePlanOut        ──┴──► skill_preview.assemble ──► model request JSON
                                                              │
                              ┌───────────────────────────────┤
                              ▼               ▼               ▼
                        designNotes    usageSummary/prompt  openQuestions
                        (不入库)        (已有列)            (不入库)
```

组装结果中的 `referenceUsage` 顺序、`refImageId` 必须与输入完全一致；字母 A/B/C 仅是展示标签，不是身份。
