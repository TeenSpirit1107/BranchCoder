import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { X, Wifi, WifiOff } from 'lucide-react';
import BrowserControlView from '@/components/BrowserControlView';

const BrowserControlPage: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  useEffect(() => {
    if (!agentId) {
      console.error('No agentId provided in URL');
      navigate('/');
      return;
    }
  }, [agentId, navigate]);

  const handleClose = () => {
    window.close();
  };

  const handleConnectionStatusChange = (status: 'connecting' | 'connected' | 'disconnected') => {
    setConnectionStatus(status);
  };

  const getVNCView = useMemo(() => {
    if (!agentId) {
      return null;
    }
    return (
      <BrowserControlView agentId={agentId} onConnectionStatusChange={handleConnectionStatusChange} />
    );
  }, [agentId]);

  if (!agentId) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <p className="text-red-500 text-lg">Agent ID 不存在</p>
          <button 
            onClick={() => navigate('/')}
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col bg-black">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 text-white border-b border-gray-700">
        <div className="flex items-center gap-3">
          {/* 连接状态指示器 */}
          <div className="flex items-center gap-2">
            {connectionStatus === 'connected' && (
              <>
                <Wifi className="w-5 h-5 text-green-500" />
                <span className="text-sm text-green-500">已连接</span>
              </>
            )}
            {connectionStatus === 'connecting' && (
              <>
                <Wifi className="w-5 h-5 text-yellow-500 animate-pulse" />
                <span className="text-sm text-yellow-500">连接中...</span>
              </>
            )}
            {connectionStatus === 'disconnected' && (
              <>
                <WifiOff className="w-5 h-5 text-red-500" />
                <span className="text-sm text-red-500">连接断开</span>
              </>
            )}
          </div>
          
          <div className="text-sm text-gray-300">
            Agent: {agentId}
          </div>
        </div>

        {/* 关闭按钮 */}
        <button
          onClick={handleClose}
          className="flex items-center justify-center w-8 h-8 rounded hover:bg-gray-700 transition-colors"
          title="关闭窗口"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* VNC交互区域 */}
      <div className="flex-1 min-h-0 max-h-[calc(100vh-1rem)]">
        {getVNCView}
      </div>
    </div>
  );
};

export default BrowserControlPage; 