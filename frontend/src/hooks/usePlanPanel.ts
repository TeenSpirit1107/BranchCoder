import { useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';

export const usePlanPanel = () => {
  const { plan } = useChatStore();
  const { showPlanPanel, togglePlanPanel } = useUIStore();
  
  // 计算任务进度
  const planProgress = useCallback((): string => {
    const completedSteps = plan?.steps.filter(step => step.status === 'completed').length ?? 0;
    return `${completedSteps} / ${plan?.steps.length ?? 1}`;
  }, [plan]);
  
  // 检查计划是否完成
  const planCompleted = useCallback((): boolean => {
    return plan?.steps.every(step => step.status === 'completed') ?? false;
  }, [plan]);
  
  // 获取当前运行的步骤
  const runningStep = useCallback((): string => {
    for (const step of plan?.steps ?? []) {
      if (step.status === 'running') {
        return step.description;
      }
    }
    return '确认任务完成';
  }, [plan]);
  
  return {
    plan,
    isShowPlanPanel: showPlanPanel,
    togglePlanPanel,
    planProgress,
    planCompleted,
    runningStep
  };
}; 