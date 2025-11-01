# 快速开始

## 安装步骤

1. 安装依赖：
```bash
npm install
```

2. 编译 TypeScript：
```bash
npm run compile
```

3. 在 VS Code 中调试：
   - 按 `F5` 启动扩展开发主机
   - 在侧边栏找到 "AI Chat" 视图

## 配置 Python AI 服务

1. 编辑 `python/ai_service.py`，实现您的 AI 逻辑
2. 在 VS Code 设置中配置：
   - `aiChat.pythonPath`: Python 路径（如 `python3` 或 `/usr/bin/python3`）
   - `aiChat.aiScriptPath`: AI 脚本路径（默认: `python/ai_service.py`）

## Python AI 服务接口

Python 脚本需要：
- 从 stdin 读取 JSON: `{"message": "用户消息", "history": [...]}`
- 向 stdout 输出 JSON: `{"response": "AI回复", "status": "success"}`

示例已包含在 `python/ai_service.py` 中。

