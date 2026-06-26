import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./ChatWidget";

const root = document.getElementById("finsight-chat-root");
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <ChatWidget
        tenant="finsight"
        apiUrl="http://localhost:5173"
        companyName="FinSight Securities"
        aiName="FinSight AI"
        position="right"
        primaryColor="#007aff"
      />
    </React.StrictMode>,
  );
}
