import { useState, useCallback } from 'react';
import { 
  listConversations, 
  deleteConversationHistory
} from '../api/conversationApi';
import { ConversationHistory, ConversationList } from '../types/conversationApi';

/**
 * useConversationList - 会话历史列表管理钩子
 * 
 * 职责：
 * 1. 管理会话历史列表的获取和显示
 * 2. 处理会话历史的删除操作
 * 3. 获取单个会话的详细信息
 */
export const useConversationList = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [history, setHistory] = useState<ConversationHistory | null>(null);
  const [conversations, setConversations] = useState<ConversationList | null>(null);

  /**
   * 获取会话列表
   */
  const fetchConversations = useCallback(async (limit: number = 50, offset: number = 0) => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('useConversationList: 开始获取会话列表...');
      const data = await listConversations(undefined, limit, offset);
      console.log('useConversationList: 获取到的原始数据:', data);
      console.log('useConversationList: 会话数量:', data?.conversations?.length || 0);
      setConversations(data);
      return data;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      console.error('useConversationList: 获取会话列表失败:', error);
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 删除指定Agent的会话历史
   */
  const deleteHistory = useCallback(async (agentId: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await deleteConversationHistory(agentId);
      if (result && history && history.agent_id === agentId) {
        setHistory(null);
      }
      
      // 如果已经加载了会话列表，从列表中移除已删除的会话
      if (conversations && conversations.conversations) {
        const updatedConversations = {
          ...conversations,
          conversations: conversations.conversations.filter(c => c.agent_id !== agentId),
          total: conversations.total - 1
        };
        setConversations(updatedConversations);
      }
      
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [history, conversations]);

  /**
   * 刷新会话列表
   */
  const refreshConversations = useCallback(async () => {
    if (conversations) {
      return await fetchConversations(50, 0);
    }
  }, [conversations, fetchConversations]);

  /**
   * 清空当前历史记录
   */
  const clearHistory = useCallback(() => {
    setHistory(null);
  }, []);

  /**
   * 清空会话列表
   */
  const clearConversations = useCallback(() => {
    setConversations(null);
  }, []);

  return {
    // 状态
    loading,
    error,
    history,
    conversations,
    
    // 方法
    fetchConversations,
    deleteHistory,
    refreshConversations,
    clearHistory,
    clearConversations
  };
}; 