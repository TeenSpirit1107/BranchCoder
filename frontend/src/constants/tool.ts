/**
 * 工具函数映射
 */
export const TOOL_FUNCTION_MAP: {[key: string]: string} = {
  // Shell工具
  "shell_exec": "执行命令",
  "shell_view": "查看命令输出",
  "shell_wait": "等待命令完成",
  "shell_write_to_process": "向进程写入数据",
  "shell_kill_process": "终止进程",
  
  // 文件工具
  "file_read": "读取文件",
  "file_write": "写入文件",
  "file_str_replace": "替换文件内容",
  "file_find_in_content": "搜索文件内容",
  "file_find_by_name": "查找文件",
  
  // 浏览器工具
  "browser_view": "查看网页",
  "browser_navigate": "导航到网页",
  "browser_restart": "重启浏览器",
  "browser_click": "点击元素",
  "browser_input": "输入文本",
  "browser_move_mouse": "移动鼠标",
  "browser_press_key": "按键",
  "browser_select_option": "选择选项",
  "browser_scroll_up": "向上滚动",
  "browser_scroll_down": "向下滚动",
  "browser_console_exec": "执行JS代码",
  "browser_console_view": "查看控制台输出",
  
  // 搜索工具
  "info_search_web": "网络搜索",
  
  // 消息工具
  "message_notify_user": "发送通知",
  "message_deliver_artifact": "交付产物",
  "message_request_user_clarification": "请求用户澄清",

  // 音频工具
  "audio_to_text": "音频转文本",
  "audio_ask_question": "分析音频",

  // 图片工具
  "image_to_text": "图片转文本",
  "image_ask_question": "分析图片",
};

/**
 * 工具函数参数映射
 */
export const TOOL_FUNCTION_ARG_MAP: {[key: string]: string} = {
  "shell_exec": "command",
  "shell_view": "id",
  "shell_wait": "id",
  "shell_write_to_process": "id",
  "shell_kill_process": "id",
  "file_read": "file",
  "file_write": "file",
  "file_str_replace": "file",
  "file_find_in_content": "file",
  "file_find_by_name": "pattern",
  "browser_view": "url",
  "browser_navigate": "url",
  "browser_click": "selector",
  "browser_input": "selector",
  "browser_move_mouse": "selector",
  "browser_press_key": "key",
  "browser_select_option": "selector",
  "info_search_web": "query",
  "message_notify_user": "message",
  "message_deliver_artifact": "message",
  "message_request_user_clarification": "message",
  "audio_to_text": "audio_path",
  "audio_ask_question": "audio_path",
  "image_to_text": "image_path",
  "image_ask_question": "image_path"
};

/**
 * 工具名称映射
 */
export const TOOL_NAME_MAP: {[key: string]: string} = {
  "shell": "终端",
  "file": "文件",
  "browser": "浏览器",
  "info": "信息",
  "message": "消息",
  "search": "搜索",
  "message_deliver_artifact": "消息",
  "audio": "音频",
  "image": "图片"
};

/**
 * 工具图标映射
 * 实际应用中需要导入相应的图标组件
 */
import { Terminal, FileText, Globe, Search, Music, Image } from 'lucide-react';

export const TOOL_ICON_MAP: {[key: string]: React.FC<React.SVGProps<SVGSVGElement>>} = {
  "shell": Terminal,
  "file": FileText,
  "browser": Globe,
  "search": Search,
  "audio": Music,
  "image": Image
}; 