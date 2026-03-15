# ClassIsland 集控服务器社区版

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)

基于 Django 实现的 [ClassIsland](https://github.com/ClassIsland/ClassIsland) 集控服务器及管理面板，兼容 ClassIsland 的 `Cyrene_MSP` 集控协议 v2.0.0.0。

## ✨ 功能特性

- **客户端管理** — 注册、握手认证（PGP 挑战）、在线状态追踪
- **班级组管理** — 创建班级组、分配课表/时间表/科目/教师等 7 种资源
- **命令下发** — 单点/广播发送通知、重启 App、更新配置等命令
- **审计日志** — 记录客户端上报的崩溃、设置变更、课程切换、插件安装等事件
- **配置上传** — 接收客户端上报的课表、时间表、壁纸等配置
- **gRPC 双向流** — 通过持久连接实时推送命令、心跳保活
- **Web 管理面板** — 基于 Bootstrap 5 的响应式后台界面

## 🏗️ 架构概览

```
┌──────────────┐  HTTP (Manifest/Resources)  ┌──────────────────┐
│  ClassIsland  │ ──────────────────────────▶ │                  │
│    Client     │  gRPC (Register/Handshake/  │  Django Server   │
│              │   CommandDeliver/Audit/...)  │  + gRPC Server   │
└──────────────┘ ◀────────────────────────── │                  │
                                              └──────────────────┘
                                                      ▲
                                                      │ HTTP
                                              ┌──────────────────┐
                                              │   管理面板 (Web)   │
                                              │  Bootstrap 5 UI  │
                                              └──────────────────┘
```

### 协议实现

| 协议层 | 实现方式 |
|--------|----------|
| 客户端 HTTP API | Django REST Framework — `/api/v1/client/{cuid}/manifest`, `/api/v1/objects/...` |
| gRPC 服务 | grpcio — ClientRegister, Handshake, ClientCommandDeliver, Audit, ConfigUpload |
| 管理面板 API | Django REST Framework — `/api/manage/...` |
| 管理面板前端 | Django 模板 + Bootstrap 5 — `/manage/...` |

## 📋 环境要求

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/ClassIsland_Management_Service_Community_Edition.git
cd ClassIsland_Management_Service_Community_Edition
```

### 2. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 3. 编译 Proto 文件

```bash
uv run python scripts/compile_protos.py
```

### 4. 初始化数据库与服务器

```bash
uv run python manage.py migrate
uv run python manage.py initserver
```

初始化时会：
- 创建默认组织
- 生成 PGP 密钥对（用于客户端握手认证）
- 创建管理员账号（默认用户名 `admin`，密码 `admin`，请及时修改）

### 5. 启动服务

```bash
# 启动 Django HTTP 服务（默认 20721 端口）
uv run python manage.py runserver 0.0.0.0:20721

# 在另一个终端启动 gRPC 服务（默认 20722 端口）
uv run python manage.py grpcserver
```

启动后访问 http://localhost:20721/ 进入管理面板。

## 📂 项目结构

```
├── api/                          # 协议文档与参考代码（只读）
│   ├── management-server-api.md  # 完整协议规范
│   ├── grpc-contract-summary.md  # gRPC 契约摘要
│   └── references/               # ClassIsland 客户端参考代码
├── classisland_management/       # Django 项目配置
│   ├── settings.py
│   └── urls.py
├── core/                         # 主应用
│   ├── models.py                 # 数据模型
│   ├── crypto.py                 # PGP 密钥生成与解密
│   ├── grpc_services.py          # gRPC 五大服务实现
│   ├── connection_manager.py     # 在线客户端连接管理
│   ├── api_views.py              # 客户端 HTTP API
│   ├── manage_api.py             # 管理面板 REST API
│   ├── panel_views.py            # 管理面板页面视图
│   ├── urls.py                   # URL 路由
│   └── management/commands/      # 管理命令
│       ├── initserver.py         # 服务器初始化
│       └── grpcserver.py         # gRPC 服务器
├── templates/manage/             # 管理面板 HTML 模板
├── scripts/
│   └── compile_protos.py         # Proto 文件编译脚本
└── pyproject.toml                # 项目配置与依赖
```

## 🔧 配置

主要配置项在 `classisland_management/settings.py`：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `GRPC_SERVER_PORT` | `20722` | gRPC 服务监听端口 |
| `SECRET_KEY` | 随机生成 | Django 密钥，生产环境务必更换 |
| `DEBUG` | `True` | 生产环境请设为 `False` |
| `DATABASES` | SQLite | 生产环境建议换用 PostgreSQL |

## 🔐 安全说明

- 默认管理员密码为 `admin`，首次登录后请立即修改
- `SECRET_KEY` 在生产环境中应通过环境变量设置
- gRPC 握手使用 PGP 密钥对进行客户端认证
- 管理面板 API 需要登录认证（SessionAuthentication）

## 📡 客户端接入

在 ClassIsland 客户端中配置集控服务器地址：

- **服务端地址**: `http://<server-ip>:20721`
- **gRPC 地址**: `<server-ip>:20722`

客户端将自动通过 HTTP 获取 Manifest 和资源，通过 gRPC 完成注册、握手和命令接收。

