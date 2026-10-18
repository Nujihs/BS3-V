# 口琴谱生成器 Jianpu to BD

一个基于Flask的简谱转换为C调十孔口琴BD谱的Web应用系统。

## 系统概述

本系统包含两个独立运行的Web服务：

1. **主服务器（端口5000）**：简谱转换服务
   - 用户注册登录
   - 简谱文本/图片转换
   - 历史记录管理
   - 音频生成和播放

2. **后台管理系统（端口5001）**：数据管理平台
   - 用户管理
   - 转换记录管理
   - 会话管理
   - 数据统计

## 主要功能

- 简谱转换：支持文本和图片输入
- 可视化展示：生成BD谱和口琴用孔示意图
- 音频播放：生成口琴演奏音频
- 用户认证：注册、登录、修改密码、重置密码
- 历史记录：保存和查询转换历史
- 后台管理：完整的CRUD操作
- 响应式设计：支持桌面端和移动端

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     口琴谱生成器系统                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │   用户前端界面      │         │   管理后台界面      │       │
│  │   (端口5000)        │         │   (端口5001)        │       │
│  └──────────┬──────────┘         └──────────┬──────────┘       │
│             │                               │                   │
│             │ HTTP API                     │ HTTP API          │
│             ▼                               ▼                   │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │   主应用服务        │         │   管理后台服务      │       │
│  │   (Flask)          │         │   (Flask)          │       │
│  └──────────┬──────────┘         └──────────┬──────────┘       │
│             │                               │                   │
│             │ 业务逻辑层                    │ 业务逻辑层          │
│             ▼                               ▼                   │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │  转换处理模块       │         │  数据管理模块       │       │
│  │  - 简谱解析         │         │  - 用户CRUD        │       │
│  │  - BD谱生成         │         │  - 记录CRUD        │       │
│  │  - 音频合成         │         │  - 会话管理        │       │
│  │  - OCR识别          │         │  - 统计分析        │       │
│  └──────────┬──────────┘         └──────────┬──────────┘       │
│             │                               │                   │
│             └───────────┬───────────────────┘                   │
│                         ▼                                       │
│              ┌──────────────────────┐                           │
│  ┌───────────┤    数据访问层       │                           │
│  │           └──────────────────────┘                           │
│  │                     │                                         │
│  │                     ▼                                         │
│  │           ┌──────────────────────┐                           │
│  │           │   SQL Server数据库   │                           │
│  │           │   - users            │                           │
│  │           │   - conversions      │                           │
│  │           │   - sessions         │                           │
│  │           └──────────────────────┘                           │
│  └────────────────────────────────────────────────────────────┘
```

---

## 前端页面布局

### 桌面端布局（>1024px）

```
┌────────────────────────────────────────────────────────────────┐
│  Logo (口琴谱生成器 | Jianpu to BD)  | 主题切换 | 用户头像      │
├──────────────┬─────────────────────────────────────────────────┤
│              │                                                 │
│  侧边栏      │         主内容区                                │
│  (固定宽度)  │                                                 │
│              │  ┌──────────────────────────────────────┐    │
│  ┌────────┐ │  │                                      │    │
│  │ Logo   │ │  │       简谱转换面板                     │    │
│  │ 图标   │ │  │   - 文本输入 / 图片上传               │    │
│  ├────────┤ │  │   - 调号选择 / 口琴类型               │    │
│  │ 口琴谱 │ │  │   - 转换按钮                         │    │
│  │ 生成器 │ │  └──────────────────────────────────────┘    │
│  ├────────┤ │                                                 │
│  │ Jianpu │ │  ┌──────────────────────────────────────┐    │
│  │ to BD  │ │  │                                      │    │
│  ├────────┤ │  │       结果展示区                       │    │
│  │ 导航   │ │  │   - BD谱文字（可复制）                │    │
│  │ 菜单   │ │  │   - 口琴用孔示意图（可下载）             │    │
│  ├────────┤ │  │   - 演奏分析                         │    │
│  │        │ │  │   - 音频播放器                       │    │
│  │ - 转换 │ │  └──────────────────────────────────────┘    │
│  │ - 历史 │ │                                                 │
│  │ - 设置 │ │  ┌──────────────────────────────────────┐    │
│  │ - 关于 │ │  │                                      │    │
│  └────────┘ │  │       历史记录（可选显示）             │    │
│              │  └──────────────────────────────────────┘    │
│              │                                                 │
│  ┌────────┐ │                                                 │
│  │ 用户   │ │                                                 │
│  │ 信息   │ │                                                 │
│  ├────────┤ │                                                 │
│  │ 头像   │ │                                                 │
│  │ 用户名 │ │                                                 │
│  └────────┘ │                                                 │
└──────────────┴─────────────────────────────────────────────────┘
```

### 移动端布局（<768px）

```
┌─────────────────────────────────┐
│ ☰  口琴谱生成器  | 🌙 | 👤      │
├─────────────────────────────────┤
│                                 │
│     主内容区（全屏显示）          │
│                                 │
│  ┌─────────────────────────┐   │
│  │                         │   │
│  │    简谱转换面板          │   │
│  │                         │   │
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │                         │   │
│  │    结果展示区            │   │
│  │                         │   │
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │                         │   │
│  │    历史记录              │   │
│  │                         │   │
│  └─────────────────────────┘   │
│                                 │
└─────────────────────────────────┘

