const API_BASE = "http://127.0.0.1:8000";

const state = {
  currentFileId: null,
  currentClaimText: "",
  currentDownloadUrl: null,
};

function getElement(id) {
  return document.getElementById(id);
}

function setLoading(buttonId, isLoading, loadingText = "Выполняется...") {
  const button = getElement(buttonId);

  if (!button) {
    return;
  }

  if (isLoading) {
    button.dataset.defaultText = button.textContent;
    button.textContent = loadingText;
    button.disabled = true;
    return;
  }

  button.textContent = button.dataset.defaultText || button.textContent;
  button.disabled = false;
}

function showMessage(type, title, text) {
  const box = getElement("messageBox");
  const globalStatus = getElement("globalStatus");

  box.className = `message-box ${type}`;
  box.innerHTML = `<strong>${title}</strong><span>${text}</span>`;

  globalStatus.className = `status-pill ${type}`;
  globalStatus.textContent = title;
}

function setInlineStatus(id, text, type = "muted") {
  const element = getElement(id);
  element.className = type === "muted" ? "inline-status" : `inline-status ${type}`;
  element.textContent = text;
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
    throw new Error("Backend недоступен. Проверьте, что FastAPI запущен на http://127.0.0.1:8000");
  }

  const data = await parseResponse(response);

  if (!response.ok) {
    throw new Error(data.detail || `Ошибка backend: ${response.status}`);
  }

  return data;
}

function updateFileInfo(data) {
  state.currentFileId = data.file_id;

  getElement("fileInfo").classList.remove("empty");
  getElement("fileInfo").innerHTML = `
    <div>
      <span class="muted-text">Текущий file_id</span>
      <code>${data.file_id}</code>
    </div>
    <button type="button" class="ghost small" id="copyFileIdButton" onclick="copyFileId()">Скопировать file_id</button>
  `;
}

