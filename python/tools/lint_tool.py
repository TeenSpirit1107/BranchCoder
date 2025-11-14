#!/usr/bin/env python3
"""
Lint Tool - Check code for syntax errors and linting issues
"""

import ast
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from utils.logger import Logger
from tools.base_tool import MCPTool

logger = Logger('lint_tool', log_to_file=False)


class LintTool(MCPTool):
    """Tool for checking code syntax and linting issues."""
    
    @property
    def name(self) -> str:
        """Tool name."""
        return "lint_code"
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": "lint_code",
                "description": "Check Python code for syntax errors and linting issues. This tool is specifically designed for Python code checking. Can check code from file path or direct code content. Returns syntax errors, linting warnings, and suggestions for improvement. Uses Python's built-in AST parser for syntax checking and optionally uses external linters (pyflakes, flake8, or pylint) if available for style checking.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python code content to check (required if file_path is not provided)"
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the Python file to check (required if code is not provided). Can be absolute or relative path."
                        },
                        "check_syntax": {
                            "type": "boolean",
                            "description": "Check for syntax errors (default: true)",
                            "default": True
                        },
                        "check_style": {
                            "type": "boolean",
                            "description": "Check for code style issues using external linters if available (default: true)",
                            "default": True
                        }
                    },
                    "required": []
                }
            }
        }
    
    def _check_python_syntax(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check Python code for syntax errors using AST parser.
        
        Args:
            code: Python code to check
            file_path: Optional file path for better error messages
        
        Returns:
            List of syntax error dictionaries
        """
        errors = []
        
        try:
            ast.parse(code, filename=file_path or "<string>")
        except SyntaxError as e:
            errors.append({
                "type": "syntax_error",
                "severity": "error",
                "message": e.msg,
                "line": e.lineno,
                "column": e.offset,
                "text": e.text,
                "file": file_path or "<string>"
            })
        except Exception as e:
            errors.append({
                "type": "syntax_error",
                "severity": "error",
                "message": f"Unexpected error during syntax check: {str(e)}",
                "file": file_path or "<string>"
            })
        
        return errors
    
    def _check_python_style(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check Python code style using external linters if available.
        Tries pyflakes, flake8, or pylint in order of preference.
        
        Args:
            code: Python code to check
            file_path: Optional file path
        
        Returns:
            List of style issue dictionaries
        """
        issues = []
        
        # Try pyflakes first (lightweight, fast)
        try:
            result = self._run_pyflakes(code, file_path)
            if result:
                issues.extend(result)
                return issues
        except Exception as e:
            logger.debug(f"pyflakes not available or failed: {e}")
        
        # Try flake8
        try:
            result = self._run_flake8(code, file_path)
            if result:
                issues.extend(result)
                return issues
        except Exception as e:
            logger.debug(f"flake8 not available or failed: {e}")
        
        # Try pylint as last resort (slower but comprehensive)
        try:
            result = self._run_pylint(code, file_path)
            if result:
                issues.extend(result)
        except Exception as e:
            logger.debug(f"pylint not available or failed: {e}")
        
        return issues
    
    def _run_pyflakes(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run pyflakes on code using subprocess."""
        issues = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run pyflakes
                result = subprocess.run(
                    ['pyflakes', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # Parse output
                for line in result.stdout.split('\n'):
                    if not line.strip():
                        continue
                    
                    # Format: file:line: message
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        issues.append({
                            "type": "style_issue",
                            "severity": "warning",
                            "message": parts[2].strip(),
                            "line": int(parts[1]) if parts[1].isdigit() else None,
                            "file": file_path or parts[0]
                        })
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
            return issues
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError, ImportError):
            return []
    
    def _run_flake8(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run flake8 on code using subprocess."""
        issues = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run flake8
                result = subprocess.run(
                    ['flake8', '--format=default', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # Parse output
                for line in result.stdout.split('\n'):
                    if not line.strip():
                        continue
                    
                    # Format: file:line:col: code message
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        issues.append({
                            "type": "style_issue",
                            "severity": "warning",
                            "message": parts[3].strip(),
                            "line": int(parts[1]) if parts[1].isdigit() else None,
                            "column": int(parts[2]) if parts[2].isdigit() else None,
                            "code": parts[2].split()[0] if len(parts) > 2 else None,
                            "file": file_path or parts[0]
                        })
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
            return issues
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return []
    
    def _run_pylint(self, code: str, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Run pylint on code using subprocess."""
        issues = []
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            try:
                # Run pylint with minimal output
                result = subprocess.run(
                    ['pylint', '--output-format=text', '--msg-template={path}:{line}:{column}: {msg_id} ({symbol}): {msg}', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Parse output
                for line in result.stdout.split('\n'):
                    if not line.strip() or line.startswith('---'):
                        continue
                    
                    # Format: file:line:col: code (symbol): message
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        msg_part = parts[3].strip()
                        # Extract code and message
                        if '(' in msg_part and ')' in msg_part:
                            code_part = msg_part.split('(')[0].strip()
                            symbol = msg_part.split('(')[1].split(')')[0]
                            message = msg_part.split('):', 1)[1].strip() if '):' in msg_part else msg_part
                        else:
                            code_part = None
                            symbol = None
                            message = msg_part
                        
                        # Determine severity from code
                        severity = "info"
                        if code_part:
                            if code_part.startswith('E'):
                                severity = "error"
                            elif code_part.startswith('W'):
                                severity = "warning"
                            elif code_part.startswith('C'):
                                severity = "convention"
                            elif code_part.startswith('R'):
                                severity = "refactor"
                        
                        issues.append({
                            "type": "style_issue",
                            "severity": severity,
                            "message": message,
                            "line": int(parts[1]) if parts[1].isdigit() else None,
                            "column": int(parts[2]) if parts[2].isdigit() else None,
                            "code": code_part,
                            "symbol": symbol,
                            "file": file_path or parts[0]
                        })
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
            return issues
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return []
    
    async def execute(
        self,
        code: Optional[str] = None,
        file_path: Optional[str] = None,
        check_syntax: bool = True,
        check_style: bool = True,
    ) -> Dict[str, Any]:
        """
        Check Python code for syntax errors and linting issues.
        
        Args:
            code: Python code content to check
            file_path: Path to Python file to check
            check_syntax: Whether to check syntax (default: True)
            check_style: Whether to check style (default: True)
        
        Returns:
            Dictionary with lint results
        """
        language = "python"  # Fixed to Python only
        logger.info(f"Linting Python code (syntax: {check_syntax}, style: {check_style})")
        
        # Validate inputs
        if not code and not file_path:
            return {
                "success": False,
                "error": "Either 'code' or 'file_path' must be provided",
                "issues": []
            }
        
        # Read code from file if file_path is provided
        if file_path and not code:
            try:
                file_path_obj = Path(file_path)
                if not file_path_obj.is_absolute():
                    # Try to resolve relative path
                    file_path_obj = file_path_obj.resolve()
                
                if not file_path_obj.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}",
                        "issues": []
                    }
                
                code = file_path_obj.read_text(encoding='utf-8')
                file_path = str(file_path_obj)
            except Exception as e:
                logger.error(f"Error reading file: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": f"Failed to read file: {str(e)}",
                    "issues": []
                }
        
        if not code:
            return {
                "success": False,
                "error": "No code content to check",
                "issues": []
            }
        
        # This tool only supports Python
        all_issues = []
        
        # Check syntax
        if check_syntax:
            syntax_errors = self._check_python_syntax(code, file_path)
            all_issues.extend(syntax_errors)
        
        # Check style
        if check_style:
            style_issues = self._check_python_style(code, file_path)
            all_issues.extend(style_issues)
        
        # Count issues by severity
        error_count = sum(1 for issue in all_issues if issue.get("severity") == "error")
        warning_count = sum(1 for issue in all_issues if issue.get("severity") == "warning")
        info_count = sum(1 for issue in all_issues if issue.get("severity") in ["info", "convention", "refactor"])
        
        return {
            "success": True,
            "file": file_path or "<string>",
            "language": language,
            "total_issues": len(all_issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "issues": all_issues
        }

