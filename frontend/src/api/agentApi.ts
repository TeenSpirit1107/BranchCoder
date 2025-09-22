import { apiClient, BASE_URL } from './client';
import { fetchEventSource, EventSourceMessage } from '@microsoft/fetch-event-source';
import { SSEEvent } from '../types/sseEvent';
import { MessageContent } from '../types/message';

// Agent相关接口
export interface Agent {
  agent_id: string;
  status: string;
  message: string;
}

export interface AgentResponse {
  data: Agent;
  code: number;
  msg: string;
}

// 发送消息响应接口
export interface SendMessageResponse {
  success: boolean;
  timestamp: number;
  queued: boolean;
}

// Flow类型接口
export interface FlowType {
  flow_id: string;
  name: string;
  description?: string;
}

// 创建Agent请求接口
export interface CreateAgentRequest {
  flow_id?: string;
}

/**
 * 创建新的Agent
 */
export const createAgent = async (flowId?: string): Promise<AgentResponse> => {
  try {
    const requestBody: CreateAgentRequest = {};
    if (flowId) {
      requestBody.flow_id = flowId;
    }

    const response = await fetch(`${BASE_URL}/agents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    return data as AgentResponse;
  } catch (error) {
    console.error('创建Agent失败:', error);
    throw error;
  }
};

/**
 * 发送消息到Agent（不返回事件流）
 * 
 * 这个接口只负责将消息放入Agent的处理队列，不返回事件流。
 * 客户端需要通过getEventStream方法来接收事件流。
 */
export const sendMessage = async (
  agentId: string,
  message: string,
  fileIds?: string[]
): Promise<SendMessageResponse> => {
  try {
    const response = await fetch(`${BASE_URL}/agents/${agentId}/send-message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        timestamp: Math.floor(Date.now() / 1000),
        file_ids: fileIds || []
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    if (data.code !== 0) {
      throw new Error(data.msg || '发送消息失败');
    }

    return data.data as SendMessageResponse;
  } catch (error) {
    console.error('发送消息失败:', error);
    throw error;
  }
};

/**
 * 获取Agent的事件流，支持断连重连
 * 
 * 这个接口允许客户端在断连后重新连接，并从指定序号开始接收事件。
 * Agent会继续在后台运行，即使没有客户端连接。
 */
export const getEventStream = (
  agentId: string,
  fromSequence: number = 1,
  onMessage: (event: SSEEvent) => void,
  onError?: (error: Error) => void,
  onOpen?: () => void,
  onClose?: () => void
) => {
  const url = `${BASE_URL}/agents/${agentId}/events?from_sequence=${fromSequence}`;
  
  const abortController = new AbortController();
  
  const eventSourcePromise = fetchEventSource(url, {
    method: 'GET',
    headers: {
      'Accept': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
    openWhenHidden: true,
    signal: abortController.signal,
    onopen: async (response) => {
      if (response.ok) {
        console.log(`事件流连接成功: Agent ${agentId}, 从序号 ${fromSequence} 开始`);
        if (onOpen) {
          onOpen();
        }
      } else {
        throw new Error(`事件流连接失败: ${response.status} ${response.statusText}`);
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
          console.error('解析事件数据失败:', err);
          if (onError) {
            onError(err instanceof Error ? err : new Error(String(err)));
          }
        }
      }
    },
    onerror(err) {
      console.error('事件流错误:', err);
      if (onError) {
        onError(err instanceof Error ? err : new Error(String(err)));
      }
      throw err;
    },
    onclose() {
      console.log('事件流连接已关闭');
      if (onClose) {
        onClose();
      }
    }
  });

  return {
    close: () => {
      abortController.abort();
    },
    promise: eventSourcePromise
  };
};

/**
 * 获取VNC URL
 */
export const getVNCUrl = (agentId: string): string => {
  // 将http转为ws，https转为wss
  const wsBaseUrl = BASE_URL.replace(/^http/, 'ws');
  return `${wsBaseUrl}/agents/${agentId}/vnc`;
}

/**
 * 与Agent聊天（使用SSE接收流式响应）
 * 
 * @deprecated 推荐使用 sendMessage + getEventStream 的组合方式
 * 这个方法保留用于向后兼容，但新代码应该使用分离的接口
 */
export const chatWithAgent = async (
  agentId: string, 
  message: MessageContent, 
  onMessage: (event: SSEEvent) => void,
  onError?: (error: Error) => void,
) => {
  try {
    const apiUrl = `${BASE_URL}/agents/${agentId}/chat`;
    const eventSource = fetchEventSource(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      openWhenHidden: true,
      body: JSON.stringify({ 
        message: message.content, 
        timestamp: Math.floor(Date.now() / 1000),
        file_ids: message.file_ids || [] 
      }),
      onmessage(event: EventSourceMessage) {
        if (event.event && event.event.trim() !== '') {
          const eventType = event.event as SSEEvent['event'];
          const eventData = JSON.parse(event.data);
          
          // 根据事件类型创建正确的SSEEvent对象
          onMessage({ event: eventType, data: eventData } as SSEEvent);
        }
      },
      onerror(err) {
        console.error('事件源错误:', err);
        if (onError) {
          onError(err instanceof Error ? err : new Error(String(err)));
        }
        throw err;
      },
    });
    return eventSource;
  } catch (error) {
    console.error('聊天错误:', error);
    if (onError) {
      onError(error instanceof Error ? error : new Error(String(error)));
    }
    throw error;
  }
};

