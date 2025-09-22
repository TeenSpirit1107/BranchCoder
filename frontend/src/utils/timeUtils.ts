/**
 * 时间相关工具函数
 */

import { useEffect, useState } from 'react';

/**
 * 将时间戳转换为相对时间（例如，几分钟前，几小时前，几天前）
 * @param timestamp 时间戳（秒）
 * @returns 格式化的相对时间字符串
 */
export const formatRelativeTime = (timestamp: number): string => {
  const now = Math.floor(Date.now() / 1000);
  const diffSec = now - timestamp;
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  const diffMonth = Math.floor(diffDay / 30);
  const diffYear = Math.floor(diffMonth / 12);

  if (diffSec < 60) {
    return '刚刚';
  } else if (diffMin < 60) {
    return `${diffMin} 分钟前`;
  } else if (diffHour < 24) {
    return `${diffHour} 小时前`;
  } else if (diffDay < 30) {
    return `${diffDay} 天前`;
  } else if (diffMonth < 12) {
    return `${diffMonth} 个月前`;
  } else {
    return `${diffYear} 年前`;
  }
};

/**
 * React Hook，用于获取定期更新的相对时间
 * @param timestamp 时间戳（秒）
 * @returns 格式化的相对时间字符串
 */
export const useRelativeTime = (timestamp: number) => {
  const [relativeTime, setRelativeTime] = useState<string>(formatRelativeTime(timestamp));

  useEffect(() => {
    // 计算初始时间
    setRelativeTime(formatRelativeTime(timestamp));

    // 设置定时器定期更新时间
    const timer = setInterval(() => {
      setRelativeTime(formatRelativeTime(timestamp));
    }, 60000); // 每分钟更新一次

    // 组件卸载时清理定时器
    return () => {
      clearInterval(timer);
    };
  }, [timestamp]);

  return relativeTime;
}; 