侧边栏（点击菜单按钮滑出）：
┌─────────────────────────────────┐
│  [×]                           │
├─────────────────────────────────┤
│                                 │
│  Logo   口琴谱生成器            │
│  图标   Jianpu to BD            │
│                                 │
│  ────────────────────────      │
│                                 │
│  📊 转换                        │
│  📜 历史                        │
│  ⚙️  设置                       │
│  ℹ️  关于                       │
│                                 │
└─────────────────────────────────┘
```

---

## 前端组件架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端页面 (index.html)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────┐            │
│  │                  布局组件                        │            │
│  ├─────────────────────────────────────────────────┤            │
│  │  - 顶部导航栏 (Top Bar) - 移动端显示菜单按钮     │            │
│  │  - 侧边栏导航 (Sidebar) - 桌面端固定            │            │
│  │  - 主内容区 (Main Content)                     │            │
│  └────────────┬────────────────────────────────────┘            │
│               │                                             │
│  ┌────────────┴────────────────────────────────────┐            │
│  │                功能组件                          │            │
│  ├──────────────────────────────────────────────────┤            │
│  │  - 登录/注册模态框 (Auth Modal)                 │            │
│  │  - 简谱转换器 (Converter Panel)                  │            │
│  │  - 结果展示区 (Result Panel)                    │            │
│  │  - 历史记录列表 (History List)                  │            │
│  │  - 音频播放器 (Audio Player)                   │            │
│  │  - 主题切换器 (Theme Toggler)                  │            │
│  │  - 用户菜单 (User Menu)                        │            │
│  └────────────┬────────────────────────────────────┘            │
│               │                                             │
│  ┌────────────┴────────────────────────────────────┐            │
│  │                工具函数 (Utils)                   │            │
│  ├──────────────────────────────────────────────────┤            │
│  │  - API请求封装 (fetchAPI)                        │            │
│  │  - Token管理 (Token Manager)                     │            │
│  │  - 本地存储管理 (Storage Manager)               │            │
│  │  - 工具函数 (Helper Functions)                  │            │
│  │  - 主题管理 (Theme Manager)                     │            │
│  └──────────────────────────────────────────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 数据流程图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   用户输入   │────▶│  前端界面   │────▶│  API请求    │
│ (文本/图片)  │     │   (HTTP)    │     │  (JSON)     │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                       ┌─────────────┐
                                       │ Flask路由    │
                                       │  (app.py)   │
                                       └─────────────┘
                                               │
         ┌───────────────────────────────────┼───────────────────────────┐
         │                                   │                           │
         ▼                                   ▼                           ▼
  ┌─────────────┐                   ┌─────────────┐             ┌─────────────┐
  │  认证模块    │                   │  转换模块    │             │  历史记录    │
  │ (auth)      │                   │  (main)     │             │ (database)  │
  └─────────────┘                   └─────────────┘             └─────────────┘
         │                                   │                           │
         ▼                                   ▼                           ▼
  ┌─────────────┐                   ┌─────────────┐             ┌─────────────┐
  │  会话管理    │                   │  简谱解析    │             │  数据库操作  │
  │ (sessions)  │                   │ (music_theory)│            │ (SQL Server)│
  └─────────────┘                   └─────────────┘             └─────────────┘
                                               │
         ┌───────────────────────────────────┼───────────────────────────┐
         │                                   │                           │
         ▼                                   ▼                           ▼
  ┌─────────────┐                   ┌─────────────┐             ┌─────────────┐
  │  OCR识别    │                   │  BD谱生成   │             │  音频合成    │
  │ (EasyOCR)   │                   │(bd_generator)│            │(audio)      │
  └─────────────┘                   └─────────────┘             └─────────────┘
                                               │
                                               ▼
                                       ┌─────────────┐
                                       │  返回结果    │
                                       │ (JSON)      │
                                       └─────────────┘
                                               │
                                               ▼
                                       ┌─────────────┐
                                       │  前端展示    │
                                       │ (HTML/JS)   │
                                       └─────────────┘
```

