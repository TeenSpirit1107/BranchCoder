# AI Chat Sidebar - VS Code Extension

一个 VS Code 扩展，在侧边栏提供 AI 对话功能。AI 功能通过 Python 脚本实现，支持 RAG（检索增强生成）技术，能够自动索引代码库并为 AI 提供上下文。

## 功能特性

- 📱 侧边栏聊天界面 - 简洁美观的对话界面
- 💬 与 AI 进行对话 - 支持多轮对话和历史记录
- 🔍 RAG 代码索引 - 自动索引工作区代码，为 AI 提供代码上下文
- 🔄 自动更新索引 - 通过快照系统检测文件变化，自动更新 RAG 索引
- 📝 Markdown 渲染 - 支持 Markdown 格式的消息渲染
- 🧹 清除聊天历史 - 一键清空对话记录
- ⚙️ 可配置的 Python 路径和脚本路径
- 📊 输出日志 - 详细的日志输出，便于调试和监控

## 安装

### 前置要求

- Node.js 和 npm
- Python 3.9 或更高版本
- [uv](https://github.com/astral-sh/uv)（推荐的 Python 包管理器）

### 安装步骤

1. 安装 Node.js 依赖：
```bash
npm install
```

2. 设置 Python 环境（使用 uv）：

```bash
# 安装 uv（如果尚未安装）
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或使用 pip:
# pip install uv

# 创建虚拟环境
uv venv

# 激活虚拟环境
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# 安装 Python 依赖
uv sync
```

3. 配置 VS Code 扩展：

在 VS Code 设置中，将 `aiChat.pythonPath` 设置为 uv 虚拟环境中的 Python 解释器路径：

- macOS/Linux: `.venv/bin/python`（相对于项目根目录）
- Windows: `.venv\Scripts\python.exe`（相对于项目根目录）

或者使用绝对路径。

4. 编译 TypeScript：
```bash
npm run compile
```

5. 按 `F5` 在扩展开发主机中运行

## 配置

在 VS Code 设置中配置以下选项：

- `aiChat.pythonPath`: Python 解释器路径
  - 默认: `python3`
  - 使用 uv 环境时: `.venv/bin/python`（Linux/macOS）或 `.venv\Scripts\python.exe`（Windows）
  - 可以使用绝对路径或相对于项目根目录的路径
- `aiChat.aiScriptPath`: AI 服务脚本路径（默认: `python/ai_service.py`）

### Python 环境变量

确保在 `python/` 目录下创建 `.env` 文件并配置必要的环境变量：

```bash
# OpenAI 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model_name  # 例如: gpt-4, gpt-3.5-turbo 等
OPENAI_BASE_URL=your_base_url  # 可选，用于自定义 API 端点
OPENAI_PROXY=your_proxy_url  # 可选，代理配置

# RAG 配置
RAG_UPDATE_INTERVAL_SECONDS=60  # RAG 更新服务的最小更新间隔（秒），默认: 60
RAG_DESCRIPTION_CONCURRENCY=2  # 描述生成的并发数，默认: 2
RAG_INDEXING_CONCURRENCY=2  # 索引构建的并发数，默认: 2
```

> **注意**：`.env` 文件应放在 `python/` 目录下，而不是项目根目录。

## 使用方法

### 访问聊天界面

1. **通过活动栏图标**（推荐）：
   - 在 VS Code 左侧活动栏找到 💬 聊天图标
   - 点击图标打开 "AI Chat" 视图

2. **通过命令面板**：
   - 按 `Ctrl+Shift+P` (Windows/Linux) 或 `Cmd+Shift+P` (Mac)
   - 输入 `AI Chat: Open AI Chat` 并选择

### 开始对话

1. 在输入框中输入消息
2. 按 `Enter` 或点击 "Send" 发送消息
3. AI 将处理消息并返回响应（支持 Markdown 格式）
4. 使用清除按钮（🧹）可以清空对话历史

### RAG 索引

- **首次打开工作区**：扩展会自动初始化 RAG 索引，索引整个代码库
- **自动更新**：扩展会定期检测文件变化并自动更新索引（间隔由 `RAG_UPDATE_INTERVAL_SECONDS` 配置）
- **关闭检测**：即使 VS Code 关闭时文件发生变化，重新打开时也会自动检测并更新
- **查看日志**：在 VS Code 的"输出"面板中，选择 "AI Service" 频道查看详细日志

## 工作原理

### AI 服务架构

扩展使用 Python 脚本处理 AI 请求，主要组件包括：

1. **前端** (`src/extension.ts`, `src/ChatPanel.ts`)
   - VS Code 扩展主程序
   - 管理 Webview 聊天界面
   - 处理用户输入和消息显示

2. **AI 服务** (`python/ai_service.py`)
   - 接收聊天消息和历史记录
   - 调用 LLM 客户端生成响应
   - 返回格式化的 AI 回复

3. **LLM 客户端** (`python/llm/`)
   - 封装 OpenAI API 调用
   - 支持异步处理
   - 管理 API 配置和错误处理

4. **RAG 服务** (`python/rag/`)
   - 代码库索引和检索
   - 自动生成代码描述
   - 增量更新索引

### RAG 索引流程

1. **初始化**：首次打开工作区时，扫描所有代码文件并创建索引
2. **快照系统**：使用文件哈希快照检测变化
3. **增量更新**：仅更新变更的文件，提高效率
4. **上下文检索**：AI 回答问题时，RAG 系统会检索相关代码上下文

## 自定义 AI 功能

### 修改 AI 服务

编辑 `python/ai_service.py` 文件中的 `get_ai_response` 函数，可以自定义 AI 响应逻辑。

### 修改 LLM 配置

编辑 `python/llm/chat_llm.py` 文件，可以：
- 更换不同的 LLM 提供商
- 调整模型参数
- 添加自定义提示词

### 调整 RAG 行为

编辑 `python/rag/` 目录下的相关文件，可以：
- 修改代码切片策略
- 调整描述生成方式
- 自定义检索算法

## 开发

### TypeScript 编译

```bash
# 编译
npm run compile

# 监听模式编译（自动重新编译）
npm run watch
```

### Python 开发

项目使用 `uv` 作为 Python 包管理器：

```bash
# 安装依赖（如果需要）
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 调试

1. 在 VS Code 中按 `F5` 启动扩展开发主机
2. 在开发主机中测试扩展功能
3. 查看调试控制台和输出面板（"AI Service" 频道）获取日志

### 项目结构

```
.
├── src/                    # TypeScript 源代码
│   ├── extension.ts        # 扩展主入口
│   ├── ChatPanel.ts        # 聊天面板逻辑
│   └── snapshot.ts         # 快照系统
├── python/                  # Python 服务
│   ├── ai_service.py       # AI 服务主脚本
│   ├── llm/                 # LLM 客户端
│   ├── rag/                 # RAG 索引服务
│   └── utils/               # 工具函数
├── media/                   # 静态资源（CSS 等）
├── out/                     # TypeScript 编译输出
└── package.json            # Node.js 配置
```

## 许可证

MIT

