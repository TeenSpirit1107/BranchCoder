import { getFileMetadata, FileMetadata } from '../api/agentApi';
import { useState, useEffect, useMemo } from 'react';
import { FileText, FileImage, FileCode, FileAudio, FileVideo, FileJson } from 'lucide-react';

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

export default function ChatFile({ fileId }: { fileId: string }) {
  const [fileMetadata, setFileMetadata] = useState<FileMetadata | null>(null);

  useEffect(() => {
    getFileMetadata(fileId).then(setFileMetadata);
  }, [fileId]);

  const FileIcon = useMemo(() => {
    return getFileIcon(fileMetadata?.filename || '');
  }, [fileMetadata?.filename]);

  return (
    <div className="flex items-center p-2 bg-[var(--fill-tsp-gray-main)] rounded-md border border-[var(--border-main)]">
      <FileIcon size={18} className="mr-2 text-[var(--icon-secondary)]" />
      <div className="flex flex-col">
        <span className="text-sm font-medium">{fileMetadata?.filename}</span>
      </div>
    </div>
  );
}