---

## 技术栈

### 前端
- HTML5, CSS3, JavaScript ES6+
- Tailwind CSS 3.x（响应式设计）
- html2canvas 1.x（图片生成）

### 后端
- Python 3.8+
- Flask 3.x（Web框架）
- EasyOCR 1.7.0+（OCR识别）
- NumPy 1.24.0+（数值计算）
- SciPy 1.11.0+（科学计算）
- Pillow 10.0.0+（图像处理）
- soundfile 0.12.0+（音频处理）

### 数据库
- SQL Server 2016+
- PyODBC 5.0+（数据库驱动）

---

## 数据库设计

### （一）需求分析

系统主要需求如下：

**（1）普通用户功能**
- 用户注册与登录
- 简谱文本输入转换
- 简谱图片上传识别
- 查看转换结果（BD谱、口琴用孔示意图、音频）
- 下载BD谱和音频文件
- 查看个人历史转换记录
- 删除历史转换记录
- 修改个人密码
- 切换日间/夜间主题
- 用户登出

**（2）管理员功能**
- 登录系统
- 查看所有用户信息列表（支持分页和搜索）
- 创建新用户
- 编辑用户信息
- 删除用户
- 修改用户密码
- 查看所有转换记录
- 查看转换记录详情
- 删除转换记录
- 查看会话列表
- 删除指定会话
- 清理过期会话
- 查看系统统计数据（用户数、转换数、会话数等）

**（3）数据一致性要求**
- 用户删除时，删除该用户的所有会话记录
- 用户删除时，保留该用户的转换记录（作为历史数据），但user_id置为NULL
- 会话自动过期机制
- Token唯一性约束

### （二）概念设计

关系数据库中包含以下实体及联系：

**（1）用户实体**
每个用户有自己的用户ID、用户名、密码哈希、邮箱、注册时间、最后登录时间等属性。
- 用户ID（主键）：自增整数
- 用户名（唯一）：登录账号
- 密码哈希：加密存储的密码
- 邮箱（唯一）：用户联系邮箱
- 注册时间：用户创建时间
- 最后登录时间：最近登录时间

**（2）转换记录实体**
每次简谱转换产生一条转换记录，包含输入内容、参数设置、转换结果等。
- 记录ID（主键）：自增整数
- 用户ID（外键）：关联用户（可为NULL，表示匿名用户）
- 输入文本：简谱文本内容
- 输入图片：简谱图片（Base64编码）
- 调号：原始调号（C、G、F、D等）
- 口琴类型：口琴类型（C、D、F、G、LowC等）
- BD谱文本：转换后的BD谱
- BD谱图片：口琴用孔示意图（Base64编码）
- 演奏分析：分析结果（JSON格式）
- 转换时间：转换操作时间

