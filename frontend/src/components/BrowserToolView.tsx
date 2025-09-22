import React, { useEffect, useRef, useCallback } from 'react';
// @ts-expect-error - NoVNC library doesn't have TypeScript definitions
import RFB from '@novnc/novnc/lib/rfb';
import { getVNCUrl } from '../api/agentApi';

// 定义ToolContent接口，与Vue项目的types/message.ts中一致
interface ToolContent {
  name: string;
  function: string;
  args: Record<string, unknown>;
  result?: unknown;
}

interface BrowserToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

const BrowserToolView: React.FC<BrowserToolViewProps> = ({ agentId, toolContent }) => {
  const vncContainerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<RFB | null>(null);

  // 创建VNC连接的函数
  const createVNCConnection = useCallback(() => {
    if (!vncContainerRef.current || rfbRef.current) return;

    const wsUrl = getVNCUrl(agentId);

    // 创建NoVNC连接 - 只读模式
    rfbRef.current = new RFB(vncContainerRef.current, wsUrl, {
      credentials: { password: '' },
      shared: true,
      repeaterID: '',
      wsProtocols: ['binary'],
      // 缩放选项
      scaleViewport: true, // 自动缩放以适应容器
    });

    // 显式设置viewOnly属性 - 确保只读模式
    rfbRef.current.viewOnly = true;
    rfbRef.current.scaleViewport = true;

    rfbRef.current.addEventListener('connect', () => {
      console.log('VNC连接成功');
    });

    rfbRef.current.addEventListener('disconnect', (e: CustomEvent) => {
      console.log('VNC连接断开', e);
    });

    rfbRef.current.addEventListener('credentialsrequired', () => {
      console.log('VNC需要凭证');
    });
  }, [agentId]);

  // 断开VNC连接的函数
  const disconnectVNC = useCallback(() => {
    if (rfbRef.current) {
      rfbRef.current.disconnect();
      rfbRef.current = null;
    }
  }, []);

  // 处理页面可见性变化
  const handleVisibilityChange = useCallback(() => {
    if (document.visibilityState === 'hidden') {
      console.log('页面隐藏，断开VNC连接');
      disconnectVNC();
    } else if (document.visibilityState === 'visible') {
      console.log('页面显示，重新建立VNC连接');
      createVNCConnection();
    }
  }, [createVNCConnection, disconnectVNC]);

  useEffect(() => {
    // 初始连接
    createVNCConnection();

    // 添加页面可见性监听器
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // 清理函数
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      disconnectVNC();
    };
  }, [createVNCConnection, handleVisibilityChange, disconnectVNC]);

  return (
    <>
      <div className="h-[36px] flex items-center px-3 w-full bg-[var(--background-gray-main)] border-b border-[var(--border-main)] rounded-t-[12px] shadow-[inset_0px_1px_0px_0px_#FFFFFF] dark:shadow-[inset_0px_1px_0px_0px_#FFFFFF30]">
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-[250px] truncate text-[var(--text-tertiary)] text-sm font-medium text-center">
            {
              (toolContent?.args?.url) ?
              <a href={String(toolContent?.args?.url)} target="_blank" rel="noopener noreferrer" className="text-[var(--text-primary)]">
                {String(toolContent?.args?.url)}
              </a>
              :
              'Browser'
            }
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 w-full overflow-y-auto">
        <div className="px-0 py-0 flex flex-col relative h-full">
          <div className="w-full h-full object-cover flex items-center justify-center bg-[var(--fill-white)] relative">
            <div className="w-full h-full">
              <div 
                ref={vncContainerRef} 
                style={{ 
                  display: 'flex', 
                  width: '100%', 
                  height: '100%', 
                  overflow: 'auto', 
                  background: 'rgb(40, 40, 40)' 
                }}
              ></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default BrowserToolView; 