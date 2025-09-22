import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SidebarState {
  // 侧边栏开关状态
  isOpen: boolean;
  // 切换侧边栏开关状态
  toggle: () => void;
  // 打开侧边栏
  open: () => void;
  // 关闭侧边栏
  close: () => void;
}

export const useSidebar = create<SidebarState>()(
  persist(
    (set) => ({
      isOpen: false,
      toggle: () => set((state) => ({ isOpen: !state.isOpen })),
      open: () => set({ isOpen: true }),
      close: () => set({ isOpen: false }),
    }),
    {
      name: 'sidebar-storage',
    }
  )
); 