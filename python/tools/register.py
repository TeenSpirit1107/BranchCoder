#!/usr/bin/env python3
"""
Tool Registration Module
Automatically discovers and registers all MCP tools in the tools directory.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, List, Type, Optional, Any
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('tool_register', log_to_file=False)

# Global tool registry
_tool_registry: Dict[str, MCPTool] = {}
_tool_instances: Dict[str, MCPTool] = {}


def register_tools(tools_directory: Optional[str] = None) -> Dict[str, MCPTool]:
    """
    Automatically discover and register all MCP tools in the tools directory.
    
    This function:
    1. Scans the tools directory for Python modules
    2. Imports each module
    3. Finds all classes that inherit from MCPTool
    4. Instantiates and registers them
    
    Args:
        tools_directory: Optional path to tools directory. If None, uses the directory
                        containing this register.py file.
    
    Returns:
        Dictionary mapping tool names to tool instances
    """
    global _tool_registry, _tool_instances
    
    # Clear existing registry
    _tool_registry.clear()
    _tool_instances.clear()
    
    # Determine tools directory
    if tools_directory is None:
        # Use the directory containing this file
        tools_directory = str(Path(__file__).parent)
    
    tools_path = Path(tools_directory)
    
    if not tools_path.exists():
        logger.error(f"Tools directory does not exist: {tools_directory}")
        return {}
    
    logger.info(f"Scanning tools directory: {tools_directory}")
    
    # Get the package name - need to use full module path
    # If we're in python/tools/register.py, we want to import 'tools'
    import sys
    
    # Get the parent directory (python/) and add it to path if needed
    parent_dir = str(tools_path.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Import the tools package
    try:
        tools_package = importlib.import_module('tools')
    except ImportError as e:
        logger.error(f"Failed to import tools package: {e}")
        return {}
    
    # Iterate through all modules in the tools package
    for importer, modname, ispkg in pkgutil.iter_modules(tools_package.__path__, tools_package.__name__ + "."):
        # Skip __init__ and base_tool and register itself
        if modname.endswith('.__init__') or modname.endswith('.base_tool') or modname.endswith('.register'):
            continue
        
        try:
            # Import the module
            module = importlib.import_module(modname)
            logger.debug(f"Imported module: {modname}")
            
            # Find all classes in the module that inherit from MCPTool
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a subclass of MCPTool and not MCPTool itself
                if (issubclass(obj, MCPTool) and 
                    obj is not MCPTool and 
                    obj.__module__ == modname):
                    
                    try:
                        # Instantiate the tool
                        tool_instance = obj()
                        tool_name = tool_instance.name
                        
                        # Check for name conflicts
                        if tool_name in _tool_registry:
                            logger.warning(
                                f"Tool name conflict: {tool_name} already registered. "
                                f"Overwriting with {obj.__name__} from {modname}"
                            )
                        
                        # Register the tool
                        _tool_registry[tool_name] = tool_instance
                        _tool_instances[tool_name] = tool_instance
                        
                        logger.info(f"Registered tool: {tool_name} ({obj.__name__})")
                        
                    except Exception as e:
                        logger.error(f"Failed to instantiate tool {obj.__name__} from {modname}: {e}", exc_info=True)
                        continue
        
        except Exception as e:
            logger.error(f"Failed to process module {modname}: {e}", exc_info=True)
            continue
    
    logger.info(f"Registered {len(_tool_registry)} tools: {list(_tool_registry.keys())}")
    return _tool_registry.copy()


def get_tool(tool_name: str) -> Optional[MCPTool]:
    """
    Get a registered tool by name.
    
    Args:
        tool_name: Name of the tool
    
    Returns:
        Tool instance or None if not found
    """
    return _tool_registry.get(tool_name)


def get_all_tools() -> Dict[str, MCPTool]:
    """
    Get all registered tools.
    
    Returns:
        Dictionary mapping tool names to tool instances
    """
    return _tool_registry.copy()


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get tool definitions for all registered tools (for LLM function calling).
    
    Returns:
        List of tool definition dictionaries
    """
    return [tool.get_tool_definition() for tool in _tool_registry.values()]


def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Execute a registered tool by name (synchronous wrapper).
    Note: This creates a new event loop. For async contexts, use execute_tool_async instead.
    
    Args:
        tool_name: Name of the tool to execute
        **kwargs: Arguments to pass to the tool
    
    Returns:
        Tool execution result
    """
    tool = get_tool(tool_name)
    if tool is None:
        return {"error": f"Tool not found: {tool_name}"}
    
    import asyncio
    try:
        # Check if we're in an async context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we can't use run() - need to use async version
            raise RuntimeError(
                "Cannot execute tool synchronously when event loop is running. "
                "Use execute_tool_async() instead."
            )
        else:
            return loop.run_until_complete(tool.execute(**kwargs))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(tool.execute(**kwargs))


async def execute_tool_async(tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Execute a registered tool by name (async version).
    
    Args:
        tool_name: Name of the tool to execute
        **kwargs: Arguments to pass to the tool
    
    Returns:
        Tool execution result
    """
    tool = get_tool(tool_name)
    if tool is None:
        return {"error": f"Tool not found: {tool_name}"}
    
    return await tool.execute(**kwargs)


# Auto-register tools when module is imported
register_tools()

