import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Trash2 } from 'lucide-react';
import { useConversationList } from '../../hooks/useConversationList';
import { useSidebar } from '../../hooks/useSidebar';
import { ConversationHistory } from '../../types/conversationApi';
import NewChatButton from './NewChatButton';
import SidebarToggle from './SidebarToggle';
import { cn } from '@/utils/cn';

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const { 
    conversations: conversationList, 
    loading, 
    fetchConversations, 
    deleteHistory 
  } = useConversationList();
  const { isOpen } = useSidebar();

  const getConversationTitle = (conversation: ConversationHistory): string => {
    // 如果有title字段，直接使用
    if (conversation.title) {
      return conversation.title;
    }
    
    // 默认标题
    return `对话 ${conversation.agent_id.substring(0, 8)}`;
  };

  useEffect(() => {
    const loadConversations = async () => {
      try {
        console.log('开始加载会话历史...');
        await fetchConversations();
      } catch (error) {
        console.error('加载会话历史失败:', error);
      }
    };

    loadConversations();
  }, [fetchConversations, isOpen]);

  const handleSelectChat = (agentId: string) => {
    navigate(`/chat/${agentId}`);
  };

  const handleDeleteChat = async (event: React.MouseEvent, agentId: string) => {
    event.stopPropagation();
    
    try {
      await deleteHistory(agentId);
    } catch (error) {
      console.error('删除会话失败:', error);
    }
  };

  // 获取排序后的会话列表
  const sortedConversations = conversationList?.conversations 
    ? [...conversationList.conversations].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
    : [];

  return (
    <div className={cn("flex flex-col h-full w-64 bg-[#202123] text-white duration-300 transition-all",
      isOpen ? "translate-x-0" : "-translate-x-full w-0"
    )}>
      {/* 侧边栏顶部区域 */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <h1 className="text-xl font-semibold">AI-Manus</h1>
        <SidebarToggle />
      </div>

      {/* 侧边栏内容 */}
      <div className="flex flex-col h-full overflow-hidden">
        {/* 新建聊天按钮 */}
        <div className="p-2">
          <NewChatButton className="w-full" />
        </div>

        {/* 会话历史列表 */}
        <div className="flex-1 overflow-y-auto pb-4">
          {loading ? (
            <div className="text-center text-sm text-white/50 p-4">加载中...</div>
          ) : sortedConversations.length === 0 ? (
            <div className="text-center text-sm text-white/50 p-4">暂无历史会话</div>
          ) : (
            <div className="space-y-1 px-2">
              {sortedConversations.map((conversation) => (
                <div
                  key={conversation.agent_id}
                  className="flex items-center rounded-md p-2 text-sm cursor-pointer hover:bg-white/10 group"
                  onClick={() => handleSelectChat(conversation.agent_id)}
                >
                  <MessageSquare size={18} className="flex-shrink-0" />
                  <div className="ml-2 flex-1 truncate">
                    {getConversationTitle(conversation)}
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 flex-shrink-0">
                    <button
                      className="h-6 w-6 p-1 rounded-sm hover:bg-white/10"
                      onClick={(e) => handleDeleteChat(e, conversation.agent_id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sidebar; 