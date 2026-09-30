# React + FastAPI Monorepo

JavaScript React (Vite) frontend + FastAPI backend, with dev proxy wiring.

## Structure

```
.
├── backend/     # FastAPI (uv + ruff + pyright)
├── frontend/    # React + Vite (JavaScript)
├── scripts/     # dev.ps1 — start both servers without hanging
└── README.md
```

## Feature notes (图片工作台)

- **商品资料页记录图片自身信息**：`productRelation`（同款同规格 / 其他商品 / 不含商品 / 不确定）与 `aiStatus`（是 / 否 / 不确定）相互独立，备注为 `desc`。
- **图片方案页决定本次怎么用**：`referenceUsage: [{ refImageId, roles, useFor, ignore }]`，角色含主体依据（至多一张）/细节补充/安装与使用/构图参考/视觉风格。数组顺序即使用顺序；素材排序不改写已保存方案。
- **`refImageIds` 与 `referenceUsage` 由后端保持一致**；草稿可缺角色，确认前需补齐；已确认方案内容冻结。
- **「本次参考说明」** 由结构化数据生成预览（如「A图提供灯身外观；B图只补充接口…」），本轮不调用模型。
- **迁移**：启动时幂等映射旧 `source`/`purposes`，旧列保留；被方案引用的参考图不可删除。

## Prerequisites

- [Node.js](https://nodejs.org/) 20+
- [uv](https://docs.astral.sh/uv/)

## Backend

```bash
cd backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Example endpoints: `GET /api/health`, `GET /api/hello?name=...`

Lint / type-check:

```bash
cd backend
uv run ruff check src/
uv run ruff format src/
uv run pyright src/
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:5173
- Vite proxies `/api/*` → `http://localhost:8000`

## Dev workflow

One shot (starts both, waits until ready):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Or manually:

1. Start backend on port 8000 (terminal 1)
2. Start frontend on port 5173 (terminal 2)
3. Open http://localhost:5173 — the page calls `/api/health` and `/api/hello`

Note: on Windows, start long-running servers without `Start-Process -RedirectStandardOutput/-NoNewWindow` (that hangs the shell). Prefer `scripts/dev.ps1`. `npm` is a `.cmd` shim — wrap it as `cmd /c npm run dev`.
