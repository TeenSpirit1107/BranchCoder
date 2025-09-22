export type MessageType = "user" | "assistant" | "tool" | "step" | "request_clarification" | "done";

export interface Message {
  type: MessageType;
  content: BaseContent;
}

export interface BaseContent {
  timestamp: number;
}

export interface MessageContent extends BaseContent {
  content: string;
  file_ids?: string[];
}

export interface ToolContent extends BaseContent {
  name: string;
  function: string;
  args: any;
  result?: any;
}

export interface StepContent extends BaseContent {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tools: ToolContent[];
} 