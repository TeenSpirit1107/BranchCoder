import React, { useState } from 'react';
import { Bot, Files, Loader2, FileCode, Monitor, Gamepad2 } from 'lucide-react';
import { useChatStore } from '../../store/chatStore';
import { useNavigate, useParams } from 'react-router-dom';
import { cn } from '@/utils/cn';  
import FileListModal from './FileListModal';
import SidebarToggle from '../layout/SidebarToggle';
import { useSidebar } from '../../hooks/useSidebar';
import { getCodeServerUrl } from '../../api/agentApi';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '../ui/dropdown-menu';

const ChatNavBar: React.FC = () => {
  const { title, resetState } = useChatStore();
  const navigate = useNavigate();
  const { agentId } = useParams<{ agentId: string }>();
  const [showFileModal, setShowFileModal] = useState(false);
  const [codeServerLoading, setCodeServerLoading] = useState(false);
  const { isOpen } = useSidebar();

  // 处理Code Server按钮点击
  const handleCodeServerClick = async () => {
    if (!agentId || codeServerLoading) return;
    
    setCodeServerLoading(true);
    try {
      const response = await getCodeServerUrl(agentId);
      // 在新窗口中打开Code Server
      window.open(response.code_server_url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('打开Code Server失败:', error);
      alert('打开代码编辑器失败，请稍后重试');
    } finally {
      setCodeServerLoading(false);
    }
  };

  // 处理浏览器控制按钮点击
  const handleBrowserControlClick = () => {
    if (!agentId) return;
    
    // 在新窗口中打开浏览器控制页面
    const browserControlUrl = `/browser-view/${agentId}`;
    window.open(browserControlUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className={cn("sticky top-0 z-10 bg-[var(--background-gray-main)]",
      "flex-shrink-0 flex flex-row items-center justify-center",
      "pt-3 pb-1 h-12")}
    >
      <div className="flex flex-col gap-[4px] w-full">
        <div className="text-[var(--text-primary)] text-lg font-medium flex flex-row items-center justify-center min-w-0 w-full">
          {/* 侧边栏切换按钮 - 仅在侧边栏关闭时显示 */}
          {!isOpen && (
            <div className="flex h-8 w-8 items-center justify-center">
              <SidebarToggle className="text-[var(--icon-secondary)] hover:bg-[var(--fill-tsp-gray-main)]" />
            </div>
          )}
          
          {/* 返回首页按钮 */}
          <div 
            onClick={() => {
              resetState();
              navigate('/');
            }}
            className="flex h-8 w-8 items-center justify-center cursor-pointer hover:bg-[var(--fill-tsp-gray-main)] rounded-md"
          >
            <Bot className="h-6 w-6 text-[var(--icon-secondary)]" size={24} />
          </div>
          
          <div className="flex flex-row items-center gap-2 min-w-0 flex-grow">
            <span className="whitespace-nowrap text-ellipsis overflow-hidden">
              {title}
            </span>
          </div>
          
          {/* 接管按钮 - 使用Dropdown */}
          {agentId && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <div 
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-md",
                    codeServerLoading 
                      ? "cursor-not-allowed opacity-50" 
                      : "cursor-pointer hover:bg-[var(--fill-tsp-gray-main)]"
                  )}
                  title="接管控制"
                >
                  {codeServerLoading ? (
                    <Loader2 className="h-5 w-5 text-[var(--icon-secondary)] animate-spin" />
                  ) : (
                    <Gamepad2 className="h-5 w-5 text-[var(--icon-secondary)]" />
                  )}
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem 
                  onClick={handleCodeServerClick}
                  disabled={codeServerLoading}
                  className="flex items-center gap-2"
                >
                  <FileCode className="h-4 w-4" />
                  打开代码编辑器
                </DropdownMenuItem>
                <DropdownMenuItem 
                  onClick={handleBrowserControlClick}
                  className="flex items-center gap-2"
                >
                  <Monitor className="h-4 w-4" />
                  接管浏览器
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          
          <div 
            onClick={() => setShowFileModal(true)}
            className="flex h-8 w-8 items-center justify-center cursor-pointer hover:bg-[var(--fill-tsp-gray-main)] rounded-md"
            title="查看文件列表"
          >
            <Files className="h-5 w-5 text-[var(--icon-secondary)]" />
          </div>
        </div>
      </div>
      
      {/* 文件列表Modal */}
      {agentId && (
        <FileListModal 
          agentId={agentId}
          onClose={() => setShowFileModal(false)} 
          open={showFileModal}
        />
      )}
    </div>
  );
};

export default ChatNavBar; 