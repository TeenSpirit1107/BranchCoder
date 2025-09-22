import React from 'react';
import { useRelativeTime } from '../utils/timeUtils';
import { ToolContent } from '../types/message';
import { TOOL_FUNCTION_MAP, TOOL_FUNCTION_ARG_MAP, TOOL_NAME_MAP, TOOL_ICON_MAP } from '../constants/tool';

interface ToolUseProps {
  tool: ToolContent;
  onClick: () => void;
}

const ToolUse: React.FC<ToolUseProps> = ({ tool, onClick }) => {
  const relativeTime = useRelativeTime(tool.timestamp);

  // 获取工具信息
  const getToolInfo = () => {
    let functionArg = tool.args[TOOL_FUNCTION_ARG_MAP[tool.function]] || '';
    if (TOOL_FUNCTION_ARG_MAP[tool.function] === 'file') {
      functionArg = functionArg.replace(/^\/home\/ubuntu\//, '');
    }
    return {
      icon: TOOL_ICON_MAP[tool.name] || null,
      name: TOOL_NAME_MAP[tool.name] || '',
      function: TOOL_FUNCTION_MAP[tool.function] || '',
      functionArg: functionArg
    };
  };

  const toolInfo = getToolInfo();

  const handleClick = () => {
    onClick();
  };

  // 如果是消息工具，直接显示文本
  if (tool.name === 'message' || tool.name === 'message_deliver_artifact' && tool.args?.text) {
    return (
      <div className='flex flex-col gap-2'>
        <p className="text-[var(--text-secondary)] text-[14px] overflow-hidden text-ellipsis whitespace-pre-line">
          {tool.args.text}
        </p>
      </div>
    );
  }

  // 对于其他工具类型
  if (toolInfo) {
    const IconComponent = toolInfo.icon;
    
    return (
      <div className="flex items-center group gap-2 cursor-pointer"> 
        <div className="flex-1 min-w-0">
          <div
            onClick={handleClick}
            className="rounded-[15px] items-center gap-2 px-[10px] py-[3px] border border-[var(--border-light)] bg-[var(--fill-tsp-gray-main)] inline-flex max-w-full clickable hover:bg-[var(--fill-tsp-gray-dark)] dark:hover:bg-white/[0.02]"
          >
            <div className="w-[16px] inline-flex items-center text-[var(--text-primary)]">
              {IconComponent && <IconComponent width={21} height={21} />}
            </div>
            <div className="flex-1 h-full min-w-0 flex">
              <div className="inline-flex items-center h-full rounded-full text-[14px] text-[var(--text-secondary)] max-w-[100%]">
                <div 
                  className="max-w-[100%] text-ellipsis overflow-hidden whitespace-nowrap text-[13px]"
                  title={`${toolInfo.function}${toolInfo.functionArg}`}
                >
                  <div className="flex items-center">
                    {toolInfo.function}
                    {toolInfo.functionArg !== '' && <span className="flex-1 min-w-0 rounded-[6px] px-1 ml-1 relative top-[0px] text-[12px] font-mono max-w-full text-ellipsis overflow-hidden whitespace-nowrap text-[var(--text-tertiary)]">
                      <code>{toolInfo.functionArg}</code>
                    </span>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="float-right transition text-[12px] text-[var(--text-tertiary)] invisible group-hover:visible">
          {relativeTime}
        </div>
      </div>
    );
  }

  return null;
};

export default ToolUse; 