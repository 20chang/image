# 图片方案 Skill

把商品资料、参考图角色与制图要求，组织成可交给模型的生图指令。

## 结构

```
skills/
  common/            # 通用流程 + 输入输出契约（所有族共用）
    00-overview.md
    10-io-contract.md
  families/          # 六族规则（按图片主要任务区分）
    main.md          # 完整实现
    wear.md          # 边界 + 待实现
    handheld.md
    scene.md
    texture.md
    compare.md
  cases/             # 测试样例输入 + 人工编写样例输出
    car-light-main.case.json
    car-light-main.sample.md
```

## 六族

| 族 | 主要任务 | 本轮 |
|----|----------|------|
| main | 清楚展示商品及本次售卖内容 | 完整实现 |
| wear | 穿戴、安装或操作关系 | 待实现 |
| handheld | 握持方式与相对比例 | 待实现 |
| scene | 使用环境与情境 | 待实现 |
| texture | 有依据的材质与结构细节 | 待实现 |
| compare | 有事实依据的差异对照 | 待实现 |

每族统一六节：**目标、必要输入、设计选择、约束、检查标准、案例**。

## 通用流程职责

1. 读取商品事实（每次调用作为输入，不写死进通用规则）
2. 理解参考图及使用范围（`referenceUsage`: roles / useFor / ignore）
3. 处理资料冲突（产品关系 / AI 状态 vs 主张的事实）
4. 组织方案与提示词（设计说明、参考安排、生图提示词、待确认问题）

## dry_run 预览

```bash
cd backend
uv run python -m backend.skill_preview --family main --case ../skills/cases/car-light-main.case.json
```

输出包含：加载的规则文件列表、组装后的模型请求、参考图 ID 与顺序对照表、字段映射说明。

**本轮不调用模型、不出图。** 模型调用与实际出图列入下一轮。
