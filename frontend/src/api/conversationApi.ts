import { apiClient, BASE_URL } from './client';
import { SSEEvent } from '../types/sseEvent';
import { ConversationHistory, ConversationList } from '../types/conversationApi';
import { fetchEventSource, EventSourceMessage } from '@microsoft/fetch-event-source';

// 会话事件接口
export interface ConversationEvent {
  id: string;
  agent_id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  timestamp: string;
  sequence: number;
}

/**
 * 获取指定Agent的会话历史
 * @param agentId Agent ID
 * @returns 会话历史数据
 */
export const getConversationHistory = async (agentId: string): Promise<ConversationHistory> => {
  const response = await apiClient.get<ConversationHistory>(`/conversations/agent/${agentId}`);
  return response.data;
};

/**
 * 删除指定Agent的会话历史
 * @param agentId Agent ID
 * @returns 删除结果
 */
export const deleteConversationHistory = async (agentId: string): Promise<boolean> => {
  const response = await apiClient.delete<{ success: boolean }>(`/conversations/agent/${agentId}`);
  return response.data.success;
};

/**
 * 列出会话历史
 * @param userId 用户ID（可选）
 * @param limit 每页数量
 * @param offset 偏移量
 * @returns 会话列表
 */
export const listConversations = async (
  userId?: string,
  limit: number = 50,
  offset: number = 0
): Promise<ConversationList> => {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  
  if (userId) {
    params.append('user_id', userId);
  }
  
  console.log('conversationApi: 发送请求到:', `/conversations/list?${params.toString()}`);
  const response = await apiClient.get<ConversationList>(`/conversations/list?${params.toString()}`);
  console.log('conversationApi: 收到响应:', response);
  console.log('conversationApi: 响应数据:', response.data);
  return response.data;
};

/**
 * 重放指定Agent的会话事件（使用新的事件流架构）
 * @param agentId Agent ID
 * @param fromSequence 起始序号，默认为1
 * @param onMessage 消息回调函数
 * @param onError 错误回调函数
 * @returns 事件源控制对象
 */
export const replayConversation = (
  agentId: string,
  fromSequence: number = 1,
  onMessage: (event: SSEEvent) => void,
  onError?: (error: Error) => void
) => {
  const url = `${BASE_URL}/conversations/agent/${agentId}/replay?from_sequence=${fromSequence}`;
  
  const abortController = new AbortController();
  
  fetchEventSource(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
    openWhenHidden: true,
    signal: abortController.signal,
    body: JSON.stringify({
      from_sequence: fromSequence
    }),
    onopen: async (response) => {
      if (response.ok) {
        console.log(`会话重放连接成功: Agent ${agentId}, 从序号 ${fromSequence} 开始`);
      } else {
        throw new Error(`会话重放连接失败: ${response.status} ${response.statusText}`);
      }
    },
    onmessage(event: EventSourceMessage) {
      if (event.event && event.event.trim() !== '') {
        try {
          const eventType = event.event as SSEEvent['event'];
          const eventData = JSON.parse(event.data);
          
          // 根据事件类型创建正确的SSEEvent对象
          onMessage({ event: eventType, data: eventData } as SSEEvent);
        } catch (err) {
          console.error('解析重放事件数据失败:', err);
          if (onError) {
            onError(err instanceof Error ? err : new Error(String(err)));
          }
        }
      }
    },
    onerror(err) {
      console.error('会话重放SSE连接错误:', err);
      if (onError) {
        onError(err instanceof Error ? err : new Error(String(err)));
      }
      throw err;
    },
  });
  
  return {
    close: () => {
      abortController.abort();
    }
  };
};
