import React, { useState, useRef, useCallback, useEffect } from "react";
import MessageList from "./MessageList";
import ChatInput from "./ChatInput";
import type { ChatPanelProps, Message } from "./types";

const TEXTS: Record<
  string,
  {
    welcome: (n: string, c: string) => string;
    err: (c: string) => string;
    placeholder: string;
  }
> = {
  "zh-CN": {
    welcome: (n, c) =>
      `您好，我是 ${c} 的智能金融助手 ${n}。\n\n我可以回答关于公司业务、金融概念和市场术语的问题。请注意，我无法提供投资建议或股价预测。`,
    err: (c) => `您好，不能回复此问题，我是 FinSight AI，${c} 的智能金融助手。`,
    placeholder: "输入您的问题...",
  },
  "zh-TW": {
    welcome: (n, c) =>
      `您好，我是 ${c} 的智能金融助手 ${n}。\n\n我可以回答關於公司業務、金融概念和市場術語的問題。請注意，我無法提供投資建議或股價預測。`,
    err: (c) => `您好，無法回覆此問題，我是 FinSight AI，${c} 的智能金融助手。`,
    placeholder: "請輸入您的問題...",
  },
  en: {
    welcome: (n, c) =>
      `Hi, I am ${n}, the AI financial assistant of ${c}.\n\nI can answer questions about financial concepts, market terminology, and company services. Please note that I cannot provide investment advice or stock price predictions.`,
    err: (c) =>
      `Sorry, I cannot answer this question. I am FinSight AI, the financial assistant of ${c}.`,
    placeholder: "Type your question...",
  },
};

export default function ChatPanel({
  apiUrl,
  companyName,
  aiName,
  primaryColor,
  onClose,
  lang,
}: ChatPanelProps) {
  const t = TEXTS[lang] || TEXTS["en"];
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "system",
      content: t.welcome(aiName, companyName),
    },
  ]);
  const [streaming, setStreaming] = useState(false);
  const sessionIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pageTokenRef = useRef<string>("");

  // 获取页面验证 token，每 4 分钟刷新
  useEffect(() => {
    const fetchToken = () => {
      fetch(`${apiUrl}/api/token`)
        .then((r) => r.json())
        .then((d) => {
          pageTokenRef.current = d.token;
        })
        .catch(() => {});
    };
    fetchToken();
    const timer = setInterval(fetchToken, 240_000); // 4 min < 5 min expiry
    return () => clearInterval(timer);
  }, [apiUrl]);

  const THINKING_MSG: Message = {
    id: "thinking",
    role: "assistant",
    content: "●●●",
    streaming: false,
  };

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || streaming) return;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text,
      };
      setMessages((prev) => [...prev, userMsg, THINKING_MSG]);
      setStreaming(true);

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        const res = await fetch(`${apiUrl}/api/chat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-page-token": pageTokenRef.current,
          },
          body: JSON.stringify({
            content: text,
            session_id: sessionIdRef.current,
          }),
          signal: abort.signal,
        });
        const data = await res.json();
        sessionIdRef.current = data.session_id;
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== "thinking"),
          { id: `ai-${Date.now()}`, role: "assistant", content: data.reply },
        ]);
      } catch (err: any) {
        if (err.name === "AbortError") return;
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== "thinking"),
          {
            id: `err-${Date.now()}`,
            role: "assistant",
            content: t.err(companyName),
          },
        ]);
      }
      setStreaming(false);
      abortRef.current = null;
    },
    [apiUrl, streaming, companyName],
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
    setMessages((prev) => prev.filter((m) => m.id !== "thinking"));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          backgroundColor: "rgba(15,23,42,0.8)",
          flexShrink: 0,
        }}
      >
        <div style={{ fontWeight: 600, fontSize: 16, color: "#f1f5f9" }}>
          {aiName}
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 4,
            borderRadius: 6,
            color: "#94a3b8",
            fontSize: 20,
            lineHeight: 1,
          }}
          aria-label="关闭"
        >
          ✕
        </button>
      </div>

      <MessageList messages={messages} aiName={aiName} />
      <ChatInput
        onSend={handleSend}
        onStop={handleStop}
        streaming={streaming}
        disabled={false}
        primaryColor={primaryColor}
        placeholder={t.placeholder}
      />
    </div>
  );
}
