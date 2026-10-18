# BS3 · Vercel 部署版

这是原项目 [Nujihs/BS3](https://github.com/Nujihs/BS3)（简谱转十孔口琴 BD 谱系统）的 **Vercel 适配改造版**。原仓库代码未做任何改动，本目录为独立新项目。

## 一、为什么原项目无法直接部署 Vercel（改造背景）

| 原项目 | Vercel 限制 | 本版处理 |
| --- | --- | --- |
| 常驻 Flask 双服务（5000/5001） | 只有 Serverless 函数 | 单函数 `api/index.py` + DispatcherMiddleware 挂载主应用与后台管理 |
| 前端为 Jinja2 模板渲染 | 静态托管不渲染模板 | 首页静态化到 `public/`，由 Vercel 静态托管；后台管理保留 Jinja2（函数内可渲染） |
| SQL Server + pyodbc + ODBC 驱动 | 无驱动、无数据库 | 迁移到 **PostgreSQL**（`psycopg2`），支持 `DATABASE_URL`（Neon / Supabase / Vercel Postgres） |
| EasyOCR（PyTorch + OpenCV，数百 MB） | 超过函数体积/时长限制 | 移除，图片识别改为**可插拔外部 OCR API**；未配置时文本转换不受影响 |
| 音频写 `output/` 后经 `/static/audio/` 提供 | 文件系统只读、不持久 | 音频直接以 **base64 data URI** 内联返回，前端可直接播放/下载 |
| 仓库提交了 `.env` | 密钥泄露风险 | `.env` 已加入 `.gitignore` |

## 二、项目结构

```
BS3-vercel/
├── api/index.py              # Vercel Serverless 入口（WSGI 适配 + 双应用挂载 + 路径恢复）
├── vercel.json               # rewrites（含 __path 路径传递）与函数配置
├── public/                   # Vercel 静态托管根：index.html + static/
│   ├── index.html            # 静态化后的首页（无 Jinja2 语法）
│   └── static/               # CSS / 图片资源
├── backend/
│   ├── app.py                # 主应用（认证/转换/历史，PostgreSQL + 音频 base64 + OCR 可插拔）
│   ├── admin_app.py          # 后台管理（PostgreSQL 版，NamedTupleCursor）
│   ├── auth_pg.py            # 认证模块（PostgreSQL）
│   ├── database_manager_pg.py# 数据管理（PostgreSQL）
│   ├── db_pg.py              # 连接封装（DATABASE_URL / 分项变量）
│   ├── ocr_client.py         # 外部 OCR API 客户端（可配置）
│   ├── config.py             # 音乐理论映射（未改动）
│   ├── main.py               # 转换控制器（图片入口改为 OCR 客户端）
│   ├── music_theory.py       # 简谱解析（未改动）
│   ├── bd_generator.py       # BD 谱生成（未改动）
│   └── audio_synthesizer.py  # 音频合成（新增 to_wav_bytes）
├── admin/                    # 后台管理模板与静态资源（Jinja2，函数内渲染）
├── public/                   # 前端唯一源：index.html（静态化）+ static/（Vercel 静态托管与本地 Flask 渲染共用）
├── schema.sql                # PostgreSQL 表结构
├── create_db.py              # 数据库初始化脚本
├── requirements.txt          # 精简依赖（无 easyocr/opencv/scipy/pyodbc）
├── .env.example              # 环境变量示例
├── .vercelignore             # 排除 legacy/、.env 等
├── legacy/                   # 原 SQL Server / EasyOCR 代码归档（不参与部署）
└── test_vercel_flow.py       # 主应用全流程测试脚本
    test_vercel_handler.py    # Vercel handler 适配层模拟测试脚本
```

## 三、本地运行（已在本机测试通过）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备 PostgreSQL 并初始化
#    （本地示例：用户 jianpu / 密码 jianpu123 / 库 jianpu_db）
python create_db.py

# 3. 配置环境变量（复制 .env.example 为 .env，填写 DATABASE_URL）

# 4. 启动主应用（端口 5000）
python backend/app.py

# 5. （可选）启动后台管理（端口 5001）
python backend/admin_app.py
```

访问：
- 主应用：http://127.0.0.1:5000
- 后台管理：http://127.0.0.1:5001（账号 admin / admin123）

## 四、部署到 Vercel

### 方式 A：GitHub 导入（推荐）
1. 将本目录推送到一个新的 GitHub 仓库（**不要**推回原 BS3 仓库）。
2. Vercel 控制台 → Add New Project → Import 该仓库。
3. 框架预设保持默认（Vercel 会自动识别 Python + 静态 `public/`）。
4. 在 Project Settings → Environment Variables 中配置：
   | 变量 | 说明 |
   | --- | --- |
   | `DATABASE_URL` | 托管 PostgreSQL 连接串（Neon / Supabase / Vercel Postgres，免费额度即可） |
   | `FLASK_SECRET_KEY` | 随机长字符串 |
   | `OCR_API_URL` / `OCR_API_KEY` | 可选，图片识别需要 |
5. Deploy。构建时 Vercel 会执行 `pip install -r requirements.txt` 并把 `public/` 作为静态根、`api/index.py` 作为 Serverless 函数。

### 方式 B：Vercel CLI
```bash
npm i -g vercel
vercel login
vercel deploy   # 在项目目录内，按提示配置环境变量
```

### 数据库初始化
托管 PostgreSQL 建好后，在 Neon / Supabase 控制台（或 psql）执行 `schema.sql`，或在部署前本地执行 `python create_db.py`（`DATABASE_URL` 指向托管库）。

## 五、路由约定（vercel.json）

- `public/` 静态文件（首页、CSS、图片）由 Vercel 直接托管。
- 所有 `api/*`、`admin/*` 及未匹配路径通过 rewrite 进入 `api/index.py`。
- rewrite 会把原始路径放进 `__path` query 参数，`api/index.py` 在进入 WSGI 前恢复 `PATH_INFO`，保证 Flask 路由正确（这是 Flask 上 Vercel 的关键点）。
- 后台管理挂载在 `/admin` 前缀（DispatcherMiddleware）。

## 六、已完成的本地测试（2026-10-18）

| 测试 | 结果 |
| --- | --- |
| 主应用全流程（注册/登录/Token/文本转换/BD谱图片/口琴图示/音频WAV/历史/鉴权/登出/OCR提示） | 18/18 通过 |
| 后台管理（登录/仪表板/用户列表/详情/转换记录/会话/统计/未登录拦截） | 全部通过 |
| Vercel handler 模拟（路径恢复、双应用挂载、404、表单登录） | 6/6 通过 |

## 七、已知限制与说明

1. **图片 OCR**：原 EasyOCR 无法在 Serverless 运行，图片识别需配置外部 OCR API（`ocr_client.py` 已实现通用协议：POST 图片 + Bearer 鉴权 + 可配置文本字段）。未配置时返回明确提示。
2. **后台管理密码**：沿用原项目硬编码 `admin/admin123`，生产环境请自行改为数据库校验或环境变量。
3. **音频大小**：音频以 base64 内联返回，长曲目会增大响应体；如需流式播放可后续接入对象存储。
4. **函数时长**：`vercel.json` 配置了 `maxDuration: 60`（Hobby 上限），转换+合成在测试中远低于该值。
