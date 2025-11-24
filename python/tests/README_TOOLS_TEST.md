# Tools 测试程序说明

本目录包含所有工具的测试程序，用于验证每个工具的准确性和功能。

## 测试文件列表

1. **test_tools.py** - 综合测试套件，包含所有工具的测试
2. **test_command_tool.py** - CommandTool 独立测试
3. **test_lint_tool.py** - LintTool 独立测试
4. **test_web_search_tool.py** - WebSearchTool 独立测试
5. **test_fetch_url_tool.py** - FetchUrlTool 独立测试
6. **test_workspace_rag_tool.py** - WorkspaceRAGTool 独立测试

## 运行测试

### 方法 1: 运行综合测试（推荐）

运行所有工具的测试：

```bash
cd python
python test/test_tools.py
```

### 方法 2: 运行单个工具的测试

运行特定工具的测试：

```bash
# CommandTool 测试
python test/test_command_tool.py

# LintTool 测试
python test/test_lint_tool.py

# WebSearchTool 测试
python test/test_web_search_tool.py

# FetchUrlTool 测试
python test/test_fetch_url_tool.py

# WorkspaceRAGTool 测试
python test/test_workspace_rag_tool.py
```

### 方法 3: 使用 pytest（如果已安装）

```bash
# 运行所有测试
pytest test/test_tools.py -v

# 运行特定工具的测试
pytest test/test_command_tool.py -v
pytest test/test_lint_tool.py -v
pytest test/test_web_search_tool.py -v
pytest test/test_fetch_url_tool.py -v
pytest test/test_workspace_rag_tool.py -v
```

## 测试覆盖范围

### CommandTool 测试
- ✅ 基本命令执行
- ✅ 工作区目录设置
- ✅ 无效命令处理
- ✅ 命令超时处理
- ✅ 输出和错误流捕获
- ✅ 工具定义验证

### LintTool 测试
- ✅ 有效代码检查
- ✅ 语法错误检测
- ✅ 文件路径检查
- ✅ 缺失参数处理
- ✅ 无效文件路径处理
- ✅ 代码风格检查（如果 linter 可用）
- ✅ 复杂代码多问题检测
- ✅ 工具定义验证

### WebSearchTool 测试
- ✅ 基本网络搜索
- ✅ 空查询处理
- ✅ 不同搜索类型（general, api_documentation, python_packages, github）
- ✅ 最大结果数限制
- ✅ 结果结构验证
- ✅ 工具定义验证
- ✅ 最小 max_results 处理

### FetchUrlTool 测试
- ✅ 有效 URL 获取
- ✅ 无效 URL 处理
- ✅ 最大字符数截断
- ✅ HTTP 错误处理
- ✅ 内容提取质量
- ✅ 工具定义验证

### WorkspaceRAGTool 测试
- ✅ 无工作区目录处理
- ✅ 工具定义验证
- ✅ 工作区目录设置
- ✅ RAG 检索（需要索引存在）
- ✅ 多个查询测试
- ✅ 结果结构验证
- ✅ 空查询处理

## 注意事项

1. **网络依赖**: WebSearchTool 和 FetchUrlTool 的测试需要网络连接。如果网络不可用，某些测试可能会显示警告但不会失败。

2. **RAG 索引**: WorkspaceRAGTool 的某些测试需要 RAG 索引存在。如果索引不存在，测试会显示警告但不会失败。

3. **外部工具**: LintTool 的代码风格检查需要外部 linter（pyflakes, flake8, 或 pylint）。如果这些工具不可用，测试仍会通过，但不会检测风格问题。

4. **Python 版本**: 测试需要 Python 3.9 或更高版本。

## 测试结果解读

测试输出会显示：
- ✓ 通过的测试
- ✗ 失败的测试
- ⚠ 警告（通常是由于外部依赖不可用）

每个测试套件最后会显示总结：
- 通过的测试数量
- 失败的测试数量

## 故障排除

### 导入错误
如果遇到导入错误，确保从 `python` 目录运行测试：
```bash
cd python
python test/test_tools.py
```

### 网络错误
WebSearchTool 和 FetchUrlTool 的测试可能需要网络连接。如果网络不可用，这些测试会显示警告但不会失败。

### RAG 索引错误
如果 WorkspaceRAGTool 测试失败，可能需要先创建 RAG 索引。这通常通过运行索引服务来完成。

## 贡献

添加新测试时，请遵循现有测试的结构：
1. 使用 `async def` 定义异步测试函数
2. 使用 `assert` 进行断言
3. 提供清晰的测试输出
4. 处理可能的网络/外部依赖问题

