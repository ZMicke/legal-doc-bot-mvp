const API_BASE = "http://127.0.0.1:8000";

const state = {
  currentFileId: null,
  currentFileName: "",
  currentClaimText: "",
  currentDownloadUrl: null,
  lastResponse: null,
};

function getElement(id) {
  return document.getElementById(id);
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanErrorMessage(error) {
  const message = error?.message || "Произошла ошибка";
  if (message.includes("Traceback") || message.includes("sqlalchemy") || message.includes("psycopg2")) {
    return "Сервер вернул техническую ошибку. Подробности сохранены в консоли разработчика.";
  }
  return message;
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });

  if (tabName === "history") loadHistory(false);
  if (tabName === "knowledge") loadKnowledgeList(false);
}

function useExample(text) {
  getElement("userRequest").value = text;
  updateSteps();
}

function setButtonLoading(button, isLoading, loadingText, defaultText) {
  if (!button) return;
  if (isLoading) {
    button.dataset.defaultText = defaultText || button.textContent;
    button.textContent = loadingText;
    button.disabled = true;
    return;
  }
  button.textContent = button.dataset.defaultText || defaultText || button.textContent;
  button.disabled = false;
}

function showToast(message, type = "info") {
  const container = getElement("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

async function parseResponse(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch (error) {
    return { detail: text || "Сервер вернул ответ в неизвестном формате" };
  }
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    console.error(error);
    throw new Error("Не удалось подключиться к серверу");
  }

  const data = await parseResponse(response);
  if (!response.ok) {
    console.error("Backend error", data);
    throw new Error(data.detail || `Ошибка сервера: ${response.status}`);
  }
  return data;
}

function updateSteps() {
  getElement("step-contract").classList.toggle("done", Boolean(state.currentFileId));
  getElement("step-problem").classList.toggle("active", !state.currentFileId);
  getElement("step-problem").classList.toggle("done", Boolean(getElement("userRequest").value.trim()));
  getElement("step-details").classList.toggle("active", Boolean(state.currentFileId));
  getElement("step-result").classList.toggle("done", Boolean(state.currentClaimText));
}

function isSupportedFile(file) {
  return /\.(txt|docx|pdf)$/i.test(file?.name || "");
}

async function uploadDocument() {
  const fileInput = getElement("contractFile");
  const file = fileInput.files[0];
  if (!file) {
    showToast("Выберите договор для загрузки", "warning");
    return;
  }
  if (!isSupportedFile(file)) {
    showToast("Файл не поддерживается. Используйте TXT, DOCX или PDF", "warning");
    return;
  }

  const button = getElement("uploadButton");
  const formData = new FormData();
  formData.append("file", file);
  setButtonLoading(button, true, "Загружаем...", "Загрузить договор");
  getElement("uploadStatus").className = "status-badge neutral";
  getElement("uploadStatus").textContent = "Загружаем";

  try {
    const data = await requestJson("/documents/upload", { method: "POST", body: formData });
    console.log("Document upload response", data);
    state.currentFileId = data.file_id;
    state.currentFileName = file.name;
    getElement("fileInfo").className = "file-summary";
    getElement("fileInfo").textContent = `Договор загружен: ${file.name}`;
    getElement("uploadStatus").className = "status-badge success";
    getElement("uploadStatus").textContent = "Договор загружен";
    getElement("generateButton").disabled = false;
    showToast("Договор загружен", "success");
    updateSteps();
  } catch (error) {
    console.error(error);
    getElement("uploadStatus").className = "status-badge error";
    getElement("uploadStatus").textContent = "Ошибка загрузки";
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Загрузить договор");
  }
}

function buildManualFields() {
  return {
    violation_date: getElement("violationDate").value.trim(),
    violation_description: getElement("violationDescription").value.trim(),
    response_deadline: getElement("responseDeadline").value.trim(),
    penalty_amount: getElement("penaltyAmount").value.trim(),
    sender_name: getElement("senderName").value.trim(),
    sender_address: getElement("senderAddress").value.trim(),
    recipient_name: getElement("recipientName").value.trim(),
    recipient_address: getElement("recipientAddress").value.trim(),
  };
}

async function generateClaim() {
  if (!state.currentFileId) {
    showToast("Сначала загрузите договор", "warning");
    return;
  }

  const userRequest = getElement("userRequest").value.trim();
  if (!userRequest) {
    showToast("Опишите проблему, по которой нужно подготовить претензию", "warning");
    return;
  }

  const button = getElement("generateButton");
  const payload = {
    file_id: state.currentFileId,
    user_request: userRequest,
    claim_type: "auto",
    use_llm: true,
    manual_fields: buildManualFields(),
  };

  setButtonLoading(button, true, "Формируем претензию...", "Сформировать претензию");
  getElement("generationStatus").textContent = "Анализируем договор и готовим текст претензии...";

  try {
    const data = await requestJson("/claims/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    console.log("Claim generation response", data);
    renderGenerationResult(data);
    showToast("Претензия сформирована", "success");
    await loadHistory(false);
  } catch (error) {
    console.error(error);
    getElement("generationStatus").textContent = "Не удалось сформировать претензию";
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Сформировать претензию");
  }
}

function renderGenerationResult(data) {
  state.lastResponse = data;
  state.currentClaimText = data.claim_text || data.result_text || "";
  state.currentDownloadUrl = data.download_url || null;

  const result = getElement("claimResult");
  result.className = "document-card";
  result.textContent = state.currentClaimText || "Сервер не вернул текст претензии.";

  getElement("generationStatus").textContent = data.claim_request_id
    ? `Претензия №${data.claim_request_id} готова.`
    : "Претензия готова.";

  getElement("resultActions").classList.remove("hidden");
  getElement("copyClaimButton").disabled = !state.currentClaimText;

  const downloadLink = getElement("downloadLink");
  if (state.currentDownloadUrl) {
    downloadLink.href = `${API_BASE}${state.currentDownloadUrl}`;
    downloadLink.classList.remove("disabled");
    downloadLink.removeAttribute("aria-disabled");
  } else {
    downloadLink.href = "#";
    downloadLink.classList.add("disabled");
    downloadLink.setAttribute("aria-disabled", "true");
  }

  renderLegalArticles(data.law_articles || []);
  renderWarnings(collectWarnings(data));
  updateSteps();
}

function renderLegalArticles(lawArticles = []) {
  const container = getElement("lawArticlesOutput");
  const seen = new Set();
  const items = lawArticles
    .map((item) => item.article || item.title || "")
    .filter(Boolean)
    .filter((title) => {
      const normalized = title.toLowerCase();
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    })
    .slice(0, 8);

  if (!items.length) {
    container.className = "legal-basis empty";
    container.textContent = "";
    return;
  }

  container.className = "legal-basis";
  container.innerHTML = `
    <strong>Использованы правовые основания:</strong>
    <ul>${items.map((title) => `<li>${escapeHtml(title)}</li>`).join("")}</ul>
  `;
}

function collectWarnings(data) {
  const warnings = [];
  if (data.web_fallback_used) warnings.push("При подготовке использовался поиск по внешним источникам.");
  if (data.llm_error) warnings.push("LLM не смогла улучшить текст. Использован базовый проект претензии.");
  if (data.web_error) warnings.push("Не удалось получить часть материалов из интернета.");
  const qualityWarnings = data.trace?.quality_checks?.warnings || [];
  return warnings.concat(qualityWarnings);
}

function renderWarnings(warnings = []) {
  const container = getElement("warningsOutput");
  if (!warnings.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <div class="warning-card">
      <strong>Есть рекомендации для проверки</strong>
      <ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>
    </div>
  `;
}

async function loadHistory(showToastOnSuccess = false) {
  const button = getElement("loadHistoryButton");
  setButtonLoading(button, true, "Обновляем...", "Обновить");
  try {
    const data = await requestJson("/claims/history");
    console.log("History response", data);
    renderHistory(data.items || []);
    if (showToastOnSuccess) showToast("История обновлена", "success");
  } catch (error) {
    console.error(error);
    getElement("historyOutput").className = "history-list empty";
    getElement("historyOutput").textContent = "Не удалось загрузить историю.";
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Обновить");
  }
}

function renderHistory(items) {
  const container = getElement("historyOutput");
  const lastItems = items.slice(0, 5);
  if (!lastItems.length) {
    container.className = "history-list empty";
    container.textContent = "История пока пуста. Сформируйте первую претензию.";
    return;
  }

  container.className = "history-list";
  container.innerHTML = lastItems.map((item) => {
    const date = item.created_at ? new Date(item.created_at).toLocaleString("ru-RU") : "Дата не указана";
    const request = item.user_request || "Запрос не указан";
    const preview = item.preview || item.result_text || "Текст пока недоступен";
    const download = item.download_url
      ? `<a class="button secondary" href="${API_BASE}${item.download_url}" target="_blank" rel="noreferrer">Скачать DOCX</a>`
      : "";
    return `
      <article class="history-card">
        <header>
          <div>
            <h3>Претензия №${escapeHtml(item.id)}</h3>
            <p class="section-kicker">${escapeHtml(date)}</p>
          </div>
          <div class="history-actions">
            <button type="button" class="secondary" onclick="openHistoryItem(${Number(item.id)})">Открыть</button>
            ${download}
          </div>
        </header>
        <p><strong>${escapeHtml(request)}</strong></p>
        <p class="preview-text">${escapeHtml(preview).slice(0, 260)}</p>
      </article>
    `;
  }).join("");
}

async function openHistoryItem(id) {
  try {
    const data = await requestJson(`/claims/${id}`);
    console.log("History item response", data);
    switchTab("create");
    renderGenerationResult({
      claim_request_id: data.id,
      claim_text: data.result_text,
      download_url: data.download_url,
      law_articles: [],
    });
    showToast(`Открыта претензия №${id}`, "success");
  } catch (error) {
    console.error(error);
    showToast(cleanErrorMessage(error), "error");
  }
}

async function clearHistory() {
  const confirmed = window.confirm("Удалить историю претензий? Скачанные DOCX-файлы на сервере также будут удалены.");
  if (!confirmed) return;
  const button = getElement("clearHistoryButton");
  setButtonLoading(button, true, "Очищаем...", "Очистить историю");
  try {
    const data = await requestJson("/claims/history", { method: "DELETE" });
    console.log("Clear history response", data);
    renderHistory([]);
    showToast("История очищена", "success");
  } catch (error) {
    console.error(error);
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Очистить историю");
  }
}

async function addRagUrl() {
  const payload = {
    title: getElement("ragUrlTitle").value.trim(),
    source_type: getElement("ragUrlSourceType").value.trim(),
    source_url: getElement("ragSourceUrl").value.trim(),
  };
  if (!payload.title || !payload.source_type || !payload.source_url) {
    showToast("Заполните название, тип источника и ссылку", "warning");
    return;
  }

  const button = getElement("addRagUrlButton");
  setButtonLoading(button, true, "Добавляем...", "Добавить ссылку");
  try {
    const data = await requestJson("/knowledge/add-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    console.log("RAG URL response", data);
    getElement("maintenanceOutput").textContent = "Ссылка добавлена. При необходимости переиндексируйте базу.";
    await loadKnowledgeList(false);
    showToast("Ссылка добавлена в базу знаний", "success");
  } catch (error) {
    console.error(error);
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Добавить ссылку");
  }
}

async function uploadRagFile() {
  const title = getElement("ragFileTitle").value.trim();
  const sourceType = getElement("ragFileSourceType").value.trim();
  const file = getElement("ragFile").files[0];
  if (!title || !sourceType || !file) {
    showToast("Заполните название, тип источника и выберите файл", "warning");
    return;
  }
  if (!isSupportedFile(file)) {
    showToast("Файл не поддерживается. Используйте TXT, DOCX или PDF", "warning");
    return;
  }

  const formData = new FormData();
  formData.append("title", title);
  formData.append("source_type", sourceType);
  formData.append("file", file);

  const button = getElement("uploadRagFileButton");
  setButtonLoading(button, true, "Загружаем...", "Загрузить документ");
  try {
    const data = await requestJson("/knowledge/upload-file", { method: "POST", body: formData });
    console.log("RAG file response", data);
    getElement("maintenanceOutput").textContent = "Документ добавлен. При необходимости переиндексируйте базу.";
    await loadKnowledgeList(false);
    showToast("Документ добавлен в базу знаний", "success");
  } catch (error) {
    console.error(error);
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Загрузить документ");
  }
}

async function loadKnowledgeList(showToastOnSuccess = false) {
  const button = getElement("loadKnowledgeButton");
  setButtonLoading(button, true, "Обновляем...", "Обновить список");
  try {
    const data = await requestJson("/knowledge/list");
    console.log("Knowledge list response", data);
    renderKnowledgeList(data.items || []);
    if (showToastOnSuccess) showToast("Список базы знаний обновлен", "success");
  } catch (error) {
    console.error(error);
    getElement("knowledgeListOutput").className = "knowledge-list empty";
    getElement("knowledgeListOutput").textContent = "Не удалось загрузить список материалов.";
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Обновить список");
  }
}

function renderKnowledgeList(items) {
  const container = getElement("knowledgeListOutput");
  if (!items.length) {
    container.className = "knowledge-list empty";
    container.textContent = "База знаний пока пуста.";
    return;
  }

  container.className = "knowledge-list";
  container.innerHTML = items.map((item) => {
    const preview = item.content || item.text_preview || "";
    const url = item.source_url
      ? `<a class="source-link" href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(item.source_url)}</a>`
      : "";
    return `
      <article class="knowledge-card">
        <header>
          <div>
            <h3>${escapeHtml(item.title || "Материал без названия")}</h3>
            <p class="section-kicker">${escapeHtml(item.source_type || "Тип источника не указан")}</p>
          </div>
        </header>
        ${url ? `<p>${url}</p>` : ""}
        <p class="preview-text">${escapeHtml(preview).slice(0, 320) || "Описание материала отсутствует."}</p>
      </article>
    `;
  }).join("");
}

async function reindexKnowledge() {
  const button = getElement("reindexButton");
  setButtonLoading(button, true, "Переиндексируем...", "Переиндексировать базу");
  try {
    const data = await requestJson("/knowledge/reindex", { method: "POST" });
    console.log("RAG reindex response", data);
    const result = data.result || {};
    const itemsCount = result.items_count ?? 0;
    const chunksCount = result.total_chunks ?? 0;
    getElement("maintenanceOutput").textContent = `База переиндексирована. Материалов: ${itemsCount}, фрагментов: ${chunksCount}.`;
    await loadKnowledgeList(false);
    showToast("База знаний переиндексирована", "success");
  } catch (error) {
    console.error(error);
    showToast(cleanErrorMessage(error), "error");
  } finally {
    setButtonLoading(button, false, "", "Переиндексировать базу");
  }
}

async function copyClaimText() {
  if (!state.currentClaimText) {
    showToast("Сначала сформируйте или откройте претензию", "warning");
    return;
  }
  try {
    await navigator.clipboard.writeText(state.currentClaimText);
    showToast("Текст скопирован", "success");
  } catch (error) {
    console.error(error);
    showToast("Не удалось скопировать текст", "error");
  }
}

function resetClaimForm() {
  state.currentFileId = null;
  state.currentFileName = "";
  state.currentClaimText = "";
  state.currentDownloadUrl = null;
  state.lastResponse = null;

  getElement("contractFile").value = "";
  getElement("userRequest").value = "";
  getElement("violationDate").value = "";
  getElement("violationDescription").value = "";
  getElement("responseDeadline").value = "10";
  getElement("penaltyAmount").value = "";
  getElement("senderName").value = "";
  getElement("senderAddress").value = "";
  getElement("recipientName").value = "";
  getElement("recipientAddress").value = "";

  getElement("uploadStatus").className = "status-badge neutral";
  getElement("uploadStatus").textContent = "Ожидает файл";
  getElement("fileInfo").className = "file-summary empty";
  getElement("fileInfo").textContent = "Выберите файл в формате TXT, DOCX или PDF.";
  getElement("generateButton").disabled = true;
  getElement("generationStatus").textContent = "Претензия еще не сформирована.";
  getElement("resultActions").classList.add("hidden");
  getElement("claimResult").className = "document-card empty";
  getElement("claimResult").textContent = "После генерации здесь появится готовый текст претензии.";
  getElement("lawArticlesOutput").className = "legal-basis empty";
  getElement("lawArticlesOutput").textContent = "";
  getElement("warningsOutput").innerHTML = "";

  updateSteps();
  showToast("Форма очищена", "success");
}

document.addEventListener("DOMContentLoaded", () => {
  getElement("userRequest").addEventListener("input", updateSteps);
  loadHistory(false);
  loadKnowledgeList(false);
  updateSteps();
});
