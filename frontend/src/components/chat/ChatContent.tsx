import React, { useMemo } from 'react';
import { ArrowDown } from 'lucide-react';
import { useChatStore } from '../../store/chatStore';
import { useUIStore } from '../../store/uiStore';
import { useChatScroll } from '../../hooks/useChatScroll';
import { Message, MessageContent } from '../../types/message';
import ChatMessage from '../ChatMessage';
import PlanPanel from './PlanPanel';
import ChatBox from '../ChatBox';
import { useAgentChat } from '@/hooks/useAgentChat';

interface ChatContentProps {
  inputMessage: string;
  setInputMessage: (message: string) => void;
  sendMessage: (message: MessageContent) => void;
}

const ChatContent: React.FC<ChatContentProps> = ({
  inputMessage,
  setInputMessage,
  sendMessage,
}) => {
  const { messages, plan } = useChatStore();
  const { isConnected } = useAgentChat();
  const { follow, currentTool } = useUIStore();
  const { contentRef, messagesEndRef, handleScroll, handleFollow } = useChatScroll();

  const getMessageContent = useMemo(() => {
    return messages.map((message: Message, index: number) => (
      <ChatMessage 
        key={index} 
        message={message} 
      />
    ))
  }, [messages]);

  return (
    <div className="flex flex-col flex-1 min-w-0 h-[calc(100%-3rem)]">
      {/* 中间内容区域 - 消息列表(可滚动) */}
      <div 
        ref={contentRef}
        className="flex-1 overflow-y-auto px-5"
        onScroll={handleScroll}
      >
        <div className="flex flex-col gap-[12px] pt-[12px]">
          {getMessageContent}

          {/* 加载指示器 */}
          {isConnected && (
            <div className="flex items-center gap-1 text-[var(--text-tertiary)] text-sm">
              <span>思考中</span>
              <span className="flex gap-1 relative top-[4px]">
                <span 
                  className="w-[3px] h-[3px] rounded bg-[var(--icon-tertiary)] inline-block animate-dot-animation"
                  style={{ 
                    animationDelay: '0ms'
                  }}
                ></span>
                <span 
                  className="w-[3px] h-[3px] rounded bg-[var(--icon-tertiary)] inline-block animate-dot-animation"
                  style={{ 
                    animationDelay: '200ms'
                  }}
                ></span>
                <span 
                  className="w-[3px] h-[3px] rounded bg-[var(--icon-tertiary)] inline-block animate-dot-animation"
                  style={{ 
                    animationDelay: '400ms'
                  }}
                ></span>
              </span>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 底部区域 - 使用flex布局 */}
      <div className="flex-shrink-0 bg-[var(--background-gray-main)]">
        <div className="mx-auto max-w-[768px] sm:min-w-[390px] w-full px-5">
          {/* 计划面板区域 */}
          {!currentTool && plan && plan.steps.length > 0 && (
            <>
              {!follow && (
                <button 
                  onClick={handleFollow}
                  className="flex items-center justify-center w-[36px] h-[36px] rounded-full bg-[var(--background-white-main)] hover:bg-[var(--background-gray-main)] clickable border border-[var(--border-main)] shadow-[0px_5px_16px_0px_var(--shadow-S),0px_0px_1.25px_0px_var(--shadow-S)] absolute bottom-[200px] left-1/2 -translate-x-1/2"
                >
                  <ArrowDown className="text-[var(--icon-primary)]" size={20} />
                </button>
              )}
              <div className="bg-[var(--background-gray-main)] rounded-[22px_22px_0px_0px] pb-2">
                <PlanPanel />
              </div>
            </>
          )}
          {/* 聊天输入框区域 */}
          <div className="py-2">
            <ChatBox 
              value={inputMessage}
              onChange={setInputMessage}
              onSubmit={(fileIds) => sendMessage({content: inputMessage, file_ids: fileIds || [], timestamp: Math.floor(Date.now() / 1000)})}
              placeholder="给Manus一个任务..."
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatContent; 