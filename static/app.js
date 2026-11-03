/**
 * VIT Mumbai College Enquiry Chatbot — Premium Real-Time AI Client
 * Grounded in official records from https://vit.edu.in/
 */

(function () {
  "use strict";

  // DOM Elements
  const form = document.getElementById("chatForm");
  const input = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const messagesEl = document.getElementById("messages");
  const welcome = document.getElementById("welcome");
  const clearBtn = document.getElementById("clearBtn");
  const sidebarNewChatBtn = document.getElementById("sidebarNewChatBtn");
  const exportBtn = document.getElementById("exportBtn");
  const refreshKbBtn = document.getElementById("refreshKbBtn");
  const toast = document.getElementById("toast");
  const menuToggleBtn = document.getElementById("menuToggleBtn");
  const closeDrawerBtn = document.getElementById("closeDrawerBtn");
  const sidebar = document.getElementById("sidebar");
  const drawerBackdrop = document.getElementById("drawerBackdrop");
  const providerStatusLabel = document.getElementById("providerStatusLabel");
  const sessionsListEl = document.getElementById("sessionsList");
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const themeToggleLabel = document.getElementById("themeToggleLabel");
  const sidebarThemeToggleBtn = document.getElementById("sidebarThemeToggleBtn");
  const sidebarThemeToggleLabel = document.getElementById("sidebarThemeToggleLabel");

  // Storage Keys
  const STORAGE_KEY = "vit_mumbai_chat_v3";
  const SESSION_KEY = "vit_mumbai_session_id";

  // Application State
  let sessionId = localStorage.getItem(SESSION_KEY) || generateUUID();
  localStorage.setItem(SESSION_KEY, sessionId);

  const history = [];      // { role: "user" | "assistant", content: string }
  let transcript = [];     // { role, text, time, sources }
  let toastTimer = null;
  let isStreaming = false;

  function generateUUID() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 2800);
  }

  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
  }

  // Robust Markdown Parser
  function renderMarkdown(rawText) {
    const escaped = escapeHtml(rawText);
    const lines = escaped.split("\n");
    const output = [];
    let inList = false;
    let listType = "";
    let inTable = false;
    let tableRows = [];

    function flushTable() {
      if (!inTable || tableRows.length === 0) return;
      const allText = tableRows.map(row => row.join(" ")).join(" ");
      const isFeeTable = /fee|tuition|development|fra|annual|concession/i.test(allText) && /₹|\bfee\b/i.test(allText);

      let html = '';
      if (isFeeTable) {
        html += '<div class="fee-dashboard-panel">';
        html += '<div class="fee-dashboard-panel-header">';
        html += '  <div class="fee-dashboard-panel-title"><span>💰</span> Official Fee Structure &amp; Concessions</div>';
        html += '  <button class="fee-dashboard-open-btn" type="button" onclick="window.openFeeDashboardModal()">📊 View Full Dashboard</button>';
        html += '</div>';
        html += '<div class="fee-table-responsive" tabindex="0" role="region" aria-label="Official Fee Breakdown Table"><table class="fee-table">';
      } else {
        html += '<div class="table-wrap"><table>';
      }

      const headerRow = tableRows[0];
      html += '<thead><tr>';
      headerRow.forEach(cell => {
        const isNum = /₹|fee|amount|total/i.test(cell);
        html += `<th${isNum ? ' style="text-align: right;"' : ''}>${formatInline(cell)}</th>`;
      });
      html += '</tr></thead><tbody>';

      for (let r = 1; r < tableRows.length; r++) {
        const rowText = tableRows[r].join(" ");
        const isHighlight = /obc|ebc|open/i.test(rowText) && isFeeTable;
        html += `<tr${isHighlight ? ' class="highlight-row"' : ''}>`;
        tableRows[r].forEach(cell => {
          const isCurrency = /₹/.test(cell);
          html += `<td${isCurrency ? ' style="text-align: right;"' : ''}>${formatInline(cell)}</td>`;
        });
        html += '</tr>';
      }
      html += '</tbody></table></div>';

      if (isFeeTable) {
        html += '<div class="fee-disclaimer-banner" style="margin-top:10px;padding:8px 12px;font-size:11.5px;">';
        html += '  <div class="disclaimer-icon" style="font-size:16px;">⚖</div>';
        html += '  <div class="disclaimer-content" style="font-size:11px;line-height:1.4;"><strong>Official FRA Notice:</strong> Approved by Fee Regulating Authority Maharashtra (Code 3139). Subject to MahaDBT verification. Verify circulars at <a href="https://vit.edu.in/admissions/" target="_blank" rel="noopener noreferrer">vit.edu.in/admissions/ ↗</a>.</div>';
        html += '</div>';
        html += '</div>';
      }

      output.push(html);
      inTable = false;
      tableRows = [];
    }

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();

      // Check Table Row (| col1 | col2 |)
      if (line.startsWith("|") && line.endsWith("|")) {
        if (inList) {
          output.push(`</${listType}>`);
          inList = false;
        }
        // Skip separator row (|---|---|)
        if (/^\|(\s*[-:]+[-|\s:]*)\|$/.test(line)) {
          continue;
        }
        const cells = line.split("|").slice(1, -1).map(c => c.trim());
        inTable = true;
        tableRows.push(cells);
        continue;
      } else {
        if (inTable) {
          flushTable();
        }
      }

      // Check List Items (- or *)
      const ulMatch = line.match(/^[-*]\s+(.*)$/);
      const olMatch = line.match(/^(\d+)\.\s+(.*)$/);

      if (ulMatch) {
        if (!inList || listType !== "ul") {
          if (inList) output.push(`</${listType}>`);
          output.push("<ul>");
          inList = true;
          listType = "ul";
        }
        output.push(`<li>${formatInline(ulMatch[1])}</li>`);
        continue;
      } else if (olMatch) {
        if (!inList || listType !== "ol") {
          if (inList) output.push(`</${listType}>`);
          output.push("<ol>");
          inList = true;
          listType = "ol";
        }
        output.push(`<li>${formatInline(olMatch[2])}</li>`);
        continue;
      } else {
        if (inList) {
          output.push(`</${listType}>`);
          inList = false;
        }
      }

      // Blockquote (> text)
      if (line.startsWith("&gt; ") || line.startsWith("> ")) {
        const quoteText = line.replace(/^(&gt;|>)\s*/, "");
        output.push(`<blockquote>${formatInline(quoteText)}</blockquote>`);
        continue;
      }

      // Headers
      if (line.startsWith("### ")) {
        output.push(`<h3>${formatInline(line.slice(4))}</h3>`);
      } else if (line.startsWith("## ")) {
        output.push(`<h2>${formatInline(line.slice(3))}</h2>`);
      } else if (line.startsWith("# ")) {
        output.push(`<h2>${formatInline(line.slice(2))}</h2>`);
      } else if (line.length === 0) {
        output.push("");
      } else {
        output.push(`<p>${formatInline(line)}</p>`);
      }
    }

    if (inTable) flushTable();
    if (inList) output.push(`</${listType}>`);

    return output.join("\n");
  }

  function formatInline(text) {
    let formatted = text;

    // Markdown Links: [label](url)
    formatted = formatted.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (match, label, url) => {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`;
    });

    // Auto-link raw URLs not already in href
    formatted = formatted.replace(/(?<!href=")(https?:\/\/[^\s<]+)/g, (match, url) => {
      const cleanUrl = url.replace(/[),.]+$/, "");
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl} ↗</a>`;
    });

    // Format currency amounts: ₹ 1,76,521 or ₹1,76,521 to never break across lines
    formatted = formatted.replace(/(₹\s?[\d,]+(?:\.\d{2})?)/g, '<span class="fee-amount">$1</span>');

    // Bold: **text**
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Italic: *text*
    formatted = formatted.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, "$1<em>$2</em>$3");

    // Inline Code: `code`
    formatted = formatted.replace(/`([^`]+)`/g, "<code>$1</code>");

    return formatted;
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(transcript.slice(-60)));
      localStorage.setItem(SESSION_KEY, sessionId);
    } catch {
      // Storage quota or restriction
    }
  }

  function copyText(text, btnElement) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => markCopied(btnElement)).catch(() => fallbackCopy(text, btnElement));
    } else {
      fallbackCopy(text, btnElement);
    }
  }

  function fallbackCopy(text, btnElement) {
    const tempArea = document.createElement("textarea");
    tempArea.value = text;
    tempArea.style.position = "fixed";
    tempArea.style.opacity = "0";
    document.body.appendChild(tempArea);
    tempArea.select();
    try {
      document.execCommand("copy");
      markCopied(btnElement);
    } catch {
      showToast("Unable to copy to clipboard.");
    }
    document.body.removeChild(tempArea);
  }

  function markCopied(btn) {
    if (!btn) return;
    const originalHTML = btn.innerHTML;
    btn.classList.add("copied");
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>Copied!</span>';
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = originalHTML;
    }, 2000);
  }

  // Create message bubble container
  function createMessageRow(role, options = {}) {
    if (welcome) welcome.style.display = "none";

    const row = document.createElement("div");
    row.className = `message-row ${role} ${options.error ? "error-note" : ""}`.trim();

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    if (role === "assistant") {
      avatar.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>';
    } else {
      avatar.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    }
    avatar.setAttribute("aria-hidden", "true");

    const wrap = document.createElement("div");
    wrap.className = "bubble-wrap";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const nowTime = options.time
      ? new Date(options.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    meta.textContent = role === "user" ? `You · ${nowTime}` : `VIT Assistant · ${nowTime}`;
    wrap.appendChild(meta);

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    wrap.appendChild(bubble);

    row.append(avatar, wrap);
    messagesEl.appendChild(row);
    row.scrollIntoView({ behavior: "smooth", block: "end" });

    return { row, bubble, wrap };
  }

  function attachSources(wrap, sources) {
    if (!Array.isArray(sources) || sources.length === 0) return;
    let card = wrap.querySelector(".sources-card");
    if (!card) {
      card = document.createElement("div");
      card.className = "sources-card";

      const label = document.createElement("div");
      label.className = "sources-label";
      label.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg><span>OFFICIAL SOURCES REFERENCED</span>';
      card.appendChild(label);

      const chipsWrap = document.createElement("div");
      chipsWrap.className = "sources-chips";

      sources.forEach(src => {
        const chip = document.createElement("a");
        chip.className = `source-chip ${src.is_live ? "live-chip" : ""}`;
        chip.href = src.url;
        chip.target = "_blank";
        chip.rel = "noopener noreferrer";
        const icon = src.is_live ? "🟢" : "🏛";
        const liveTag = src.is_live ? " (Live Verified)" : "";
        chip.innerHTML = `<span>${icon}</span> <span>${escapeHtml(src.title)}${liveTag}</span> <span>↗</span>`;
        chipsWrap.appendChild(chip);
      });

      card.appendChild(chipsWrap);
      wrap.appendChild(card);
    }
  }

  function attachActions(wrap, text, retryText) {
    let actions = wrap.querySelector(".bubble-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "bubble-actions";

      const copyBtn = document.createElement("button");
      copyBtn.className = "msg-action-btn";
      copyBtn.type = "button";
      copyBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><span>Copy Answer</span>';
      copyBtn.addEventListener("click", () => copyText(text, copyBtn));
      actions.appendChild(copyBtn);

      if (retryText) {
        const retryBtn = document.createElement("button");
        retryBtn.className = "msg-action-btn";
        retryBtn.type = "button";
        retryBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg><span>Retry</span>';
        retryBtn.addEventListener("click", () => sendMessage(retryText));
        actions.appendChild(retryBtn);
      }

      wrap.appendChild(actions);
    }
  }

  function renderMessage(role, text, options = {}) {
    const { bubble, wrap, row } = createMessageRow(role, options);
    if (role === "assistant" && !options.error) {
      bubble.innerHTML = renderMarkdown(text);
      if (options.sources) attachSources(wrap, options.sources);
      attachActions(wrap, text, options.retryText);
    } else {
      bubble.textContent = text;
    }
    return row;
  }

  function addMessage(role, text, options = {}) {
    renderMessage(role, text, options);
    transcript.push({
      role,
      text,
      time: new Date().toISOString(),
      sources: options.sources || null
    });
    persist();
  }

  function setBusy(busy) {
    isStreaming = busy;
    sendBtn.disabled = busy;
    input.disabled = busy;
    if (busy) {
      sendBtn.innerHTML = '<span class="btn-spinner"></span>';
      sendBtn.setAttribute("aria-label", "Generating answer");
    } else {
      sendBtn.innerHTML = '<svg class="send-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
      sendBtn.setAttribute("aria-label", "Send question");
    }
  }

  function resizeInput() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  // Real-Time Streaming Message Sender
  async function sendMessage(rawMessage) {
    const message = (rawMessage || "").trim();
    if (!message || isStreaming) return;

    addMessage("user", message);
    history.push({ role: "user", content: message });

    input.value = "";
    resizeInput();
    setBusy(true);

    // Create assistant bubble with bouncing cyan dots
    const { row, bubble, wrap } = createMessageRow("assistant");
    bubble.innerHTML = '<div class="typing-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-caption">Consulting verified vit.edu.in records...</span></div>';

    let streamedText = "";
    let retrievedSources = [];

    // Controller with safety timeout to prevent getting stuck
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          history: history.slice(0, -1).slice(-10)
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep partial line

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;

          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;

          let data = null;
          try {
            data = JSON.parse(jsonStr);
          } catch (parseErr) {
            continue; // Skip partial lines
          }

          if (data.type === "sources") {
            retrievedSources = data.sources || [];
            attachSources(wrap, retrievedSources);
          } else if (data.type === "chunk") {
            streamedText += data.text;
            bubble.innerHTML = renderMarkdown(streamedText) + '<span class="streaming-cursor"></span>';
            row.scrollIntoView({ behavior: "smooth", block: "end" });
          } else if (data.type === "done") {
            bubble.innerHTML = renderMarkdown(streamedText);
            attachActions(wrap, streamedText, message);
            history.push({ role: "assistant", content: streamedText });
            transcript.push({
              role: "assistant",
              text: streamedText,
              time: new Date().toISOString(),
              sources: retrievedSources
            });
            persist();
            loadSessionsList();
          } else if (data.type === "error") {
            throw new Error(data.error || "AI streaming error");
          }
        }
      }

      // Ensure cursor is removed
      bubble.querySelector(".streaming-cursor")?.remove();

      if (!streamedText) {
        throw new Error("No response generated by streaming engine.");
      }

    } catch (err) {
      console.warn("SSE streaming interrupted or error, attempting standard fallback:", err);
      clearTimeout(timeoutId);

      // Fallback to standard non-streaming /api/chat
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            session_id: sessionId,
            history: history.slice(0, -1).slice(-10)
          })
        });
        const fallbackData = await res.json();
        if (res.ok) {
          const ans = fallbackData.answer || "No response received.";
          bubble.innerHTML = renderMarkdown(ans);
          if (fallbackData.sources) attachSources(wrap, fallbackData.sources);
          attachActions(wrap, ans, message);
          history.push({ role: "assistant", content: ans });
          transcript.push({
            role: "assistant",
            text: ans,
            time: new Date().toISOString(),
            sources: fallbackData.sources || null
          });
          persist();
          loadSessionsList();
        } else {
          bubble.innerHTML = escapeHtml(fallbackData.error || "Unable to complete request.");
          row.classList.add("error-note");
          attachActions(wrap, fallbackData.error, message);
        }
      } catch (fallbackErr) {
        bubble.innerHTML = "Unable to connect to the AI service. Please ensure your server and API keys are configured, then click Retry.";
        row.classList.add("error-note");
        attachActions(wrap, "Server unreachable", message);
      }
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  // Load Past Chat Sessions from SQLite
  async function loadSessionsList() {
    if (!sessionsListEl) return;
    try {
      const res = await fetch("/api/sessions");
      if (!res.ok) return;
      const data = await res.json();
      const sessions = data.sessions || [];

      if (sessions.length === 0) {
        sessionsListEl.innerHTML = '<div class="session-empty-hint">Your saved chats will appear here</div>';
        return;
      }

      sessionsListEl.innerHTML = "";
      sessions.forEach(s => {
        const item = document.createElement("div");
        item.className = `session-item ${s.session_id === sessionId ? "active" : ""}`;

        const titleSpan = document.createElement("span");
        titleSpan.className = "session-item-title";
        titleSpan.textContent = s.title || "College Enquiry";
        titleSpan.title = s.title || "College Enquiry";

        const delBtn = document.createElement("button");
        delBtn.className = "session-item-del";
        delBtn.type = "button";
        delBtn.innerHTML = "✕";
        delBtn.title = "Delete conversation";
        delBtn.addEventListener("click", e => {
          e.stopPropagation();
          deleteSession(s.session_id);
        });

        item.append(titleSpan, delBtn);
        item.addEventListener("click", () => switchSession(s.session_id));
        sessionsListEl.appendChild(item);
      });
    } catch {
      // Ignore background session list failures
    }
  }

  async function switchSession(targetSessionId) {
    if (targetSessionId === sessionId) return;
    sessionId = targetSessionId;
    localStorage.setItem(SESSION_KEY, sessionId);

    try {
      const res = await fetch(`/api/sessions/${targetSessionId}`);
      if (!res.ok) return;
      const data = await res.json();
      const messages = data.messages || [];

      history.length = 0;
      transcript = [];
      messagesEl.innerHTML = "";
      if (welcome) welcome.style.display = messages.length > 0 ? "none" : "flex";

      messages.forEach(m => {
        renderMessage(m.role, m.content, {
          sources: m.sources,
          time: m.created_at
        });
        history.push({ role: m.role, content: m.content });
        transcript.push({
          role: m.role,
          text: m.content,
          sources: m.sources,
          time: m.created_at
        });
      });

      persist();
      loadSessionsList();
      showToast("Conversation loaded.");
      toggleDrawer(false);
    } catch {
      showToast("Could not load session.");
    }
  }

  async function deleteSession(targetSessionId) {
    try {
      await fetch(`/api/sessions/${targetSessionId}`, { method: "DELETE" });
      if (targetSessionId === sessionId) {
        clearChat(false);
      } else {
        loadSessionsList();
        showToast("Conversation deleted.");
      }
    } catch {
      showToast("Failed to delete conversation.");
    }
  }

  // Restore Saved Transcript from LocalStorage
  function restoreTranscript() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(saved) || saved.length === 0) return;

      transcript = saved.filter(item => item && ["user", "assistant"].includes(item.role) && typeof item.text === "string");
      if (transcript.length > 0) {
        if (welcome) welcome.style.display = "none";
        transcript.forEach(item => {
          renderMessage(item.role, item.text, {
            sources: item.sources || null,
            time: item.time || null
          });
          history.push({ role: item.role, content: item.text });
        });
        showToast("Restored active conversation.");
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function clearChat(promptConfirm = true) {
    if (promptConfirm && transcript.length && !window.confirm("Start a new chat session?")) {
      return;
    }
    history.length = 0;
    transcript = [];
    messagesEl.innerHTML = "";
    if (welcome) welcome.style.display = "flex";
    sessionId = generateUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
    localStorage.removeItem(STORAGE_KEY);
    input.value = "";
    resizeInput();
    input.focus();
    loadSessionsList();
    showToast("New conversation started.");
    toggleDrawer(false);
  }

  function exportChat() {
    if (!transcript.length) {
      showToast("No messages to export yet.");
      return;
    }

    const header = [
      "===================================================================",
      "Vidyalankar Institute of Technology (VIT), Mumbai",
      "Official College Enquiry Assistant — Conversation Transcript",
      `Session ID: ${sessionId}`,
      `Exported On: ${new Date().toLocaleString()}`,
      "Institute Code: 3139 · Autonomous Institute · NAAC 'A+' Accredited",
      "Official Records Portal: https://vit.edu.in/",
      "===================================================================\n"
    ];

    const body = transcript.map(item => {
      const who = item.role === "user" ? "STUDENT" : "VIT ENQUIRY ASSISTANT";
      const timeStr = item.time ? `[${new Date(item.time).toLocaleTimeString()}] ` : "";
      let entry = `${timeStr}${who}:\n${item.text}\n`;
      if (item.sources && item.sources.length) {
        entry += "\nReferenced Official Sources:\n";
        item.sources.forEach(s => {
          entry += `  - ${s.title}: ${s.url}\n`;
        });
        entry += "\n";
      }
      return entry;
    });

    const fullText = header.join("\n") + body.join("\n-------------------------------------------------------------------\n");
    const blob = new Blob([fullText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `vit-mumbai-enquiry-${new Date().toISOString().slice(0, 10)}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    showToast("Transcript downloaded successfully.");
  }

  async function refreshKnowledgeBase() {
    if (!refreshKbBtn) return;
    const originalHTML = refreshKbBtn.innerHTML;
    refreshKbBtn.disabled = true;
    refreshKbBtn.innerHTML = '<span class="btn-spinner" style="border-color:#16365a;border-top-color:#06b6d4;"></span><span>Crawling vit.edu.in...</span>';
    showToast("Re-indexing official VIT pages...");

    try {
      const res = await fetch("/api/knowledge/refresh", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        showToast(`Knowledge synced! Total chunks: ${data.chunks_total || 28}`);
      } else {
        showToast("Refresh notice: " + (data.error || "Sync completed."));
      }
    } catch {
      showToast("Could not reach refresh endpoint.");
    } finally {
      refreshKbBtn.disabled = false;
      refreshKbBtn.innerHTML = originalHTML;
    }
  }

  async function checkHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) return;
      const data = await res.json();
      if (providerStatusLabel) {
        const active = data.active_provider;
        if (active === "anthropic") {
          providerStatusLabel.textContent = `Anthropic Claude (${data.providers.anthropic.model})`;
        } else if (active === "gemini") {
          providerStatusLabel.textContent = `Google Gemini (${data.providers.gemini.model})`;
        } else {
          providerStatusLabel.textContent = "AI Key Required in .env";
        }
      }
    } catch {
      // Ignore background check failure
    }
  }

  function toggleDrawer(open) {
    if (!sidebar) return;
    if (open) {
      sidebar.classList.add("open");
      drawerBackdrop?.classList.add("active");
    } else {
      sidebar.classList.remove("open");
      drawerBackdrop?.classList.remove("active");
    }
  }

  // Event Listeners
  input.addEventListener("input", resizeInput);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  // Global Keyboard Shortcut: Ctrl+K or Cmd+K for New Chat
  window.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      clearChat(true);
    }
  });

  form.addEventListener("submit", event => {
    event.preventDefault();
    sendMessage(input.value);
  });

  // Welcome suggestion cards
  document.querySelectorAll(".suggestion-card").forEach(button => {
    button.addEventListener("click", () => {
      const question = button.dataset.question;
      if (question) sendMessage(question);
    });
  });

  // Sidebar Topic Navigator click handlers
  document.querySelectorAll(".topic-item[data-ask]").forEach(button => {
    button.addEventListener("click", () => {
      const question = button.dataset.ask;
      if (question) {
        sendMessage(question);
        toggleDrawer(false);
      }
    });
  });

  clearBtn?.addEventListener("click", () => clearChat(true));
  sidebarNewChatBtn?.addEventListener("click", () => clearChat(true));
  exportBtn?.addEventListener("click", exportChat);
  refreshKbBtn?.addEventListener("click", refreshKnowledgeBase);

  // Financial Dashboard Modal Controls
  const feeModal = document.getElementById("feeModal");
  const openFeeModalBtn = document.getElementById("openFeeModalBtn");
  const closeFeeModalBtn = document.getElementById("closeFeeModalBtn");
  const closeFeeModalFooterBtn = document.getElementById("closeFeeModalFooterBtn");
  const feeModalBackdrop = document.getElementById("feeModalBackdrop");
  const sidebarFeeBadge = document.getElementById("sidebarFeeBadge");
  let lastActiveElement = null;

  function openFeeModal() {
    if (!feeModal) return;
    lastActiveElement = document.activeElement;
    feeModal.hidden = false;
    feeModal.classList.add("open");
    feeModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    document.documentElement.classList.add("modal-open");
    document.body.style.overflow = "hidden";

    // Focus close button for accessibility
    setTimeout(() => {
      closeFeeModalBtn?.focus();
    }, 50);
  }

  function closeFeeModal() {
    if (!feeModal) return;
    feeModal.hidden = true;
    feeModal.classList.remove("open");
    feeModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    document.documentElement.classList.remove("modal-open");
    document.body.style.overflow = "";

    // Restore previous focus
    if (lastActiveElement && typeof lastActiveElement.focus === "function") {
      lastActiveElement.focus();
    }
  }

  window.openFeeDashboardModal = openFeeModal;
  window.closeFeeDashboardModal = closeFeeModal;

  // 1. Top-right X button
  closeFeeModalBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeFeeModal();
  });

  // 2. Bottom Close Dashboard button
  closeFeeModalFooterBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeFeeModal();
  });

  // 3. Click backdrop to close
  feeModalBackdrop?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeFeeModal();
  });

  // 4. Click outside modal card to close
  feeModal?.addEventListener("click", (e) => {
    const card = feeModal.querySelector(".fee-modal-card");
    if (card && !card.contains(e.target)) {
      closeFeeModal();
    }
  });

  // Prevent clicks inside modal card from bubbling up to overlay click
  feeModal?.querySelector(".fee-modal-card")?.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Open triggers
  openFeeModalBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    openFeeModal();
  });

  sidebarFeeBadge?.addEventListener("click", (e) => {
    e.stopPropagation();
    openFeeModal();
  });

  // Delegated open for buttons generated in dynamic assistant messages
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest(".fee-dashboard-open-btn");
    if (trigger) {
      e.preventDefault();
      openFeeModal();
    }
  });

  // 5. Escape key to close modal
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" || e.keyCode === 27) {
      if (feeModal && (!feeModal.hidden || feeModal.classList.contains("open"))) {
        e.preventDefault();
        closeFeeModal();
      }
    }
  });

  // Financial Dashboard Tab Switching
  document.querySelectorAll(".fee-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      document.querySelectorAll(".fee-tab-btn").forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".fee-tab-panel").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      const targetPanel = document.getElementById(`tab-${targetTab}`);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });

  menuToggleBtn?.addEventListener("click", () => toggleDrawer(true));
  closeDrawerBtn?.addEventListener("click", () => toggleDrawer(false));
  drawerBackdrop?.addEventListener("click", () => toggleDrawer(false));

  // ==========================================================================
  // Light / Dark Theme Management
  // Compliant with Modern Web Guidance (color-scheme sync, FOUC-safe, cross-tab)
  // ==========================================================================
  const THEME_STORAGE_KEY = "theme";

  function getSystemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function getResolvedTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "dark" || saved === "light") return saved;
    return getSystemTheme();
  }

  function updateThemeUI(theme) {
    const isDark = theme === "dark";
    if (themeToggleBtn) {
      themeToggleBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
      themeToggleBtn.setAttribute("title", isDark ? "Switch to light theme" : "Switch to dark theme");
    }
    if (themeToggleLabel) {
      themeToggleLabel.textContent = isDark ? "Light" : "Dark";
    }
    if (sidebarThemeToggleBtn) {
      sidebarThemeToggleBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }
    if (sidebarThemeToggleLabel) {
      sidebarThemeToggleLabel.textContent = isDark ? "Light Mode" : "Dark Mode";
    }
  }

  function setTheme(theme, persist = true) {
    const resolved = (theme === "dark" || theme === "light") ? theme : getSystemTheme();
    document.documentElement.setAttribute("data-theme", resolved);

    // Keep meta color-scheme and CSS in sync
    const colorSchemeMeta = document.querySelector('meta[name="color-scheme"]');
    if (colorSchemeMeta) colorSchemeMeta.content = resolved;

    // Update browser theme-color meta tag
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
      themeColorMeta.content = resolved === "dark" ? "#070d18" : "#0b1a30";
    }

    if (persist) {
      try {
        localStorage.setItem(THEME_STORAGE_KEY, resolved);
      } catch (e) {}
    }

    updateThemeUI(resolved);
  }

  function toggleTheme() {
    const current = getResolvedTheme();
    const next = current === "dark" ? "light" : "dark";
    setTheme(next, true);
    showToast(next === "dark" ? "🌙 Switched to Dark Theme" : "☀️ Switched to Light Theme");
  }

  themeToggleBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    toggleTheme();
  });

  sidebarThemeToggleBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    toggleTheme();
  });

  // Cross-tab synchronization via storage event
  window.addEventListener("storage", (e) => {
    if (e.key === THEME_STORAGE_KEY && (e.newValue === "light" || e.newValue === "dark")) {
      setTheme(e.newValue, false);
    }
  });

  // Listen to OS / system theme preference changes when no explicit override is stored
  if (window.matchMedia) {
    const colorSchemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleSystemChange = (e) => {
      if (!localStorage.getItem(THEME_STORAGE_KEY)) {
        setTheme(e.matches ? "dark" : "light", false);
      }
    };
    if (colorSchemeQuery.addEventListener) {
      colorSchemeQuery.addEventListener("change", handleSystemChange);
    } else if (colorSchemeQuery.addListener) {
      colorSchemeQuery.addListener(handleSystemChange);
    }
  }

  // Initialize
  setTheme(getResolvedTheme(), false);
  restoreTranscript();
  checkHealth();
  loadSessionsList();
})();
