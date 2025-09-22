export interface BaseEventData {
  timestamp: number;
}

export interface MessageEventData extends BaseEventData {
  content: string;
}

export interface UserInputEventData extends BaseEventData {
  content: string;
  file_ids: string[];
}

export interface ToolEventData extends BaseEventData {
  name: string;
  function: string;
  args: any;
  result?: any;
}

export interface StepEventData extends BaseEventData {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface PlanEventData extends BaseEventData {
  steps: {
    id: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
  }[];
  issuperplan?: boolean;
  issubplan?: boolean;
}

export interface ErrorEventData extends BaseEventData {
  error: string;
}

export interface TitleEventData extends BaseEventData {
  title: string;
}

export interface DoneEventData extends BaseEventData {
}

// SSE事件类型
export type SSEEvent = 
  | { event: 'message'; data: MessageEventData }
  | { event: 'user_input'; data: UserInputEventData }
  | { event: 'tool'; data: ToolEventData }
  | { event: 'step'; data: StepEventData }
  | { event: 'plan'; data: PlanEventData }
  | { event: 'error'; data: ErrorEventData }
  | { event: 'title'; data: TitleEventData }
  | { event: 'done'; data: DoneEventData }; 