**（3）会话实体**
用户登录后创建会话记录，用于身份验证。
- 会话ID（主键）：自增整数
- 用户ID（外键）：关联用户
- Token（唯一）：会话令牌
- 过期时间：会话失效时间
- 创建时间：会话创建时间

**（4）实体间联系**
- 用户与转换记录：一个用户可以有多条转换记录，一条转换记录属于一个用户（或匿名）→ 1:N关系
- 用户与会话：一个用户可以有多个会话，一个会话属于一个用户 → 1:N关系

对应所有实体和联系，ER图如下：

![ER图](ER图.png)

### （三）逻辑设计

对应概念设计的ER图，设计相应的关系模式，包含以下表：

**（1）用户表users**

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|---------|------|------|
| id | INT | PRIMARY KEY, IDENTITY | 用户ID，主键，自增 |
| username | NVARCHAR(50) | UNIQUE NOT NULL | 用户名，唯一，非空 |
| password_hash | NVARCHAR(255) | NOT NULL | 密码哈希（SHA256+盐值），非空 |
| email | NVARCHAR(100) | UNIQUE NOT NULL | 邮箱，唯一，非空 |
| created_at | DATETIME2 | NOT NULL | 注册时间，非空，默认为当前时间 |
| last_login | DATETIME2 | NULL | 最后登录时间，可为空 |

SQL语句：
```sql
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(50) UNIQUE NOT NULL,
    password_hash NVARCHAR(255) NOT NULL,
    email NVARCHAR(100) UNIQUE NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    last_login DATETIME2 NULL
);
```

**（2）转换记录表conversions**

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|---------|------|------|
| id | INT | PRIMARY KEY, IDENTITY | 记录ID，主键，自增 |
| user_id | INT | FOREIGN KEY | 用户ID，外键，可为NULL（匿名用户） |
| input_text | NVARCHAR(MAX) | NULL | 输入的简谱文本 |
| input_image | NVARCHAR(MAX) | NULL | 输入的简谱图片（Base64） |
| key_signature | NVARCHAR(10) | NOT NULL | 调号（C、G、F、D、Bb等） |
| harmonica_type | NVARCHAR(10) | NOT NULL | 口琴类型（C、D、F、G、LowC等） |
| bd_text | NVARCHAR(MAX) | NOT NULL | 转换后的BD谱文本 |
| bd_image | NVARCHAR(MAX) | NULL | 指法图（Base64编码） |
| analysis | NVARCHAR(MAX) | NULL | 演奏分析（JSON格式） |
| created_at | DATETIME2 | NOT NULL | 转换时间，非空，默认为当前时间 |

外键约束：
```sql
ALTER TABLE conversions
ADD CONSTRAINT fk_conversions_user
FOREIGN KEY (user_id) REFERENCES users(id)
ON DELETE SET NULL;
```

SQL语句：
```sql
CREATE TABLE conversions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NULL,
    input_text NVARCHAR(MAX) NULL,
    input_image NVARCHAR(MAX) NULL,
    key_signature NVARCHAR(10) NOT NULL,
    harmonica_type NVARCHAR(10) NOT NULL,
    bd_text NVARCHAR(MAX) NOT NULL,
    bd_image NVARCHAR(MAX) NULL,
    analysis NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT fk_conversions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

**（3）会话表sessions**

| 字段名 | 数据类型 | 约束 | 说明 |
|--------|---------|------|------|
| id | INT | PRIMARY KEY, IDENTITY | 会话ID，主键，自增 |
| user_id | INT | FOREIGN KEY NOT NULL | 用户ID，外键，非空 |
| token | NVARCHAR(255) | UNIQUE NOT NULL | 会话令牌，唯一，非空 |
| expires_at | DATETIME2 | NOT NULL | 过期时间，非空 |
| created_at | DATETIME2 | NOT NULL | 创建时间，非空，默认为当前时间 |

外键约束：
```sql
ALTER TABLE sessions
ADD CONSTRAINT fk_sessions_user
FOREIGN KEY (user_id) REFERENCES users(id)
ON DELETE CASCADE;
```

SQL语句：
```sql
CREATE TABLE sessions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,
    token NVARCHAR(255) UNIQUE NOT NULL,
    expires_at DATETIME2 NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

