import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import ToolPanel from '../components/ToolPanel';
import ChatContent from '../components/chat/ChatContent';
import ChatNavBar from '../components/chat/ChatNavBar';
import { useAgentChat } from '../hooks/useAgentChat';
import { useUIStore } from '../store/uiStore';
import { MessageContent } from '../types/message';

const ChatPage: React.FC = () => {
  const { agentId } = useParams<{ agentId: string }>();
  const { initializeConnection, reset } = useAgentChat(agentId);
  const [inputMessage, setInputMessage] = useState('');
  
  // 直接使用UI store
  const { 
    setCurrentTool,
    currentTool
  } = useUIStore();
  
  // 使用钩子处理聊天逻辑
  const { sendMessage } = useAgentChat(agentId);
  
  // 处理发送消息
  const handleSendMessage = async (msg: MessageContent) => {
    setInputMessage('');
    await sendMessage(msg);
  };

  useEffect(() => {
    if (agentId) {
      reset();
      initializeConnection();
    }
  }, [agentId, initializeConnection, reset]);
  
  // 如果没有agentId，不应该渲染ChatPage
  if (!agentId) {
    return null;
  }
  
  return (
    <div className="relative flex flex-col w-full h-full">
      <div className="flex flex-row h-full w-full max-w-full">
        {/* 主体内容区域 */}
        <div className="flex flex-1 overflow-hidden flex-col h-full w-full max-w-[768px] mx-auto sm:min-w-[390px]">
          {/* 顶部标题栏 */}
          <ChatNavBar />
          {/* 聊天区域 */}
          <ChatContent 
            inputMessage={inputMessage}
            setInputMessage={setInputMessage}
            sendMessage={handleSendMessage}
          />
        </div>
        {/* 右侧工具面板区域 */}
        <div className={`transition-all duration-300 border-l border-[var(--border-main)] h-full overflow-hidden ${currentTool ? 'w-[50%] min-w-[400px]' : 'w-0'}`}>
          {currentTool && (
            <ToolPanel 
              currentTool={currentTool}
              agentId={agentId} 
              onClose={() => setCurrentTool(undefined)}
              showPlanPanel={!!currentTool}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatPage; 