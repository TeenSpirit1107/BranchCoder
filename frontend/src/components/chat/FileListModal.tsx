import React, { useEffect, useState, useCallback } from 'react';
import { Download, Folder, File, ArrowLeft, RefreshCw, Eye } from 'lucide-react';
import { FileListItem, FileListResponse, downloadFile, listFiles } from '../../api/agentApi';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose, DialogOverlay } from '../ui/dialog';
import { useUIStore } from '@/store/uiStore';
import { ToolContent } from '../../types/message';

interface FileListModalProps {
  agentId: string;
  onClose: () => void;
  open: boolean;
}

const FileListModal: React.FC<FileListModalProps> = ({ agentId, onClose, open }) => {
  const [fileList, setFileList] = useState<FileListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState<string>('/home/ubuntu');
  const { showTool } = useUIStore();

  const fetchFileList = useCallback(async (path: string = '/') => {
    setLoading(true);
    setError(null);
    try {
      const response = await listFiles(agentId, path);
      setFileList(response);
      setCurrentPath(response.current_path);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取文件列表失败');
      console.error('获取文件列表失败', err);
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    if (open) {
      fetchFileList(currentPath);
    }
  }, [agentId, currentPath, open, fetchFileList]);

  const handleFileClick = (item: FileListItem) => {
    if (item.is_dir) {
      // 如果是目录，导航到该目录
      setCurrentPath(item.path);
    } else {
      // 如果是文件，下载该文件
      downloadFile(agentId, item.path, item.name);
    }
  };

  const navigateToParent = () => {
    // 导航到上一级目录
    if (currentPath === '/') return;
    
    const pathParts = currentPath.split('/').filter(Boolean);
    pathParts.pop();
    const parentPath = pathParts.length === 0 ? '/' : '/' + pathParts.join('/');
    setCurrentPath(parentPath);
  };

  // 检查是否为可预览的文件
  const isPreviewable = useCallback((filename: string) => {
    if (!filename) return false;
    
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    
    // 可预览的文件类型
    const previewableExtensions = [
      // 文本文件
      'txt', 'md', 'markdown', 'json', 'xml', 'yaml', 'yml', 'csv',
      // 代码文件
      'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'cs', 'go', 
      'php', 'rb', 'html', 'css', 'scss', 'less', 'sh', 'bash', 'sql',
      // 配置文件
      'ini', 'conf', 'config', 'env', 'properties', 'toml',
      // 文档文件
      'log', 'rst', 'tex', 'pdf', 
      // 图片文件
      'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico',
      // 音频文件
      'mp3', 'wav', 'ogg', 'aac', 'm4a', 'flac', 'wma'
    ];
    
    return previewableExtensions.includes(extension);
  }, []);

  // 获取文件类型
  const getFileType = useCallback((filename: string): 'text' | 'image' | 'audio' => {
    if (!filename) return 'text';
    
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    
    // 图片文件
    if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico'].includes(extension)) {
      return 'image';
    }
    
    // 音频文件
    if (['mp3', 'wav', 'ogg', 'aac', 'm4a', 'flac', 'wma'].includes(extension)) {
      return 'audio';
    }
    
    // 默认为文本文件
    return 'text';
  }, []);

  // 处理预览点击
  const handlePreview = (item: FileListItem) => {
    if (agentId && item.path) {
      const fileType = getFileType(item.name);
      let toolContent: ToolContent;
      
      if (fileType === 'image') {
        // 创建图片工具内容
        toolContent = {
          name: 'image',
          function: 'image_view',
          args: {
            image_path: item.path
          },
          timestamp: Date.now()
        };
      } else if (fileType === 'audio') {
        // 创建音频工具内容
        toolContent = {
          name: 'audio',
          function: 'audio_play',
          args: {
            audio_path: item.path
          },
          timestamp: Date.now()
        };
      } else {
        // 创建文件工具内容（文本文件）
        toolContent = {
          name: 'file',
          function: 'file_read',
          args: {
            file: item.path
          },
          timestamp: Date.now()
        };
      }
      
      // 显示工具面板并设置当前工具
      showTool(toolContent);
      onClose();
    }
  };

  // 格式化文件大小
  const formatFileSize = (size: number): string => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  // 格式化修改时间
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen: boolean) => !isOpen && onClose()}>
      <DialogOverlay />
      <DialogContent className="flex flex-col max-w-4xl w-[90vw] h-[80vh]">
        <DialogHeader>
          <DialogTitle>文件列表</DialogTitle>
          <DialogClose />
        </DialogHeader>
        
        {/* 导航栏 */}
        <div className="flex items-center p-3 border-b border-[var(--border-main)]">
          <button 
            onClick={navigateToParent}
            disabled={currentPath === '/'}
            className={`p-1 mr-2 rounded-md ${currentPath === '/' ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-[var(--fill-tsp-gray-main)]'}`}
          >
            <ArrowLeft size={18} />
          </button>
          <div className="flex-grow truncate">
            当前路径: <span className="font-mono">{currentPath}</span>
          </div>
          <button 
            onClick={() => fetchFileList(currentPath)}
            className="p-1 rounded-md hover:bg-[var(--fill-tsp-gray-main)]"
            title="刷新"
          >
            <RefreshCw size={18} />
          </button>
        </div>
        
        {/* 文件列表内容 */}
        <div className="flex-grow overflow-y-auto p-2" style={{ minHeight: 0 }}>
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <RefreshCw size={24} className="animate-spin mr-2" />
              <span>加载中...</span>
            </div>
          ) : error ? (
            <div className="text-red-500 p-4 text-center">
              {error}
            </div>
          ) : fileList && fileList.items.length === 0 ? (
            <div className="text-center p-8 text-gray-500">
              此目录为空
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left border-b border-[var(--border-main)]">
                  <th className="p-2">名称</th>
                  <th className="p-2 w-24">大小</th>
                  <th className="p-2 w-40">修改时间</th>
                  <th className="p-2 w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                {fileList?.items.map((item) => (
                  <tr key={item.path} className="border-b border-[var(--border-main)] hover:bg-[var(--fill-tsp-gray-main)]">
                    <td 
                      className="p-2 cursor-pointer flex items-center"
                      onClick={() => handleFileClick(item)}
                    >
                      {item.is_dir ? (
                        <Folder size={18} className="mr-2 text-[var(--icon-secondary)]" />
                      ) : (
                        <File size={18} className="mr-2 text-[var(--icon-secondary)]" />
                      )}
                      <span className="truncate">{item.name}</span>
                    </td>
                    <td className="p-2">
                      {item.is_dir ? '-' : formatFileSize(item.size)}
                    </td>
                    <td className="p-2">
                      {formatDate(item.modified_time)}
                    </td>
                    <td className="p-2">
                      <div className="flex items-center gap-1">
                        {!item.is_dir && isPreviewable(item.name) && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePreview(item);
                            }}
                            className="p-1 hover:bg-[var(--fill-tsp-gray-main)] rounded-md"
                            title="预览文件"
                          >
                            <Eye size={16} className="text-[var(--icon-secondary)]" />
                          </button>
                        )}
                        {!item.is_dir && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              downloadFile(agentId, item.path, item.name);
                            }}
                            className="p-1 hover:bg-[var(--fill-tsp-gray-main)] rounded-md"
                            title="下载"
                          >
                            <Download size={16} className="text-[var(--icon-secondary)]" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default FileListModal; 