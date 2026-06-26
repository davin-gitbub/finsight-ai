/** FinSight AI — TypeScript 类型定义 */

// ──── WebSocket 协议 ────

export type WsEventType =
  | "connected"
  | "status"
  | "token"
  | "sources"
  | "done"
  | "error";

export interface WsEvent {
  type: WsEventType;
  content?: string;
  session_id?: string;
  code?: string;
  sources?: Source[];
}

export interface Source {
  title: string;
  page: number | string;
}

// ──── 消息 ────

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: Source[];
  rating?: number;
  streaming?: boolean;
  status?: string;
}

// ──── 组件 Props ────

export interface ChatWidgetProps {
  tenant?: string;
  apiUrl?: string;
  companyName?: string;
  aiName?: string;
  position?: "left" | "right";
  primaryColor?: string;
  lang?: string;
}

export interface ChatPanelProps {
  tenant: string;
  apiUrl: string;
  companyName: string;
  aiName: string;
  primaryColor: string;
  onClose: () => void;
  lang: string;
}

export interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  primaryColor: string;
}

export interface MessageListProps {
  messages: Message[];
  aiName: string;
}

// ──── WebSocket 状态 ────

export type WsStatus = "connecting" | "connected" | "disconnected" | "error";
