import { toast as shadcnToast } from "@/hooks/use-toast";
import { Toaster } from "@/components/ui/toaster";

// 创建一个兼容原有API的toast对象
export const toast = {
  show: (message: string, type: 'info' | 'success' | 'error' | 'warning' = 'info', duration = 3000) => {
    // 根据不同类型设置不同的变体
    const variant = type === 'error' ? "destructive" : "default";
    
    shadcnToast({
      title: type.charAt(0).toUpperCase() + type.slice(1),
      description: message,
      duration: duration,
      variant: variant,
      className: getToastClassByType(type),
    });
  },
  info: (message: string, duration?: number) => toast.show(message, 'info', duration),
  success: (message: string, duration?: number) => toast.show(message, 'success', duration),
  error: (message: string, duration?: number) => toast.show(message, 'error', duration),
  warning: (message: string, duration?: number) => toast.show(message, 'warning', duration),
};

// 获取不同类型的样式类名
const getToastClassByType = (type: string): string => {
  switch (type) {
    case 'success':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'error':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'warning':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    default: // info
      return 'bg-blue-100 text-blue-800 border-blue-200';
  }
};

// Toast组件就是shadcn的Toaster组件
const Toast = () => <Toaster />;

export default Toast; 