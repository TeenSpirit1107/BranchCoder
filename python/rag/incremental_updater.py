"""
Incremental RAG Update Module
Handles incremental updates to RAG indices for changed files only.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Tuple

from rag.description_generator import DescriptionGenerator, DescribeOutput, FileDescription
from rag.function_slicer import FunctionSlicer
from rag.class_slicer import ClassSlicer
from rag.hash import (
    get_description_output_path,
)
from utils.logger import Logger

logger = Logger('incremental_updater', log_to_file=False)


async def process_single_file_for_update(
    description_generator: DescriptionGenerator,
    workspace_dir: str,
    rel_file_path: str,
) -> Tuple[FileDescription, List, List]:
    """
    Process a single file for incremental update.
    
    Args:
        description_generator: DescriptionGenerator instance
        workspace_dir: Path to the workspace directory
        rel_file_path: Relative file path within workspace
        
    Returns:
        Tuple of (FileDescription, List[DescribedFunction], List[DescribedClass])
    """
    workspace_path = Path(workspace_dir)
    
    # Slice entire workspace to get all functions and classes
    # Then filter for the specific file
    # Note: This is necessary because slicers need workspace context for proper parsing
    function_slice = FunctionSlicer().slice_workspace(workspace_path)
    class_slice = ClassSlicer().slice_workspace(workspace_path)
    
    # Filter for the specific file
    file_functions = [fn for fn in function_slice.items if fn.file == rel_file_path]
    file_classes = [cl for cl in class_slice.classes if cl.file == rel_file_path]
    
    # Group classes by file for the processing method
    classes_by_file = {rel_file_path: file_classes}
    
    # Use the existing _process_single_file method from DescriptionGenerator
    result = await description_generator._process_single_file(
        rel_file=rel_file_path,
        fns=file_functions,
        workspace_dir=workspace_path,
        classes_by_file=classes_by_file,
        global_fn_desc_by_qualname={},
        global_fn_desc_by_tail2={},
        global_fn_desc_by_tail1={},
        global_cls_desc_by_qualname={},
        global_cls_desc_by_name={},
        total_files=1,
        file_index=1,
    )
    
    return result


async def update_changed_files_incremental(
    description_generator: DescriptionGenerator,
    indexing_service,
    workspace_dir: str,
    changed_files: List[str],
    deleted_files: List[str],
) -> dict:
    """
    Incrementally update RAG indices for specified files.
    This function handles the complete incremental update workflow.
    
    Args:
        description_generator: DescriptionGenerator instance
        indexing_service: IndexingService instance
        workspace_dir: Path to the workspace directory
        changed_files: List of relative file paths that have been changed or added
        deleted_files: List of relative file paths that have been deleted
        
    Returns:
        Dictionary with update statistics:
        {
            "changed_files": list of changed file paths,
            "added_files": list of newly added file paths (same as changed_files),
            "deleted_files": list of deleted file paths,
            "updated": True/False
        }
    """
    logger.info(f"Incremental update for workspace: {workspace_dir}")
    logger.info(f"Files to process: {len(changed_files)} changed/added, {len(deleted_files)} deleted")
    
    if not changed_files and not deleted_files:
        logger.info("No files to update")
        return {
            "changed_files": [],
            "added_files": [],
            "deleted_files": [],
            "updated": False
        }
    
    # Changed files and added files are treated the same way - both need to be processed
    files_to_process = changed_files
    
    # Load existing description_output.json
    description_output_path = get_description_output_path(workspace_dir)
    existing_output = DescribeOutput(files=[], functions=[], classes=[])
    
    if Path(description_output_path).exists():
        try:
            with open(description_output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                existing_output = DescribeOutput(**data)
        except Exception as e:
            logger.warning(f"Error loading existing description_output.json: {e}")
    
    # Files to remove: deleted files + changed files (changed files need to be removed and re-added)
    files_to_remove = deleted_files + changed_files
    
    # Process each changed/added file
    new_file_descs = []
    new_functions = []
    new_classes = []
    
    for rel_file_path in files_to_process:
        try:
            logger.info(f"Processing file: {rel_file_path}")
            file_desc, described_funcs, described_classes = await process_single_file_for_update(
                description_generator=description_generator,
                workspace_dir=workspace_dir,
                rel_file_path=rel_file_path,
            )
            new_file_descs.append(file_desc)
            new_functions.extend(described_funcs)
            new_classes.extend(described_classes)
            logger.info(f"Successfully processed file: {rel_file_path}")
        except asyncio.CancelledError:
            # 如果单个文件处理被取消，记录并继续处理其他文件
            # 不要重新抛出，让定时任务继续运行
            logger.warning(f"Processing file {rel_file_path} was cancelled (possibly LLM timeout), skipping this file")
            continue
        except Exception as e:
            logger.error(f"Error processing file {rel_file_path}: {e}", exc_info=True)
            continue
    
    # Update description_output.json: remove old entries and add new ones
    # Remove entries for changed/deleted files
    file_paths_to_remove = set(files_to_process + files_to_remove)
    
    updated_files = [f for f in existing_output.files if f.file not in file_paths_to_remove]
    updated_files.extend(new_file_descs)
    
    updated_functions = [f for f in existing_output.functions if f.file not in file_paths_to_remove]
    updated_functions.extend(new_functions)
    
    updated_classes = [c for c in existing_output.classes if c.file not in file_paths_to_remove]
    updated_classes.extend(new_classes)
    
    # Create updated output
    updated_output = DescribeOutput(
        files=updated_files,
        functions=updated_functions,
        classes=updated_classes,
    )
    
    # Save updated description_output.json
    Path(description_output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(description_output_path, 'w', encoding='utf-8') as f:
        json.dump(updated_output.model_dump(), f, indent=2, ensure_ascii=False)
    logger.info(f"Updated description_output.json")
    
    # Incrementally update indices (only add/remove changed files, don't rebuild entire index)
    logger.info("Incrementally updating indices for changed files")
    await indexing_service.update_indices_incremental(
        updated_output=updated_output,
        files_to_remove=files_to_remove,
        new_file_descs=new_file_descs,
        new_functions=new_functions,
        new_classes=new_classes,
    )
    logger.info("Incremental index update completed")
    
    return {
        "changed_files": changed_files,
        "added_files": changed_files,  # Changed files are treated as added files
        "deleted_files": deleted_files,
        "updated": True
    }

