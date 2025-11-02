"""
Workspace Hash Management Module
Handles computation and storage of workspace file hashes for RAG indexing cache.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from utils.logger import Logger

# Initialize logger
logger = Logger('workspace_hash', log_to_file=False)


def compute_file_hash(file_path: Path) -> str:
    """
    Compute MD5 hash of a single file based on its content.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 hash string (hexdigest), or empty string if file doesn't exist
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return ""
        file_content = file_path.read_bytes()
        return hashlib.md5(file_content).hexdigest()
    except Exception as e:
        logger.warning(f"Error computing hash for file {file_path}: {e}")
        return ""


def compute_workspace_file_hashes(workspace_dir: str) -> dict:
    """
    Compute hash for each relevant code file in workspace_dir.
    Returns a mapping from relative file path to file hash.
    Only includes common code file extensions and excludes build/cache directories.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Dictionary mapping relative file paths (as strings) to their MD5 hashes
        Format: {"relative/path/file.py": "hash1", ...}
    """
    workspace_path = Path(workspace_dir)
    if not workspace_path.exists():
        logger.warning(f"Workspace directory does not exist: {workspace_dir}")
        return {}
    
    file_hashes = {}
    
    # File extensions to include
    code_extensions = {
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h', 
        '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala'
    }
    
    # Directories to exclude
    exclude_dirs = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', 
        'build', 'dist', '.rag_store', 'out', '.next', '.cache', 
        'target', '.idea', '.vscode', '.vs'
    }
    
    file_count = 0
    # Walk through workspace and hash each file
    for file_path in sorted(workspace_path.rglob('*')):
        # Skip directories
        if file_path.is_dir():
            continue
        
        # Skip excluded directories
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            continue
        
        # Only include code files
        if file_path.suffix not in code_extensions:
            continue
        
        try:
            # Compute hash for this file
            file_hash = compute_file_hash(file_path)
            if file_hash:
                rel_path = file_path.relative_to(workspace_path)
                # Use forward slashes for consistency across platforms
                rel_path_str = str(rel_path).replace('\\', '/')
                file_hashes[rel_path_str] = file_hash
                file_count += 1
        except Exception as e:
            logger.warning(f"Error processing file {file_path}: {e}")
            continue
    
    logger.info(f"Computed hashes for {file_count} files in workspace: {workspace_dir}")
    return file_hashes


def get_workspace_storage_path(workspace_dir: str) -> str:
    """
    Get storage path for workspace-specific indices.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Absolute path to workspace-specific storage directory
    """
    workspace_path = Path(workspace_dir)
    # Use absolute path hash to create unique storage directory
    workspace_hash = hashlib.md5(str(workspace_path.absolute()).encode('utf-8')).hexdigest()[:12]
    module_dir = Path(__file__).parent.parent
    return str((module_dir / ".rag_store" / f"workspace_{workspace_hash}").absolute())


def get_workspace_metadata_path(workspace_dir: str) -> str:
    """
    Get path to workspace metadata file.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Absolute path to metadata file
    """
    storage_path = get_workspace_storage_path(workspace_dir)
    return str(Path(storage_path) / "workspace_metadata.json")


def get_description_output_path(workspace_dir: str) -> str:
    """
    Get path to description_output.json file for the workspace.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Absolute path to description_output.json file
    """
    storage_path = get_workspace_storage_path(workspace_dir)
    return str(Path(storage_path) / "description_output.json")


def load_workspace_metadata(workspace_dir: str) -> Optional[dict]:
    """
    Load workspace metadata (hash, workspace_dir, etc.).
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Dictionary with metadata or None if not found
    """
    metadata_path = get_workspace_metadata_path(workspace_dir)
    try:
        if Path(metadata_path).exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                logger.info(f"Loaded workspace metadata from: {metadata_path}")
                return metadata
    except Exception as e:
        logger.warning(f"Error loading workspace metadata: {e}")
    return None


def save_workspace_metadata(workspace_dir: str, file_hashes: dict) -> bool:
    """
    Save workspace metadata to disk, including file-to-hash mappings.
    
    Args:
        workspace_dir: Path to the workspace directory
        file_hashes: Dictionary mapping relative file paths to their hashes
                    Format: {"relative/path/file.py": "hash1", ...}
        
    Returns:
        True if saved successfully, False otherwise
    """
    metadata_path = get_workspace_metadata_path(workspace_dir)
    try:
        metadata = {
            "workspace_dir": str(Path(workspace_dir).absolute()),
            "file_hashes": file_hashes,
        }
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved workspace metadata for {len(file_hashes)} files to: {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving workspace metadata: {e}")
        return False


def get_changed_files(workspace_dir: str) -> dict:
    """
    Compare current workspace files with saved hashes and return changed files.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Dictionary with keys:
        - "changed": list of file paths that have changed
        - "added": list of file paths that are new
        - "deleted": list of file paths that no longer exist
        - "unchanged": list of file paths that haven't changed
    """
    # Load saved metadata
    metadata = load_workspace_metadata(workspace_dir)
    if not metadata:
        # No saved metadata, all files are considered new
        current_hashes = compute_workspace_file_hashes(workspace_dir)
        return {
            "changed": [],
            "added": list(current_hashes.keys()),
            "deleted": [],
            "unchanged": [],
        }
    
    saved_hashes = metadata.get("file_hashes", {})
    current_hashes = compute_workspace_file_hashes(workspace_dir)
    
    changed = []
    added = []
    deleted = []
    unchanged = []
    
    # Check for changed and unchanged files
    for file_path in current_hashes:
        if file_path in saved_hashes:
            if current_hashes[file_path] != saved_hashes[file_path]:
                changed.append(file_path)
            else:
                unchanged.append(file_path)
        else:
            added.append(file_path)
    
    # Check for deleted files
    for file_path in saved_hashes:
        if file_path not in current_hashes:
            deleted.append(file_path)
    
    logger.info(f"File changes detected - Changed: {len(changed)}, Added: {len(added)}, Deleted: {len(deleted)}, Unchanged: {len(unchanged)}")
    
    return {
        "changed": changed,
        "added": added,
        "deleted": deleted,
        "unchanged": unchanged,
    }


def check_indices_exist(workspace_dir: str) -> bool:
    """
    Check if indices exist for the workspace.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        True if at least one index exists, False otherwise
    """
    storage_path = get_workspace_storage_path(workspace_dir)
    file_index_path = Path(storage_path) / "file"
    func_index_path = Path(storage_path) / "function"
    class_index_path = Path(storage_path) / "class"
    
    indices_exist = (
        file_index_path.exists() or
        func_index_path.exists() or
        class_index_path.exists()
    )
    
    return indices_exist

