# AI Chat Sidebar - VS Code Extension

一个 VS Code 扩展，在侧边栏提供 AI 对话功能。AI 功能通过 Python 脚本实现。

## 功能特性

- 📱 侧边栏聊天界面
- 💬 与 AI 进行对话
- 🧹 清除聊天历史
- ⚙️ 可配置的 Python 路径和脚本路径

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

确保创建 `.env` 文件（在项目根目录）并配置必要的环境变量：

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model_name
OPENAI_BASE_URL=your_base_url
OPENAI_PROXY=your_proxy_url  # 可选

# RAG 配置
RAG_UPDATE_INTERVAL_SECONDS=60  # RAG 更新服务的最小更新间隔（秒），默认: 60
RAG_DESCRIPTION_CONCURRENCY=2  # 描述生成的并发数，默认: 2
RAG_INDEXING_CONCURRENCY=2  # 索引构建的并发数，默认: 2
```

## 使用方法

1. 在侧边栏找到 "AI Chat" 视图
2. 在输入框中输入消息
3. 按 `Enter` 或点击 "Send" 发送消息
4. AI 将处理消息并返回响应

## 自定义 AI 功能

编辑 `python/ai_service.py` 文件中的 `get_ai_response` 函数，集成您的 AI 模型：

```python
def get_ai_response(message: str, history: List[Dict[str, str]]) -> str:
    # 在这里集成您的 AI 模型
    # 例如：OpenAI API、本地 LLM 等
    pass
```

## 开发

```bash
# 编译
npm run compile

# 监听模式编译
npm run watch
```

## 许可证

MIT

