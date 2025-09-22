import React, { useEffect, useState, useCallback } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { useChatStore } from '../store/chatStore';
import { getAvailableFlows } from '../api/agentApi';

interface FlowSelectorProps {
  disabled?: boolean;
}

const FlowSelector: React.FC<FlowSelectorProps> = ({
  disabled = false
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const {
    selectedFlow,
    flows,
    setFlows,
    setSelectedFlow
  } = useChatStore();

  const fetchFlows = useCallback(async () => {    
    try {
      setLoading(true);
      setError(null);
      const availableFlows = await getAvailableFlows();
      setFlows(availableFlows);
      
      // 如果没有选中的flow，默认选择第一个
      if (!selectedFlow && availableFlows.length > 0) {
        setSelectedFlow(availableFlows[0].flow_id);
      }
    } catch (err) {
      console.error('获取flow类型失败:', err);
      setError('获取flow类型失败');
    } finally {
      setLoading(false);
    }
  }, [selectedFlow, setSelectedFlow, setFlows]);

  // 组件挂载时获取flow列表
  useEffect(() => {
    fetchFlows();
  }, [fetchFlows]);

  const selectedFlowData = flows.find(flow => flow.flow_id === selectedFlow);

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--text-secondary)]">
        <div className="w-4 h-4 border-2 border-[var(--border-primary)] border-t-transparent rounded-full animate-spin"></div>
        <span>加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-500">
        <span>⚠️ {error}</span>
      </div>
    );
  }

  return (
    <Select
      value={selectedFlow}
      onValueChange={setSelectedFlow}
      disabled={disabled}
    >
      <SelectTrigger className="w-[180px] h-8 text-sm border-[var(--border-light)] dark:border-[var(--border-white)] bg-[var(--background-tsp-card-gray)] dark:bg-[var(--background-menu-white)] text-[var(--text-primary)] hover:bg-[var(--hover-color)] disabled:bg-[var(--background-gray-light)] disabled:text-[var(--text-disable)] disabled:cursor-not-allowed">
        <SelectValue placeholder="选择Flow">
          {selectedFlowData?.name || '选择Flow'}
        </SelectValue>
      </SelectTrigger>
      <SelectContent className="bg-[var(--background-menu-white)] dark:bg-[var(--background-menu-dark)] border-[var(--border-light)] dark:border-[var(--border-white)]">
        {flows.map((flow) => (
          <SelectItem 
            key={flow.flow_id} 
            value={flow.flow_id}
            className="text-[var(--text-primary)] hover:bg-[var(--hover-color)] focus:bg-[var(--hover-color)]"
          >
            <div className="flex flex-col">
              <span className="font-medium">{flow.name}</span>
              {flow.description && (
                <span className="text-xs text-[var(--text-secondary)]">{flow.description}</span>
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default FlowSelector; 