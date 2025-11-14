# 手动测试工具程序使用说明

## 运行程序

```bash
cd python
uv run python test/manual_test_tools.py
```

或者直接运行：

```bash
cd python/test
uv run python manual_test_tools.py
```

## 功能说明

这个程序提供了一个交互式界面，可以测试所有工具：

### 1. CommandTool - 执行命令
- 输入要执行的 shell 命令
- 可以设置超时时间
- 如果设置了工作区目录，命令会在该目录下执行

### 2. LintTool - 代码检查
- 可以选择直接输入代码或从文件读取
- 可以控制是否检查语法和代码风格
- 显示所有发现的问题

### 3. WebSearchTool - 网络搜索
- 输入搜索关键词
- 选择搜索类型（通用、API文档、Python包、GitHub）
- 设置最大结果数
- 显示搜索结果

### 4. FetchUrlTool - 获取网页内容
- 输入要获取的 URL
- 设置最大字符数限制
- 显示提取的文本内容

### 5. WorkspaceRAGTool - 工作区代码检索
- 需要先设置工作区目录
- 输入搜索查询
- 显示相关的代码文件、函数和类

## 使用示例

### 测试命令工具
```
选择工具: 1
命令: echo "Hello, World!"
超时: 30
```

### 测试代码检查
```
选择工具: 2
输入方式: 1 (直接输入)
代码:
def hello():
    print("Hello")
    return True

检查语法: y
检查风格: y
```

### 测试网络搜索
```
选择工具: 3
搜索关键词: Python programming
最大结果数: 10
搜索类型: 1 (通用)
```

### 测试 URL 获取
```
选择工具: 4
URL: https://www.example.com
最大字符数: 1000
```

### 测试 RAG 检索
```
选择工具: 5
工作区目录: /path/to/workspace
搜索查询: function definition
```

## 输出格式

所有工具的输出结果都会以 JSON 格式打印，便于查看：
- 格式化的缩进
- 中文字符正确显示
- 清晰的结构

## 提示

- 使用 Ctrl+C 可以随时退出程序
- 每次测试后可以选择继续测试其他工具或退出
- 工作区目录设置后会在后续测试中保持，除非手动更改
- 所有输入都有合理的默认值，可以直接按回车使用默认值