### （四）数据库关系图

- **users (1) ↔ conversions (N)**: 一个用户可以有多条转换记录
  - 外键：conversions.user_id → users.id
  - 级联规则：ON DELETE SET NULL（用户删除时保留转换记录）

- **users (1) ↔ sessions (N)**: 一个用户可以有多个会话
  - 外键：sessions.user_id → users.id
  - 级联规则：ON DELETE CASCADE（用户删除时删除所有会话）

![系统架构图](系统架构图.png)
![用例图](用例图.png)

---

## 项目结构

```
BS2/
├── backend/                     # 后端代码
│   ├── app.py                   # 主应用服务器（端口5000）
│   ├── admin_app.py             # 后台管理系统（端口5001）
│   ├── main.py                  # 简谱转换控制器
│   ├── music_theory.py          # 音乐理论转换
│   ├── bd_generator.py          # BD谱生成器
│   ├── audio_synthesizer.py     # 音频合成器
│   ├── final_jianpu_pipeline.py # 简谱识别流程
│   ├── jianpu_segmenter.py      # 图像分割模块
│   ├── config.py                # 系统配置
│   ├── auth_sqlserver.py        # 用户认证管理
│   ├── database_manager_sqlserver.py # 数据库操作
│   └── db_config.py             # 数据库配置
│
├── frontend/                    # 前端代码
│   ├── templates/
│   │   └── index.html          # 主应用页面
│   └── static/
│       ├── css/
│       ├── images/
│       └── js/
│
├── admin/                      # 后台管理界面
│   └── templates/
│       ├── base.html            # 基础模板
│       ├── login.html           # 登录页面
│       ├── dashboard.html       # 仪表板
│       ├── users.html           # 用户列表
│       ├── user_form.html       # 用户表单
│       ├── user_detail.html     # 用户详情
│       ├── change_password.html # 修改密码
│       ├── conversions.html      # 转换记录列表
│       ├── conversion_detail.html # 转换记录详情
│       └── sessions.html       # 会话列表
│
├── output/                     # 音频输出文件
├── database/                   # 数据库相关文件
├── create_sql_server_db.py     # 数据库初始化脚本
├── requirements.txt             # Python依赖包
├── .env.example                # 环境变量示例
└── README.md                   # 项目说明文档
```

---

## 快速开始

### 环境要求

- **Python** 3.8 或更高版本
- **SQL Server** 2017 或更高版本
- **ODBC Driver 17 for SQL Server**

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd BS2
   ```

2. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置数据库**

   复制 `.env.example` 创建 `.env` 文件：
   ```env
   # SQL Server 配置
   SQL_SERVER_DRIVER={ODBC Driver 17 for SQL Server}
   SQL_SERVER_SERVER=localhost
   SQL_SERVER_DATABASE=JianpuDB
   SQL_SERVER_TRUSTED_CONNECTION=yes
   
   # Flask 密钥
   FLASK_SECRET_KEY=your-secret-key-here
   ```

4. **初始化数据库**

   ```bash
   python create_sql_server_db.py
   ```

5. **启动服务**

   **启动主服务器（端口5000）**
   
   Windows:
   ```bash
   start.bat
   ```
   
   Linux/Mac:
   ```bash
   bash start.sh
   ```

   **启动后台管理（端口5001）**
   
   Windows:
   ```bash
   start_admin.bat
   ```
   
   Linux/Mac:
   ```bash
   bash start_admin.sh
   ```

6. **访问系统**

   - **主应用**：http://127.0.0.1:5000
   - **后台管理**：http://127.0.0.1:5001
     - 默认账号：`admin`
     - 默认密码：`admin123`

---

## API接口

### 主服务器 API (端口: 5000)

#### 认证接口
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/verify` - 验证Token
- `POST /api/auth/logout` - 用户登出
- `POST /api/auth/change-password` - 修改密码
- `POST /api/auth/reset-password` - 重置密码
- `POST /api/auth/verify-username` - 验证用户名是否存在

