import { create } from 'zustand';
import { Message, ToolContent, StepContent } from '../types/message';
import { PlanEventData } from '../types/sseEvent';
import { FlowType } from '../api/agentApi';
import { ConnectionStatus } from '../types/conversationApi';

// 核心聊天状态 - 只保留必要的数据状态
interface ChatState {
  // 核心数据状态
  messages: Message[];
  connectionState: ConnectionStatus;
  title: string;
  plan: PlanEventData | undefined;
  
  // Flow相关状态
  selectedFlow: string | undefined;
  flows: FlowType[];
  
  // 基础操作
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  setConnectionState: (connectionState: ConnectionStatus) => void;
  setTitle: (title: string) => void;
  setPlan: (plan: PlanEventData | undefined) => void;
  
  // Flow操作
  setSelectedFlow: (flowId: string) => void;
  setFlows: (flows: FlowType[]) => void;
  
  // 消息操作
  updateStepStatus: (stepId: string, status: 'completed' | 'failed') => void;
  addToolToStep: (stepId: string, tool: ToolContent) => void;
  
  // 重置
  resetState: () => void;
  
  // 计算属性 - 通过getter实现
  getLastStep: () => StepContent | undefined;
  getLastNoMessageTool: () => ToolContent | undefined;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // 初始状态 - 只保留核心数据
  messages: [],
  connectionState: ConnectionStatus.DISCONNECTED,
  title: '新聊天',
  plan: undefined,
  
  // Flow初始状态
  selectedFlow: undefined,
  flows: [],
  
  // 基础操作
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setConnectionState: (connectionState) => set({ connectionState }),
  setTitle: (title) => set({ title }),
  setPlan: (plan) => set({ plan }),
  
  // Flow操作
  setSelectedFlow: (flowId) => set({ selectedFlow: flowId }),
  setFlows: (flows) => set({ flows }),
  
  // 消息操作
  updateStepStatus: (stepId, status) => set((state) => {
    const newMessages = state.messages.map(message => {
      if (message.type === 'step' && (message.content as StepContent).id === stepId) {
        return {
          ...message,
          content: {
            ...message.content,
            status
          } as StepContent
        };
      }
      return message;
    });
    
    return { messages: newMessages };
  }),
  
  addToolToStep: (stepId, tool) => set((state) => {
    const newMessages = state.messages.map(message => {
      if (message.type === 'step' && (message.content as StepContent).id === stepId) {
        const stepContent = message.content as StepContent;
        return {
          ...message,
          content: {
            ...stepContent,
            tools: [...stepContent.tools, tool]
          } as StepContent
        };
      }
      return message;
    });
    
    return { messages: newMessages };
  }),
  
  // 重置状态
  resetState: () => set({
    messages: [],
    connectionState: ConnectionStatus.DISCONNECTED,
    title: '新聊天',
    plan: undefined,
    // 保留flow状态，不重置
  }),
  
  // 计算属性
  getLastStep: () => {
    const { messages } = get();
    const stepMessages = messages.filter(message => message.type === 'step');
    if (stepMessages.length > 0) {
      return stepMessages[stepMessages.length - 1].content as StepContent;
    }
    return undefined;
  },
  
  getLastNoMessageTool: () => {
    const { messages } = get();
    const toolMessages = messages.filter(m => m.type === 'tool');
    const lastToolMessage = toolMessages[toolMessages.length - 1];
    if (lastToolMessage) {
      const toolContent = lastToolMessage.content as ToolContent;
      return toolContent.name !== 'message' ? toolContent : undefined;
    }
    return undefined;
  },
})); 