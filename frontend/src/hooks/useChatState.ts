import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';

/**
 * useChatState - 统一的聊天状态管理钩子
 * 
 * 职责：
 * 1. 整合所有聊天相关状态
 * 2. 提供统一的状态访问接口
 * 3. 减少组件中的状态管理复杂度
 */
export const useChatState = () => {
  // 核心数据状态
  const {
    messages,
    title,
    plan,
    setMessages,
    addMessage,
    setTitle,
    setPlan,
    updateStepStatus,
    addToolToStep,
    resetState,
    getLastStep,
    getLastNoMessageTool
  } = useChatStore();
  
  // UI状态 - 直接从UI store获取
  const {
    realTime,
    follow,
    showPlanPanel,
    showToolPanel,
    currentTool,
    setRealTime,
    setFollow,
    setShowPlanPanel,
    setShowToolPanel,
    setCurrentTool,
    toggleRealTime,
    toggleFollow,
    togglePlanPanel,
    toggleToolPanel,
    showTool,
    closeTool
  } = useUIStore();
  
  return {
    // 核心数据状态
    messages,
    title,
    plan,
    
    // UI状态
    realTime,
    follow,
    showPlanPanel,
    showToolPanel,
    currentTool,
    
    // 计算属性
    lastStep: getLastStep(),
    lastNoMessageTool: getLastNoMessageTool(),
    
    // 数据操作方法
    setMessages,
    addMessage,
    setTitle,
    setPlan,
    updateStepStatus,
    addToolToStep,
    resetState,
    
    // UI操作方法
    setRealTime,
    setFollow,
    setShowPlanPanel,
    setShowToolPanel,
    setCurrentTool,
    toggleRealTime,
    toggleFollow,
    togglePlanPanel,
    toggleToolPanel,
    showTool,
    closeTool
  };
}; 