import { Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Toast from './components/Toast';
import Sidebar from './components/layout/Sidebar';
import { cn } from '@/utils/cn';

const HomePage = lazy(() => import('./pages/HomePage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const BrowserControlPage = lazy(() => import('./pages/BrowserControlPage'));

function App() {
  return (
    <div className="h-screen flex overflow-hidden bg-white">
      {/* 侧边栏 - 只在打开状态时显示 */}
      <Sidebar />

      {/* 主内容区域 */}
      <div className={cn(
        "flex-1 min-w-0 h-full relative transition-all duration-300"
      )}>
        <div className="flex h-full bg-[var(--background-gray-main)]">
          <Suspense fallback={<div className="flex items-center justify-center w-full h-full">加载中...</div>}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/chat/:agentId" element={<ChatPage />} />
              <Route path="/browser-view/:agentId" element={<BrowserControlPage />} />
            </Routes>
          </Suspense>
        </div>
      </div>
      <Toast />
    </div>
  );
}

export default App; 