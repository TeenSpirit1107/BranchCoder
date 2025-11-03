"""
Workspace Hash Management Module
Handles computation and storage of workspace file hashes for RAG indexing cache.
"""

import hashlib
import json
import time
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


def save_workspace_metadata(workspace_dir: str, file_hashes: dict = None, last_update_time: Optional[float] = None) -> bool:
    """
    Save workspace metadata to disk.
    NOTE: file_hashes are now stored in snapshot.json, so this function only saves last_update_time.
    
    Args:
        workspace_dir: Path to the workspace directory
        file_hashes: Deprecated - hashes are now stored in snapshot.json (ignored for compatibility)
        last_update_time: Optional timestamp of last update (if None, preserves existing or uses current time)
        
    Returns:
        True if saved successfully, False otherwise
    """
    metadata_path = get_workspace_metadata_path(workspace_dir)
    try:
        # If last_update_time not provided, try to preserve existing one
        if last_update_time is None:
            existing_metadata = load_workspace_metadata(workspace_dir)
            if existing_metadata and "last_update_time" in existing_metadata:
                last_update_time = existing_metadata.get("last_update_time")
            else:
                # No existing metadata or no last_update_time, use current time
                last_update_time = time.time()
        
        metadata = {
            "workspace_dir": str(Path(workspace_dir).absolute()),
            "last_update_time": last_update_time,
        }
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved workspace metadata (last_update_time) to: {metadata_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving workspace metadata: {e}")
        return False


def get_changed_files(workspace_dir: str) -> dict:
    """
    Compare current workspace files with saved hashes from snapshot.json and return changed files.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Dictionary with keys:
        - "changed": list of file paths that have changed
        - "added": list of file paths that are new
        - "deleted": list of file paths that no longer exist
        - "unchanged": list of file paths that haven't changed
    """
    logger.info(f"[Hash检查] 开始检查工作区文件变化: {workspace_dir}")
    
    # Load saved hashes from snapshot.json
    saved_hashes = load_snapshot_hashes(workspace_dir)
    if not saved_hashes:
        # No saved snapshot, all files are considered new
        logger.info("[Hash检查] 未找到保存的快照，所有文件视为新增")
        current_hashes = compute_workspace_file_hashes(workspace_dir)
        result = {
            "changed": [],
            "added": list(current_hashes.keys()),
            "deleted": [],
            "unchanged": [],
        }
        logger.info(f"[Hash检查] 结果 - 新增: {len(result['added'])} 个文件")
        return result
    
    logger.info(f"[Hash检查] 已保存的hash记录: {len(saved_hashes)} 个文件")

    current_hashes = compute_workspace_file_hashes(workspace_dir)
    logger.info(f"[Hash检查] 当前文件hash计算完成: {len(current_hashes)} 个文件")

    changed = []
    added = []
    deleted = []
    unchanged = []

    # Check for changed and unchanged files
    for file_path in current_hashes:
        if file_path in saved_hashes:
            if current_hashes[file_path] != saved_hashes[file_path]:
                changed.append(file_path)
                logger.debug(f"[Hash检查] 文件变化: {file_path} (旧hash: {saved_hashes[file_path][:8]}..., 新hash: {current_hashes[file_path][:8]}...)")
            else:
                unchanged.append(file_path)
        else:
            added.append(file_path)
            logger.debug(f"[Hash检查] 新增文件: {file_path}")

    # Check for deleted files
    for file_path in saved_hashes:
        if file_path not in current_hashes:
            deleted.append(file_path)
            logger.debug(f"[Hash检查] 删除文件: {file_path}")

    logger.info(
        f"[Hash检查] 文件变化检测完成 - "
        f"变化: {len(changed)}, "
        f"新增: {len(added)}, "
        f"删除: {len(deleted)}, "
        f"未变化: {len(unchanged)}"
    )

    if changed:
        logger.info(f"[Hash检查] 变化的文件列表: {changed}")
    if added:
        logger.info(f"[Hash检查] 新增的文件列表: {added}")
    if deleted:
        logger.info(f"[Hash检查] 删除的文件列表: {deleted}")

    return {
        "changed": changed,
        "added": added,
        "deleted": deleted,
        "unchanged": unchanged,
    }


def get_last_update_time(workspace_dir: str) -> Optional[float]:
    """
    Get the last update time for the workspace.

    Args:
        workspace_dir: Path to the workspace directory

    Returns:
        Timestamp of last update, or None if not found
    """
    metadata = load_workspace_metadata(workspace_dir)
    if metadata:
        return metadata.get("last_update_time")
    return None


def save_last_update_time(workspace_dir: str, update_time: Optional[float] = None) -> bool:
    """
    Save the last update time for the workspace.
    
    Args:
        workspace_dir: Path to the workspace directory
        update_time: Timestamp to save (if None, current time is used)
        
    Returns:
        True if saved successfully, False otherwise
    """
    if update_time is None:
        update_time = time.time()
    
    # Only save last_update_time, file_hashes are in snapshot.json
    return save_workspace_metadata(workspace_dir, last_update_time=update_time)


def load_snapshot_hashes(workspace_dir: str) -> dict:
    """
    Load file hashes from snapshot.json.
    
    Args:
        workspace_dir: Path to the workspace directory
        
    Returns:
        Dictionary mapping relative file paths to their hashes
        Format: {"relative/path/file.py": "hash1", ...}
    """
    storage_path = get_workspace_storage_path(workspace_dir)
    snapshot_path = Path(storage_path) / "snapshot.json"
    
    if not snapshot_path.exists():
        logger.debug(f"Snapshot not found at: {snapshot_path}")
        return {}
    
    try:
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)
        
        # Extract hashes from snapshot
        saved_hashes = {}
        files = snapshot_data.get("files", {})
        for relative_path, file_data in files.items():
            if isinstance(file_data, dict) and "hash" in file_data:
                saved_hashes[relative_path] = file_data["hash"]
            elif isinstance(file_data, str):
                # Legacy format: direct hash string
                saved_hashes[relative_path] = file_data
        
        logger.debug(f"Loaded {len(saved_hashes)} file hashes from snapshot")
        return saved_hashes
    except Exception as e:
        logger.warning(f"Error loading snapshot hashes: {e}")
        return {}


