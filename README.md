# AI Chat Sidebar - VS Code Extension

一个 VS Code 扩展，在侧边栏提供 AI 对话功能。AI 功能通过 Python 脚本实现。

## 功能特性

- 📱 侧边栏聊天界面
- 💬 与 AI 进行对话
- 🧹 清除聊天历史
- ⚙️ 可配置的 Python 路径和脚本路径

## 安装

1. 安装依赖：
```bash
npm install
```

2. 编译 TypeScript：
```bash
npm run compile
```

3. 按 `F5` 在扩展开发主机中运行

## 配置

在 VS Code 设置中配置以下选项：

- `aiChat.pythonPath`: Python 解释器路径（默认: `python3`）
- `aiChat.aiScriptPath`: AI 服务脚本路径（默认: `python/ai_service.py`）

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

