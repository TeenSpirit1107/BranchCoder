import { useRef, useEffect, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useChatUI } from './useChatUI';

export const useChatScroll = () => {
  const contentRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { messages } = useChatStore();
  const { follow, setFollow } = useChatUI();
  
  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, []);
  
  // 检查是否已滚动到底部
  const isScrolledToBottom = useCallback((threshold = 10) => {
    if (!contentRef.current) return false;
    const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
    return scrollHeight - scrollTop - clientHeight <= threshold;
  }, []);
  
  // 自动滚动到底部
  useEffect(() => {
    if (follow && contentRef.current) {
      scrollToBottom();
    }
  }, [messages, follow, scrollToBottom]);
  
  // 处理消息滚动事件
  const handleScroll = useCallback(() => {
    if (contentRef.current) {
      setFollow(isScrolledToBottom());
    }
  }, [isScrolledToBottom, setFollow]);
  
  // 强制跟随
  const handleFollow = useCallback(() => {
    setFollow(true);
    scrollToBottom();
  }, [setFollow, scrollToBottom]);
  
  return {
    contentRef,
    messagesEndRef,
    scrollToBottom,
    handleScroll,
    handleFollow
  };
}; 