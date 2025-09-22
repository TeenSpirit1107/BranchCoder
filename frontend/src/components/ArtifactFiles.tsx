import { useMemo } from 'react';
import { FileText, FileImage, FileCode, FileAudio, FileVideo, FileJson, Download, Eye } from 'lucide-react';
import { downloadFile } from '../api/agentApi';
import { useUIStore } from '@/store/uiStore';
import { ToolContent } from '../types/message';

// 根据文件扩展名获取对应图标
const getFileIcon = (filename: string) => {
  if (!filename) return FileText;
  
  const extension = filename.split('.').pop()?.toLowerCase() || '';
  
  // 图片文件
  if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp'].includes(extension)) {
    return FileImage;
  }
  
  // 代码文件
  if (['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'cs', 'go', 'php', 'rb', 'html', 'css', 'scss', 'less', 'sh', 'bash'].includes(extension)) {
    return FileCode;
  }
  
  // 音频文件
  if (['mp3', 'wav', 'ogg', 'flac', 'aac'].includes(extension)) {
    return FileAudio;
  }
  
  // 视频文件
  if (['mp4', 'webm', 'avi', 'mov', 'wmv', 'mkv'].includes(extension)) {
    return FileVideo;
  }
  
  // JSON文件
  if (['json'].includes(extension)) {
    return FileJson;
  }
  
  // 默认文件图标
  return FileText;
};

// 从路径中提取文件名
const extractFilename = (path: string): string => {
  if (!path) return '';
  const parts = path.split('/');
  return parts[parts.length - 1];
};

// 单个文件组件
interface ArtifactFileItemProps {
  filePath: string;
  agentId: string;
}

const ArtifactFileItem: React.FC<ArtifactFileItemProps> = ({ filePath, agentId }) => {
  const filename = useMemo(() => extractFilename(filePath), [filePath]);
  const { showTool } = useUIStore();
  
  const FileIcon = useMemo(() => {
    return getFileIcon(filename);
  }, [filename]);

  const handleDownload = () => {
    if (agentId && filePath) {
      downloadFile(agentId, filePath, filename);
    }
  };

  // 检查是否为可预览的文本文件
  const isPreviewable = useMemo(() => {
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
  }, [filename]);

  // 获取文件类型
  const getFileType = useMemo(() => {
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
  }, [filename]);

  // 处理预览点击
  const handlePreview = () => {
    if (agentId && filePath) {
      let toolContent: ToolContent;
      
      if (getFileType === 'image') {
        // 创建图片工具内容
        toolContent = {
          name: 'image',
          function: 'image_view',
          args: {
            image_path: filePath
          },
          timestamp: Date.now()
        };
      } else if (getFileType === 'audio') {
        // 创建音频工具内容
        toolContent = {
          name: 'audio',
          function: 'audio_play',
          args: {
            audio_path: filePath
          },
          timestamp: Date.now()
        };
      } else {
        // 创建文件工具内容（文本文件）
        toolContent = {
          name: 'file',
          function: 'file_read',
          args: {
            file: filePath
          },
          timestamp: Date.now()
        };
      }
      
      // 显示工具面板并设置当前工具
      showTool(toolContent);
    }
  };

  return (
    <div className="flex items-center p-2 bg-[var(--fill-tsp-gray-main)] rounded-md border border-[var(--border-main)] hover:bg-[var(--fill-tsp-gray-dark)]">
      <FileIcon size={18} className="text-[var(--icon-secondary)]" />
      <div className="flex flex-col flex-grow px-2" title={filename}>
        <span className="text-sm font-medium truncate max-w-[200px]">{filename}</span>
      </div>
      <div className="flex items-center gap-1">
        {isPreviewable && (
          <button 
            onClick={handlePreview}
            className="p-1 rounded-full hover:bg-[var(--fill-tsp-white-dark)]"
            title="预览文件"
          >
            <Eye size={16} className="text-[var(--icon-secondary)]" />
          </button>
        )}
        <button 
          onClick={handleDownload}
          className="p-1 rounded-full hover:bg-[var(--fill-tsp-white-dark)]"
          title="下载文件"
        >
          <Download size={16} className="text-[var(--icon-secondary)]" />
        </button>
      </div>
    </div>
  );
};

// 多个文件组件
interface ArtifactFilesProps {
  filePaths: string[];
  agentId: string;
}

export default function ArtifactFiles({ filePaths, agentId }: ArtifactFilesProps) {
  if (!filePaths || filePaths.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-1 lg:grid-cols-2 gap-3">
      {filePaths.map((filePath: string, index: number) => (
        <ArtifactFileItem 
          key={index}
          filePath={filePath} 
          agentId={agentId} 
        />
      ))}
    </div>
  );
} 