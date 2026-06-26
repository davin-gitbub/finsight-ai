import React, { useRef, useCallback, useEffect } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop?: () => void;
  streaming?: boolean;
  disabled: boolean;
  primaryColor: string;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  onStop,
  streaming = false,
  disabled,
  primaryColor,
  placeholder,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingRef = useRef(streaming);
  const disabledRef = useRef(disabled);
  const onSendRef = useRef(onSend);
  const onStopRef = useRef(onStop);

  // Keep refs in sync
  streamingRef.current = streaming;
  disabledRef.current = disabled;
  onSendRef.current = onSend;
  onStopRef.current = onStop;

  // Native event listeners - same approach as main page
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    let imeKeyDown = false;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        if (e.isComposing) {
          imeKeyDown = true;
          return;
        }
        e.preventDefault();
        if (!streamingRef.current) el.form?.requestSubmit();
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey && imeKeyDown) {
        imeKeyDown = false;
        if (!streamingRef.current) el.form?.requestSubmit();
      }
    };

    el.addEventListener("keydown", onKeyDown);
    el.addEventListener("keyup", onKeyUp);
    return () => {
      el.removeEventListener("keydown", onKeyDown);
      el.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (streamingRef.current) {
      onStopRef.current?.();
      return;
    }
    const el = textareaRef.current;
    if (!el) return;
    const trimmed = el.value.trim();
    if (!trimmed || disabledRef.current) return;
    el.value = "";
    el.style.height = "auto";
    onSendRef.current(trimmed);
  }, []);

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 100) + "px";
  }, []);

  return (
    <div
      style={{
        padding: "12px 16px 16px",
        borderTop: "1px solid rgba(0,0,0,0.06)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        backgroundColor: "rgba(255,255,255,0.8)",
        flexShrink: 0,
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
          backgroundColor: "#f5f5f7",
          borderRadius: 12,
          padding: "4px 4px 4px 16px",
          border: "1px solid rgba(0,0,0,0.04)",
        }}
      >
        <textarea
          ref={textareaRef}
          defaultValue=""
          onInput={handleInput}
          placeholder={
            disabled ? "Connecting..." : placeholder || "Type your question..."
          }
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            resize: "none",
            backgroundColor: "transparent",
            fontSize: 15,
            color: "#1d1d1f",
            padding: "8px 0",
            fontFamily: "inherit",
            lineHeight: 1.5,
            maxHeight: 120,
          }}
        />
        <button
          type="submit"
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            border: "none",
            backgroundColor: primaryColor,
            color: "white",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            transition: "opacity 0.2s",
            opacity: disabled ? 0.4 : 1,
          }}
          aria-label={streaming ? "停止" : "发送"}
        >
          {streaming ? (
            <svg width="18" height="18" viewBox="0 0 24 24">
              <rect x="5" y="5" width="14" height="14" rx="3" fill="#d1d1d6" />
            </svg>
          ) : (
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </form>
    </div>
  );
}
