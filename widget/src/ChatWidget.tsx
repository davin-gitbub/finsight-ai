import React, { useState, useEffect } from "react";
import ChatPanel from "./ChatPanel";
import type { ChatWidgetProps } from "./types";

const MOBILE_BREAKPOINT = 640;

const DEFAULT_STYLES = {
  button: {
    width: 56,
    height: 56,
    borderRadius: 28,
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center" as const,
    justifyContent: "center" as const,
    boxShadow: "0 4px 16px rgba(0,0,0,0.15), 0 1px 4px rgba(0,0,0,0.08)",
    transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
    zIndex: 999999,
    position: "fixed" as const,
    bottom: 24,
  },
  panel: {
    position: "fixed" as const,
    bottom: 92,
    zIndex: 999999,
    width: "min(380px, calc(100vw - 32px))",
    height: "min(600px, calc(100dvh - 100px), calc(100vh - 140px))",
    borderRadius: 16,
    overflow: "hidden",
    boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
    display: "flex",
    flexDirection: "column" as const,
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    backgroundColor: "rgba(15,23,42,0.97)",
    border: "1px solid rgba(255,255,255,0.06)",
    transition: "all 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
  },
  mobilePanel: {
    bottom: 76,
    width: "100vw",
    height: "calc(min(100dvh, 100vh) - 76px)",
    borderRadius: 0,
    border: "none",
  },
};

export default function ChatWidget({
  tenant = "finsight",
  apiUrl = "http://localhost:8000",
  companyName = "FinSight Securities",
  aiName = "FinSight AI",
  position = "right",
  primaryColor = "#007aff",
  lang: langProp,
}: ChatWidgetProps) {
  const [open, setOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined"
      ? window.innerWidth < MOBILE_BREAKPOINT
      : false,
  );
  const isRight = position === "right";

  function getSavedLang() {
    return (
      langProp ||
      (typeof window !== "undefined"
        ? localStorage.getItem("finsight-lang") || "zh-CN"
        : "zh-CN")
    );
  }
  const [currentLang, setCurrentLang] = useState(getSavedLang);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Listen for global language changes
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      setCurrentLang(e.detail);
    };
    window.addEventListener("finsight-lang-change", handler as EventListener);
    return () =>
      window.removeEventListener(
        "finsight-lang-change",
        handler as EventListener,
      );
  }, []);

  // 移动端打开面板时锁定 body 滚动，关闭时恢复
  useEffect(() => {
    if (isMobile && open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [isMobile, open]);

  const panelStyle = isMobile
    ? {
        ...DEFAULT_STYLES.panel,
        ...DEFAULT_STYLES.mobilePanel,
        [isRight ? "right" : "left"]: 0,
      }
    : {
        ...DEFAULT_STYLES.panel,
        [isRight ? "right" : "left"]: 24,
        opacity: open ? 1 : 0,
        transform: open
          ? "translateY(0) scale(1)"
          : "translateY(20px) scale(0.95)",
      };

  return (
    <>
      {/* 聊天面板 */}
      {open && (
        <div
          style={{
            ...panelStyle,
            pointerEvents: open ? "auto" : "none",
          }}
        >
          <ChatPanel
            tenant={tenant}
            apiUrl={apiUrl}
            companyName={companyName}
            aiName={aiName}
            primaryColor={primaryColor}
            onClose={() => setOpen(false)}
            lang={currentLang}
          />
        </div>
      )}

      {/* 浮动按钮 — 移动端隐藏 */}
      {!isMobile && (
        <button
          style={{
            ...DEFAULT_STYLES.button,
            [isRight ? "right" : "left"]: 24,
            backgroundColor: open ? "#f0f2f5" : primaryColor,
          }}
          onClick={() => setOpen(!open)}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "scale(1.08)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "scale(1)";
          }}
          aria-label={open ? "关闭聊天" : "打开聊天"}
        >
          {open ? (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#f1f5f9"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : (
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          )}
        </button>
      )}
    </>
  );
}