#### 转换接口
- `POST /api/convert/text` - 文本转BD谱
- `POST /api/convert/image` - 图片转BD谱
- `GET /static/audio/<filename>` - 获取音频文件

#### 历史记录接口
- `GET /api/conversions` - 获取历史记录
- `GET /api/conversions/<id>` - 获取单条记录
- `DELETE /api/conversions/<id>` - 删除历史记录

### 后台管理 API (端口: 5001)

#### 用户管理
- `GET /users` - 用户列表（支持分页、搜索）
- `GET /users/<id>` - 用户详情
- `POST /users/new` - 创建用户
- `POST /users/<id>/edit` - 编辑用户
- `POST /users/<id>/delete` - 删除用户
- `POST /users/<id>/change-password` - 修改用户密码

#### 转换记录管理
- `GET /conversions` - 转换记录列表
- `GET /conversions/<id>` - 记录详情
- `POST /conversions/<id>/delete` - 删除记录

#### 会话管理
- `GET /sessions` - 会话列表
- `POST /sessions/<id>/delete` - 删除会话
- `POST /sessions/clear-expired` - 清理过期会话

#### 统计数据
- `GET /api/stats` - 获取统计数据（用户数、转换数、会话数、调号分布、口琴类型分布）

---

## 使用说明

### 简谱转换

1. **注册/登录账号**
   - 首次使用需要注册账号
   - 已有账号直接登录

2. **选择输入方式**
   - **文本输入**：直接输入简谱文本（如：`1 2 3 4 5 6 7`）
   - **图片识别**：上传简谱图片，自动OCR识别

3. **设置参数**
   - 选择调号（C、G、F、D、Bb等）
   - 选择口琴类型（C、D、F、G等）

4. **执行转换**
   - 点击"转换"按钮
   - 等待处理完成

5. **查看结果**
   - BD谱文本：可复制
   - 口琴用孔示意图：口琴实物图，高亮显示孔位
   - 演奏分析：难度级别、技巧要求
   - 音频预览：在线播放

### 历史记录

- 登录后自动加载个人历史记录
- 点击历史记录可快速查看完整结果
- 支持删除单条记录

### 用户设置

- 点击头像打开用户菜单
- 修改密码
- 切换日间/夜间主题
- 退出登录

---

## 常见问题

### 数据库连接失败

**问题**：无法连接到SQL Server

**解决方案**：
1. 确认SQL Server服务已启动
2. 检查ODBC驱动是否正确安装（ODBC Driver 17 for SQL Server）
3. 验证`.env`文件中的连接配置
4. 如果使用Windows身份验证，确认`TRUSTED_CONNECTION=yes`

### 简谱识别不准确

**问题**：OCR识别的简谱不准确

**解决方案**：
1. 确保图片清晰、对比度高
2. 简谱符号完整无遮挡
3. 可以手动输入简谱文本
4. 尝试使用更高分辨率的图片

### 音频无法播放

**问题**：音频文件无法播放

**解决方案**：
1. 检查浏览器是否支持WAV格式
2. 确认音频文件已正确生成在`output/`目录
3. 检查音频合成模块是否正常工作

### 后台管理无法访问

**问题**：无法访问后台管理系统

**解决方案**：
1. 确认后台管理服务已启动（端口5001）
2. 检查防火墙设置
3. 确认已正确登录（账号：admin，密码：admin123）

---

## 部署说明

