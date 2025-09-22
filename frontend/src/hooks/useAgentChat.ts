import { useCallback, useEffect } from 'react';
import { useChatStore } from '../store/chatStore';
import { useChatUI } from './useChatUI';
import { MessageContent, ToolContent, StepContent, Message } from '../types/message';
import { SSEEvent, MessageEventData, ToolEventData, StepEventData, UserInputEventData } from '../types/sseEvent';
import { createAgent, sendMessage } from '../api/agentApi';
import { useConversation } from './useConversation';
import { toast } from '@/components/Toast';
import { useNavigate } from 'react-router-dom';
import { ConnectionStatus } from '../types/conversationApi';

/**
 * useAgentChat - 上层聊天管理钩子
 * 
 * 职责：
 * 1. 使用useConversation管理底层事件流
 * 2. 将SSE事件转换为渲染所需的消息格式
 * 3. 管理聊天状态和UI状态
 * 4. 处理用户交互（发送消息、创建Agent等）
 */
export const useAgentChat = (agentId?: string) => {
  const {
    messages,
    selectedFlow,
    connectionState,
    addMessage,
    setConnectionState,
    setTitle,
    setPlan,
    updateStepStatus,
    addToolToStep,
    resetState,
    getLastStep,
    setMessages
  } = useChatStore();
  
  const {
    setShowToolPanel,
    setCurrentTool,
    realTime,
  } = useChatUI();
  
  const navigate = useNavigate();
  
  // 处理事件并转换为消息格式
  const handleEventsUpdate = useCallback((events: SSEEvent[]) => {    
    setMessages([]);
    // 按顺序处理每个事件，构建完整的消息列表
    events.forEach((event) => {
      if (event.event === 'message') {
        // 处理消息事件
        const messageData = event.data as MessageEventData;
        addMessage({
          type: 'assistant',
          content: {
            ...messageData
          } as MessageContent,
        });
      } else if (event.event === 'user_input') {
        // 处理用户输入事件
        const userInputData = event.data as UserInputEventData;
        addMessage({
          type: 'user',
          content: {
            ...userInputData
          } as MessageContent,
        });
      } else if (event.event === 'tool') {
        // 处理工具事件
        const toolData = event.data as ToolEventData;
        const lastStep = getLastStep();
        const toolContent: ToolContent = {
          ...toolData
        };

        if (lastStep?.status === 'running') {
          // 更新最后一个步骤的工具列表
          addToolToStep(lastStep.id, toolContent);
        } else {
          // 添加新的工具消息
          addMessage({
            type: 'tool',
            content: toolContent,
          });
        }

        // 处理工具面板显示逻辑
        if (toolContent.name !== 'message') {
          if (realTime) {
            setCurrentTool(toolContent);
          }
          setShowToolPanel(true);
        }
      } else if (event.event === 'step') {
        // 处理步骤事件
        const stepData = event.data as StepEventData;

        if (stepData.status === 'running') {
          // 添加新的步骤
          addMessage({
            type: 'step',
            content: {
              ...stepData,
              tools: []
            } as StepContent,
          });
        } else if (stepData.status === 'completed' || stepData.status === 'failed') {
          // 更新步骤状态
          updateStepStatus(stepData.id, stepData.status);
        }
      } else if (event.event === 'title') {
        // 更新标题
        setTitle(event.data.title);
      } else if (event.event === 'error') {
        // 显示错误
        toast.error(`错误: ${event.data.error}`);
      } else if (event.event === 'plan') {
        // 更新计划
        setPlan(event.data);
      } else if (event.event === 'done') {
        // 完成
        // 添加新的步骤
        addMessage({
          type: 'done',
          content: {
            ...event.data,
          },
        });
      }
    });
  }, [
    setMessages,
    addMessage, 
    getLastStep, 
    addToolToStep, 
    setShowToolPanel, 
    updateStepStatus, 
    setTitle, 
    setPlan, 
    setCurrentTool, 
    realTime
  ]);
  
  // 使用底层的useConversation管理事件流
  const {
    isConnected,
    initializeConnection,
    events,
    reset,
    reconnect
  } = useConversation(handleEventsUpdate);
  
  // 重置聊天状态
  const resetChatState = useCallback(() => {
    reset();
    resetState();
    setCurrentTool(undefined);
  }, [reset, resetState, setCurrentTool]);
  
  // 发送消息
  const sendMessageToAgent = useCallback(async (msg: MessageContent) => {
    if ((!msg.content.trim() && (!msg.file_ids || msg.file_ids.length === 0)) || connectionState === ConnectionStatus.CONNECTING) {
      return;
    }
    
    // 创建用户消息并立即添加到界面
    const userMessage: Message = {
      type: 'user',
      content: {
        timestamp: Math.floor(Date.now() / 1000),
        content: msg.content,
        file_ids: msg.file_ids
      } as MessageContent,
    };
    addMessage(userMessage);
    
    if (!agentId) {
      // 重置
      resetChatState();
      // 首页：需要先创建Agent
      setConnectionState(ConnectionStatus.CONNECTING);
      try {
        // 创建新的Agent
        const response = await createAgent(selectedFlow);
        const newAgentId = response.data.agent_id;
        
        console.log(`创建新Agent: ${newAgentId}`);
        navigate(`/chat/${newAgentId}`);
        
        // 发送消息给新Agent
        try {
          await sendMessage(newAgentId, msg.content, msg.file_ids);
          console.log('消息已发送到新Agent队列');
        } catch (error) {
          console.error('发送消息到新Agent失败:', error);
          toast.error('发送消息失败');
        }
        
        return newAgentId;
      } catch (error) {
        console.error('创建Agent失败:', error);
        toast.error('创建Agent失败，请稍后重试');
        return null;
      }
    } else {
      try {
        // 发送消息到现有Agent
        await sendMessage(agentId, msg.content, msg.file_ids);
        reconnect();
        console.log('消息已发送到Agent队列');
        return agentId;
      } catch (error) {
        console.error('发送消息失败:', error);
        toast.error('发送消息失败');
        return null;
      }
    }
  }, [agentId, selectedFlow, connectionState, addMessage, navigate, reconnect, resetChatState, setConnectionState]);
  
  // 当agentId变化时，确保事件流状态正确
  useEffect(() => {
    if (agentId && !isConnected) {
      console.log(`Agent ${agentId} 未连接，尝试初始化连接`);
      initializeConnection();
    }
  }, [
    agentId, 
    isConnected, 
    initializeConnection
  ]);

  useEffect(() => {
    console.log(`connectionState: ${connectionState}`);
  }, [connectionState]);
  
  return {
    // 消息和状态
    messages,
    
    // 连接状态
    isConnected,
    
    // 方法
    sendMessage: sendMessageToAgent,

    initializeConnection,
    reset,
    
    // 调试信息
    _debug: {
      eventsCount: events.length,
      messagesCount: messages.length
    }
  };
}; 