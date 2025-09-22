import React, { lazy, Suspense, useMemo } from 'react';
import { Minimize2, Play, Loader2 } from 'lucide-react';
import { TOOL_ICON_MAP, TOOL_NAME_MAP } from '../constants/tool';
import PlanPanel from './chat/PlanPanel';
import { useUIStore } from '@/store/uiStore';
import { useChatStore } from '@/store/chatStore';

// 懒加载工具组件
const BrowserToolView = lazy(() => import('./BrowserToolView'));
const FileToolView = lazy(() => import('./FileToolView'));
const ShellToolView = lazy(() => import('./ShellToolView'));
const SearchToolView = lazy(() => import('./SearchToolView'));
const AudioToolView = lazy(() => import('./AudioToolView'));
const ImageToolView = lazy(() => import('./ImageToolView'));

// 加载中组件
const LoadingFallback = () => (
  <div className="flex justify-center items-center h-full p-4">
    <div className="flex flex-col items-center gap-2">
      <Loader2 className="h-8 w-8 text-[var(--icon-secondary)] animate-spin" />
      <span className="text-sm text-[var(--text-tertiary)]">工具加载中...</span>
    </div>
  </div>
);

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
}

interface ToolPanelProps {
  agentId?: string;
  onClose?: () => void;
  currentTool: ToolContent | undefined;
  showPlanPanel?: boolean;
}

const ToolPanel: React.FC<ToolPanelProps> = ({ 
  agentId, 
  onClose, 
  currentTool,
  showPlanPanel = true 
}) => {  
  const { realTime, setRealTime, setCurrentTool } = useUIStore();
  // 获取计算属性
  const { getLastNoMessageTool } = useChatStore();
  const lastNoMessageTool = getLastNoMessageTool();

  const toolInfo = useMemo(() => {
    if (!currentTool) return null;

    // 使用更宽松的类型定义以避免类型错误
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const TOOL_COMPONENT_MAP: Record<string, React.ComponentType<any>> = {
      'browser': BrowserToolView,
      'file': FileToolView,
      'shell': ShellToolView,
      'search': SearchToolView,
      'audio': AudioToolView,
      'image': ImageToolView,
    };

    return {
      name: TOOL_NAME_MAP[currentTool.name] || '',
      view: TOOL_COMPONENT_MAP[currentTool.name] || null,
      function: currentTool.function || '',
      functionArg: currentTool.args || '',
    };
  }, [currentTool]);

  const ToolComponent = useMemo(() => {
    if (!toolInfo) return null;

    return toolInfo.view;
  }, [toolInfo]);

  const ToolIcon = TOOL_ICON_MAP[currentTool?.name || ''];

  if (!currentTool) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-[var(--border-main)] flex items-center px-4 h-[48px] gap-2">
        <div className="flex items-center gap-2">
          {ToolIcon && (
            <ToolIcon width={18} height={18} />
          )}
        </div>
        <div className="flex-1 text-[var(--text-primary)] font-medium">
          <span>{toolInfo?.name || '工具面板'}</span>
        </div>
        <button
          onClick={onClose}
          className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
        >
          <Minimize2 size={18} />
        </button>
      </div>
      <div className="flex-1 p-4 overflow-hidden flex flex-col">
        <div className="h-full flex flex-col flex-1">
          <div className="flex flex-col rounded-[12px] overflow-hidden bg-[var(--background-gray-main)] border border-[var(--border-dark)] dark:border-black/30 shadow-[0px_4px_32px_0px_rgba(0,0,0,0.04)] flex-1 min-h-0 relative">
            {toolInfo && ToolComponent && (
              <Suspense fallback={<LoadingFallback />}>
                <ToolComponent agentId={agentId} toolContent={currentTool} />
              </Suspense>
            )}
            {!realTime && (
              <div className="mt-auto flex items-center justify-center gap-2 px-4 py-2 absolute bottom-16 left-1/2 -translate-x-1/2">
                <button
                  className="h-10 px-3 border border-[var(--border-main)] flex items-center gap-1 bg-[var(--background-white-main)] hover:bg-[var(--background-gray-main)] shadow-[0px_5px_16px_0px_var(--shadow-S),0px_0px_1.25px_0px_var(--shadow-S)] rounded-full cursor-pointer"
                  onClick={() => {
                    setRealTime(true);
                    setCurrentTool(lastNoMessageTool);
                  }}
                >
                  <Play size={16} />
                  <span className="text-[var(--text-primary)] text-sm font-medium">
                    跳转到实时
                  </span>
                </button>
              </div>
            )}
          </div>
          {/* PlanPanel放在工具面板下方 */}
          {showPlanPanel && (
            <div className="mt-4">
              <PlanPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ToolPanel; 