async function uploadDocument() {
  const fileInput = getElement("contractFile");

  if (!fileInput.files.length) {
    showMessage("warning", "Файл не выбран", "Выберите договор в формате TXT, DOCX или PDF.");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  setLoading("uploadButton", true, "Загружается...");
  getElement("uploadStatus").textContent = "Идёт загрузка и извлечение текста";

  try {
    const data = await requestJson("/documents/upload", {
      method: "POST",
      body: formData,
    });

    updateFileInfo(data);
    getElement("uploadStatus").textContent = "Договор загружен";
    showMessage("success", "Договор загружен", `Текст извлечён, file_id: ${data.file_id}`);
  } catch (error) {
    console.error(error);
    getElement("uploadStatus").textContent = "Ошибка загрузки";
    showMessage("error", "Ошибка загрузки", error.message);
  } finally {
    setLoading("uploadButton", false);
  }
}

function buildManualFields() {
  return {
    violation_date: getElement("violationDate").value,
    violation_description: getElement("violationDescription").value,
    response_deadline: getElement("responseDeadline").value,
    penalty_amount: getElement("penaltyAmount").value,
    sender_name: getElement("senderName").value,
    sender_address: getElement("senderAddress").value,
    recipient_name: getElement("recipientName").value,
    recipient_address: getElement("recipientAddress").value,
  };
}

function renderLawArticles(items = []) {
  const container = getElement("lawArticlesOutput");

  if (!items.length) {
    container.className = "law-list empty";
    container.textContent = "Правовые основания не найдены.";
    return;
  }

  container.className = "law-list";
  container.innerHTML = items.map((item) => {
    const title = item.article
      ? `${item.article} — ${item.title || "без названия"}`
      : item.title || "Источник без названия";
    const source = item.source ? `<span class="status-pill muted">${item.source}</span>` : "";
    const mandatory = item.mandatory ? `<span class="status-pill info">обязательная статья</span>` : "";
    const sourceUrl = item.source_url
      ? `<a href="${item.source_url}" target="_blank" rel="noreferrer">Открыть источник</a>`
      : "";

    return `
      <article class="law-item">
        <p><strong>${title}</strong></p>
        <div class="meta-row">${source}${mandatory}</div>
        <p>${(item.text || "").slice(0, 700)}</p>
        ${sourceUrl}
      </article>
    `;
  }).join("");
}

function renderWarnings(data) {
  const warnings = [];

  if (data.web_fallback_used) {
    warnings.push({
      type: "info",
      title: "Использовался поиск в интернете",
      text: "Система дополнительно проверила официальные источники из настроек web fallback.",
    });
  }

  if (data.llm_error) {
    warnings.push({ type: "warning", title: "LLM недоступна", text: data.llm_error });
  }

  if (data.web_error) {
    warnings.push({ type: "warning", title: "Web fallback", text: data.web_error });
  }

  if (data.vector_error) {
    warnings.push({ type: "warning", title: "ChromaDB", text: data.vector_error });
  }

  getElement("warningsOutput").innerHTML = warnings.map((item) => `
    <div class="message-item ${item.type}">
      <p><strong>${item.title}</strong></p>
      <p>${item.text}</p>
    </div>
  `).join("");
}

function renderGenerationResult(data) {
  state.currentClaimText = data.claim_text || "";
  state.currentDownloadUrl = data.download_url || null;

  getElement("claimResult").textContent = state.currentClaimText || "Backend не вернул текст претензии.";
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

  const metaItems = [
    `<span class="status-pill success">Претензия сформирована</span>`,
    `<span class="status-pill muted">ID: ${data.claim_request_id}</span>`,
  ];

  if (data.use_llm) {
    metaItems.push(`<span class="status-pill info">LLM включена</span>`);
  }

  getElement("resultMeta").innerHTML = metaItems.join("");
  renderLawArticles(data.law_articles || []);
  renderWarnings(data);
}

async function generateClaim() {
  if (!state.currentFileId) {
    showMessage("warning", "Нет договора", "Сначала загрузите договор и получите file_id.");
    return;
  }

  const payload = {
    file_id: state.currentFileId,
    user_request: getElement("userRequest").value,
    use_llm: getElement("useLlm").checked,
    manual_fields: buildManualFields(),
  };

  setLoading("generateButton", true, "Генерируется...");
  setInlineStatus("generationStatus", "Анализ договора, поиск правовых оснований и подготовка DOCX...");

  try {
    const data = await requestJson("/claims/generate-delay-claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    renderGenerationResult(data);
    setInlineStatus("generationStatus", "Претензия сформирована", "success");
    showMessage("success", "Готово", "Претензия сформирована, DOCX доступен для скачивания.");
    await loadHistory(false);
  } catch (error) {
    console.error(error);
    setInlineStatus("generationStatus", "Ошибка генерации", "error");
    showMessage("error", "Ошибка генерации", error.message);
  } finally {
    setLoading("generateButton", false);
  }
}

async function loadHistory(showSuccess = true) {
  setLoading("loadHistoryButton", true, "Обновляется...");

  try {
    const data = await requestJson("/claims/history");
    const container = getElement("historyOutput");

    if (!data.items.length) {
      container.className = "history-list empty";
      container.textContent = "История претензий пуста.";
      if (showSuccess) {
        showMessage("info", "История пуста", "Сгенерированные претензии пока отсутствуют.");
      }
      return;
    }

    container.className = "history-list";
    container.innerHTML = data.items.map((item) => {
      const download = item.download_url
        ? `<a class="button secondary" href="${API_BASE}${item.download_url}" target="_blank" rel="noreferrer">Скачать DOCX</a>`
        : "";

      return `
        <article class="history-card">
          <header>
            <div>
              <p><strong>Запись #${item.id}</strong></p>
              <p class="muted-text">${item.created_at || "дата не указана"}</p>
            </div>
            <div class="history-actions">
              <button type="button" class="secondary" onclick="openClaim(${item.id})">Показать текст</button>
              ${download}
            </div>
          </header>
          <p><strong>file_id:</strong> <code>${item.file_id}</code></p>
          <p><strong>Запрос:</strong> ${item.user_request || ""}</p>
          <div class="history-preview">${item.preview || "Нет preview"}</div>
        </article>
      `;
    }).join("");

    if (showSuccess) {
      showMessage("success", "История обновлена", `Найдено записей: ${data.count}`);
    }
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка истории", error.message);
  } finally {
    setLoading("loadHistoryButton", false);
  }
}

async function openClaim(id) {
  try {
    const data = await requestJson(`/claims/${id}`);
    state.currentClaimText = data.result_text || "";
    state.currentDownloadUrl = data.download_url || null;
    getElement("claimResult").textContent = state.currentClaimText || "Текст претензии пуст.";
    getElement("copyClaimButton").disabled = !state.currentClaimText;
    getElement("resultMeta").innerHTML = `
      <span class="status-pill info">Открыта запись #${data.id}</span>
      <span class="status-pill muted">file_id: ${data.file_id}</span>
    `;
    showMessage("info", "Запись открыта", `Показан полный текст претензии #${id}.`);
  } catch (error) {
    console.error(error);
    showMessage("error", "Не удалось открыть запись", error.message);
  }
}

async function clearHistory() {
  const confirmed = window.confirm(
    "Вы уверены, что хотите очистить историю претензий? DOCX-файлы также будут удалены."
  );

  if (!confirmed) {
    return;
  }

  setLoading("clearHistoryButton", true, "Очищается...");

  try {
    const data = await requestJson("/claims/history", { method: "DELETE" });
    await loadHistory(false);
    showMessage(
      "success",
      "История очищена",
      `${data.message}. Удалено записей: ${data.deleted_count}, файлов: ${data.deleted_files_count}.`
    );
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка очистки", error.message);
  } finally {
    setLoading("clearHistoryButton", false);
  }
}

function renderKnowledgePreview(data) {
  const preview = data.text_preview
    ? `<p><strong>Preview:</strong></p><div class="history-preview">${data.text_preview}</div>`
    : "";
  getElement("maintenanceOutput").innerHTML = `
    <p><strong>${data.message || "Материал добавлен"}</strong></p>
    <p>Длина текста: ${data.text_length ?? "не указана"}</p>
    ${preview}
    <p class="muted-text">Рекомендуется выполнить переиндексацию RAG.</p>
  `;
}

async function addKnowledgeUrl() {
  const payload = {
    title: getElement("ragUrlTitle").value.trim(),
    source_type: getElement("ragUrlSourceType").value.trim(),
    source_url: getElement("ragSourceUrl").value.trim(),
  };

  if (!payload.title || !payload.source_type || !payload.source_url) {
    showMessage("warning", "Заполните поля", "Для добавления ссылки нужны название, тип источника и URL.");
    return;
  }

  setLoading("addRagUrlButton", true, "Добавляется...");

  try {
    const data = await requestJson("/knowledge/add-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    renderKnowledgePreview(data);
    await loadKnowledgeList(false);
    showMessage("success", "Ссылка добавлена в RAG", "Материал сохранён в базе знаний. Можно выполнить переиндексацию.");
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка добавления ссылки", error.message);
  } finally {
    setLoading("addRagUrlButton", false);
  }
}

async function uploadKnowledgeFile() {
  const fileInput = getElement("ragFile");
  const title = getElement("ragFileTitle").value.trim();
  const sourceType = getElement("ragFileSourceType").value.trim();

  if (!title || !sourceType || !fileInput.files.length) {
    showMessage("warning", "Заполните поля", "Для загрузки нужны название, тип источника и файл TXT, DOCX или PDF.");
    return;
  }

  const formData = new FormData();
  formData.append("title", title);
  formData.append("source_type", sourceType);
  formData.append("file", fileInput.files[0]);

  setLoading("uploadRagFileButton", true, "Загружается...");

  try {
    const data = await requestJson("/knowledge/upload-file", {
      method: "POST",
      body: formData,
    });

    renderKnowledgePreview(data);
    await loadKnowledgeList(false);
    showMessage("success", "Документ добавлен в RAG", "Материал сохранён в базе знаний. Можно выполнить переиндексацию.");
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка загрузки RAG-документа", error.message);
  } finally {
    setLoading("uploadRagFileButton", false);
  }
}

async function loadKnowledgeList(showSuccess = true) {
  setLoading("loadKnowledgeButton", true, "Обновляется...");

  try {
    const data = await requestJson("/knowledge/list");
    const container = getElement("knowledgeListOutput");

    if (!data.items.length) {
      container.className = "knowledge-list empty";
      container.textContent = "База знаний RAG пока пуста.";
      if (showSuccess) {
        showMessage("info", "RAG пуст", "Материалы базы знаний пока отсутствуют.");
      }
      return;
    }

    container.className = "knowledge-list";
    container.innerHTML = `
      <p><strong>Материалов: ${data.count}</strong></p>
      ${data.items.map((item) => {
        const content = item.content || "";
        const url = item.source_url
          ? `<p><strong>URL:</strong> <a href="${item.source_url}" target="_blank" rel="noreferrer">${item.source_url}</a></p>`
          : "";

        return `
          <article class="knowledge-card">
            <p><strong>${item.title || "Без названия"}</strong></p>
            <p><strong>Тип:</strong> ${item.source_type || "не указан"}</p>
            ${url}
            <p><strong>Длина content:</strong> ${content.length}</p>
            <p><strong>Vector chunks:</strong> ${item.vector_chunks_count ?? "не индексировалось"}</p>
            <div class="history-preview">${content.slice(0, 600) || "Preview отсутствует"}</div>
          </article>
        `;
      }).join("")}
    `;

    if (showSuccess) {
      showMessage("success", "Список RAG обновлён", `Материалов: ${data.count}`);
    }
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка списка RAG", error.message);
  } finally {
    setLoading("loadKnowledgeButton", false);
  }
}

async function reindexKnowledge() {
  setLoading("reindexButton", true, "Переиндексация...");

  try {
    const data = await requestJson("/knowledge/reindex", { method: "POST" });
    const result = data.result || {};

    getElement("maintenanceOutput").innerHTML = `
      <p><strong>${data.message || "Переиндексация завершена"}</strong></p>
      <p>Материалов: ${result.items_count ?? 0}</p>
      <p>Chunks: ${result.total_chunks ?? 0}</p>
      ${result.vector_error ? `<p class="error">ChromaDB: ${result.vector_error}</p>` : ""}
    `;
    await loadKnowledgeList(false);
    showMessage("success", "RAG переиндексирован", `Материалов: ${result.items_count ?? 0}, chunks: ${result.total_chunks ?? 0}.`);
  } catch (error) {
    console.error(error);
    showMessage("error", "Ошибка переиндексации", error.message);
  } finally {
    setLoading("reindexButton", false);
  }
}

async function copyClaimText() {
  if (!state.currentClaimText) {
    showMessage("warning", "Нет текста", "Сначала сформируйте или откройте претензию.");
    return;
  }

  await navigator.clipboard.writeText(state.currentClaimText);
  showMessage("success", "Текст скопирован", "Текст претензии помещён в буфер обмена.");
}

async function copyFileId() {
  if (!state.currentFileId) {
    showMessage("warning", "Нет file_id", "Сначала загрузите договор.");
    return;
  }

  await navigator.clipboard.writeText(state.currentFileId);
  showMessage("success", "file_id скопирован", state.currentFileId);
}

function resetForm() {
  getElement("userRequest").value = "Составь претензию по просрочке оказания услуг с ссылками на законодательство";
  getElement("violationDate").value = "";
  getElement("violationDescription").value = "";
  getElement("responseDeadline").value = "10";
  getElement("penaltyAmount").value = "";
  getElement("senderName").value = "";
  getElement("senderAddress").value = "";
  getElement("recipientName").value = "";
  getElement("recipientAddress").value = "";
  getElement("useLlm").checked = true;
  showMessage("info", "Форма очищена", "Поля параметров претензии сброшены. Загруженный file_id сохранён.");
}

document.addEventListener("DOMContentLoaded", () => {
  loadHistory(false);
  loadKnowledgeList(false);
});
