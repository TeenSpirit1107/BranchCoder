import { useCallback, useRef, useEffect } from 'react';
import { 
  getConversationHistory, 
  replayConversation
} from '../api/conversationApi';
import { getEventStream } from '../api/agentApi';
import { SSEEvent } from '../types/sseEvent';
import { useChatStore } from '@/store/chatStore';
import { ConnectionStatus } from '@/types/conversationApi';
import { useParams } from 'react-router-dom';

/**
 * 事件流控制接口
 */
interface EventStreamControl {
  close: () => void;
  promise?: Promise<void>;
}

/**
 * useConversation - 底层事件流管理钩子
 * 
 * 职责：
 * 1. 管理与后端的事件流连接
 * 2. 获取历史事件并重放
 * 3. 持续接收新的实时事件
 * 4. 通过回调函数将完整的事件列表传递给上层
 * 
 * 优化点：
 * - 简化状态结构，只保留必要状态
 * - 改进错误处理和重连逻辑
 * - 使用ref管理非渲染相关状态
 */
export const useConversation = (
  onEventsUpdate: (events: SSEEvent[]) => void
) => {
  const { agentId } = useParams<{ agentId: string }>();
  // 简化状态管理 - 只保留影响渲染的状态
  const { setConnectionState, connectionState } = useChatStore();

  // 使用ref管理非渲染相关状态
  const eventsRef = useRef<SSEEvent[]>([]);
  const eventStreamRef = useRef<EventStreamControl | null>(null);
  const replayStreamRef = useRef<EventStreamControl | null>(null);
  const isInitializedRef = useRef<boolean>(false);

  // 添加事件到列表并通知上层
  const addEvent = useCallback((event: SSEEvent) => {
    eventsRef.current = [...eventsRef.current, event];
    onEventsUpdate([...eventsRef.current]);
    
  }, [onEventsUpdate]);

  // 批量添加事件（用于历史事件重放）
  const addEvents = useCallback((events: SSEEvent[]) => {
    eventsRef.current = [...eventsRef.current, ...events];
    onEventsUpdate([...eventsRef.current]);
  }, [onEventsUpdate]);

  // 清空事件列表
  const clearEvents = useCallback(() => {
    eventsRef.current = [];
    onEventsUpdate([]);
  }, [onEventsUpdate]);

  // 停止所有连接
  const stopAllConnections = useCallback(() => {
    console.log("停止所有连接");
    if (eventStreamRef.current) {
      eventStreamRef.current.close();
      eventStreamRef.current = null;
    }
    if (replayStreamRef.current) {
      replayStreamRef.current.close();
      replayStreamRef.current = null;
    }
    setConnectionState(ConnectionStatus.DISCONNECTED);
  }, [setConnectionState]);

  // 启动实时事件流
  const startEventStream = useCallback((fromSequence: number = 1) => {
    if (!agentId) return;

    console.log(`启动实时事件流: Agent ${agentId}, 从序号 ${fromSequence} 开始`);

    // 停止现有连接
    if (eventStreamRef.current) {
      eventStreamRef.current.close();
    }

    setConnectionState(ConnectionStatus.CONNECTING);

    const eventStreamControl = getEventStream(
      agentId,
      fromSequence,
      (event: SSEEvent) => {
        addEvent(event);
      },
      (error: Error) => {
        console.error('实时事件流错误:', error);
        setConnectionState(ConnectionStatus.ERROR);
      },
      () => {
        console.log('实时事件流连接已建立');
        setConnectionState(ConnectionStatus.CONNECTED);
      },
      () => {
        console.log('实时事件流连接已关闭');
        setConnectionState(ConnectionStatus.DISCONNECTED);
      }
    );

    eventStreamRef.current = eventStreamControl;
  }, [agentId, addEvent, setConnectionState]);

  // 加载历史事件
  const loadHistoricalEvents = useCallback(async () => {
    if (!agentId) return;

    console.log(`加载历史事件: Agent ${agentId}`);
    setConnectionState(ConnectionStatus.CONNECTING);

    try {
      // 首先尝试获取会话历史信息
      const historyData = await getConversationHistory(agentId);
      console.log('获取到会话历史数据:', historyData);

      // 如果有历史事件，通过重放接口获取
      if (historyData.events && historyData.events.length > 0) {
        setConnectionState(ConnectionStatus.CONNECTED);

        return new Promise<void>((resolve, reject) => {
          const historicalEvents: SSEEvent[] = [];
          let isCompleted = false;

          const replayControl = replayConversation(
            agentId,
            1, // 从第一个事件开始重放
            (event: SSEEvent) => {
              if (isCompleted) return;
              
              console.log('收到历史事件:', event);
              historicalEvents.push(event);

              // 如果是done事件，表示重放完成
              if (event.event === 'done') {
                isCompleted = true;
                console.log(`历史事件重放完成，共 ${historicalEvents.length} 个事件`);
                
                // 批量添加历史事件（排除done事件）
                const validEvents = historicalEvents.filter(e => e.event !== 'done');
                addEvents(validEvents);
                
                resolve();
              }
            },
            (error: Error) => {
              if (isCompleted) return;
              
              console.error('历史事件重放失败:', error);
              setConnectionState(ConnectionStatus.ERROR);
              reject(error);
            }
          );

          replayStreamRef.current = replayControl;

          // 设置超时，防止无限等待
          setTimeout(() => {
            if (!isCompleted) {
              console.log('历史事件重放超时，使用已获取的事件');
              isCompleted = true;
              
              if (replayControl) {
                replayControl.close();
              }
              
              // 即使超时也添加已获取的事件
              const validEvents = historicalEvents.filter(e => e.event !== 'done');
              if (validEvents.length > 0) {
                addEvents(validEvents);
              }
              
              resolve();
            }
          }, 10000); // 10秒超时
        });
      } else {
        console.log('没有历史事件');
        setConnectionState(ConnectionStatus.DISCONNECTED);
      }
    } catch (error) {
      console.error('加载历史事件失败:', error);
      const err = error instanceof Error ? error : new Error(String(error));
      setConnectionState(ConnectionStatus.ERROR);
      throw err;
    } finally {
      console.log('加载历史事件结束');
      setConnectionState(ConnectionStatus.DISCONNECTED);
    }
  }, [agentId, addEvents, setConnectionState]);

  // 初始化连接（加载历史 + 启动实时流）
  const initializeConnection = useCallback(async () => {
    if (!agentId || isInitializedRef.current || eventsRef.current.length > 0) {
      console.log(`初始化连接: Agent ${agentId} 已初始化`);
      return;
    }

    console.log(`初始化连接: Agent ${agentId}`);
    isInitializedRef.current = true;

    try {
      // 清空现有事件
      clearEvents();
      
      // 1. 先加载历史事件
      await loadHistoricalEvents();

      // 2. 然后启动实时事件流（从当前序号开始）
      const nextSequence = eventsRef.current.length + 1;
      startEventStream(nextSequence);

    } catch (error) {
      console.error('初始化连接失败:', error);
      // 即使历史事件加载失败，也尝试启动实时事件流
      startEventStream(1);
    }
  }, [
    agentId, 
    clearEvents, 
    loadHistoricalEvents, 
    startEventStream
  ]);

  // 重新连接（仅启动实时流，不重新加载历史）
  const reconnect = useCallback(() => {
    if (!agentId) return;

    console.log(`重新连接: Agent ${agentId}`);
    
    // 从当前序号开始重新连接
    const nextSequence = eventsRef.current.length + 1;
    startEventStream(nextSequence);
  }, [agentId, startEventStream]);

  // 完全重置（清空所有数据并重新初始化）
  const reset = useCallback(() => {
    console.log('重置连接状态');
    
    stopAllConnections();
    clearEvents();
    isInitializedRef.current = false;
    
    setConnectionState(ConnectionStatus.DISCONNECTED);
  }, [stopAllConnections, clearEvents, setConnectionState]);

  // 当agentId变化时，重新初始化
  useEffect(() => {
    if (agentId && isInitializedRef.current === false) {
      // 初始化连接
      initializeConnection();
    } else if (!agentId) {
      // 如果没有agentId，重置所有状态
      console.log("没有agentId，重置所有状态");
      reset();
    }
  }, [agentId, initializeConnection, reset]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      stopAllConnections();
    };
  }, [stopAllConnections]);

  return {
    // 状态
    events: eventsRef.current,
    
    // 便捷的状态检查
    isConnected: connectionState === ConnectionStatus.CONNECTED,
    
    // 方法
    initializeConnection,
    reconnect,
    reset,
    
    // 内部方法（供调试使用）
    _internal: {
      loadHistoricalEvents,
      startEventStream,
      stopAllConnections
    }
  };
}; 