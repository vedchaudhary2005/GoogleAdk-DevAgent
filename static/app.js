/**
 * DevAgent Enterprise - Frontend Client
 * Handles real-time SSE streaming, ADK agent step telemetry,
 * MongoDB conversation management, dynamic model selector, and fallback alerts.
 */

// Application State
const state = {
  conversations: [],
  activeConversationId: null,
  availableModels: {},
  defaultModel: "",
  selectedModel: localStorage.getItem("devagent_selected_model") || "",
  isStreaming: false,
};

// DOM Elements
const el = {
  sidebar: document.getElementById("sidebar"),
  btnToggleSidebar: document.getElementById("btn-toggle-sidebar"),
  btnNewChat: document.getElementById("btn-new-chat"),
  conversationsList: document.getElementById("conversations-list"),
  chatSearch: document.getElementById("chat-search"),
  activeChatTitle: document.getElementById("active-chat-title"),
  btnRenameChat: document.getElementById("btn-rename-chat"),
  modelSelector: document.getElementById("model-selector"),
  fallbackBanner: document.getElementById("fallback-banner"),
  fallbackBannerText: document.getElementById("fallback-banner-text"),
  btnCloseBanner: document.getElementById("btn-close-banner"),
  chatFeed: document.getElementById("chat-feed"),
  welcomeScreen: document.getElementById("welcome-screen"),
  messagesContainer: document.getElementById("messages-container"),
  messageInput: document.getElementById("message-input"),
  btnSend: document.getElementById("btn-send"),
};

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await loadModels();
  await loadConversations();
});

function setupEventListeners() {
  // Sidebar Toggle
  el.btnToggleSidebar.addEventListener("click", () => {
    el.sidebar.classList.toggle("collapsed");
  });

  // New Chat Button
  el.btnNewChat.addEventListener("click", () => {
    startNewConversation();
  });

  // Chat Search Filter
  el.chatSearch.addEventListener("input", (e) => {
    filterConversations(e.target.value);
  });

  // Rename Title Button
  el.btnRenameChat.addEventListener("click", () => {
    if (state.activeConversationId) {
      renameConversation(state.activeConversationId);
    }
  });

  // Model Selector Change
  el.modelSelector.addEventListener("change", (e) => {
    state.selectedModel = e.target.value;
    localStorage.setItem("devagent_selected_model", state.selectedModel);
    if (state.activeConversationId) {
      updateConversationModel(state.activeConversationId, state.selectedModel);
    }
  });

  // Close Fallback Banner
  el.btnCloseBanner.addEventListener("click", () => {
    el.fallbackBanner.classList.add("hidden");
  });

  // Auto-resize textarea and Enter to send
  el.messageInput.addEventListener("input", autoResizeTextarea);
  el.messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Send Button
  el.btnSend.addEventListener("click", handleSendMessage);

  // Welcome Screen Prompt Cards
  document.querySelectorAll(".prompt-card").forEach((card) => {
    card.addEventListener("click", () => {
      const prompt = card.getAttribute("data-prompt");
      if (prompt) {
        el.messageInput.value = prompt;
        autoResizeTextarea();
        handleSendMessage();
      }
    });
  });
}

function autoResizeTextarea() {
  el.messageInput.style.height = "auto";
  el.messageInput.style.height = `${Math.min(el.messageInput.scrollHeight, 180)}px`;
}

// ==========================================
// MODELS MANAGEMENT
// ==========================================

async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    state.availableModels = data.providers || {};
    state.defaultModel = data.default_model || "";

    if (!state.selectedModel) {
      state.selectedModel = state.defaultModel;
    }

    renderModelSelector();
  } catch (err) {
    console.error("Failed to load models:", err);
  }
}

function renderModelSelector() {
  el.modelSelector.innerHTML = "";

  for (const [providerKey, provider] of Object.entries(state.availableModels)) {
    const optgroup = document.createElement("optgroup");
    optgroup.label = provider.name || providerKey.toUpperCase();

    (provider.models || []).forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = `${model.name} (${model.id})`;
      if (model.id === state.selectedModel) {
        option.selected = true;
      }
      optgroup.appendChild(option);
    });

    el.modelSelector.appendChild(optgroup);
  }
}

// ==========================================
// CONVERSATIONS MANAGEMENT (MONGODB)
// ==========================================

async function loadConversations() {
  try {
    const res = await fetch("/api/conversations");
    const data = await res.json();
    state.conversations = data.conversations || [];
    renderConversationsList();

    if (state.conversations.length > 0 && !state.activeConversationId) {
      selectConversation(state.conversations[0].conversation_id);
    } else if (state.conversations.length === 0) {
      startNewConversation();
    }
  } catch (err) {
    console.error("Failed to load conversations:", err);
    el.conversationsList.innerHTML = `<div class="loading-state">Could not connect to MongoDB.</div>`;
  }
}

