import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';

/**
 * useChatUI - 聊天界面状态管理钩子
 * 
 * 职责：
 * 1. 整合UI状态和计算属性
 * 2. 提供统一的UI状态访问接口
 * 3. 使用Zustand管理UI状态
 * 
 * 现在使用Zustand store管理UI状态，更加简洁和高效
 */
export const useChatUI = () => {
  // 从UI store获取所有UI状态和操作
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
    closeTool,
  } = useUIStore();
  
  // 从chatStore获取计算属性
  const { getLastNoMessageTool } = useChatStore();
  
  return {
    // UI状态
    realTime,
    follow,
    showPlanPanel,
    showToolPanel,
    currentTool,
    
    // 计算属性 - 使用store的getter
    lastNoMessageTool: getLastNoMessageTool(),
    
    // 操作方法
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
    closeTool,
  };
}; 