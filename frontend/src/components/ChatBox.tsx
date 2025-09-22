import React, { useState, useEffect, useRef } from 'react';
import { ArrowUp, Upload, X, FileText, FileImage, FileCode, FileAudio, FileVideo, FileJson } from 'lucide-react';
import { uploadFile } from '../api/agentApi';
import { toast } from '@/components/Toast';
import FlowSelector from './FlowSelector';

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

interface ChatBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (fileIds?: string[]) => void;
  rows?: number;
  placeholder?: string;
  disabled?: boolean;
}

const ChatBox: React.FC<ChatBoxProps> = ({ 
  value, 
  onChange, 
  onSubmit, 
  rows = 1,
  placeholder = "给Manus一个任务...",
  disabled: chatDisabled = false
}) => {
  const [disabled, setDisabled] = useState(true);
  const [isComposing, setIsComposing] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<{id: string, name: string}[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // 当输入值改变时，设置禁用状态
  useEffect(() => {
    setDisabled(value.trim() === '' && uploadedFiles.length === 0);
  }, [value, uploadedFiles]);

  // 处理回车键按下事件
  const handleEnterKeydown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isComposing) {
      // 如果处于输入法组合状态，不做任何处理，允许默认行为
      return;
    }
    
    // 不在输入法组合状态且按钮未禁用时，阻止默认行为并提交
    if (!disabled && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  // 处理文件上传
  const handleFileUpload = async (files: FileList | File[]) => {
    const filesArray = Array.from(files);
    
    for (const file of filesArray) {
      try {
        const result = await uploadFile(file);
        if (result && result.id) {
          // 添加上传成功的文件ID和名称
          setUploadedFiles(prev => [...prev, {
            id: result.id, 
            name: result.filename || file.name
          }]);
          toast.success(`文件 ${file.name} 上传成功`);
        }
      } catch (error) {
        console.error('上传文件失败:', error);
        toast.error(`文件 ${file.name} 上传失败`);
      }
    }
  };

  // 处理粘贴事件
  const handlePaste = (event: React.ClipboardEvent) => {
    const items = event.clipboardData.items;
    const files: File[] = [];
    
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    
    if (files.length > 0) {
      handleFileUpload(files);
      event.preventDefault(); // 防止粘贴图片插入到文本区域
    }
  };

  // 处理拖拽事件
  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
    
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      handleFileUpload(event.dataTransfer.files);
    }
  };

  // 移除已上传文件
  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  // 处理提交
  const handleSubmit = () => {
    if (disabled) return;
    
    // 传递文件ID列表给父组件
    const fileIds = uploadedFiles.length > 0 ? uploadedFiles.map(file => file.id) : undefined;
    onSubmit(fileIds);
    
    // 清空已上传文件列表
    setUploadedFiles([]);
  };

  // 发送图标组件
  const SendIcon = ({ disabled }: { disabled: boolean }) => (
    <ArrowUp 
      size={18} 
      className={disabled ? 'text-gray-300' : 'text-white'} 
      strokeWidth={2.5}
    />
  );

  return (
    <div className="pb-3 relative bg-[var(--background-gray-main)]">
      <div 
        className={`flex flex-col gap-3 rounded-[22px] transition-all relative bg-[var(--fill-input-chat)] py-3 max-h-[300px] shadow-[0px_12px_32px_0px_rgba(0,0,0,0.02)] border ${
          isDragging ? 'border-blue-500 border-dashed' : 'border-black/8 dark:border-[var(--border-main)]'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {uploadedFiles.length > 0 && (
          <div className="px-4 flex flex-wrap gap-2">
            {uploadedFiles.map((file, index) => {
              const FileIcon = getFileIcon(file.name);
              return (
                <div 
                  key={index} 
                  className="bg-[var(--background-tsp-card-gray)] dark:bg-[var(--background-menu-white)] rounded-lg px-3 py-1.5 flex items-center gap-2 text-sm border border-[var(--border-light)] dark:border-[var(--border-white)]"
                >
                  <FileIcon size={16} className="text-[var(--icon-secondary)]" />
                  <span className="text-[var(--text-primary)] max-w-[120px] truncate">{file.name}</span>
                  <button 
                    onClick={() => removeFile(index)}
                    className="text-[var(--icon-tertiary)] hover:text-[var(--icon-secondary)] rounded-full hover:bg-[var(--hover-color)] p-1"
                    title="移除文件"
                  >
                    <X size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <div className="overflow-y-auto pl-4 pr-2">
          <textarea
            ref={textareaRef}
            className="flex rounded-md border-input focus-visible:outline-none focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 overflow-hidden flex-1 bg-transparent p-0 pt-[1px] border-0 focus-visible:ring-0 focus-visible:ring-offset-0 w-full placeholder:text-[var(--text-disable)] text-[15px] shadow-none resize-none min-h-[40px]"
            rows={rows}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={() => setIsComposing(false)}
            onKeyDown={handleEnterKeydown}
            onPaste={handlePaste}
            placeholder={isDragging ? "拖放文件到这里上传..." : placeholder}
            style={{ height: '46px' }}
            disabled={chatDisabled}
          />
        </div>
        <footer className="flex flex-row justify-between w-full px-3">
          <div className="flex gap-2 pr-2 items-center">
            <FlowSelector disabled={chatDisabled} />
            <div className="flex gap-2">
              <button
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:opacity-90 border border-[var(--border-primary)]"
                onClick={() => document.getElementById('file-upload')?.click()}
                title="上传文件"
                disabled={chatDisabled}
              >
                <Upload size={18} />
                <input
                  id="file-upload"
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => e.target.files && handleFileUpload(e.target.files)}
                  disabled={chatDisabled}
                />
              </button>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              className={`whitespace-nowrap text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 text-primary-foreground hover:bg-primary/90 p-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors hover:opacity-90 ${
                disabled || chatDisabled
                  ? 'cursor-not-allowed bg-[var(--fill-tsp-white-dark)]' 
                  : 'cursor-pointer bg-[var(--Button-primary-black)]'
              }`}
              onClick={handleSubmit}
              disabled={disabled || chatDisabled}
            >
              <SendIcon disabled={disabled || chatDisabled} />
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default ChatBox; 