function renderConversationsList() {
  el.conversationsList.innerHTML = "";

  if (state.conversations.length === 0) {
    el.conversationsList.innerHTML = `<div class="loading-state">No conversations yet.</div>`;
    return;
  }

  state.conversations.forEach((conv) => {
    const item = document.createElement("div");
    item.className = `history-item ${conv.conversation_id === state.activeConversationId ? "active" : ""}`;
    item.dataset.id = conv.conversation_id;

    item.innerHTML = `
      <span class="history-item-title" title="${escapeHtml(conv.title)}">${escapeHtml(conv.title)}</span>
      <div class="history-item-actions">
        <button class="btn-item-action btn-rename" title="Rename">✏️</button>
        <button class="btn-item-action btn-delete" title="Delete">🗑️</button>
      </div>
    `;

    item.addEventListener("click", (e) => {
      if (e.target.closest(".btn-rename")) {
        e.stopPropagation();
        renameConversation(conv.conversation_id);
      } else if (e.target.closest(".btn-delete")) {
        e.stopPropagation();
        deleteConversation(conv.conversation_id);
      } else {
        selectConversation(conv.conversation_id);
      }
    });

    el.conversationsList.appendChild(item);
  });
}

function filterConversations(term) {
  const q = term.toLowerCase().trim();
  const items = el.conversationsList.querySelectorAll(".history-item");
  items.forEach((item) => {
    const title = item.querySelector(".history-item-title").textContent.toLowerCase();
    item.style.display = title.includes(q) ? "flex" : "none";
  });
}

function startNewConversation() {
  state.activeConversationId = null;
  el.activeChatTitle.textContent = "New Conversation";
  el.messagesContainer.innerHTML = "";
  el.welcomeScreen.style.display = "block";
  document.querySelectorAll(".history-item").forEach((it) => it.classList.remove("active"));
  el.messageInput.focus();
}

async function selectConversation(id) {
  if (state.isStreaming) return;
  state.activeConversationId = id;

  document.querySelectorAll(".history-item").forEach((it) => {
    it.classList.toggle("active", it.dataset.id === id);
  });

  try {
    const res = await fetch(`/api/conversations/${id}`);
    if (!res.ok) throw new Error("Conversation not found");
    const data = await res.json();

    el.activeChatTitle.textContent = data.conversation.title || "Conversation";

    if (data.conversation.model && data.conversation.model !== state.selectedModel) {
      state.selectedModel = data.conversation.model;
      el.modelSelector.value = state.selectedModel;
      localStorage.setItem("devagent_selected_model", state.selectedModel);
    }

    renderMessages(data.messages || []);
  } catch (err) {
    console.error("Failed to fetch conversation:", err);
  }
}

async function renameConversation(id) {
  const current = state.conversations.find((c) => c.conversation_id === id);
  const newTitle = prompt("Enter conversation title:", current ? current.title : "");
  if (!newTitle || !newTitle.trim()) return;

  try {
    const res = await fetch(`/api/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle.trim() }),
    });
    if (res.ok) {
      if (state.activeConversationId === id) {
        el.activeChatTitle.textContent = newTitle.trim();
      }
      await loadConversations();
    }
  } catch (err) {
    console.error("Failed to rename conversation:", err);
  }
}

async function deleteConversation(id) {
  if (!confirm("Are you sure you want to delete this conversation?")) return;

  try {
    const res = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
    if (res.ok) {
      if (state.activeConversationId === id) {
        startNewConversation();
      }
      await loadConversations();
    }
  } catch (err) {
    console.error("Failed to delete conversation:", err);
  }
}

async function updateConversationModel(id, model) {
  try {
    await fetch(`/api/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
  } catch (err) {
    console.error("Failed to update conversation model:", err);
  }
}

// ==========================================
// CHAT & MESSAGES RENDERING
// ==========================================

function renderMessages(messages) {
  el.messagesContainer.innerHTML = "";

  if (messages.length === 0) {
    el.welcomeScreen.style.display = "block";
    return;
  }

  el.welcomeScreen.style.display = "none";

  messages.forEach((msg) => {
    appendMessageBubble(msg.role, msg.content, {
      model: msg.model,
      metadata: msg.metadata,
      created_at: msg.created_at,
    });
  });

  scrollToBottom();
}

function appendMessageBubble(role, content, options = {}) {
  el.welcomeScreen.style.display = "none";

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  let headerHtml = "";
  if (role === "assistant") {
    const modelTag = options.model ? `<span class="model-pill ${options.metadata?.was_fallback ? 'fallback' : ''}">${escapeHtml(options.model)}</span>` : "";
    const fallbackTag = options.metadata?.was_fallback ? `<span class="badge-tag" style="background:#533f03; color:#e3b341;">Auto-Fallback</span>` : "";
    headerHtml = `
      <div class="message-header">
        <span class="agent-badge">DevAgent</span>
        ${modelTag}
        ${fallbackTag}
      </div>
    `;
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = `
    ${headerHtml}
    <div class="markdown-body">${renderMarkdown(content)}</div>
  `;

  row.appendChild(bubble);
  el.messagesContainer.appendChild(row);

  // Attach copy code buttons
  setupCodeCopyButtons(bubble);

  return { row, bubble };
}

function renderMarkdown(text) {
  if (!text) return "";
  try {
    if (window.marked) {
      return marked.parse(text);
    }
  } catch (e) {
    console.warn("Markdown parse error:", e);
  }
  return `<p>${escapeHtml(text).replace(/\n/g, "<br>")}</p>`;
}

function setupCodeCopyButtons(container) {
  container.querySelectorAll("pre code").forEach((block) => {
    if (window.hljs) {
      hljs.highlightElement(block);
    }
    const pre = block.parentElement;
    if (!pre.querySelector(".btn-copy-code")) {
      const copyBtn = document.createElement("button");
      copyBtn.className = "btn-copy-code";
      copyBtn.textContent = "Copy";
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(block.innerText).then(() => {
          copyBtn.textContent = "Copied!";
          setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
        });
      });
      pre.style.position = "relative";
      pre.appendChild(copyBtn);
    }
  });
}

