import React, { useRef, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "./types";

interface MessageListProps {
  messages: Message[];
  aiName: string;
}

const COPY_ICON = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    style={{ width: 12, height: 12 }}
  >
    <rect x="9" y="9" width="13" height="13" rx="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
);

const CHECK_ICON = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2.5}
    style={{ width: 12, height: 12 }}
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard
      .writeText(text)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  };

  return (
    <button
      onClick={handleCopy}
      title="复制"
      style={{
        background: "none",
        border: "none",
        cursor: "pointer",
        padding: "3px 4px",
        borderRadius: 5,
        color: copied ? "#34d399" : "#64748b",
        display: "inline-flex",
        alignItems: "center",
        gap: 2,
        fontSize: 11,
      }}
      className="copy-btn-fix"
      onMouseEnter={(e) => {
        if (!copied) (e.target as HTMLElement).style.color = "#94a3b8";
      }}
      onMouseLeave={(e) => {
        if (!copied) (e.target as HTMLElement).style.color = "#64748b";
      }}
    >
      {copied ? CHECK_ICON : COPY_ICON}
      {copied ? "已复制" : ""}
    </button>
  );
}

export default function MessageList({ messages, aiName }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "16px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {messages.map((msg) => (
        <div key={msg.id} style={{ maxWidth: "85%" }} className="msg-wrap">
          {msg.role === "system" && (
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 15,
                color: "#e2e8f0",
                lineHeight: 1.6,
                margin: "0 auto",
                textAlign: "center",
                maxWidth: "100%",
                fontWeight: 500,
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          )}

          {msg.role === "user" && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-end",
              }}
            >
              <div
                style={{
                  backgroundColor: "#3b82f6",
                  color: "white",
                  borderRadius: "16px 16px 4px 16px",
                  padding: "10px 16px",
                  fontSize: 15,
                  lineHeight: 1.5,
                }}
              >
                {msg.content}
              </div>
              <CopyButton text={msg.content} />
            </div>
          )}

          {msg.role === "assistant" && (
            <div
              style={msg.id === "thinking" ? { display: "inline-block" } : {}}
            >
              <div
                style={{
                  backgroundColor: "#1e293b",
                  borderRadius: "16px 16px 16px 4px",
                  padding: msg.id === "thinking" ? "8px 14px" : "12px 16px",
                  fontSize: 15,
                  color: "#e2e8f0",
                  lineHeight: 1.6,
                  fontWeight: 600,
                  display: msg.id === "thinking" ? "inline-block" : "block",
                }}
              >
                {msg.status && msg.streaming && (
                  <div
                    style={{
                      color: "#94a3b8",
                      fontStyle: "italic",
                      fontSize: 13,
                      marginBottom: 4,
                    }}
                  >
                    {msg.status}
                  </div>
                )}

                {msg.id === "thinking" ? (
                  <div
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "6px 18px",
                    }}
                  >
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: "#64748b",
                          display: "inline-block",
                          animation: "dotWave 1.2s ease-in-out infinite",
                          animationDelay: `${i * 0.15}s`,
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ href, children }) => (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: "#818cf8" }}
                        >
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {msg.content || (msg.streaming ? "..." : "")}
                  </ReactMarkdown>
                )}

                {msg.streaming && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 7,
                      height: 13,
                      backgroundColor: "#007aff",
                      animation: "blink 0.8s infinite",
                      marginLeft: 2,
                      borderRadius: 1,
                      verticalAlign: "middle",
                    }}
                  />
                )}
              </div>
              {!msg.streaming && msg.content && msg.id !== "thinking" && (
                <CopyButton text={msg.content} />
              )}
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
