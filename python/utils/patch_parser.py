#!/usr/bin/env python3
"""
Patch Parser Utilities
Functions for detecting and extracting patch information from text.
"""

import re
from typing import List, Optional, Tuple


def is_patch_content(text: str) -> bool:
    """
    Check if the text appears to be patch content.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be patch content
    """
    if not text or not text.strip():
        return False
    
    # Check for standard unified diff format: --- file_path
    if re.search(r'^---\s+', text, re.MULTILINE):
        return True
    
    # Check for simplified patch format: *** Begin Patch
    if '*** Begin Patch' in text or '*** Update File:' in text:
        return True
    
    # Check for hunk headers: @@ -number,number +number,number @@
    if re.search(r'^@@\s*-\d+(?:,\d+)?\s*\+\d+(?:,\d+)?\s*@@', text, re.MULTILINE):
        return True
    
    return False


def extract_patch_info(text: str) -> Optional[List[Tuple[str, str]]]:
    """
    Extract target file paths and patch content from text.
    Supports both single-file and multi-file patches.
    
    Args:
        text: Patch content text
        
    Returns:
        List of tuples (target_file_path, patch_content_for_this_file) or None if not a valid patch
        For single-file patches, returns a list with one tuple.
    """
    if not is_patch_content(text):
        return None
    
    lines = text.split('\n')
    patches = []
    
    # Try to extract file paths from standard unified diff format
    i = 0
    while i < len(lines):
        if lines[i].startswith('---'):
            old_file = lines[i][4:].strip().split('\t')[0].strip()
            # Remove 'a/' or 'b/' prefix if present
            if old_file.startswith('a/') or old_file.startswith('b/'):
                old_file = old_file[2:]
            # Restore leading / for absolute paths
            if not old_file.startswith('/'):
                old_file = '/' + old_file
            
            # Look for +++ line
            if i + 1 < len(lines) and lines[i + 1].startswith('+++'):
                new_file = lines[i + 1][4:].strip().split('\t')[0].strip()
                if new_file.startswith('a/') or new_file.startswith('b/'):
                    new_file = new_file[2:]
                if not new_file.startswith('/'):
                    new_file = '/' + new_file
                
                # Use new_file as target, or old_file if new_file is /dev/null
                target_file = new_file if new_file != '/dev/null' else old_file
                if target_file == '/dev/null':
                    target_file = old_file
                
                # Find the end of this patch (next --- or end of text)
                patch_start = i
                patch_end = len(lines)
                for j in range(i + 2, len(lines)):
                    if lines[j].startswith('---'):
                        patch_end = j
                        break
                
                # Extract patch content for this file
                patch_content = '\n'.join(lines[patch_start:patch_end]).strip()
                patches.append((target_file, patch_content))
                
                # Move to next patch
                i = patch_end
                continue
        
        i += 1
    
    # Try simplified format: *** Update File: file_path
    if '*** Update File:' in text and not patches:
        # Extract all file patches from simplified format
        lines = text.split('\n')
        i = 0
        current_file = None
        patch_start = None
        
        while i < len(lines):
            line = lines[i]
            
            # Look for "*** Update File:" marker
            if '*** Update File:' in line:
                # Save previous patch if exists
                if current_file and patch_start is not None:
                    patch_content = '\n'.join(lines[patch_start:i]).strip()
                    if patch_content:
                        patches.append((current_file, patch_content))
                
                # Extract new file path
                current_file = line.split('*** Update File:')[1].strip()
                if not current_file.startswith('/'):
                    current_file = '/' + current_file
                patch_start = i
                i += 1
                continue
            
            # Look for "*** End Patch" marker
            if '*** End Patch' in line:
                if current_file and patch_start is not None:
                    patch_content = '\n'.join(lines[patch_start:i+1]).strip()
                    if patch_content:
                        patches.append((current_file, patch_content))
                current_file = None
                patch_start = None
                i += 1
                continue
            
            i += 1
        
        # Handle case where patch doesn't end with "*** End Patch"
        if current_file and patch_start is not None:
            patch_content = '\n'.join(lines[patch_start:]).strip()
            if patch_content:
                patches.append((current_file, patch_content))
    
    if patches:
        return patches
    
    # If we can't extract file path, return None
    # The patch tool might be able to parse it, but we need a file path
    return None