export interface ConsoleRecord {
  ps1: string;
  command: string;
  output: string;
}

export interface ShellViewResponse {
  output: string;
  session_id: string;
  console: ConsoleRecord[];
}

/**
 * 查看Shell会话输出
 * @param agentId Agent ID
 * @param sessionId Shell会话ID
 * @returns Shell会话输出内容
 */
export async function viewShellSession(agentId: string, sessionId: string): Promise<ShellViewResponse> {
  const response = await apiClient.post<ShellViewResponse>(`/agents/${agentId}/shell`, { session_id: sessionId });
  return response.data;
}

export interface FileViewResponse {
  content: string;
  file: string;
}

/**
 * 查看文件内容
 * @param agentId Agent ID
 * @param file 文件路径
 * @returns 文件内容
 */
export async function viewFile(agentId: string, file: string): Promise<FileViewResponse> {
  const response = await apiClient.post<FileViewResponse>(`/agents/${agentId}/file`, { file });
  return response.data;
}

/**
 * 文件上传响应
 */
export interface FileUploadResponse {
  id: string;
  filename: string;
  path: string;
}

/**
 * 上传文件到用户账户
 * @param file 要上传的文件对象
 * @param metadata 可选的文件元数据（对象形式）
 * @returns 上传结果，包含文件ID和路径
 */
export async function uploadFile(
  file: File, 
  metadata?: Record<string, unknown>
): Promise<FileUploadResponse> {
  // 创建FormData对象
  const formData = new FormData();
  formData.append('file', file);
  
  if (metadata) {
    formData.append('metadata', JSON.stringify(metadata));
  }

  try {
    const response = await fetch(`${BASE_URL}/users/me/files`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.msg || `上传失败: ${response.status}`);
    }

    const data = await response.json();
    return data as FileUploadResponse;
  } catch (error) {
    console.error('文件上传失败:', error);
    throw error;
  }
}

/**
 * 获取文件下载链接
 * @param agentId Agent ID
 * @param filePath 要下载的文件路径
 * @returns 文件下载URL
 */
export function getFileDownloadUrl(agentId: string, filePath: string): string {
  // 编码文件路径，确保URL安全
  const encodedFilePath = encodeURIComponent(filePath);
  return `${BASE_URL}/agents/${agentId}/file/download?file=${encodedFilePath}`;
}

/**
 * 下载文件
 * @param agentId Agent ID
 * @param filePath 要下载的文件路径
 * @param fileName 保存的文件名（可选）
 */
export async function downloadFile(
  agentId: string, 
  filePath: string, 
  fileName?: string
): Promise<void> {
  try {
    // 获取下载链接
    const downloadUrl = getFileDownloadUrl(agentId, filePath);
    
    // 创建一个临时链接元素
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.target = '_blank';
    
    // 设置下载文件名
    if (fileName) {
      link.download = fileName;
    } else {
      // 如果没有提供文件名，尝试从路径中获取
      const pathParts = filePath.split('/');
      link.download = pathParts[pathParts.length - 1];
    }
    
    // 添加到文档并触发点击
    document.body.appendChild(link);
    link.click();
    
    // 清理
    document.body.removeChild(link);
  } catch (error) {
    console.error('文件下载失败:', error);
    throw error;
  }
}

export interface FileMetadata {
  id: string;
  filename: string;
}

/**
 * 通过文件id获取用户上传文件的元数据
 * @param fileId 文件id
 * @returns 文件元数据
 */
export async function getFileMetadata(fileId: string): Promise<FileMetadata> {
  const response = await apiClient.get<FileMetadata>(`/users/me/files/${fileId}`);
  return response.data;
}

/**
 * 文件列表响应
 */
export interface FileListItem {
  name: string;
  path: string;
  size: number;
  is_dir: boolean;
  modified_time: string;
}

export interface FileListResponse {
  current_path: string;
  items: FileListItem[];
}

/**
 * 获取目录文件列表
 * @param agentId Agent ID
 * @param path 目录路径，默认为根目录
 * @returns 文件列表
 */
export async function listFiles(
  agentId: string, 
  path: string = '/'
): Promise<FileListResponse> {
  const response = await apiClient.post<FileListResponse>(`/agents/${agentId}/list-files`, { path });
  return response.data;
}

/**
 * 获取所有可用的flow类型
 */
export const getAvailableFlows = async (): Promise<FlowType[]> => {
  try {
    const response = await fetch(`${BASE_URL}/agents/flows`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    if (data.code !== 0) {
      throw new Error(data.msg || '获取flow类型失败');
    }

    return data.data as FlowType[];
  } catch (error) {
    console.error('获取可用flow失败:', error);
    throw error;
  }
};

// Code Server相关接口
export interface CodeServerResponse {
  agent_id: string;
  code_server_url: string;
}

/**
 * 获取Agent的Code Server子域名URL
 */
export const getCodeServerUrl = async (agentId: string): Promise<CodeServerResponse> => {
  try {
    const response = await fetch(`${BASE_URL}/agents/${agentId}/code-server-url`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    if (data.code !== 0) {
      throw new Error(data.msg || '获取Code Server URL失败');
    }

    return data.data as CodeServerResponse;
  } catch (error) {
    console.error('获取Code Server URL失败:', error);
    throw error;
  }
}; 