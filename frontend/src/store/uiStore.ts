import { create } from 'zustand';
import { ToolContent } from '../types/message';

// UI状态接口
interface UIState {
  // UI状态
  realTime: boolean;
  follow: boolean;
  showPlanPanel: boolean;
  showToolPanel: boolean;
  currentTool: ToolContent | undefined;
  isPending: boolean;

  // 基础操作
  setRealTime: (realTime: boolean) => void;
  setFollow: (follow: boolean) => void;
  setShowPlanPanel: (show: boolean) => void;
  setShowToolPanel: (show: boolean) => void;
  setCurrentTool: (tool: ToolContent | undefined) => void;
  
  // 切换操作
  toggleRealTime: () => void;
  toggleFollow: () => void;
  togglePlanPanel: () => void;
  toggleToolPanel: () => void;
  
  // 复合操作
  showTool: (tool: ToolContent) => void;
  closeTool: () => void;
  setIsPending: (isPending: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  // 初始状态
  realTime: true,
  follow: true,
  showPlanPanel: false,
  showToolPanel: false,
  currentTool: undefined,
  isPending: false,
  
  // 基础操作
  setRealTime: (realTime) => set({ realTime }),
  setFollow: (follow) => set({ follow }),
  setShowPlanPanel: (showPlanPanel) => set({ showPlanPanel }),
  setShowToolPanel: (showToolPanel) => set({ showToolPanel }),
  setCurrentTool: (currentTool) => set({ currentTool }),
  setIsPending: (isPending) => set({ isPending }),

  // 切换操作
  toggleRealTime: () => set((state) => ({ realTime: !state.realTime })),
  toggleFollow: () => set((state) => ({ follow: !state.follow })),
  togglePlanPanel: () => set((state) => ({ showPlanPanel: !state.showPlanPanel })),
  toggleToolPanel: () => set((state) => ({ showToolPanel: !state.showToolPanel })),
  
  // 复合操作
  showTool: (tool) => set({ 
    currentTool: tool, 
    showToolPanel: true, 
    realTime: false // 查看工具时切换到非实时模式
  }),
  closeTool: () => set({ 
    currentTool: undefined, 
    showToolPanel: false 
  }),
})); 