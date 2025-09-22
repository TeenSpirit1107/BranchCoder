import React from 'react';
import { Bot } from 'lucide-react';
import ChatBox from '../ChatBox';
import ManusLogoTextIcon from '../icons/ManusLogoTextIcon';
import { MessageContent } from '../../types/message';
import SidebarToggle from '../layout/SidebarToggle';
import { useSidebar } from '../../hooks/useSidebar';

interface HomePageContentProps {
  inputMessage: string;
  setInputMessage: (message: string) => void;
  handleSendMessage: (message: MessageContent) => void;
}

const HomePageContent: React.FC<HomePageContentProps> = ({
  inputMessage,
  setInputMessage,
  handleSendMessage
}) => {
  const { isOpen } = useSidebar();
  return (
    <div className="flex flex-col h-full w-full overflow-auto">
      <div className="flex flex-col flex-1 min-w-0 mx-auto sm:min-w-[390px] px-5 justify-center items-start gap-2 relative max-w-full sm:max-w-full h-full w-full">
        <div className="absolute top-4 left-5 ps-7">
          <div className="flex gap-2 items-center">
            { !isOpen && <SidebarToggle />}
            <Bot size={38}/>
            <ManusLogoTextIcon />
          </div>
        </div>
        
        <div className="w-full max-w-full sm:max-w-[768px] sm:min-w-[390px] mx-auto mt-[180px] mb-auto">
          <div className="w-full flex pl-4 items-center justify-start pb-4">
            <span 
              className="text-[var(--text-primary)] text-start font-serif text-[32px] leading-[40px]"
              style={{
                fontFamily: 'ui-serif, Georgia, Cambria, "Times New Roman", Times, serif'
              }}
            >
              你好呀,
              <br />
              <span className="text-[var(--text-tertiary)]">
                我能为您做什么?
              </span>
            </span>
          </div>
          <div className="flex flex-col gap-1 w-full">
            <div className="flex flex-col bg-[var(--background-gray-main)] w-full">
              <div className="[&:not(:empty)]:pb-2 bg-[var(--background-gray-main)] rounded-[22px_22px_0px_0px]">
              </div>
              <ChatBox 
                rows={2} 
                value={inputMessage} 
                onChange={setInputMessage} 
                onSubmit={(fileIds) => handleSendMessage({content: inputMessage, file_ids: fileIds || [], timestamp: Math.floor(Date.now() / 1000)})}
                placeholder="给Manus一个任务..."
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePageContent; 