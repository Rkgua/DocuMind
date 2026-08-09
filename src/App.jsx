import { useState, useRef, useCallback, useEffect } from "react";
import "./App.css";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import RobotAvatar from "./components/RobotAvatar";

function App() {
  //状态管理部分
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [totalDocIds, setTotalDocIds] = useState([]);
  const [references, setReferences] = useState({});
  const [sessionId, setSessionId] = useState(null);
  const [robotStatus, setRobotStatus] = useState("entrance");
  const abortControllerRef = useRef(null);
  const robotStatusTimerRef = useRef(null);

  const setRobotStatusFor = useCallback((status, duration = 0) => {
    if (robotStatusTimerRef.current) {
      clearTimeout(robotStatusTimerRef.current);
      robotStatusTimerRef.current = null;
    }
    setRobotStatus(status);
    if (duration > 0) {
      robotStatusTimerRef.current = setTimeout(() => {
        setRobotStatus("idle");
        robotStatusTimerRef.current = null;
      }, duration);
    }
  }, []);

  // 页面加载 → 闪亮登场 → 待机
  useEffect(() => {
    const t = setTimeout(() => setRobotStatus("idle"), 1100);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    return () => {
      if (robotStatusTimerRef.current) {
        clearTimeout(robotStatusTimerRef.current);
      }
    };
  }, []);

  const handleInputActivity = useCallback(
    (active) => {
      if (!isStreaming) {
        setRobotStatus(active ? "listening" : "idle");
      }
    },
    [isStreaming],
  );

  // 用户发送后进入思考，收到首个流式片段后进入输出状态
  const handleSend = useCallback(
    async (text) => {
      const userMsg = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);

      setIsStreaming(true);
      setRobotStatusFor("thinking");
      const aiMsgId = Date.now();
      const aiMsg = { role: "ai", content: "", id: aiMsgId };
      setMessages((prev) => [...prev, aiMsg]);

      // 处理流式请求的关键，确保在用户点击“停止”或组件卸载时，
      // 能立刻中断正在进行的网络请求，防止内存泄漏和状态错乱
      const controller = new AbortController();
      abortControllerRef.current = controller;
      let hasOutput = false;
      let terminalStatusSet = false;

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            // 全选时传 null（后端用全部文档），部分勾选时才传具体 ID
            document_ids:
              selectedDocs.length === totalDocIds.length ? null : selectedDocs,
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
          if (chunk && !hasOutput) {
            hasOutput = true;
            setRobotStatusFor("responding");
          }
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
        if (controller.signal.aborted) return;
        terminalStatusSet = true;
        setRobotStatusFor("success", 900);
      } catch (err) {
        if (err.name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: m.content || "请求失败，请重试。" }
                : m,
            ),
          );
          terminalStatusSet = true;
          setRobotStatusFor("error", 1100);
        }
      } finally {
        setIsStreaming(false);
        if (!terminalStatusSet) setRobotStatus("idle");
        abortControllerRef.current = null;
      }
    },
    [selectedDocs, totalDocIds, sessionId, setRobotStatusFor],
  );

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setReferences({});
    setSessionId(null);
  }, []);

  const handleLoadHistory = useCallback((historyMessages, histId) => {
    // 给历史消息补 id（用于参考来源匹配）
    const withIds = historyMessages.map((msg, i) => ({
      ...msg,
      id: msg.id || `hist_${i}`,
    }));
    setMessages(withIds);
    setSessionId(histId);
    setReferences({});
  }, []);

  return (
    <div className="app-container">
      <div className="robot-fixed">
        <RobotAvatar
          status={robotStatus}
          size={250}
        />
      </div>
      <Sidebar
        selectedDocs={selectedDocs}
        onDocsChange={setSelectedDocs}
        onTotalDocsChange={setTotalDocIds}
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
        onInputActivity={handleInputActivity}
      />
    </div>
  );
}

export default App;
