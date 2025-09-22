import React from 'react';
import { ChevronUp, ChevronDown, Clock, Loader2 } from 'lucide-react';
import { usePlanPanel } from '../../hooks/usePlanPanel';
import StepSuccessIcon from '../icons/StepSuccessIcon';

interface StepType {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

const PlanPanel: React.FC = () => {
  const {
    plan,
    isShowPlanPanel,
    togglePlanPanel,
    planProgress,
    planCompleted,
    runningStep
  } = usePlanPanel();

  if (!plan || plan.steps.length === 0) {
    return null;
  }

  if (isShowPlanPanel) {
    return (
      <div className="border border-black/8 dark:border-[var(--border-main)] bg-[var(--background-menu-white)] rounded-[16px] sm:rounded-[12px] shadow-[0px_0px_1px_0px_rgba(0,_0,_0,_0.05),_0px_8px_32px_0px_rgba(0,_0,_0,_0.04)] z-99 flex flex-col py-4">
        <div className="flex px-4 mb-4 w-full">
          <div className="flex items-start ml-auto">
            <div className="flex items-center justify-center gap-2">
              <div 
                onClick={togglePlanPanel}
                className="flex h-7 w-7 items-center justify-center cursor-pointer hover:bg-[var(--fill-tsp-gray-main)] rounded-md"
              >
                <ChevronDown className="text-[var(--icon-tertiary)]" size={16} />
              </div>
            </div>
          </div>
        </div>
        <div className="px-4">
          <div className="bg-[var(--fill-tsp-gray-main)] rounded-lg pt-4">
            <div className="flex justify-between w-full px-4">
              <span className="text-[var(--text-primary)] font-bold">
                {plan.issubplan ? '子任务进度' : plan.issuperplan ? '主任务进度' : 'kk任务进度'}
              </span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-[var(--text-tertiary)]">{planProgress()}</span>
              </div>
            </div>
            <div className="max-h-[min(calc(100vh-360px),400px)] overflow-y-auto">
              {plan.steps.map((step: StepType) => (
                <div 
                  key={step.id}
                  className="flex items-start gap-2.5 w-full px-4 py-2 truncate"
                >
                  {step.status === 'completed' ? (
                    <StepSuccessIcon />
                  ) : step.status === 'running' ? (
                    <Loader2 className="relative top-[2px] flex-shrink-0 animate-spin duration-1000 infinite" size={16} />
                  ) : (
                    <Clock className="relative top-[2px] flex-shrink-0" size={16} />
                  )}
                  <div className="flex flex-col w-full gap-[2px] truncate">
                    <div 
                      className="text-sm truncate" 
                      title={step.description}
                      style={{ color: 'var(--text-primary)' }}
                    >
                      {step.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      onClick={togglePlanPanel}
      className="flex flex-row items-start justify-between pe-3 relative clickable border border-black/8 dark:border-[var(--border-main)] bg-[var(--background-menu-white)] rounded-[16px] sm:rounded-[12px] shadow-[0px_0px_1px_0px_rgba(0,_0,_0,_0.05),_0px_8px_32px_0px_rgba(0,_0,_0,_0.04)] z-99"
    >
      <div className="flex-1 min-w-0 relative overflow-hidden">
        <div className="w-full" style={{ height: '36px', '--offset': '-36px' } as React.CSSProperties}>
          <div className="w-full">
            <div className="flex items-start gap-2.5 w-full px-4 py-2 truncate">
              {planCompleted() ? (
                <StepSuccessIcon />
              ) : (
                <Loader2 className="relative top-[2px] flex-shrink-0 animate-spin duration-1000 infinite" size={16} />
              )}
              <div className="flex flex-col w-full gap-[2px] truncate">
                <div 
                  className="text-sm truncate" 
                  title={runningStep()} 
                  style={{ color: 'var(--text-tertiary)' }}
                >
                  {runningStep()}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <button className="flex h-full cursor-pointer justify-center gap-2 hover:opacity-80 flex-shrink-0 items-start py-2.5">
        <span className="text-xs text-[var(--text-tertiary)] hidden sm:flex">{planProgress()}</span>
        <ChevronUp className="text-[var(--icon-tertiary)]" size={16} />
      </button>
    </div>
  );
};

export default PlanPanel; 