function scrollToBottom() {
  el.chatFeed.scrollTop = el.chatFeed.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==========================================
// SEND MESSAGE & SSE STREAMING
// ==========================================

async function handleSendMessage() {
  if (state.isStreaming) return;
  const text = el.messageInput.value.trim();
  if (!text) return;

  // Clear input
  el.messageInput.value = "";
  autoResizeTextarea();

  // If no conversation selected, create one in MongoDB first
  if (!state.activeConversationId) {
    try {
      const convRes = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: text.slice(0, 35) + (text.length > 35 ? "..." : ""),
          model: state.selectedModel,
        }),
      });
      const convData = await convRes.json();
      state.activeConversationId = convData.conversation_id;
      el.activeChatTitle.textContent = convData.title;
      await loadConversations();
    } catch (err) {
      console.error("Failed to auto-create conversation:", err);
      state.activeConversationId = "chat_" + Date.now();
    }
  }

  // Render User Message
  appendMessageBubble("user", text);
  scrollToBottom();

  // Prepare Assistant Message Card with steps accordion and typing indicator
  state.isStreaming = true;
  el.btnSend.disabled = true;

  const assistantRow = document.createElement("div");
  assistantRow.className = "message-row assistant";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  // Message Header
  const header = document.createElement("div");
  header.className = "message-header";
  header.innerHTML = `
    <span class="agent-badge">DevAgent</span>
    <span class="model-pill" id="current-stream-model">${escapeHtml(state.selectedModel)}</span>
    <span class="memory-pill hidden" id="current-stream-memory">🧠 Cross-Chat Memory Applied</span>
  `;
  bubble.appendChild(header);

  // Agent Steps Accordion
  const accordion = document.createElement("div");
  accordion.className = "steps-accordion";
  accordion.innerHTML = `
    <div class="steps-summary" id="accordion-toggle">
      <div class="steps-summary-left">
        <span>⚙️ ADK Agent Execution Flow</span>
        <span class="badge-tag" id="step-counter">0 events</span>
      </div>
      <span class="accordion-arrow">▼</span>
    </div>
    <div class="steps-list" id="steps-list"></div>
  `;
  bubble.appendChild(accordion);

  const accordionToggle = accordion.querySelector("#accordion-toggle");
  const stepsList = accordion.querySelector("#steps-list");
  const stepCounter = accordion.querySelector("#step-counter");
  const modelPill = header.querySelector("#current-stream-model");
  const memoryPill = header.querySelector("#current-stream-memory");

  accordionToggle.addEventListener("click", () => {
    const isHidden = stepsList.style.display === "none";
    stepsList.style.display = isHidden ? "flex" : "none";
    accordion.querySelector(".accordion-arrow").textContent = isHidden ? "▼" : "▲";
  });

  // Body content & Typing indicator
  const typingIndicator = document.createElement("div");
  typingIndicator.className = "typing-indicator";
  typingIndicator.innerHTML = `
    <div class="pulse-dot"></div>
    <span id="typing-status-text">DevAgent is thinking...</span>
  `;
  bubble.appendChild(typingIndicator);

  const markdownBody = document.createElement("div");
  markdownBody.className = "markdown-body";
  bubble.appendChild(markdownBody);

  assistantRow.appendChild(bubble);
  el.messagesContainer.appendChild(assistantRow);
  scrollToBottom();

  let accumulatedText = "";
  let eventCount = 0;

  function addStepEntry(tagClass, tagText, details) {
    eventCount++;
    stepCounter.textContent = `${eventCount} events`;
    const entry = document.createElement("div");
    entry.className = "step-entry";
    entry.innerHTML = `
      <span class="step-tag ${tagClass}">${escapeHtml(tagText)}</span>
      <span>${escapeHtml(details)}</span>
    `;
    stepsList.appendChild(entry);
    scrollToBottom();
  }

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: state.activeConversationId,
        message: text,
        model: state.selectedModel,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Keep unfinished chunk in buffer

      for (const block of lines) {
        if (!block.trim()) continue;

        let eventType = "message";
        let eventData = "";

        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) {
            eventType = line.replace("event:", "").trim();
          } else if (line.startsWith("data:")) {
            eventData = line.replace("data:", "").trim();
          }
        }

        if (!eventData) continue;

        try {
          const payload = JSON.parse(eventData);

          if (eventType === "start") {
            modelPill.textContent = payload.requested_model;
            if (payload.has_cross_chat_memory) {
              memoryPill.classList.remove("hidden");
            }
          } else if (eventType === "memory_context") {
            memoryPill.classList.remove("hidden");
            addStepEntry("escalate", "Memory", payload.info);
          } else if (eventType === "status") {
            const statusEl = document.getElementById("typing-status-text");
            if (statusEl) statusEl.textContent = `${payload.model} (Attempt ${payload.attempt})...`;
          } else if (eventType === "transfer") {
            addStepEntry("transfer", "Transfer", `${payload.from_agent} ➔ ${payload.to_agent}`);
          } else if (eventType === "tool_call") {
            const argsStr = JSON.stringify(payload.args || {});
            addStepEntry("tool", "Tool Call", `${payload.agent} ➔ ${payload.tool}(${argsStr})`);
            const statusEl = document.getElementById("typing-status-text");
            if (statusEl) statusEl.textContent = `Executing tool: ${payload.tool}...`;
          } else if (eventType === "tool_result") {
            addStepEntry("result", "Tool Result", `${payload.tool} returned output`);
          } else if (eventType === "review_verdict") {
            addStepEntry("review", "Review", `${payload.verdict}: ${payload.feedback.slice(0, 100)}...`);
          } else if (eventType === "escalate") {
            addStepEntry("escalate", "Escalate", payload.message);
          } else if (eventType === "fallback") {
            // Show Fallback Banner
            el.fallbackBanner.classList.remove("hidden");
            el.fallbackBannerText.textContent = payload.reason;
            modelPill.textContent = payload.to_model;
            modelPill.classList.add("fallback");
            addStepEntry("review", "Fallback", `Auto-switched from ${payload.from_model} to ${payload.to_model}`);
          } else if (eventType === "token") {
            accumulatedText += payload.text;
            markdownBody.innerHTML = renderMarkdown(accumulatedText);
            setupCodeCopyButtons(markdownBody);
            scrollToBottom();
          } else if (eventType === "done") {
            if (payload.model_used) {
              modelPill.textContent = payload.model_used;
              if (payload.was_fallback) {
                modelPill.classList.add("fallback");
              }
            }
            if (payload.full_text && !accumulatedText) {
              accumulatedText = payload.full_text;
              markdownBody.innerHTML = renderMarkdown(accumulatedText);
              setupCodeCopyButtons(markdownBody);
            }
          } else if (eventType === "error") {
            addStepEntry("review", "Error", payload.error);
            markdownBody.innerHTML += `<div style="color:var(--accent-red); margin-top:8px;">⚠️ ${escapeHtml(payload.error)}</div>`;
          }
        } catch (parseErr) {
          console.warn("Failed to parse SSE payload:", parseErr, eventData);
        }
      }
    }
  } catch (err) {
    console.error("Chat streaming error:", err);
    markdownBody.innerHTML += `<div style="color:var(--accent-red); margin-top:8px;">⚠️ Connection error: ${escapeHtml(err.message)}</div>`;
  } finally {
    typingIndicator.remove();
    state.isStreaming = false;
    el.btnSend.disabled = false;
    scrollToBottom();
    // Refresh conversation list in sidebar to update timestamps & titles
    loadConversations();
  }
}
