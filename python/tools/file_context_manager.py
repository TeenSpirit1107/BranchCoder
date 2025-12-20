#!/usr/bin/env python3
"""
File Context Manager
Manages opened files and their content for dynamic context injection into system prompts.
"""

from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
from enum import Enum
from utils.logger import Logger

logger = Logger('file_context_manager', log_to_file=False)

# Global file context manager instances (per workspace)
_file_context_managers: Dict[str, 'FileContextManager'] = {}


def get_file_context_manager(workspace_dir: str) -> 'FileContextManager':
    """Get or create file context manager for a workspace."""
    if workspace_dir not in _file_context_managers:
        _file_context_managers[workspace_dir] = FileContextManager(workspace_dir)
    return _file_context_managers[workspace_dir]


class FileOpenMode(Enum):
    """File open mode: temporary (one-time use) or persistent (stays open)"""
    TEMPORARY = "temporary"  # Only for this iteration, auto-closed after use
    PERSISTENT = "persistent"  # Stays open until explicitly closed


class FileContextManager:
    """
    Manages file context for agents.
    Tracks which files are open and dynamically loads their content.
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        # Map: file_path -> (mode, content_hash)
        # mode: FileOpenMode
        # content_hash: to detect file changes
        self._open_files: Dict[str, Tuple[FileOpenMode, Optional[str]]] = {}
        # Cache for file contents to avoid repeated reads
        self._content_cache: Dict[str, Tuple[str, str]] = {}  # path -> (content, hash)
    
    def open_file(self, file_path: str, mode: FileOpenMode = FileOpenMode.PERSISTENT) -> bool:
        """
        Open a file for context inclusion.
        
        Args:
            file_path: Path to the file (can be absolute or relative to workspace)
            mode: TEMPORARY (one-time use) or PERSISTENT (stays open)
        
        Returns:
            True if file was opened successfully, False otherwise
        """
        try:
            # Resolve file path
            resolved_path = self._resolve_path(file_path)
            if resolved_path is None:
                logger.warning(f"Cannot resolve file path: {file_path}")
                return False
            
            if not resolved_path.exists():
                logger.warning(f"File does not exist: {resolved_path}")
                return False
            
            if not resolved_path.is_file():
                logger.warning(f"Path is not a file: {resolved_path}")
                return False
            
            # Store file as open
            file_str = str(resolved_path)
            self._open_files[file_str] = (mode, None)  # hash will be computed when loading
            
            logger.info(f"Opened file: {file_str} (mode: {mode.value}), total open files: {len(self._open_files)}")
            return True
            
        except Exception as e:
            logger.error(f"Error opening file {file_path}: {e}", exc_info=True)
            return False
    
    def close_file(self, file_path: str) -> bool:
        """
        Close a file and remove it from context.
        
        Args:
            file_path: Path to the file (can be absolute or relative to workspace)
        
        Returns:
            True if file was closed successfully, False otherwise
        """
        try:
            resolved_path = self._resolve_path(file_path)
            if resolved_path is None:
                return False
            
            file_str = str(resolved_path)
            if file_str in self._open_files:
                del self._open_files[file_str]
                logger.info(f"Closed file: {file_str}")
                return True
            else:
                logger.debug(f"File was not open: {file_str}")
                return False
                
        except Exception as e:
            logger.error(f"Error closing file {file_path}: {e}", exc_info=True)
            return False
    
    def close_all_files(self) -> None:
        """Close all open files."""
        count = len(self._open_files)
        self._open_files.clear()
        self._content_cache.clear()
        logger.info(f"Closed all {count} open files")
    
    def close_temporary_files(self) -> None:
        """Close all temporary files (called after each iteration)."""
        to_close = [
            path for path, (mode, _) in self._open_files.items()
            if mode == FileOpenMode.TEMPORARY
        ]
        for path in to_close:
            del self._open_files[path]
            if path in self._content_cache:
                del self._content_cache[path]
        if to_close:
            logger.debug(f"Closed {len(to_close)} temporary files")
    
    def get_open_files(self) -> List[str]:
        """Get list of all open file paths."""
        return list(self._open_files.keys())
    
    def is_file_open(self, file_path: str) -> bool:
        """Check if a file is currently open."""
        resolved_path = self._resolve_path(file_path)
        if resolved_path is None:
            return False
        return str(resolved_path) in self._open_files
    
    def load_file_content(self, file_path: str) -> Optional[str]:
        """
        Load file content, with caching.
        
        Args:
            file_path: Path to the file
        
        Returns:
            File content as string, or None if error
        """
        try:
            resolved_path = self._resolve_path(file_path)
            if resolved_path is None or not resolved_path.exists():
                return None
            
            file_str = str(resolved_path)
            
            # Check cache first
            if file_str in self._content_cache:
                cached_content, cached_hash = self._content_cache[file_str]
                current_hash = self._compute_hash(resolved_path)
                if current_hash == cached_hash:
                    return cached_content
            
            # Read file
            try:
                content = resolved_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                # Try with error handling
                content = resolved_path.read_text(encoding='utf-8', errors='replace')
            
            # Update cache
            current_hash = self._compute_hash(resolved_path)
            self._content_cache[file_str] = (content, current_hash)
            
            return content
            
        except Exception as e:
            logger.error(f"Error loading file content {file_path}: {e}", exc_info=True)
            return None
    
    def get_all_file_contents(self) -> Dict[str, str]:
        """
        Get contents of all open files.
        Dynamically loads latest content from disk.
        
        Returns:
            Dictionary mapping file paths to their contents
        """
        result = {}
        # Create a list of keys to iterate over, in case we need to modify _open_files
        open_files_list = list(self._open_files.keys())
        for file_path in open_files_list:
            # file_path is already an absolute path string stored in _open_files
            # We need to load it directly without re-resolving
            try:
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"Open file no longer exists, removing from context: {file_path}")
                    # Remove non-existent file from open files
                    if file_path in self._open_files:
                        del self._open_files[file_path]
                    if file_path in self._content_cache:
                        del self._content_cache[file_path]
                    continue
                
                # Check cache first
                if file_path in self._content_cache:
                    cached_content, cached_hash = self._content_cache[file_path]
                    current_hash = self._compute_hash(path)
                    if current_hash == cached_hash:
                        result[file_path] = cached_content
                        continue
                
                # Read file
                try:
                    content = path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = path.read_text(encoding='utf-8', errors='replace')
                
                # Update cache
                current_hash = self._compute_hash(path)
                self._content_cache[file_path] = (content, current_hash)
                result[file_path] = content
                
            except Exception as e:
                logger.error(f"Error loading file content {file_path}: {e}", exc_info=True)
                # Don't remove from _open_files, just skip this file
                continue
        return result
    
    def format_files_for_prompt(self) -> str:
        """
        Format all open files' content for inclusion in system prompt.
        
        Returns:
            Formatted string with file contents
        """
        file_contents = self.get_all_file_contents()
        if not file_contents:
            logger.debug(f"No file contents to format, but {len(self._open_files)} files are open")
            return ""
        
        logger.debug(f"Formatting {len(file_contents)} files for prompt")
        lines = ["\n=== Currently Open Files ==="]
        for file_path, content in file_contents.items():
            # Use relative path if possible for cleaner display
            display_path = self._get_display_path(file_path)
            lines.append(f"\n--- File: {display_path} ---")
            lines.append(content)
            lines.append("")  # Empty line between files
        
        return "\n".join(lines)
    
    def inherit_from(self, other: 'FileContextManager') -> None:
        """
        Inherit persistent files from another FileContextManager.
        Used when creating child agents.
        
        Args:
            other: The parent FileContextManager to inherit from
        """
        inherited_count = 0
        for file_path, (mode, _) in other._open_files.items():
            if mode == FileOpenMode.PERSISTENT:
                # Only inherit persistent files
                self._open_files[file_path] = (mode, None)
                inherited_count += 1
        
        if inherited_count > 0:
            logger.info(f"Inherited {inherited_count} persistent files from parent")
    
    def _resolve_path(self, file_path: str) -> Optional[Path]:
        """Resolve file path to absolute Path."""
        try:
            path = Path(file_path)
            if path.is_absolute():
                return path
            elif self.workspace_dir:
                return (self.workspace_dir / path).resolve()
            else:
                return path.resolve()
        except Exception as e:
            logger.error(f"Error resolving path {file_path}: {e}")
            return None
    
    def _get_display_path(self, file_path: str) -> str:
        """Get display-friendly path (relative to workspace if possible)."""
        try:
            path = Path(file_path)
            if self.workspace_dir and path.is_relative_to(self.workspace_dir):
                return str(path.relative_to(self.workspace_dir))
            return file_path
        except:
            return file_path
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute a simple hash of file for change detection."""
        try:
            stat = file_path.stat()
            # Use mtime and size as a simple hash
            return f"{stat.st_mtime}_{stat.st_size}"
        except:
            return "unknown"