### 生产环境部署

1. **修改配置文件**
   - 更新 `.env` 文件中的数据库连接信息
   - 修改 `FLASK_SECRET_KEY` 为随机生成的密钥

2. **使用Gunicorn部署（推荐）**
   ```bash
   # 安装 Gunicorn
   pip install gunicorn

   # 启动主服务器
   gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app

   # 启动后台管理
   gunicorn -w 2 -b 0.0.0.0:5001 backend.admin_app:app
   ```

3. **使用Nginx反向代理**
   ```nginx
   # 主服务器配置
   server {
       listen 80;
       server_name your-domain.com;
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }

   # 后台管理配置
   server {
       listen 81;
       server_name admin.your-domain.com;
       location / {
           proxy_pass http://127.0.0.1:5001;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

4. **使用Systemd管理服务**
   ```ini
   # /etc/systemd/system/jianpu-main.service
   [Unit]
   Description=Jianpu to BD Main Server
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/BS2
   Environment="PATH=/path/to/venv/bin"
   ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 backend.app:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

### Docker部署

1. **创建Dockerfile**
   ```dockerfile
   FROM python:3.9-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   EXPOSE 5000 5001

   CMD ["python", "backend/app.py"]
   ```

2. **创建docker-compose.yml**
   ```yaml
   version: '3.8'

   services:
     main:
       build: .
       ports:
         - "5000:5000"
       environment:
         - FLASK_SECRET_KEY=${SECRET_KEY}
         - SQL_SERVER_SERVER=sqlserver
       depends_on:
         - sqlserver

     admin:
       build: .
       command: python backend/admin_app.py
       ports:
         - "5001:5001"
       environment:
         - FLASK_SECRET_KEY=${SECRET_KEY}
         - SQL_SERVER_SERVER=sqlserver
       depends_on:
         - sqlserver

     sqlserver:
       image: mcr.microsoft.com/mssql/server:2019-latest
       environment:
         - ACCEPT_EULA=Y
         - SA_PASSWORD=YourStrong@Passw0rd
       ports:
         - "1433:1433"
   ```

---

## 性能优化

### 数据库优化

1. **添加索引**
   ```sql
   CREATE INDEX idx_conversions_user ON conversions(user_id);
   CREATE INDEX idx_conversions_created ON conversions(created_at DESC);
   CREATE INDEX idx_sessions_user ON sessions(user_id);
   CREATE INDEX idx_sessions_expires ON sessions(expires_at);
   ```

2. **定期清理过期会话**
   ```python
   # 在后端定时任务中添加
   from datetime import datetime, timedelta
   def cleanup_expired_sessions():
       cutoff = datetime.now() - timedelta(days=30)
       db.execute("DELETE FROM sessions WHERE expires_at < ?", (cutoff,))
   ```

3. **使用连接池**
   ```python
   # 在 db_config.py 中配置
   SQL_SERVER_SETTINGS = {
       'pool_size': 10,
       'max_overflow': 20,
       'pool_timeout': 30,
       'pool_recycle': 3600
   }
   ```

### 前端优化

1. **启用资源压缩**
   ```nginx
   gzip on;
   gzip_types text/plain text/css application/json application/javascript text/xml;
   gzip_min_length 1000;
   ```

2. **添加CDN加速**
   - 将静态资源上传到CDN
   - 修改 `base.html` 中的静态资源URL

3. **启用浏览器缓存**
   ```nginx
   location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
       expires 30d;
       add_header Cache-Control "public, immutable";
   }
   ```

---

## 测试说明

### 单元测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试文件
python -m pytest tests/test_auth.py -v

