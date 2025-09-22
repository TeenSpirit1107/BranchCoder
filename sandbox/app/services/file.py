"""
File Operation Service Implementation - Async Version
"""
import os
import re
import glob
import asyncio
from typing import Optional
import binascii
from charset_normalizer import from_bytes as cn_from_bytes
from app.models.file import (
    FileReadResult, FileWriteResult, FileReplaceResult,
    FileSearchResult, FileFindResult, FileUploadResponse,
    FileExistsResult
)


class FileService:
    """File Operation Service"""

    async def read_file(self, file: str, start_line: Optional[int] = None, 
                 end_line: Optional[int] = None, sudo: bool = False) -> FileReadResult:
        """
        Asynchronously read file content
        
        Args:
            file: Absolute file path
            start_line: Starting line (0-based)
            end_line: Ending line (not included)
            sudo: Whether to use sudo privileges
        """
        # Check if file exists
        if not os.path.exists(file) and not sudo:
            # 返回可读错误文本而不是抛异常
            return FileReadResult(content=f"File does not exist: {file}", file=file)

        # Helper: hex preview for binary files (first N bytes)
        def hex_preview(data: bytes, limit: int = 256) -> str:
            head = data[:limit]
            hex_str = binascii.hexlify(head).decode("ascii")
            grouped = " ".join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))
            note = "\n...[truncated hex preview]..." if len(data) > limit else ""
            return f"[binary file detected; showing first {len(head)} bytes in hex]\n{grouped}{note}"

        # Helper: attempt robust decoding using charset-normalizer
        def robust_decode(data: bytes) -> str:
            try:
                matches = cn_from_bytes(data)
                best = matches.best() if hasattr(matches, "best") else None
                if best and getattr(best, "encoding", None):
                    encoding = best.encoding
                    try:
                        return data.decode(encoding)
                    except Exception:
                        # Fallback to replace if strict decoding fails
                        return data.decode(encoding, errors="replace")
            except Exception:
                # If detection fails, continue to common fallbacks
                pass

            # 4) As a last resort, decode with replacement to avoid exceptions
            return hex_preview(data)

        try:
            raw: bytes
            if sudo:
                # Read with sudo (bytes)
                command = f"sudo cat '{file}'"
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    # Return a readable message rather than throwing generic 500
                    return FileReadResult(content=f"Failed to read file: {stderr.decode(errors='replace')}", file=file)
                raw = stdout
            else:
                # Asynchronously read file bytes to avoid UnicodeDecodeError
                def read_file_bytes():
                    try:
                        with open(file, 'rb') as f:
                            return f.read()
                    except Exception as e:
                        return str(e).encode()
                raw = await asyncio.to_thread(read_file_bytes)

            # Decide how to present content
            content = robust_decode(raw)

            # Process line range on decoded content
            if start_line is not None or end_line is not None:
                lines = content.splitlines()
                start = start_line if start_line is not None else 0
                end = end_line if end_line is not None else len(lines)
                content = '\n'.join(lines[start:end])

            return FileReadResult(
                content=content,
                file=file
            )
        except Exception as e:
            # Fallback: never explode with 500 due to decoding; return readable error text
            safe_message = f"Failed to read file safely: {str(e)}"
            return FileReadResult(content=safe_message, file=file)

    async def write_file(self, file: str, content: str, append: bool = False,
                  leading_newline: bool = False, trailing_newline: bool = False,
                  sudo: bool = False) -> FileWriteResult:
        """
        Asynchronously write file content
        
        Args:
            file: Absolute file path
            content: Content to write
            append: Whether to append mode
            leading_newline: Whether to add a leading newline
            trailing_newline: Whether to add a trailing newline
            sudo: Whether to use sudo privileges
        """
        try:
            # Prepare content
            if leading_newline:
                content = '\n' + content
            if trailing_newline:
                content = content + '\n'
            
            bytes_written = 0
            
            # Write with sudo
            if sudo:
                mode = '>>' if append else '>'
                # Create temporary file
                temp_file = f"/tmp/file_write_{os.getpid()}.tmp"
                
                # Asynchronously write to temporary file
                def write_temp_file():
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return len(content.encode('utf-8'))
                
                bytes_written = await asyncio.to_thread(write_temp_file)
                
                # Use sudo to write temporary file content to target file
                command = f"sudo bash -c \"cat {temp_file} {mode} '{file}'\""
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    return FileWriteResult(file=file, bytes_written=0)
                
                # Clean up temporary file
                os.unlink(temp_file)
            else:
                # Ensure directory exists
                os.makedirs(os.path.dirname(file), exist_ok=True)
                
                # Asynchronously write file
                def write_file_async():
                    mode = 'a' if append else 'w'
                    with open(file, mode, encoding='utf-8') as f:
                        return f.write(content)
                
                bytes_written = await asyncio.to_thread(write_file_async)
            
            return FileWriteResult(
                file=file,
                bytes_written=bytes_written
            )
        except Exception:
            return FileWriteResult(file=file, bytes_written=0)

    async def str_replace(self, file: str, old_str: str, new_str: str, 
                   sudo: bool = False) -> FileReplaceResult:
        """
        Asynchronously replace string in file
        
        Args:
            file: Absolute file path
            old_str: Original string to be replaced
            new_str: New replacement string
            sudo: Whether to use sudo privileges
        """
        # First read file content
        file_result = await self.read_file(file, sudo=sudo)
        content = file_result.content
        
        # Calculate replacement count
        replaced_count = content.count(old_str)
        if replaced_count == 0:
            return FileReplaceResult(
                file=file,
                replaced_count=0
            )
        
        # Perform replacement
        new_content = content.replace(old_str, new_str)
        
        # Write back to file
        await self.write_file(file, new_content, sudo=sudo)
        
        return FileReplaceResult(
            file=file,
            replaced_count=replaced_count
        )

    async def find_in_content(self, file: str, regex: str, 
                       sudo: bool = False) -> FileSearchResult:
        """
        Asynchronously search in file content
        
        Args:
            file: Absolute file path
            regex: Regular expression pattern
            sudo: Whether to use sudo privileges
        """
        # Read file
        file_result = await self.read_file(file, sudo=sudo)
        content = file_result.content
        
        # Process line by line
        lines = content.splitlines()
        matches = []
        line_numbers = []
        
        # Compile regular expression
        try:
            pattern = re.compile(regex)
        except Exception:
            return FileSearchResult(file=file, matches=[], line_numbers=[])
        
        # Find matches (use async processing for possibly large files)
        def process_lines():
            nonlocal matches, line_numbers
            for i, line in enumerate(lines):
                if pattern.search(line):
                    matches.append(line)
                    line_numbers.append(i)
        
        await asyncio.to_thread(process_lines)
        
        return FileSearchResult(
            file=file,
            matches=matches,
            line_numbers=line_numbers
        )

    async def find_by_name(self, path: str, glob_pattern: str) -> FileFindResult:
        """
        Asynchronously find files by name pattern
        
        Args:
            path: Directory path to search
            glob_pattern: File name pattern (glob syntax)
        """
        # Check if path exists
        if not os.path.exists(path):
            return FileFindResult(path=path, files=[])
        
        # Asynchronously find files
        def glob_async():
            search_pattern = os.path.join(path, glob_pattern)
            return glob.glob(search_pattern, recursive=True)
        
        files = await asyncio.to_thread(glob_async)
        
        return FileFindResult(
            path=path,
            files=files
        )

    async def upload_file(self, file_content: bytes, 
                   destination_path: str, make_executable: bool = False) -> FileUploadResponse:
        """
        Asynchronously upload a binary file to the filesystem
        
        Args:
            file_content: Binary content of the file
            destination_path: Absolute path to save the file to
            make_executable: Whether to make the file executable
            
        Returns:
            FileUploadResponse with the result of the operation
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Write the file
            def write_file_async():
                with open(destination_path, 'wb') as f:
                    f.write(file_content)
                
                # Make executable if requested
                if make_executable:
                    mode = os.stat(destination_path).st_mode
                    os.chmod(destination_path, mode | 0o111)  # Add execute permission for all
                
                return os.path.getsize(destination_path)
                
            size = await asyncio.to_thread(write_file_async)
            
            # Check if the file is executable
            is_executable = False
            if os.path.exists(destination_path):
                mode = os.stat(destination_path).st_mode
                is_executable = bool(mode & 0o111)  # Check if any execute bit is set
            
            return FileUploadResponse(
                file=destination_path,
                size=size,
                is_executable=is_executable
            )
        except Exception:
            return FileUploadResponse(file=destination_path, size=0, is_executable=False)

    async def download_file(self, file_path: str) -> bytes:
        """
        Asynchronously read binary file content
        
        Args:
            file_path: Absolute path of the file to download
            
        Returns:
            Binary content of the file
        """
        # Check if file exists
        if not os.path.exists(file_path):
            return b""
            
        if not os.path.isfile(file_path):
            return b""
            
        try:
            # Asynchronously read file
            def read_file_async():
                try:
                    with open(file_path, 'rb') as f:
                        return f.read()
                except Exception:
                    return b""
            
            # Execute IO operation in thread pool
            content = await asyncio.to_thread(read_file_async)
            return content
        except Exception:
            return b""

    async def file_exists(self, path: str) -> FileExistsResult:
        """
        检查文件或目录是否存在
        
        Args:
            path: 要检查的文件或目录路径
            
        Returns:
            FileExistsResult: 包含文件存在状态的结果
        """
        try:
            # 异步执行文件系统检查
            def check_exists_async():
                exists = os.path.exists(path)
                is_file = os.path.isfile(path) if exists else None
                is_dir = os.path.isdir(path) if exists else None
                return exists, is_file, is_dir
            
            exists, is_file, is_dir = await asyncio.to_thread(check_exists_async)
            
            return FileExistsResult(
                path=path,
                exists=exists,
                is_file=is_file,
                is_dir=is_dir
            )
        except Exception:
            return FileExistsResult(path=path, exists=False, is_file=None, is_dir=None)


# Service instance
file_service = FileService()
