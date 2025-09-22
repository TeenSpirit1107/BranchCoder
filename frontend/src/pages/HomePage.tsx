import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import HomePageContent from '../components/chat/HomePageContent';
import { useAgentChat } from '../hooks/useAgentChat';
import { MessageContent } from '../types/message';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [inputMessage, setInputMessage] = useState('');
  
  // 使用钩子处理聊天逻辑，不传入agentId表示创建新聊天
  const { sendMessage } = useAgentChat();
  
  // 处理发送消息并导航到新的聊天页
  const handleSendMessage = async (msg: MessageContent) => {
    setInputMessage('');
    const newAgentId = await sendMessage(msg);
    
    // 创建新聊天后导航到聊天页
    if (newAgentId) {
      navigate(`/chat/${newAgentId}`, { replace: true });
    }
  };
  
  return (
    <div className="relative flex flex-col w-full h-full">
      <HomePageContent 
        inputMessage={inputMessage}
        setInputMessage={setInputMessage}
        handleSendMessage={handleSendMessage}
      />
    </div>
  );
};

export default HomePage; 