# 生成覆盖率报告
python -m pytest --cov=backend --cov-report=html tests/
```

### API测试

```bash
# 测试登录API
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 测试文本转换API
curl -X POST http://127.0.0.1:5000/api/convert/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"input_text": "1 2 3 4 5", "key": "C", "harmonica": "C"}'
```

---

## 更新日志

### v2.0.0 (2024-04-11)
- ✨ 新增暗夜模式支持
- ✨ 新增用户头像上传功能
- 🎨 优化UI设计，提升用户体验
- 🔧 改进登录界面布局和颜色方案
- 🐛 修复暗夜模式下文字显示问题
- 🐛 修复管理员登录页面样式问题

### v1.0.0 (2024-03-01)
- 🎉 首次发布
- ✨ 实现简谱文本转换功能
- ✨ 实现简谱图片OCR识别
- ✨ 实现BD谱可视化
- ✨ 实现音频合成和播放
- ✨ 实现用户认证系统
- ✨ 实现后台管理系统
- ✨ 支持历史记录管理

---

## 贡献指南

欢迎贡献代码、报告Bug或提出新功能建议！

### 开发流程

1. **Fork项目**
   ```bash
   git clone https://github.com/your-username/BS2.git
   cd BS2
   ```

2. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **提交更改**
   ```bash
   git add .
   git commit -m "Add some feature"
   ```

4. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **提交Pull Request**

### 代码规范

- 遵循PEP 8 Python代码规范
- 使用有意义的变量和函数名
- 添加必要的注释和文档字符串
- 提交前运行测试确保代码质量

---

## 常见问题补充

### 数据库连接失败

**问题**：无法连接到SQL Server

**解决方案**：
1. 确认SQL Server服务已启动
2. 检查ODBC驱动是否正确安装（ODBC Driver 17 for SQL Server）
3. 验证`.env`文件中的连接配置
4. 如果使用Windows身份验证，确认`TRUSTED_CONNECTION=yes`

### 简谱识别不准确

**问题**：OCR识别的简谱不准确

**解决方案**：
1. 确保图片清晰、对比度高
2. 简谱符号完整无遮挡
3. 可以手动输入简谱文本
4. 尝试使用更高分辨率的图片

### 音频无法播放

**问题**：音频文件无法播放

**解决方案**：
1. 检查浏览器是否支持WAV格式
2. 确认音频文件已正确生成在`output/`目录
3. 检查音频合成模块是否正常工作

### 后台管理无法访问

**问题**：无法访问后台管理系统

**解决方案**：
1. 确认后台管理服务已启动（端口5001）
2. 检查防火墙设置
3. 确认已正确登录（账号：admin，密码：admin123）

### 内存占用过高

**问题**：长时间运行后内存占用过高

**解决方案**：
1. 定期重启服务
2. 清理过期的会话记录
3. 限制音频文件缓存大小
4. 考虑使用数据库连接池

---

## 联系方式

- **项目主页**：[GitHub Repository](https://github.com/your-username/BS2)
- **问题反馈**：[Issues](https://github.com/your-username/BS2/issues)
- **邮箱**：your-email@example.com

---

## 致谢

感谢以下开源项目的支持：

- [Flask](https://flask.palletsprojects.com/) - Web框架
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR识别
- [Tailwind CSS](https://tailwindcss.com/) - CSS框架
- [Remix Icon](https://remixicon.com/) - 图标库

---

## 许可证

本项目仅供学习和个人使用。

---

## 项目特色

1. **完整的用户系统**：支持注册、登录、权限管理
2. **双服务架构**：主服务和后台管理分离，便于维护
3. **智能OCR识别**：自动识别简谱图片，减少手动输入
4. **实时音频合成**：基于物理建模的音频生成算法
5. **响应式设计**：完美适配桌面端和移动端
6. **暗夜模式**：护眼设计，提升用户体验
7. **历史记录**：自动保存转换历史，方便追溯
8. **可视化展示**：BD谱和口琴用孔示意图直观展示

---

## 未来计划

- [ ] 支持更多口琴类型（半音阶、和弦口琴等）
- [ ] 添加简谱编辑器功能
- [ ] 支持MIDI导出
- [ ] 添加乐谱分享社区
- [ ] 移动端原生应用开发
- [ ] AI智能纠错功能
- [ ] 多语言支持（英文、日文等）
