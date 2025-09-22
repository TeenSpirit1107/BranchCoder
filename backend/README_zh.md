# AI Manus 后端服务

[English](README.md) | 中文

AI Manus 是一个基于 FastAPI 和 OpenAI API 的智能对话代理系统。该后端采用领域驱动设计(DDD)架构，支持智能对话、文件操作、Shell命令执行以及浏览器自动化等功能。

## 项目架构

项目采用领域驱动设计(DDD)架构，清晰地分离各层职责：

```
backend/
├── app/
│   ├── domain/          # 领域层：包含核心业务逻辑
│   │   ├── models/      # 领域模型定义
│   │   ├── services/    # 领域服务
│   │   ├── external/    # 外部服务接口
│   │   └── prompts/     # 提示词模板
│   ├── application/     # 应用层：编排业务流程
│   │   ├── services/    # 应用服务
│   │   └── schemas/     # 数据模式定义
│   ├── interfaces/      # 接口层：定义系统对外接口
│   │   └── api/
│   │       └── routes.py # API路由定义
│   ├── infrastructure/  # 基础设施层：提供技术实现
│   └── main.py          # 应用入口
├── Dockerfile           # Docker配置文件
├── run.sh               # 生产环境启动脚本
├── dev.sh               # 开发环境启动脚本
├── requirements.txt     # 项目依赖
└── README.md            # 项目文档
```

## 核心功能

1. **AI Agent管理**：创建和管理AI Agent实例
2. **实时对话**：通过Server-Sent Events (SSE)实现与Agent的实时对话
3. **工具调用**：支持多种工具调用，包括：
   - 浏览器自动化操作（使用Playwright）
   - Shell命令执行与查看
   - 文件读写操作
4. **沙盒环境**：使用Docker容器提供隔离的执行环境
5. **VNC可视化**：通过WebSocket连接支持远程查看沙盒环境
6. **网络搜索**：支持Google搜索集成（可选功能）

## 环境要求

- Python 3.9+
- Docker 20.10+

## 安装配置

1. **创建虚拟环境**:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. **安装依赖**:
```bash
pip install -r requirements.txt
```

3. **环境变量配置**:
创建 `.env` 文件并设置以下环境变量:
```
# Model provider configuration
API_KEY=your_api_key_here                # OpenAI 或其他模型供应商的 API 密钥
API_BASE=https://api.openai.com/v1       # 模型 API 的基础 URL，可替换为其他模型供应商的 API 地址

# Model configuration
MODEL_NAME=gpt-4o                        # 使用的模型名称
TEMPERATURE=0.7                          # 模型温度参数
MAX_TOKENS=2000                          # 模型单次请求最大输出 token 数量

# Google search configuration
GOOGLE_SEARCH_API_KEY=                   # Google Search API 密钥，用于网络搜索功能（可选）
GOOGLE_SEARCH_ENGINE_ID=                 # Google 自定义搜索引擎 ID（可选）

# Sandbox configuration
SANDBOX_IMAGE=simpleyyt/manus-sandbox          # 沙盒环境 Docker 镜像
SANDBOX_NAME_PREFIX=sandbox              # 沙盒容器名称前缀
SANDBOX_TTL_MINUTES=30                   # 沙盒容器生存时间（分钟）
SANDBOX_NETWORK=manus-network            # Docker 网络名称，用于沙盒容器间通信

# Log configuration
LOG_LEVEL=INFO                           # 日志级别，可选: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## 运行方式

### 开发环境
```bash
# 启动开发服务器（带热重载功能）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务将在 http://localhost:8000 启动。

### Docker部署
```bash
# 构建Docker镜像
docker build -t manus-ai-agent .

# 运行容器
docker run -p 8000:8000 --env-file .env -v /var/run/docker.sock:/var/run/docker.sock manus-ai-agent
```

> 注意：如果使用Docker部署，需要挂载Docker套接字以便后端可以创建沙盒容器。

## API接口文档

基础URL: `/api/v1`

### 1. 创建Agent

- **接口**: `POST /api/v1/agents`
- **描述**: 创建一个新的 AI Agent 实例
- **请求体**: 无
- **响应**:
  ```json
  {
    "code": 0,
    "msg": "success",
    "data": {
      "agent_id": "string",
      "status": "created",
      "message": "Agent created successfully"
    }
  }
  ```

### 2. 与 Agent 对话

- **接口**: `POST /api/v1/agents/{agent_id}/chat`
- **描述**: 与指定Agent进行对话
- **请求体**:
  ```json
  {
    "message": "用户消息内容",
    "timestamp": 1234567890
  }
  ```
- **响应**: Server-Sent Events (SSE) 流
- **事件类型**:
  - `message`: 文本消息
  - `title`: 标题信息
  - `plan`: 计划步骤
  - `step`: 步骤状态
  - `tool`: 工具调用
  - `error`: 错误信息
  - `done`: 流程结束

### 3. 查看Shell会话内容

- **接口**: `POST /api/v1/agents/{agent_id}/shell`
- **描述**: 查看指定Agent的Shell会话内容
- **请求体**:
  ```json
  {
    "session_id": "shell会话ID"
  }
  ```
- **响应**: Shell会话内容

### 4. 查看文件内容

- **接口**: `POST /api/v1/agents/{agent_id}/file`
- **描述**: 查看指定Agent沙盒环境中的文件内容
- **请求体**:
  ```json
  {
    "file": "文件路径"
  }
  ```
- **响应**: 文件内容

### 5. VNC连接

- **接口**: `WebSocket /api/v1/agents/{agent_id}/vnc`
- **描述**: 建立与Agent沙盒环境的VNC WebSocket连接
- **协议**: WebSocket (二进制模式)

## 错误处理

所有API在发生错误时会返回统一格式的响应：
```json
{
  "code": 400,
  "msg": "错误描述",
  "data": null
}
```

常见错误码：
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误

## 开发指南

### 添加新工具

1. 在 `domain/external` 目录下定义工具接口
2. 在 `infrastructure` 层实现工具功能
3. 在 `application/services` 中集成工具
