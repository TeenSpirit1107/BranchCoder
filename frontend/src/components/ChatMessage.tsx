import React, { useState } from 'react';
import { Bot, Check, ChevronDown, CheckCircle } from 'lucide-react';
import ManusTextIcon from './icons/ManusTextIcon';
import { Message, MessageContent, ToolContent, StepContent } from '../types/message';
import ToolUse from './ToolUse';
import { useRelativeTime } from '../utils/timeUtils';
import { useUIStore } from '../store/uiStore';
import { cn } from '@/utils/cn';
import ChatFile from './ChatFile';
import ArtifactFiles from './ArtifactFiles';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const relativeTime = useRelativeTime(message.content.timestamp);
  const { setCurrentTool, setRealTime } = useUIStore();

  // 根据消息类型获取不同的内容
  const messageContent = message.content as MessageContent;
  const toolContent = message.content as ToolContent;
  const stepContent = message.content as StepContent;

  // 处理工具点击事件
  const handleToolClick = (tool: ToolContent) => {
    setCurrentTool(tool);
    setRealTime(false);
  };

  // 根据消息类型渲染不同的内容
  if (message.type === 'user') {
    return (
      <div className="flex w-full flex-col items-end justify-end gap-1 group mt-3">
        <div className="flex items-end">
          <div className="flex items-center justify-end gap-[2px] invisible group-hover:visible">
            <div className="float-right transition text-[12px] text-[var(--text-tertiary)] invisible group-hover:visible">
              {relativeTime}
            </div>
          </div>
        </div>
        <div className="flex max-w-[90%] relative flex-col gap-2 items-end">
          <div className="flex flex-col gap-2">
            {messageContent.file_ids?.map((fileId, index) => (
              <ChatFile key={index} fileId={fileId} />
            ))}
          </div>
          <div
            className="relative flex items-center rounded-[12px] overflow-hidden bg-[var(--fill-white)] dark:bg-[var(--fill-tsp-white-main)] p-3 ltr:rounded-br-none rtl:rounded-bl-none border border-[var(--border-main)] dark:border-0"
          >
            {messageContent.content}
          </div>
        </div>
      </div>
    );
  }

  if (message.type === 'assistant') {
    return (
      <div className="flex flex-col gap-2 w-full group mt-3">
        <div className="flex items-center justify-between h-7 group">
          <div className="flex items-center gap-[3px]">
            <Bot size={24} className="w-6 h-6" />
            <ManusTextIcon />
          </div>
          <div className="flex items-center gap-[2px] invisible group-hover:visible">
            <div className="float-right transition text-[12px] text-[var(--text-tertiary)] invisible group-hover:visible">
              {relativeTime}
            </div>
          </div>
        </div>
        <div className={cn(
          "max-w-none p-0 m-0 prose prose-sm sm:prose-base dark:prose-invert text-base text-[var(--text-primary)]",
          "prose-headings:text-[var(--text-primary)]", 
          "prose-p:text-[var(--text-primary)]",
          "prose-a:text-[var(--text-link)]", 
          "prose-strong:text-[var(--text-primary)]", 
          "prose-code:text-[var(--text-primary)]",
          "prose-pre:bg-[var(--fill-tsp-white-light)] prose-pre:text-[var(--text-primary)]",
          "prose-body:text-[var(--text-primary)]",
          "prose-li:text-[var(--text-primary)] prose-ol:text-[var(--text-primary)] prose-ul:text-[var(--text-primary)]",
          "prose-blockquote:text-[var(--text-primary)]"
        )}>
          <MarkdownRenderer
            content={messageContent.content}
          />
        </div>
      </div>
    );
  }

  if (message.type === 'tool') {
    // 检查是否为交付成果的消息传递功能
    const isDeliverArtifact = toolContent.function === 'message_deliver_artifact';
    // 从args中获取artifacts（如果存在）
    const artifacts = isDeliverArtifact && toolContent.args?.artifacts ? 
      toolContent.args.artifacts as string[] : 
      [];
    
    return (
      <div className="flex flex-col gap-2">
        <ToolUse tool={toolContent} onClick={() => handleToolClick(toolContent)} />
        {isDeliverArtifact && artifacts.length > 0 && (
          <div className="ml-6 mt-1">
            <ArtifactFiles 
              filePaths={artifacts}
              agentId={window.location.pathname.split('/').pop() || ''} 
            />
          </div>
        )}
      </div>
    );
  }

  if (message.type === 'step') {
    return (
      <div className="flex flex-col">
        <div 
          className="text-sm w-full clickable flex gap-2 justify-between group/header truncate text-[var(--text-primary)]"
        >
          <div className="flex flex-row gap-2 justify-center items-center truncate">
            {stepContent.status !== 'completed' ? (
              <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center border border-[var(--border-dark)] rounded-[15px]"></div>
            ) : (
              <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center border-[var(--border-dark)] rounded-[15px] bg-[var(--text-disable)] dark:bg-[var(--fill-tsp-white-dark)] border-0">
                <Check className="text-[var(--icon-white)] dark:text-[var(--icon-white-tsp)]" size={10} />
              </div>
            )}
            <div 
              className={cn(
                "truncate font-medium markdown-content",
                "text-[var(--text-primary)]"
              )}
            >
              {stepContent.description ? <MarkdownRenderer content={stepContent.description} /> : ''}
            </div>
            <span className="flex-shrink-0 flex" onClick={() => setIsExpanded(!isExpanded)}>
              <ChevronDown
                className={`transition-transform duration-300 w-4 h-4 ${isExpanded ? 'rotate-180' : ''}`}
              />
            </span>
          </div>
          <div className="float-right transition text-[12px] text-[var(--text-tertiary)] invisible group-hover/header:visible">
            {relativeTime}
          </div>
        </div>
        
        {/* 步骤工具列表 */}
        <div className="flex">
          <div className="w-[24px] relative">
            <div 
              className="border-l border-dashed border-[var(--border-dark)] absolute start-[8px] top-0 bottom-0"
              style={{ height: 'calc(100% + 14px)' }}
            ></div>
          </div>
          <div
            className={`flex flex-col gap-3 flex-1 min-w-0 overflow-hidden pt-2 transition-[max-height,opacity] duration-150 ease-in-out ${
              isExpanded 
                ? 'max-h-[100000px] opacity-100' 
                : 'max-h-0 opacity-0'
            }`}
          >
            {stepContent.tools && stepContent.tools.map((tool, index) => (
              <ToolUse key={index} tool={tool} onClick={() => handleToolClick(tool)} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (message.type === 'done') {
    return (
      <div className="flex items-center gap-1 text-[var(--text-tertiary)] text-sm">
        <CheckCircle className="text-green-500 " size={20} />
        <span>已完成</span>
      </div>
    );
  }

  return null;
};

export default ChatMessage; 