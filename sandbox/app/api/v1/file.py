"""
File operation API interfaces
"""
from fastapi import APIRouter, UploadFile, File, Form, Response as FastAPIResponse
import os
from app.schemas.file import (
    FileReadRequest, FileWriteRequest, FileReplaceRequest,
    FileSearchRequest, FileFindRequest, FileExistsRequest,
    FileDownloadRequest
)
from app.schemas.response import Response
from app.services.file import file_service
import re
from urllib.parse import quote

router = APIRouter()

@router.post("/read", response_model=Response)
async def read_file(request: FileReadRequest):
    """
    Read file content
    """
    result = await file_service.read_file(
        file=request.file,
        start_line=request.start_line,
        end_line=request.end_line,
        sudo=request.sudo
    )
    
    # Construct response
    return Response(
        success=True,
        message="File read successfully",
        data=result.model_dump()
    )

@router.post("/write", response_model=Response)
async def write_file(request: FileWriteRequest):
    """
    Write file content
    """
    result = await file_service.write_file(
        file=request.file,
        content=request.content,
        append=request.append,
        leading_newline=request.leading_newline,
        trailing_newline=request.trailing_newline,
        sudo=request.sudo
    )
    
    # Construct response
    return Response(
        success=True,
        message="File written successfully",
        data=result.model_dump()
    )

@router.post("/replace", response_model=Response)
async def replace_in_file(request: FileReplaceRequest):
    """
    Replace string in file
    """
    result = await file_service.str_replace(
        file=request.file,
        old_str=request.old_str,
        new_str=request.new_str,
        sudo=request.sudo
    )
    
    # Construct response
    return Response(
        success=True,
        message=f"Replacement completed, replaced {result.replaced_count} occurrences",
        data=result.model_dump()
    )

@router.post("/search", response_model=Response)
async def search_in_file(request: FileSearchRequest):
    """
    Search in file content
    """
    result = await file_service.find_in_content(
        file=request.file,
        regex=request.regex,
        sudo=request.sudo
    )
    
    # Construct response
    return Response(
        success=True,
        message=f"Search completed, found {len(result.matches)} matches",
        data=result.model_dump()
    )

@router.post("/find", response_model=Response)
async def find_files(request: FileFindRequest):
    """
    Find files by name pattern
    """
    result = await file_service.find_by_name(
        path=request.path,
        glob_pattern=request.glob
    )
    
    # Construct response
    return Response(
        success=True,
        message=f"Search completed, found {len(result.files)} files",
        data=result.model_dump()
    )

@router.post("/upload", response_model=Response)
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    make_executable: bool = Form(False)
):
    """
    Upload a binary file to the sandbox filesystem
    
    Args:
        file: The file to upload
        path: The destination path where the file should be saved
        make_executable: Whether to make the file executable
        
    Returns:
        Response with the result of the upload operation
    """
    # Read file content
    content = await file.read()
    
    # Upload file
    result = await file_service.upload_file(
        file_content=content,
        destination_path=path,
        make_executable=make_executable
    )
    
    # Construct response
    return Response(
        success=True,
        message=f"File uploaded successfully, size: {result.size} bytes",
        data=result.model_dump()
    )

@router.post("/exists", response_model=Response)
async def check_file_exists(request: FileExistsRequest):
    """
    检查文件或目录是否存在
    
    Args:
        request: 包含要检查的路径
        
    Returns:
        包含存在状态的响应
    """
    result = await file_service.file_exists(path=request.path)
    
    # 构建响应
    return Response(
        success=True,
        message="File existence check completed",
        data=result.model_dump()
    )

@router.post("/download")
async def download_file(request: FileDownloadRequest):
    """
    下载文件
    
    Args:
        path: 要下载的文件路径
        
    Returns:
        文件的二进制内容，作为下载响应
    """
    try:
        # 获取文件二进制内容
        file_path = request.path
        content = await file_service.download_file(file_path=file_path)
        
        # 获取文件名
        file_name = os.path.basename(file_path)

        is_ascii = all(ord(c) < 128 for c in file_name)
        
        if is_ascii:
            # 如果是ASCII文件名，直接使用
            content_disposition = f'attachment; filename="{file_name}"'
        else:
            # 对于非ASCII文件名，提供两种形式
            # 1. filename参数使用ASCII文件名（可以是原始名称的简化版或转义版）
            # 2. filename*参数使用UTF-8编码的完整文件名
            
            # 创建一个简单的ASCII文件名版本
            ascii_filename = re.sub(r'[^\x00-\x7F]', '_', file_name)
            
            # 为filename*参数编码UTF-8文件名
            utf8_filename = quote(file_name)
            
            content_disposition = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{utf8_filename}'
        
        # 创建二进制响应
        return FastAPIResponse(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": content_disposition
            }
        )
    except Exception as e:
        # 出错时返回标准响应格式
        return Response(
            success=False,
            message=str(e),
            data=None
        )
