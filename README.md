# InkMill-01 · 油墨研磨台账

面向印刷油墨研磨车间的**研磨机状态、粘度取样、研磨遍次与换钵洗机工单**台账系统。  
**不是**库存、电商或 CMS 场景。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11、Flask、SQLAlchemy、PyMySQL、Flask-JWT-Extended、passlib/bcrypt、gunicorn |
| 前端 | Svelte 4、Vite、TypeScript |
| 数据库 | MySQL 8 |

## 端口与数据库

| 服务 | 宿主机端口 |
|------|------------|
| 统一入口 (Nginx) | **4200** |
| 后端 API | **9200** |
| MySQL | **3312** |

MySQL 连接：`inkmill` / `inkmill` / `inkmill`（库名/用户/密码）

## 演示账号

密码均为 **123456**：

- `admin` — 管理员
- `grinder` — 研磨工

## 领域实体（JSON 驼峰）

1. **Workshop**：`name`, `site`, `notes`
2. **Mill**：`workshopId`, `millCode`（同车间唯一）, `pigmentBase`, `bowlLiters`, `status`（`grinding` \| `idle` \| `wash`）；列表接口额外返回 `openWashOrderId` / `openWashOrderStatus`（无开放洗机工单时为 `null`）
3. **ViscositySample**：`millId`, `sampledAt`, `viscosityPaS`（须 &gt; 0，否则 HTTP 400）, `tempC`, `notes`
4. **GrindPass**：`millId`, `startedAt`, `passNo`（≥ 1）, `durationMin`（&gt; 0）, `mediaType`, `operatorName`
5. **BowlWashOrder（换钵洗机工单）**：`millId`, `reason`, `plannedAt`, `status`, `operatorName`, `createdAt`
6. **Dashboard**：`workshopTotal`, `grindingMillCount`, `samplesLast24h`, `passesLast7d`

### 洗机工单状态机（不允许绕过接口直接改状态）

状态：`open`（待清洗）→ `washing`（清洗中）→ `done`（已完成）；`open` / `washing` 均可 → `void`（已作废）。`done` / `void` 为终态。

- `POST /api/bowl-wash-orders` 创建工单，初始状态 `open`。**同一 Mill 同时只允许一个 `open`/`washing` 工单**，重复创建返回 HTTP 409。
- `POST /api/bowl-wash-orders/{id}/start`：仅 `open` 可调，置为 `washing`。开始时若 Mill 不是 `wash` 状态，默认返回 **HTTP 409**，要求先在研磨机页面把机台置为 `wash`；也允许在请求体传 `{"syncMillStatus": true}` **工单内联动**——接口在同一事务内先把 Mill 置为 `wash` 再推进工单（仅这一处联动，其余状态不互改；完成/作废工单不会自动改机台状态）。
- `POST /api/bowl-wash-orders/{id}/complete`：仅 `washing` 可调，置为 `done`，否则 409。
- `POST /api/bowl-wash-orders/{id}/void`：仅 `open` / `washing` 可调，置为 `void`；终态再操作返回 409。
- `GET /api/bowl-wash-orders?millId=` 列表，可按机台筛选。

前端「洗机工单」页（侧栏入口）：按机台筛选、新建工单、详情面板执行流转；`open → washing` 时可勾选联动置 wash。研磨机列表以徽标显示该机台是否存在开放工单。

## 快速启动（Docker）

```bash
cd InkMill-01
docker compose up --build -d
```

浏览器访问：**http://localhost:4200**  
前端 Nginx 将 `/api/` 反向代理到后端 `9200`。

后端容器启动流程：

1. 等待 MySQL 就绪（`DB_HOST=mysql`）
2. SQLAlchemy `create_all` 建表
3. `SEED_ON_START=true` 时写入演示数据
4. gunicorn 监听 `0.0.0.0:9200`

健康检查：`GET /api/health` → `{"status":"ok","service":"InkMill"}`

## 本地开发（可选）

**后端**（需本机 MySQL 或连 Docker 的 3312 端口）：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set DB_HOST=127.0.0.1
set DB_PORT=3312
set DB_USER=inkmill
set DB_PASSWORD=inkmill
set DB_NAME=inkmill
set JWT_SECRET=inkmill-jwt-secret-change-me
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
gunicorn wsgi:app --bind 127.0.0.1:9200 --reload
```

**前端**：

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器端口 **4200**，`/api` 代理到 `127.0.0.1:9200`。

## 目录结构

```
InkMill-01/
├── docker-compose.yml
├── nginx/nginx.conf          # 4200 统一入口，/api → backend
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── wsgi.py
│   └── app/                  # Flask 路由、模型与种子数据
└── frontend/
    ├── Dockerfile
    ├── vite.config.ts
    └── src/routes/           # Login / Dashboard / CRUD 页面
```

## UI 主题

墨黑底 + 朱砂强调色，无紫色光晕风格。