def verify_and_filter_changes(
    workspace_dir: str,
    changed_files: list[str],
    deleted_files: list[str],
) -> dict:
    """
    Verify and filter file changes based on actual file hashes.
    Removes files from changed_files if:
    - File doesn't exist (should be in deleted_files instead)
    - File hash matches saved hash (no actual change)
    - File was deleted and restored with same hash
    
    Removes files from deleted_files if:
    - File still exists (should be in changed_files instead if hash changed)
    
    Args:
        workspace_dir: Path to the workspace directory
        changed_files: List of file paths reported as changed
        deleted_files: List of file paths reported as deleted
        
    Returns:
        Dictionary with verified and filtered changes:
        {
            "changed_files": list of files that actually need updating,
            "deleted_files": list of files that are actually deleted
        }
    """
    workspace_path = Path(workspace_dir)
    # Load hashes from snapshot.json instead of workspace_metadata.json
    saved_hashes = load_snapshot_hashes(workspace_dir)

    verified_changed = []
    verified_deleted = []

    # Check changed files
    for file_path_str in changed_files:
        file_path = workspace_path / file_path_str

        # If file doesn't exist, it's deleted, not changed
        if not file_path.exists() or not file_path.is_file():
            logger.debug(f"File {file_path_str} in changed_files doesn't exist, skipping from changed")
            # Don't add to deleted here - it will be checked in deleted_files section
            continue

        # Compute current hash
        current_hash = compute_file_hash(file_path)
        if not current_hash:
            logger.warning(f"Could not compute hash for {file_path_str}, skipping")
            continue

        # Check if file has saved hash
        if file_path_str in saved_hashes:
            saved_hash = saved_hashes[file_path_str]
            # If hash is the same, file wasn't actually changed
            if current_hash == saved_hash:
                logger.debug(f"File {file_path_str} hash unchanged, skipping update")
                continue

        # File actually changed or is new
        verified_changed.append(file_path_str)

    # Check deleted files
    for file_path_str in deleted_files:
        file_path = workspace_path / file_path_str

        # If file doesn't exist, it's actually deleted
        if not file_path.exists() or not file_path.is_file():
            verified_deleted.append(file_path_str)
            continue

        # File exists - check if it was restored with same content
        current_hash = compute_file_hash(file_path)
        if not current_hash:
            # Can't compute hash, assume it needs updating (should be in changed)
            logger.warning(f"Could not compute hash for {file_path_str}, treating as changed instead of deleted")
            if file_path_str not in verified_changed:
                verified_changed.append(file_path_str)
            continue

        # Check if hash matches saved hash
        if file_path_str in saved_hashes:
            saved_hash = saved_hashes[file_path_str]
            if current_hash == saved_hash:
                # File was deleted and restored with same content, no update needed
                logger.debug(f"File {file_path_str} was deleted but restored with same hash, skipping")
                continue
            else:
                # File was deleted but restored with different content, needs updating
                logger.debug(f"File {file_path_str} was deleted but restored with different content, treating as changed")
                if file_path_str not in verified_changed:
                    verified_changed.append(file_path_str)
        else:
            # File was deleted but now exists (new file), treat as changed
            logger.debug(f"File {file_path_str} was deleted but now exists (new), treating as changed")
            if file_path_str not in verified_changed:
                verified_changed.append(file_path_str)

    return {
        "changed_files": verified_changed,
        "deleted_files": verified_deleted,
    }


