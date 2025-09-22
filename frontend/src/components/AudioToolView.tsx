import React, { useEffect, useState, useCallback } from 'react';
import { getFileDownloadUrl } from '../api/agentApi';
import { toast } from '@/components/Toast';
import { Volume2, VolumeX, Play, Pause, RotateCcw } from 'lucide-react';

// 定义音频工具参数类型
interface AudioToolArgs {
  audio_path?: string;
  [key: string]: unknown;
}

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: AudioToolArgs;
  result?: unknown;
}

interface AudioToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

const AudioToolView: React.FC<AudioToolViewProps> = ({ agentId, toolContent }) => {
  const [audioUrl, setAudioUrl] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [audioRef, setAudioRef] = useState<HTMLAudioElement | null>(null);

  // 从toolContent获取音频文件路径
  const audioPath = toolContent?.args?.audio_path as string || '';

  // 获取文件名
  const fileName = audioPath ? audioPath.split('/').pop() || '' : '';

  // 初始化音频URL
  const initAudioUrl = useCallback(() => {
    if (!audioPath) return;

    try {
      const url = getFileDownloadUrl(agentId, audioPath);
      setAudioUrl(url);
    } catch (error) {
      console.error('获取音频URL失败:', error);
      toast.error('获取音频URL失败');
    }
  }, [agentId, audioPath]);

  // 播放/暂停控制
  const togglePlayPause = useCallback(() => {
    if (!audioRef) return;

    if (isPlaying) {
      audioRef.pause();
    } else {
      audioRef.play().catch((error) => {
        console.error('播放音频失败:', error);
        toast.error('播放音频失败');
      });
    }
  }, [audioRef, isPlaying]);

  // 静音控制
  const toggleMute = useCallback(() => {
    if (!audioRef) return;
    
    audioRef.muted = !isMuted;
    setIsMuted(!isMuted);
  }, [audioRef, isMuted]);

  // 重置播放
  const resetAudio = useCallback(() => {
    if (!audioRef) return;
    
    audioRef.currentTime = 0;
    setCurrentTime(0);
  }, [audioRef]);

  // 音量控制
  const handleVolumeChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(event.target.value);
    setVolume(newVolume);
    if (audioRef) {
      audioRef.volume = newVolume;
    }
  }, [audioRef]);

  // 进度控制
  const handleProgressChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(event.target.value);
    setCurrentTime(newTime);
    if (audioRef) {
      audioRef.currentTime = newTime;
    }
  }, [audioRef]);

  // 格式化时间
  const formatTime = (time: number): string => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // 音频事件处理
  const handleAudioRef = useCallback((audio: HTMLAudioElement | null) => {
    if (audioRef) {
      // 清理旧的事件监听器
      audioRef.removeEventListener('loadedmetadata', () => {});
      audioRef.removeEventListener('timeupdate', () => {});
      audioRef.removeEventListener('play', () => {});
      audioRef.removeEventListener('pause', () => {});
      audioRef.removeEventListener('ended', () => {});
    }

    setAudioRef(audio);

    if (audio) {
      // 添加事件监听器
      const handleLoadedMetadata = () => {
        setDuration(audio.duration);
      };

      const handleTimeUpdate = () => {
        setCurrentTime(audio.currentTime);
      };

      const handlePlay = () => {
        setIsPlaying(true);
      };

      const handlePause = () => {
        setIsPlaying(false);
      };

      const handleEnded = () => {
        setIsPlaying(false);
        setCurrentTime(0);
      };

      audio.addEventListener('loadedmetadata', handleLoadedMetadata);
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('play', handlePlay);
      audio.addEventListener('pause', handlePause);
      audio.addEventListener('ended', handleEnded);

      // 设置初始音量
      audio.volume = volume;
    }
  }, [audioRef, volume]);

  // 当音频路径变化时初始化URL
  useEffect(() => {
    if (audioPath) {
      initAudioUrl();
    }
  }, [audioPath, initAudioUrl]);

  // 检查是否为音频文件
  const isAudioFile = (filename: string): boolean => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    return ['mp3', 'wav', 'ogg', 'aac', 'm4a', 'flac', 'wma'].includes(extension);
  };

  if (!audioPath) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <div className="text-center">
          <Volume2 className="h-12 w-12 text-[var(--icon-secondary)] mx-auto mb-2" />
          <p className="text-[var(--text-tertiary)]">未找到音频文件路径</p>
        </div>
      </div>
    );
  }

  if (!isAudioFile(fileName)) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        <div className="text-center">
          <Volume2 className="h-12 w-12 text-[var(--icon-secondary)] mx-auto mb-2" />
          <p className="text-[var(--text-tertiary)]">不支持的音频格式</p>
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
      <div className="flex-1 min-h-0 w-full overflow-y-auto">
        <div className="flex flex-col h-full p-6">
          {/* 音频播放器 */}
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-md">
              {/* 音频元素 */}
              {audioUrl && (
                <audio
                  ref={handleAudioRef}
                  src={audioUrl}
                  preload="metadata"
                  className="hidden"
                />
              )}
              
              {/* 音频可视化区域 */}
              <div className="bg-[var(--background-white-main)] rounded-lg p-6 shadow-sm border border-[var(--border-main)] mb-4">
                <div className="flex items-center justify-center mb-4">
                  <Volume2 className="h-16 w-16 text-[var(--icon-primary)]" />
                </div>
                <div className="text-center mb-4">
                  <h3 className="text-lg font-medium text-[var(--text-primary)] truncate">
                    {fileName}
                  </h3>
                </div>
              </div>

              {/* 播放控制 */}
              <div className="bg-[var(--background-white-main)] rounded-lg p-4 shadow-sm border border-[var(--border-main)]">
                {/* 进度条 */}
                <div className="mb-4">
                  <input
                    type="range"
                    min="0"
                    max={duration || 0}
                    value={currentTime}
                    onChange={handleProgressChange}
                    className="w-full h-2 bg-[var(--background-gray-main)] rounded-lg appearance-none cursor-pointer slider"
                  />
                  <div className="flex justify-between text-xs text-[var(--text-tertiary)] mt-1">
                    <span>{formatTime(currentTime)}</span>
                    <span>{formatTime(duration)}</span>
                  </div>
                </div>

                {/* 控制按钮 */}
                <div className="flex items-center justify-center gap-4 mb-4">
                  <button
                    onClick={resetAudio}
                    className="p-2 rounded-full hover:bg-[var(--background-gray-main)] transition-colors"
                    title="重置"
                  >
                    <RotateCcw size={20} className="text-[var(--text-secondary)]" />
                  </button>
                  
                  <button
                    onClick={togglePlayPause}
                    className="p-3 rounded-full bg-[var(--background-gray-main)] hover:bg-[var(--background-gray-main)] transition-colors"
                    title={isPlaying ? "暂停" : "播放"}
                  >
                    {isPlaying ? (
                      <Pause size={24} className="text-[var(--text-primary)]" />
                    ) : (
                      <Play size={24} className="text-[var(--text-primary)] ml-1" />
                    )}
                  </button>
                  
                  <button
                    onClick={toggleMute}
                    className="p-2 rounded-full hover:bg-[var(--background-gray-main)] transition-colors"
                    title={isMuted ? "取消静音" : "静音"}
                  >
                    {isMuted ? (
                      <VolumeX size={20} className="text-[var(--text-secondary)]" />
                    ) : (
                      <Volume2 size={20} className="text-[var(--text-secondary)]" />
                    )}
                  </button>
                </div>

                {/* 音量控制 */}
                <div className="flex items-center gap-2">
                  <VolumeX size={16} className="text-[var(--text-tertiary)]" />
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={volume}
                    onChange={handleVolumeChange}
                    className="flex-1 h-2 bg-[var(--background-gray-main)] rounded-lg appearance-none cursor-pointer slider"
                  />
                  <Volume2 size={16} className="text-[var(--text-tertiary)]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .slider::-webkit-slider-thumb {
          appearance: none;
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: var(--background-primary);
          cursor: pointer;
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .slider::-moz-range-thumb {
          height: 16px;
          width: 16px;
          border-radius: 50%;
          background: var(--background-primary);
          cursor: pointer;
          border: 2px solid white;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
      `}</style>
    </>
  );
};

export default AudioToolView; 