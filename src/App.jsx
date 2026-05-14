import { useState, useRef, useCallback } from "react";
import "./App.css";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";

function App() {
  //状态管理部分
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [references, setReferences] = useState({});
  const [sessionId, setSessionId] = useState(null);
  const abortControllerRef = useRef(null);


  // 核心发送逻辑，使用 useCallback 包裹以避免不必要的重渲染
  const handleSend = useCallback(
    async (text) => {
      const userMsg = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);

      setIsStreaming(true);
      const aiMsgId = Date.now();
      const aiMsg = { role: "ai", content: "", id: aiMsgId };
      setMessages((prev) => [...prev, aiMsg]);

      // 处理流式请求的关键，确保在用户点击“停止”或组件卸载时，
      // 能立刻中断正在进行的网络请求，防止内存泄漏和状态错乱
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            document_ids: selectedDocs,
            session_id: sessionId,
          }),
          signal: controller.signal,
        });

        if (!response.ok) throw new Error("Network error");

        // 读取响应头的 session_id
        const newSessionId = response.headers.get("X-Session-Id");
        if (newSessionId) setSessionId(newSessionId);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          fullContent += chunk;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, content: fullContent } : m,
            ),
          );
        }

        // 流结束后获取引用来源
        try {
          const refRes = await fetch(
            `/api/chat/${aiMsgId}/references?q=${encodeURIComponent(text)}`,
            {
              signal: controller.signal,
            },
          );
          if (refRes.ok) {
            const refData = await refRes.json();
            setReferences((prev) => ({
              ...prev,
              [aiMsgId]: refData.sources || [],
            }));
          }
        } catch {
          // 引用数据可选，获取失败不影响主流程
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: m.content || "请求失败，请重试。" }
                : m,
            ),
          );
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [selectedDocs],
  );

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setMessages([])
    setReferences({})
    setSessionId(null)
  }, [])

  const handleLoadHistory = useCallback((historyMessages, histId) => {
    // 给历史消息补 id（用于参考来源匹配）
    const withIds = historyMessages.map((msg, i) => ({
      ...msg,
      id: msg.id || `hist_${i}`,
    }))
    setMessages(withIds)
    setSessionId(histId)
    setReferences({})
  }, [])

  return (
    <div className="app-container">
      <Sidebar
        selectedDocs={selectedDocs}
        onDocsChange={setSelectedDocs}
        onNewChat={handleNewChat}
        onLoadHistory={handleLoadHistory}
      />
      <ChatArea
        messages={messages}
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={isStreaming}
        references={references}
        onNewChat={handleNewChat}
      />
    </div>
  );
}

export default App;
