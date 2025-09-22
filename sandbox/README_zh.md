# AI Manus 沙盒服务

[English](README.md) | 中文

AI Manus 沙盒是一个基于Docker容器的隔离执行环境，为 AI Agent 提供安全的 Shell 命令执行、文件操作和浏览器自动化能力。该服务通过 FastAPI 提供API接口，支持与后端服务交互。

## 技术架构

沙盒服务集成多项技术，提供 AI Agent 操作环境：

```
sandbox/
├── app/                   # 应用主目录
│   ├── api/               # API接口定义
│   │   └── v1/            # API版本 v1
│   │       ├── shell.py   # Shell命令执行接口
│   │       ├── file.py    # 文件操作接口
│   │       └── supervisor.py # 进程管理接口
│   ├── services/          # 服务实现
│   ├── schemas/           # FastAPI 接口模型
│   ├── models/            # 数据模型
│   ├── core/              # 核心配置
│   └── main.py            # 应用入口
├── Dockerfile             # Docker构建文件
├── requirements.txt       # Python依赖
├── supervisord.conf       # Supervisor配置
└── README.md              # 文档
```

## 核心功能

沙盒环境提供以下核心功能：

1. **Shell 命令执行**：安全地执行 Shell 命令，支持会话管理
2. **文件操作**：读取、写入、搜索和操作文件系统
3. **浏览器环境**：
   - 内置 Google Chrome 浏览器
   - 支持 Chrome DevTools Protocol
   - 提供远程调试接口
4. **VNC 远程访问**：
   - VNC 远程桌面服务
   - WebSocket 接口
5. **进程管理**：通过 Supervisor 管理各组件进程

## 运行环境要求

- Python 3.9+
- Docker 20.10+

## 安装配置

### 本地开发环境

1. **创建虚拟环境**：
```bash
python -m venv .venv
source .venv/bin/activate
```

2. **安装依赖**：
```bash
pip install -r requirements.txt
```


3. **启动开发服务器**：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Docker部署

```bash
# 构建镜像
docker build -t manus-sandbox .

# 运行容器
docker run -p 8080:8080 -p 9222:9222 -p 5900:5900 -p 5901:5901 manus-sandbox
```

## 端口说明

- **8080**: FastAPI 服务端口
- **9222**: Chrome 远程调试端口
- **5900**: VNC 服务端口
- **5901**: VNC WebSocket 端口

## 配置说明

沙盒服务支持以下配置项，可通过环境变量或`.env`文件设置：

- **ORIGINS**: 允许的CORS源列表，默认为`["*"]`。可设置为逗号分隔的字符串或JSON数组。
- **SERVICE_TIMEOUT_MINUTES**: 服务超时时间（分钟），默认为无限制。设置后服务将在指定时间后自动终止。
- **LOG_LEVEL**: 日志级别，可设置为`DEBUG`、`INFO`、`WARNING`、`ERROR`或`CRITICAL`，默认为`INFO`。

示例`.env`文件：
```
ORIGINS=http://localhost:3000,https://example.com
SERVICE_TIMEOUT_MINUTES=60
LOG_LEVEL=DEBUG
```

## API接口文档

基础URL: `/api/v1`

### 1. Shell相关接口

#### 执行Shell命令

- **接口**: `POST /api/v1/shell/exec`
- **描述**: 在指定的 shell 会话中执行命令
- **请求体**:
  ```json
  {
    "id": "session_id",  /* 可选，不提供则自动创建 */
    "exec_dir": "/path/to/dir",  /* 执行目录 */
    "command": "ls -la",  /* 要执行的命令 */
    "sudo": false  /* 可选，是否使用sudo执行 */
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "命令已执行",
    "data": {
      "session_id": "session_id",
      "command": "ls -la",
      "status": "running"
    }
  }
  ```

#### 查看 Shell 会话内容

- **接口**: `POST /api/v1/shell/view`
- **描述**: 查看指定 shell 会话的内容
- **请求体**:
  ```json
  {
    "id": "session_id"  /* 目标会话ID */
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "查询成功",
    "data": {
      "content": "会话输出内容",
      "session_id": "session_id"
    }
  }
  ```

#### 其它Shell操作

- **等待进程**: `POST /api/v1/shell/wait`
- **写入输入**: `POST /api/v1/shell/write`
- **终止进程**: `POST /api/v1/shell/kill`

### 2. 文件操作接口

#### 读取文件

- **接口**: `POST /api/v1/file/read`
- **描述**: 读取指定文件内容
- **请求体**:
  ```json
  {
    "file": "/path/to/file",  /* 文件路径 */
    "start_line": 1,  /* 可选，开始行 */
    "end_line": 100,  /* 可选，结束行 */
    "sudo": false  /* 可选，是否使用sudo读取 */
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "文件读取成功",
    "data": {
      "content": "文件内容",
      "line_count": 100,
      "file": "/path/to/file"
    }
  }
  ```

#### 写入文件

- **接口**: `POST /api/v1/file/write`
- **描述**: 写入内容到指定文件
- **请求体**:
  ```json
  {
    "file": "/path/to/file",  /* 文件路径 */
    "content": "文件内容",  /* 要写入的内容 */
    "sudo": false  /* 可选，是否使用sudo写入 */
  }
  ```

#### 其它文件操作

- **替换文件内容**: `POST /api/v1/file/replace`
- **搜索文件内容**: `POST /api/v1/file/search`
- **查找文件**: `POST /api/v1/file/find`

### 3. 进程管理接口

#### 获取进程状态

- **接口**: `GET /api/v1/supervisor/status`
- **描述**: 获取所有服务进程状态

#### 重启服务

- **接口**: `POST /api/v1/supervisor/restart`
- **描述**: 重启指定服务
- **请求体**:
  ```json
  {
    "service": "chrome"  /* 服务名称 */
  }
  ```

## 容器环境配置

沙盒容器内置以下环境：

- Ubuntu 22.04
- Python 3.10
- Node.js 20.18.0
- Google Chrome

## 调试指南

### 浏览器调试

1. 通过VNC客户端连接`localhost:5900`
2. 在浏览器中访问`http://localhost:9222/devtools/inspector.html`
