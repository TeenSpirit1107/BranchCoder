#!/usr/bin/env python3
"""
手动测试工具程序
可以交互式地测试所有工具，输入参数并查看输出结果
"""

import asyncio
import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.command_tool import CommandTool
from tools.lint_tool import LintTool
from tools.web_search_tool import WebSearchTool
from tools.fetch_url_tool import FetchUrlTool
from tools.workspace_rag_tool import WorkspaceRAGTool


class ToolTester:
    """交互式工具测试器"""
    
    def __init__(self):
        """初始化所有工具"""
        self.tools = {
            "1": ("CommandTool", CommandTool()),
            "2": ("LintTool", LintTool()),
            "3": ("WebSearchTool", WebSearchTool()),
            "4": ("FetchUrlTool", FetchUrlTool()),
            "5": ("WorkspaceRAGTool", WorkspaceRAGTool()),
        }
        self.workspace_dir = None
    
    def print_menu(self):
        """打印主菜单"""
        print("\n" + "=" * 80)
        print("工具测试程序")
        print("=" * 80)
        print("可用的工具:")
        for key, (name, tool) in self.tools.items():
            print(f"  {key}. {name}")
        print("  0. 退出")
        if self.workspace_dir:
            print(f"\n当前工作区目录: {self.workspace_dir}")
        print("=" * 80)
    
    def print_result(self, result, tool_name):
        """格式化打印结果"""
        print("\n" + "=" * 80)
        print(f"{tool_name} 执行结果")
        print("=" * 80)
        
        # 使用 JSON 格式化输出，更易读
        try:
            formatted = json.dumps(result, indent=2, ensure_ascii=False)
            print(formatted)
        except Exception:
            # 如果无法 JSON 序列化，直接打印
            print(result)
        
        print("=" * 80)
    
    async def test_command_tool(self):
        """测试 CommandTool"""
        tool = self.tools["1"][1]
        
        if self.workspace_dir:
            tool.set_workspace_dir(self.workspace_dir)
        
        print("\n--- CommandTool 测试 ---")
        command = input("请输入要执行的命令 (例如: echo 'Hello World'): ").strip()
        if not command:
            print("命令不能为空")
            return
        
        timeout_input = input("超时时间（秒，默认30）: ").strip()
        timeout = int(timeout_input) if timeout_input else 30
        
        print(f"\n执行命令: {command}")
        result = await tool.execute(command=command, timeout=timeout)
        self.print_result(result, "CommandTool")
    
    async def test_lint_tool(self):
        """测试 LintTool"""
        tool = self.tools["2"][1]
        
        print("\n--- LintTool 测试 ---")
        print("选择输入方式:")
        print("  1. 直接输入代码")
        print("  2. 从文件路径读取")
        choice = input("请选择 (1/2): ").strip()
        
        code = None
        file_path = None
        
        if choice == "1":
            print("\n请输入 Python 代码（输入空行结束）:")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            code = "\n".join(lines)
        elif choice == "2":
            file_path = input("请输入文件路径: ").strip()
        else:
            print("无效的选择")
            return
        
        check_syntax_input = input("检查语法? (y/n, 默认y): ").strip().lower()
        check_syntax = check_syntax_input != "n"
        
        check_style_input = input("检查代码风格? (y/n, 默认y): ").strip().lower()
        check_style = check_style_input != "n"
        
        print("\n执行代码检查...")
        result = await tool.execute(
            code=code,
            file_path=file_path,
            check_syntax=check_syntax,
            check_style=check_style
        )
        self.print_result(result, "LintTool")
    
    async def test_web_search_tool(self):
        """测试 WebSearchTool"""
        tool = self.tools["3"][1]
        
        print("\n--- WebSearchTool 测试 ---")
        query = input("请输入搜索关键词: ").strip()
        if not query:
            print("搜索关键词不能为空")
            return
        
        max_results_input = input("最大结果数 (默认10): ").strip()
        max_results = int(max_results_input) if max_results_input else 10
        
        print("\n搜索类型:")
        print("  1. general (通用)")
        print("  2. api_documentation (API文档)")
        print("  3. python_packages (Python包)")
        print("  4. github (GitHub)")
        search_type_choice = input("请选择 (1-4, 默认1): ").strip()
        
        search_type_map = {
            "1": "general",
            "2": "api_documentation",
            "3": "python_packages",
            "4": "github"
        }
        search_type = search_type_map.get(search_type_choice, "general")
        
        print(f"\n搜索: {query} (类型: {search_type})")
        result = await tool.execute(
            query=query,
            max_results=max_results,
            search_type=search_type
        )
        self.print_result(result, "WebSearchTool")
    
    async def test_fetch_url_tool(self):
        """测试 FetchUrlTool"""
        tool = self.tools["4"][1]
        
        print("\n--- FetchUrlTool 测试 ---")
        url = input("请输入 URL: ").strip()
        if not url:
            print("URL 不能为空")
            return
        
        max_chars_input = input("最大字符数 (默认8000): ").strip()
        max_chars = int(max_chars_input) if max_chars_input else 8000
        
        print(f"\n获取 URL: {url}")
        result = await tool.execute(url=url, max_chars=max_chars)
        self.print_result(result, "FetchUrlTool")
    
    async def test_workspace_rag_tool(self):
        """测试 WorkspaceRAGTool"""
        tool = self.tools["5"][1]
        
        print("\n--- WorkspaceRAGTool 测试 ---")
        
        if not self.workspace_dir:
            workspace_input = input("请输入工作区目录路径: ").strip()
            if workspace_input:
                self.workspace_dir = workspace_input
                tool.set_workspace_dir(self.workspace_dir)
            else:
                print("需要设置工作区目录")
                return
        else:
            change_input = input(f"当前工作区: {self.workspace_dir}\n是否更改? (y/n): ").strip().lower()
            if change_input == "y":
                workspace_input = input("请输入新的工作区目录路径: ").strip()
                if workspace_input:
                    self.workspace_dir = workspace_input
                    tool.set_workspace_dir(self.workspace_dir)
        
        query = input("请输入搜索查询: ").strip()
        if not query:
            print("搜索查询不能为空")
            return
        
        print(f"\nRAG 检索: {query}")
        result = await tool.execute(query=query)
        self.print_result(result, "WorkspaceRAGTool")
    
    async def run(self):
        """运行交互式测试程序"""
        print("欢迎使用工具测试程序！")
        print("你可以测试所有可用的工具")
        
        while True:
            self.print_menu()
            choice = input("\n请选择要测试的工具 (0-5): ").strip()
            
            if choice == "0":
                print("\n退出程序")
                break
            elif choice == "1":
                await self.test_command_tool()
            elif choice == "2":
                await self.test_lint_tool()
            elif choice == "3":
                await self.test_web_search_tool()
            elif choice == "4":
                await self.test_fetch_url_tool()
            elif choice == "5":
                await self.test_workspace_rag_tool()
            else:
                print("无效的选择，请重试")
            
            # 询问是否继续
            continue_input = input("\n是否继续测试其他工具? (y/n, 默认y): ").strip().lower()
            if continue_input == "n":
                print("\n退出程序")
                break


async def main():
    """主函数"""
    tester = ToolTester()
    await tester.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序出错: {e}")
        import traceback
        traceback.print_exc()

