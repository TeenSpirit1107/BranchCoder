import React from 'react';
import { Menu, X } from 'lucide-react';
import { useSidebar } from '../../hooks/useSidebar';
import { cn } from '@/utils/cn';
import { useParams } from 'react-router-dom';
import { useConversationList } from '../../hooks/useConversationList';

interface SidebarToggleProps {
  className?: string;
}

const SidebarToggle: React.FC<SidebarToggleProps> = ({ className }) => {
  const { isOpen, toggle } = useSidebar();
  const { agentId } = useParams<{ agentId: string }>();
  const { fetchConversations } = useConversationList();

  const handleToggle = () => {
    toggle();
    if (agentId) {
        fetchConversations();
    }
  }
  
  return (
    <button
      className={cn(
        "p-2 rounded-md hover:bg-black/10 transition-colors",
        className
      )}
      onClick={handleToggle}
      aria-label={isOpen ? "关闭侧边栏" : "打开侧边栏"}
    >
      {isOpen ? <X size={20} /> : <Menu size={20} />}
    </button>
  );
};

export default SidebarToggle; 