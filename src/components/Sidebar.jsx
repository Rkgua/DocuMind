import { useState, useRef, useCallback, useEffect } from "react";
import {
  MessageSquarePlus,
  Upload,
  Globe,
  Trash2,
  History,
  Plus,
  Library,
  Loader2,
  Eye,
  X,
} from "lucide-react";

function Sidebar({ selectedDocs, onDocsChange, onTotalDocsChange, onNewChat, onLoadHistory }) {
  const [documents, setDocuments] = useState([]);
  const [history, setHistory] = useState([]);
  const [activeHistory, setActiveHistory] = useState(null);
  const [uploadProgress, setUploadProgress] = useState([]);
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [isScraping, setIsScraping] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [scrapeError, setScrapeError] = useState("");
  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewChunks, setPreviewChunks] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [processingMsg, setProcessingMsg] = useState("");
  const fileInputRef = useRef(null);

  // 加载文档列表
  const loadDocuments = useCallback(async () => {
    try {
      const res = await fetch("/api/documents");
      if (res.ok) {
        const data = await res.json();
        const docs = data.documents || [];
        setDocuments(docs);
        const ids = docs.map(d => d.id);
        onTotalDocsChange(ids);
        onDocsChange(ids);
      }
    } catch {
      // 静默失败
    }
  }, [onDocsChange, onTotalDocsChange]);

  // 加载历史对话
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch("/api/conversations");
      if (res.ok) {
        const data = await res.json();
        setHistory(data.conversations || []);
        if (data.conversations?.length > 0 && !activeHistory) {
          setActiveHistory(data.conversations[0].id);
        }
      }
    } catch {
      // 静默失败
    }
  }, [activeHistory]);

  useEffect(() => {
    Promise.all([loadDocuments(), loadHistory()]).finally(() =>
      setLoading(false),
    );
  }, [loadDocuments, loadHistory]);

  const handleCheckDoc = useCallback(
    (docId) => {
      setDocuments((prev) => {
        const updated = prev.map((d) =>
          d.id === docId ? { ...d, selected: !d.selected } : d,
        );
        onDocsChange(updated.filter((d) => d.selected).map((d) => d.id));
        return updated;
      });
    },
    [onDocsChange],
  );

  const showError = useCallback((msg) => {
    setErrorMsg(msg);
    setTimeout(() => setErrorMsg(""), 4000);
  }, []);

  const handlePreviewDoc = useCallback(async (docId, e) => {
    e.stopPropagation();
    setPreviewLoading(true);
    setPreviewDoc(docId);
    try {
      const res = await fetch(`/api/documents/${docId}/chunks`);
      if (res.ok) {
        const data = await res.json();
        setPreviewChunks(data.chunks || []);
      }
    } catch {
      setPreviewChunks([]);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const handleClosePreview = useCallback(() => {
    setPreviewDoc(null);
    setPreviewChunks([]);
  }, []);

  const handleDeleteDoc = useCallback(
    async (docId, e) => {
      e.stopPropagation();
      try {
        const res = await fetch(`/api/documents/${docId}`, {
          method: "DELETE",
        });
        if (!res.ok) {
          showError("删除失败");
          return;
        }
        setDocuments((prev) => {
          const updated = prev.filter((d) => d.id !== docId);
          onDocsChange(updated.map((d) => d.id));
          return updated;
        });
      } catch {
        showError("删除失败: 无法连接服务器");
      }
    },
    [showError, onDocsChange],
  );

  // 真实文件上传
  const handleUpload = useCallback(
    async (files) => {
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append("files", file));
      const fileNames = Array.from(files).map(f => f.name);

      setProcessingMsg(`正在解析 ${fileNames[0]}${fileNames.length > 1 ? ` 等 ${fileNames.length} 个文件` : ''}...`);

      try {
        const res = await fetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          setProcessingMsg("");
          showError(`上传失败: ${res.status}`);
          return;
        }
        const result = await res.json();
        setProcessingMsg("正在将文本向量化并入库...");
        await loadDocuments();
        setProcessingMsg("");
        if (result.files) {
          setUploadProgress(
            result.files.map((f) => ({
              id: f.id,
              name: f.name,
              status: "done",
              progress: 100,
            })),
          );
          setTimeout(() => setUploadProgress([]), 3000);
        }
      } catch {
        setProcessingMsg("");
        showError("上传失败: 无法连接服务器");
      }
    },
    [loadDocuments, showError],
  );

  const handleFileChange = useCallback(
    (e) => {
      const files = e.target.files;
      if (files?.length) {
        handleUpload(files);
      }
      e.target.value = "";
    },
    [handleUpload],
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragOver(false);
      const files = e.dataTransfer.files;
      if (files?.length) {
        handleUpload(files);
      }
    },
    [handleUpload],
  );

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  // 真实网页抓取
  const handleScrape = useCallback(async () => {
    if (!scrapeUrl.trim()) return;
    setIsScraping(true);
    setScrapeError("");
    setProcessingMsg("正在抓取网页内容...");
    try {
      const res = await fetch("/api/documents/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: scrapeUrl.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setScrapeError(data.detail || `抓取失败: ${res.status}`);
        return;
      }
      setProcessingMsg("正在将文本向量化并入库...");
      await loadDocuments();
      setProcessingMsg("");
      setScrapeUrl("");
    } catch {
      setProcessingMsg("");
      setScrapeError("抓取失败: 无法连接服务器");
    } finally {
      setIsScraping(false);
    }
  }, [scrapeUrl, loadDocuments]);

  const handleHistoryClick = useCallback(
    async (histId) => {
      setActiveHistory(histId);
      setHistory((prev) =>
        prev.map((h) => ({ ...h, active: h.id === histId })),
      );
      // 加载该历史对话的消息
      try {
        const res = await fetch(`/api/conversations/${histId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.messages && onLoadHistory) {
            onLoadHistory(data.messages, histId);
          }
        }
      } catch {
        // 加载历史失败不提示
      }
    },
    [onLoadHistory],
  );

  const handleDeleteHistory = useCallback(async (histId, e) => {
    e.stopPropagation();
    try {
      const res = await fetch(`/api/conversations/${histId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setHistory((prev) => prev.filter((h) => h.id !== histId));
        // 如果删除的是当前活跃对话，重置
        setActiveHistory((prev) => (prev === histId ? null : prev));
      }
    } catch {
      // 静默失败
    }
  }, []);

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <img src="/DocumindRobot.svg" alt="DocuMind" style={{ width: 20, height: 20 }} />
          </div>
          DocuMind
        </div>
        <button className="new-chat-btn" onClick={() => { onNewChat(); loadHistory(); }}>
          <Plus size={16} />
          新建对话
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="sidebar-scroll">
        {/* Error Banner */}
        {errorMsg && (
          <div
            style={{
              padding: "8px 12px",
              marginBottom: 8,
              background: "rgba(239,68,68,0.15)",
              color: "#f87171",
              borderRadius: "var(--radius-sm)",
              fontSize: "0.8rem",
            }}
          >
            {errorMsg}
          </div>
        )}
        {processingMsg && (
          <div className="processing-banner">
            <div className="processing-spinner" />
            {processingMsg}
          </div>
        )}
        {/* Knowledge Base Section */}
        <div className="sidebar-section">
          <div className="sidebar-section-header">
            <span>知识库管理</span>
            <Library size={14} />
          </div>
          <div className="sidebar-section-body">
            {/* File Upload */}
            <div
              className={`upload-zone ${isDragOver ? "drag-over" : ""}`}
              onClick={() => fileInputRef.current?.click()}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <div className="upload-icon">
                <Upload size={28} />
              </div>
              <div className="upload-text">
                <strong>点击上传</strong> 或拖拽文件到此处
              </div>
              <div className="upload-hint">支持 PDF、DOCX、PPTX、MD、TXT 格式</div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.pptx,.ppt,.md,.txt"
                style={{ display: "none" }}
                onChange={handleFileChange}
              />
            </div>

            {/* Upload Progress */}
            {uploadProgress.length > 0 && (
              <div className="upload-progress">
                {uploadProgress.map((item) => (
                  <div key={item.id} className="upload-progress-item">
                    <span className="file-name">{item.name}</span>
                    <span className="file-status">
                      {item.status === "done"
                        ? "✅ 上传成功"
                        : `${Math.round(item.progress)}%`}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Document Check List */}
            <div style={{ padding: "8px 0" }}>
              <div className="web-scraper">
                <input
                  type="text"
                  placeholder="输入网页 URL 一键解析"
                  value={scrapeUrl}
                  onChange={(e) => setScrapeUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleScrape()}
                />
                <button
                  className="scrape-btn"
                  onClick={handleScrape}
                  disabled={isScraping || !scrapeUrl.trim()}
                >
                  {isScraping ? (
                    <Loader2
                      size={14}
                      style={{ animation: "spin 0.6s linear infinite" }}
                    />
                  ) : (
                    <Globe size={14} />
                  )}
                  {isScraping ? "" : "抓取"}
                </button>
              </div>
              {scrapeError && (
                <div
                  style={{
                    padding: "4px 8px 0",
                    fontSize: "0.75rem",
                    color: "#f87171",
                  }}
                >
                  {scrapeError}
                </div>
              )}
            </div>

            {/* 入库文档列表 */}
            <div
              className="sidebar-section-header"
              style={{ paddingBottom: 4 }}
            >
              <span>已入库文档</span>
            </div>
            {loading ? (
              <div
                style={{
                  padding: "16px 8px",
                  textAlign: "center",
                  color: "var(--text-sidebar-secondary)",
                  fontSize: "0.8rem",
                }}
              >
                <div className="spinner" style={{ margin: "0 auto 8px" }} />
                加载中...
              </div>
            ) : documents.length === 0 ? (
              <div
                style={{
                  padding: "16px 8px",
                  textAlign: "center",
                  color: "var(--text-sidebar-secondary)",
                  fontSize: "0.8rem",
                }}
              >
                暂无文档，请上传或抓取
              </div>
            ) : (
              <div className="doc-check-list">
                {documents.map((doc) => (
                  <label
                    key={doc.id}
                    className="doc-check-item"
                    onClick={() => handleCheckDoc(doc.id)}
                  >
                    <input
                      type="checkbox"
                      checked={doc.selected ?? true}
                      readOnly
                    />
                    <span className="doc-name" title={doc.name}>{doc.title || doc.name}</span>
                    <span className="doc-pages">{doc.pages || ""}</span>
                    <button
                      className="doc-action-btn doc-preview-btn"
                      onClick={(e) => handlePreviewDoc(doc.id, e)}
                      title="查看分块数据"
                    >
                      <Eye size={13} />
                    </button>
                    <button
                      className="doc-action-btn doc-delete-btn"
                      onClick={(e) => handleDeleteDoc(doc.id, e)}
                      title="删除文档"
                    >
                      <Trash2 size={13} />
                    </button>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* History Section */}
        <div className="sidebar-section" style={{ flex: 1, minHeight: 0 }}>
          <div className="sidebar-section-header">
            <span>历史对话</span>
            <History size={14} />
          </div>
          <div className="sidebar-section-body" style={{ overflow: "hidden" }}>
            <div className="history-list">
              {loading ? (
                <div
                  style={{
                    padding: "24px 8px",
                    textAlign: "center",
                    color: "var(--text-sidebar-secondary)",
                    fontSize: "0.8rem",
                  }}
                >
                  加载中...
                </div>
              ) : history.length === 0 ? (
                <div
                  style={{
                    padding: "24px 8px",
                    textAlign: "center",
                    color: "var(--text-sidebar-secondary)",
                    fontSize: "0.8rem",
                  }}
                >
                  暂无历史对话
                </div>
              ) : (
                history.map((h) => (
                  <div
                    key={h.id}
                    className={`history-item ${h.active ? "active" : ""}`}
                    onClick={() => handleHistoryClick(h.id)}
                  >
                    <MessageSquarePlus size={16} className="history-icon" />
                    <div className="history-info">
                      <div className="history-title">{h.title}</div>
                      <div className="history-date">
                        {h.created_at || h.date}
                      </div>
                    </div>
                    <button
                      className="history-delete-btn"
                      onClick={(e) => handleDeleteHistory(h.id, e)}
                      title="删除对话"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 分块预览弹窗 */}
      {previewDoc && (
        <div className="preview-overlay" onClick={handleClosePreview}>
          <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="preview-header">
              <h3>文档分块数据</h3>
              <div className="preview-header-right">
                <span className="preview-chunk-count">{previewChunks.length} 个块</span>
                <button className="preview-close-btn" onClick={handleClosePreview}>
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="preview-body">
              {previewLoading ? (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)" }}>
                  <div className="spinner" style={{ margin: "0 auto 8px" }} />
                  加载中...
                </div>
              ) : previewChunks.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)" }}>
                  暂无分块数据
                </div>
              ) : (
                <div className="preview-chunks">
                  {previewChunks.map((chunk, i) => (
                    <div key={chunk.id} className="preview-chunk-item">
                      <div className="preview-chunk-header">
                        <span className="preview-chunk-num">块 #{i + 1}</span>
                        <span className="preview-chunk-id">{chunk.id}</span>
                      </div>
                      <pre className="preview-chunk-content">{chunk.content}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

export default Sidebar;
