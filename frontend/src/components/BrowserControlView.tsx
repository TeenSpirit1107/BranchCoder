import React, { useEffect, useRef, useCallback } from 'react';
// @ts-expect-error - NoVNC library doesn't have TypeScript definitions
import RFB from '@novnc/novnc/lib/rfb';
import { getVNCUrl } from '../api/agentApi';

interface BrowserControlViewProps {
  agentId: string;
  onConnectionStatusChange?: (status: 'connecting' | 'connected' | 'disconnected') => void;
}

const BrowserControlView: React.FC<BrowserControlViewProps> = ({ 
  agentId, 
  onConnectionStatusChange 
}) => {
  const vncContainerRef = useRef<HTMLDivElement>(null);
  const rfbRef = useRef<RFB | null>(null);

  const handleConnect = useCallback(() => {
    console.log('VNC连接成功');
    onConnectionStatusChange?.('connected');
  }, [onConnectionStatusChange]);

  const handleDisconnect = useCallback((e: CustomEvent) => {
    console.log('VNC连接断开', e.detail);
    onConnectionStatusChange?.('disconnected');
  }, [onConnectionStatusChange]);

//   const handleCredentialsRequired = useCallback(() => {
//     console.log('VNC需要凭证');
//   }, []);

//   const handleSecurityFailure = useCallback((e: CustomEvent) => {
//     console.error('VNC安全验证失败', e.detail);
//     onConnectionStatusChange?.('disconnected');
//   }, [onConnectionStatusChange]);

  // 创建VNC连接的函数
  const createVNCConnection = useCallback(() => {
    if (!vncContainerRef.current || rfbRef.current) return;

    // 设置连接状态为连接中
    onConnectionStatusChange?.('connecting');

    const wsUrl = getVNCUrl(agentId);

    // 创建NoVNC连接 - 启用完整交互功能
    rfbRef.current = new RFB(vncContainerRef.current, wsUrl, {
      credentials: { password: '' },
      shared: true,
      repeaterID: '',
      wsProtocols: ['binary'],
      scaleViewport: true,
      resizeSession: true,
    });

    // 设置缩放模式和尺寸
    if (rfbRef.current) {
      rfbRef.current.scaleViewport = true;
      rfbRef.current.resizeSession = true;
      // 设置客户端期望的分辨率
      rfbRef.current.clipViewport = true;
    }

    // 绑定事件监听器
    rfbRef.current.addEventListener('connect', handleConnect);
    rfbRef.current.addEventListener('disconnect', handleDisconnect);
  }, [agentId, handleConnect, handleDisconnect, onConnectionStatusChange]);

  // 断开VNC连接的函数
  const disconnectVNC = useCallback(() => {
    if (rfbRef.current) {
      rfbRef.current.removeEventListener('connect', handleConnect);
      rfbRef.current.removeEventListener('disconnect', handleDisconnect);
      rfbRef.current.disconnect();
      rfbRef.current = null;
    }
  }, [handleConnect, handleDisconnect]);

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

  // 处理键盘事件，确保焦点在VNC上
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 阻止某些快捷键的默认行为，确保它们传递给VNC
      if (e.ctrlKey || e.altKey || e.metaKey) {
        e.preventDefault();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  return (
    <div className="w-full h-full flex items-center justify-center bg-gray-900">
      <div 
        ref={vncContainerRef} 
        className="w-full h-full"
        style={{
          display: 'flex',
          overflow: 'auto',
          background: 'rgb(40, 40, 40)',
        }}
      />
    </div>
  );
};

export default BrowserControlView; 