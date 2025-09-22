// 会话历史相关接口的类型定义

export interface ConversationEvent {
  id: string;
  agent_id: string;
  event_type: string;
  event_data: any;
  timestamp: string;
  sequence: number;
}

export interface ConversationHistory {
  agent_id: string;
  user_id: string;
  flow_id: string;
  title?: string;
  created_at: string;
  updated_at: string;
  events: ConversationEvent[];
  total_events?: number;
}

export interface ConversationList {
  conversations: ConversationHistory[];
  total: number;
  limit: number;
  offset: number;
} 

/**
 * 连接状态枚举
 */
export enum ConnectionStatus {
    DISCONNECTED = 'disconnected',
    CONNECTING = 'connecting',
    CONNECTED = 'connected',
    RECONNECTING = 'reconnecting',
    ERROR = 'error'
  }
  