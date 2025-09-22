import React, { useEffect, useState, useCallback } from 'react';
import { viewShellSession } from '../api/agentApi';
import { toast } from '@/components/Toast';

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: any;
  result?: any;
}

interface ShellToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

const ShellToolView: React.FC<ShellToolViewProps> = ({ agentId, toolContent }) => {
  const [shell, setShell] = useState('');

  // 从toolContent获取sessionId
  const sessionId = toolContent?.args?.id || '';

  // 加载Shell会话内容
  const loadShellContent = useCallback(() => {
    if (!sessionId) return;

    viewShellSession(agentId, sessionId)
      .then((response) => {
        let newShell = '';
        for (const e of response.console) {
          newShell += `<span style="color: rgb(0, 187, 0);">${e.ps1}</span><span> ${e.command}</span>\n`;
          newShell += `<span>${e.output}</span>\n`;
        }
        if (newShell !== shell) {
          setShell(newShell);
        }
      })
      .catch((error) => {
        console.error('加载Shell会话内容失败:', error);
        toast.error('加载Shell会话内容失败');
      });
  }, [agentId, sessionId, shell]);

  // 组件挂载和sessionId变化时加载内容
  useEffect(() => {
    if (sessionId) {
      loadShellContent();
    }
  }, [sessionId, loadShellContent]);

  return (
    <>
      <div className="h-[36px] flex items-center px-3 w-full bg-[var(--background-gray-main)] border-b border-[var(--border-main)] rounded-t-[12px] shadow-[inset_0px_1px_0px_0px_#FFFFFF] dark:shadow-[inset_0px_1px_0px_0px_#FFFFFF30]">
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-[250px] truncate text-[var(--text-tertiary)] text-sm font-medium text-center">
            {sessionId}
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 w-full overflow-y-auto">
        <div dir="ltr" data-orientation="horizontal" className="flex flex-col flex-1 min-h-0">
          <div 
            data-state="active" 
            data-orientation="horizontal" 
            role="tabpanel"
            tabIndex={0}
            className="py-2 focus-visible:outline-none data-[state=inactive]:hidden flex-1 font-mono text-sm leading-relaxed px-3 outline-none overflow-auto whitespace-pre-wrap break-all"
            style={{ animationDuration: '0s' }}
            dangerouslySetInnerHTML={{ __html: shell }}
          />
        </div>
      </div>
    </>
  );
};

export default ShellToolView; 