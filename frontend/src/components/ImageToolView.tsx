import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { getFileDownloadUrl } from '../api/agentApi';
import { toast } from '@/components/Toast';
import { Image, ZoomIn, ZoomOut, RotateCw, Download, Maximize2 } from 'lucide-react';

// 定义图片工具参数类型
interface ImageToolArgs {
  image_path?: string;
  [key: string]: unknown;
}

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: ImageToolArgs;
  result?: unknown;
}

interface ImageToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

const ImageToolView: React.FC<ImageToolViewProps> = ({ agentId, toolContent }) => {
  const [imageUrl, setImageUrl] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // 从toolContent获取图片文件路径
  const imagePath = toolContent?.args?.image_path as string || '';

  // 获取文件名
  const fileName = imagePath ? imagePath.split('/').pop() || '' : '';

  // 初始化图片URL
  const initImageUrl = useCallback(() => {
    if (!imagePath) return;

    try {
      const url = getFileDownloadUrl(agentId, imagePath);
      setImageUrl(url);
      setLoading(false);
    } catch (error) {
      console.error('获取图片URL失败:', error);
      toast.error('获取图片URL失败');
      setError('获取图片URL失败');
      setLoading(false);
    }
  }, [agentId, imagePath]);

  // 缩放控制
  const handleZoomIn = useCallback(() => {
    setScale(prev => Math.min(prev * 1.2, 5));
  }, []);

  const handleZoomOut = useCallback(() => {
    setScale(prev => Math.max(prev / 1.2, 0.1));
  }, []);

  const handleResetZoom = useCallback(() => {
    setScale(1);
    setRotation(0);
  }, []);

  // 旋转控制
  const handleRotate = useCallback(() => {
    setRotation(prev => (prev + 90) % 360);
  }, []);

  // 全屏控制
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev);
  }, []);

  // 下载图片
  const handleDownload = useCallback(() => {
    if (!imageUrl) return;

    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = fileName;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [imageUrl, fileName]);

  // 图片加载错误处理
  const handleImageError = useCallback(() => {
    setError('图片加载失败');
    setLoading(false);
  }, []);

  // 图片加载成功处理
  const handleImageLoad = useCallback(() => {
    setLoading(false);
    setError(null);
  }, []);

  // 当图片路径变化时初始化URL
  useEffect(() => {
    if (imagePath) {
      setLoading(true);
      setError(null);
      initImageUrl();
    }
  }, [imagePath, initImageUrl]);

  // 检查是否为图片文件
  const isImageFile = (filename: string): boolean => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    return ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico'].includes(extension);
  };

  // 键盘事件处理
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isFullscreen) return;

      switch (event.key) {
        case 'Escape':
          setIsFullscreen(false);
          break;
        case '+':
        case '=':
          event.preventDefault();
          handleZoomIn();
          break;
        case '-':
          event.preventDefault();
          handleZoomOut();
          break;
        case 'r':
        case 'R':
          event.preventDefault();
          handleRotate();
          break;
        case '0':
          event.preventDefault();
          handleResetZoom();
          break;
      }
    };

    if (isFullscreen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isFullscreen, handleZoomIn, handleZoomOut, handleRotate, handleResetZoom]);

  const ImageViewer = useMemo(() => (
    <div className="flex flex-col h-full">
      {/* 工具栏 */}
      <div className="flex items-center justify-between p-3 bg-[var(--background-white-main)] border-b border-[var(--border-main)]">
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            className="p-2 rounded hover:bg-[var(--background-gray-main)] transition-colors"
            title="缩小 (-)"
          >
            <ZoomOut size={16} className="text-[var(--text-secondary)]" />
          </button>
          <span className="text-sm text-[var(--text-tertiary)] min-w-[60px] text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={handleZoomIn}
            className="p-2 rounded hover:bg-[var(--background-gray-main)] transition-colors"
            title="放大 (+)"
          >
            <ZoomIn size={16} className="text-[var(--text-secondary)]" />
          </button>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRotate}
            className="p-2 rounded hover:bg-[var(--background-gray-main)] transition-colors"
            title="旋转 (R)"
          >
            <RotateCw size={16} className="text-[var(--text-secondary)]" />
          </button>
          <button
            onClick={handleResetZoom}
            className="px-3 py-1 text-sm rounded hover:bg-[var(--background-gray-main)] transition-colors text-[var(--text-secondary)]"
            title="重置 (0)"
          >
            重置
          </button>
          <button
            onClick={handleDownload}
            className="p-2 rounded hover:bg-[var(--background-gray-main)] transition-colors"
            title="下载"
          >
            <Download size={16} className="text-[var(--text-secondary)]" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded hover:bg-[var(--background-gray-main)] transition-colors"
            title="全屏 (Esc退出)"
          >
            <Maximize2 size={16} className="text-[var(--text-secondary)]" />
          </button>
        </div>
      </div>

      {/* 图片显示区域 */}
      <div className="flex-1 overflow-hidden bg-[var(--background-gray-main)] relative">
        <div className="w-full h-full flex items-center justify-center p-4">
          {loading && (
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--border-primary)] mx-auto mb-2"></div>
              <p className="text-[var(--text-tertiary)]">加载中...</p>
            </div>
          )}
          
          {error && (
            <div className="text-center">
              <Image className="h-12 w-12 text-[var(--icon-secondary)] mx-auto mb-2" />
              <p className="text-[var(--text-tertiary)]">{error}</p>
            </div>
          )}
          
          {imageUrl && !loading && !error && (
            <img
              src={imageUrl}
              alt={fileName}
              onLoad={handleImageLoad}
              onError={handleImageError}
              style={{
                transform: `scale(${scale}) rotate(${rotation}deg)`,
                transition: 'transform 0.2s ease-in-out',
                maxWidth: 'none',
                maxHeight: 'none',
                objectFit: 'contain',
              }}
              className="cursor-move select-none"
              draggable={false}
            />
          )}
        </div>
      </div>
    </div>
  ), [
    imageUrl, 
    fileName, 
    scale, 
    rotation, 
    error,
    loading,
    handleZoomOut, 
    handleZoomIn, 
    handleRotate, 
    handleResetZoom, 
    handleDownload, 
    toggleFullscreen,
    handleImageLoad,
    handleImageError
  ]);

  if (!imagePath) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <div className="text-center">
          <Image className="h-12 w-12 text-[var(--icon-secondary)] mx-auto mb-2" />
          <p className="text-[var(--text-tertiary)]">未找到图片文件路径</p>
        </div>
      </div>
    );
  }

  if (!isImageFile(fileName)) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <div className="text-center">
          <Image className="h-12 w-12 text-[var(--icon-secondary)] mx-auto mb-2" />
          <p className="text-[var(--text-tertiary)]">不支持的图片格式</p>
          <p className="text-sm text-[var(--text-quaternary)] mt-1">{fileName}</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="h-[36px] flex items-center px-3 w-full bg-[var(--background-gray-main)] border-b border-[var(--border-main)] rounded-t-[12px] shadow-[inset_0px_1px_0px_0px_#FFFFFF] dark:shadow-[inset_0px_1px_0px_0px_#FFFFFF30]">
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-[250px] truncate text-[var(--text-tertiary)] text-sm font-medium text-center">
            {fileName}
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 w-full overflow-hidden">
        {ImageViewer}
      </div>

      {/* 全屏模式 */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-90 flex flex-col">
          <div className="flex items-center justify-between p-4 bg-black bg-opacity-50">
            <h3 className="text-white font-medium">{fileName}</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={handleZoomOut}
                className="p-2 rounded text-white hover:bg-white hover:bg-opacity-20 transition-colors"
                title="缩小 (-)"
              >
                <ZoomOut size={20} />
              </button>
              <span className="text-white min-w-[60px] text-center">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={handleZoomIn}
                className="p-2 rounded text-white hover:bg-white hover:bg-opacity-20 transition-colors"
                title="放大 (+)"
              >
                <ZoomIn size={20} />
              </button>
              <button
                onClick={handleRotate}
                className="p-2 rounded text-white hover:bg-white hover:bg-opacity-20 transition-colors"
                title="旋转 (R)"
              >
                <RotateCw size={20} />
              </button>
              <button
                onClick={handleResetZoom}
                className="px-3 py-2 text-white rounded hover:bg-white hover:bg-opacity-20 transition-colors"
                title="重置 (0)"
              >
                重置
              </button>
              <button
                onClick={toggleFullscreen}
                className="px-3 py-2 text-white rounded hover:bg-white hover:bg-opacity-20 transition-colors"
                title="退出全屏 (Esc)"
              >
                退出全屏
              </button>
            </div>
          </div>
          <div className="flex-1 flex items-center justify-center p-4">
            {imageUrl && (
              <img
                src={imageUrl}
                alt={fileName}
                style={{
                  transform: `scale(${scale}) rotate(${rotation}deg)`,
                  transition: 'transform 0.2s ease-in-out',
                  maxWidth: '90vw',
                  maxHeight: '90vh',
                  objectFit: 'contain',
                }}
                className="cursor-move select-none"
                draggable={false}
              />
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default ImageToolView; 