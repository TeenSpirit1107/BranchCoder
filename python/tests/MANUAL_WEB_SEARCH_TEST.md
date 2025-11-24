# Web Search Tool 手动验证指南

## 方法 1: 使用 Python 交互式测试

```python
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.web_search_tool import WebSearchTool

async def test():
    tool = WebSearchTool()
    
    # 测试基本搜索
    print("测试基本搜索...")
    result = await tool.execute(query="Python programming", max_results=5)
    print(f"状态: {result['status']}")
    print(f"结果数量: {result.get('total_results', 0)}")
    if result.get('results'):
        print(f"第一个结果: {result['results'][0].get('title', 'N/A')}")
    
    # 测试不同类型的搜索
    print("\n测试 API 文档搜索...")
    result = await tool.execute(query="requests", search_type="api_documentation", max_results=3)
    print(f"结果数量: {result.get('total_results', 0)}")
    
    print("\n测试 Python 包搜索...")
    result = await tool.execute(query="numpy", search_type="python_packages", max_results=3)
    print(f"结果数量: {result.get('total_results', 0)}")
    
    print("\n测试 GitHub 搜索...")
    result = await tool.execute(query="python", search_type="github", max_results=3)
    print(f"结果数量: {result.get('total_results', 0)}")

asyncio.run(test())
```

## 方法 2: 使用测试脚本

运行以下命令：

```bash
cd /home/yf/workspace/development/branch_coder/python
python3 tests/test_web_search_tool.py
```

## 方法 3: 使用手动测试工具

运行交互式测试工具：

```bash
cd /home/yf/workspace/development/branch_coder/python
python3 tests/manual_test_tools.py
```

然后选择选项 3 (WebSearchTool)

## 方法 4: 直接测试工具工厂

```python
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.tool_factory import execute_tool
from models import ToolCallEvent

async def test():
    event = ToolCallEvent(
        tool_name='web_search',
        tool_args={'query': 'Python programming', 'max_results': 5}
    )
    
    async for result in execute_tool(event):
        print(f"类型: {result.type}")
        print(f"消息: {result.message}")
        if hasattr(result, 'result') and result.result:
            print(f"结果: {result.result.get('total_results', 0)} 个结果")

asyncio.run(test())
```

## 注意事项

1. **网络连接**: Web Search Tool 需要网络连接才能工作
2. **依赖库**: 需要安装 `ddgs` 或 `duckduckgo_search` 库
3. **搜索结果**: 搜索结果可能因网络状况和搜索服务而变化
4. **测试环境**: 在某些测试环境中，搜索可能返回 0 个结果，这是正常的

## 验证检查点

- [ ] 工具可以正常导入
- [ ] 基本搜索可以执行
- [ ] 不同类型的搜索可以执行
- [ ] 结果结构正确（包含 title, url, snippet）
- [ ] 通知方法返回正确的字符串类型
- [ ] 工具定义正确

