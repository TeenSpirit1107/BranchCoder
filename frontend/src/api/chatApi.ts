import api from '../utils/axiosConfig';

interface ChatMessage {
  content: string;
  agentId?: string;
}

interface ChatResponse {
  message: string;
  timestamp: string;
}

// 发送聊天消息
export const sendMessage = async (data: ChatMessage): Promise<ChatResponse> => {
  try {
    const response = await api.post<ChatResponse>('/chat', data);
    return response.data;
  } catch (error) {
    console.error('发送消息失败:', error);
    throw error;
  }
};

// 获取聊天历史
export const getChatHistory = async (agentId?: string): Promise<ChatResponse[]> => {
  try {
    const response = await api.get<ChatResponse[]>('/chat/history', {
      params: { agentId }
    });
    return response.data;
  } catch (error) {
    console.error('获取聊天历史失败:', error);
    throw error;
  }
}; 