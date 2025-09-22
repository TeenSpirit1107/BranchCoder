import React from 'react';
import { Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/utils/cn';

interface NewChatButtonProps {
  className?: string;
}

const NewChatButton: React.FC<NewChatButtonProps> = ({ className }) => {
  const navigate = useNavigate();
  
  const handleNewChat = () => {
    navigate('/');
  };
  
  return (
    <button 
      className={cn(
        "flex items-center justify-start p-2 rounded-md border border-white/20 text-white hover:bg-white/10 transition-colors",
        className
      )}
      onClick={handleNewChat}
      aria-label="新对话"
    >
      <Plus size={18} />
      <span className="ml-2">新对话</span>
    </button>
  );
};

export default NewChatButton; 