def get_pending_changes(workspace_dir: str) -> dict:
    """
    Get pending changes (files waiting to be updated) from metadata.

    Args:
        workspace_dir: Path to the workspace directory

    Returns:
        Dictionary with keys:
        - "changed_files": list of pending changed file paths
        - "deleted_files": list of pending deleted file paths
    """
    metadata = load_workspace_metadata(workspace_dir)
    if metadata:
        return {
            "changed_files": metadata.get("pending_changed_files", []),
            "deleted_files": metadata.get("pending_deleted_files", []),
        }
    return {"changed_files": [], "deleted_files": []}


def save_pending_changes(
    workspace_dir: str,
    changed_files: list[str],
    deleted_files: list[str],
) -> bool:
    """
    Save pending changes to metadata.
    Merges with existing pending changes to avoid duplicates.

    Args:
        workspace_dir: Path to the workspace directory
        changed_files: List of changed file paths to add
        deleted_files: List of deleted file paths to add

    Returns:
        True if saved successfully, False otherwise
    """
    # Load existing metadata
    existing_metadata = load_workspace_metadata(workspace_dir)

    # Get existing pending changes
    existing_pending = get_pending_changes(workspace_dir)
    existing_changed = set(existing_pending["changed_files"])
    existing_deleted = set(existing_pending["deleted_files"])

    # Merge new changes (use set to avoid duplicates)
    merged_changed = list(existing_changed | set(changed_files))
    merged_deleted = list(existing_deleted | set(deleted_files))

    # If a file was deleted, remove it from changed list
    merged_changed = [f for f in merged_changed if f not in merged_deleted]

    # Prepare metadata (file_hashes are in snapshot.json, not here)
    existing_metadata = load_workspace_metadata(workspace_dir)
    last_update_time = existing_metadata.get("last_update_time") if existing_metadata else None
    
    metadata = {
        "workspace_dir": str(Path(workspace_dir).absolute()),
        "last_update_time": last_update_time,
        "pending_changed_files": merged_changed,
        "pending_deleted_files": merged_deleted,
    }

    metadata_path = get_workspace_metadata_path(workspace_dir)
    try:
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved pending changes: {len(merged_changed)} changed, {len(merged_deleted)} deleted")
        return True
    except Exception as e:
        logger.error(f"Error saving pending changes: {e}")
        return False


def clear_pending_changes(workspace_dir: str) -> bool:
    """
    Clear pending changes from metadata.

    Args:
        workspace_dir: Path to the workspace directory

    Returns:
        True if cleared successfully, False otherwise
    """
    existing_metadata = load_workspace_metadata(workspace_dir)
    if not existing_metadata:
        return True  # Nothing to clear
    
    last_update_time = existing_metadata.get("last_update_time")
    
    metadata = {
        "workspace_dir": str(Path(workspace_dir).absolute()),
        "last_update_time": last_update_time,
        "pending_changed_files": [],
        "pending_deleted_files": [],
    }

    metadata_path = get_workspace_metadata_path(workspace_dir)
    try:
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info("Cleared pending changes")
        return True
    except Exception as e:
        logger.error(f"Error clearing pending changes: {e}")
        return False


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

