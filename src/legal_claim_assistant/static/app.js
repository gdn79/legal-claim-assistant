const input = document.querySelector("#documents");
const pickFiles = document.querySelector("#pickFiles");
const uploadZone = document.querySelector("#uploadZone");
const fileList = document.querySelector("#fileList");
const clearButton = document.querySelector("#clearButton");
const howButton = document.querySelector("#howButton");
const howDialog = document.querySelector("#howDialog");
const closeDialog = document.querySelector("#closeDialog");
const caseForm = document.querySelector("#caseForm");
const reviewForm = document.querySelector("#reviewForm");
const submitButton = document.querySelector("#submitButton");
const generateButton = document.querySelector("#generateButton");
const processingCard = document.querySelector("#processingCard");
const processingTitle = document.querySelector("#processingTitle");
const processingText = document.querySelector("#processingText");
const nextStep = document.querySelector("#nextStep");
const processSteps = document.querySelector("#processSteps");
const stepNodes = Array.from(document.querySelectorAll("[data-process-step]"));

const stepFallbackText = {
  1: "Файлы и вводные",
  2: "OCR и OpenAI",
  3: "Проверка карточки",
  4: "DOCX и контроль",
};

const stepTitles = {
  1: "Загрузка документов",
  2: "Анализ документов",
  3: "Проверка анализа",
  4: "Подготовка иска",
};

let pollTimer = null;

function setStepState(currentStep, state, message = "") {
  stepNodes.forEach((node) => {
    const step = Number(node.dataset.processStep);
    const small = node.querySelector("small");
    if (small && !small.dataset.defaultLabel) {
      small.dataset.defaultLabel = small.textContent;
    }

    node.classList.remove("active", "pending", "running", "complete", "error");

    if (state === "failed" && step === currentStep) {
      node.classList.add("active", "error");
      if (small) small.textContent = "Ошибка обработки";
      return;
    }

    if (state === "completed") {
      if (step <= currentStep) {
        node.classList.add("complete");
      } else {
        node.classList.add("pending");
      }
      if (step === currentStep) node.classList.add("active");
      if (small) small.textContent = step === currentStep ? "Готово" : small.dataset.defaultLabel;
      return;
    }

    if (step < currentStep) {
      node.classList.add("complete");
      if (small) small.textContent = "Готово";
      return;
    }

    if (step === currentStep) {
      node.classList.add("active", state === "running" ? "running" : "pending");
      if (small) small.textContent = message || stepFallbackText[step] || small.dataset.defaultLabel;
      return;
    }

    node.classList.add("pending");
    if (small) small.textContent = small.dataset.defaultLabel;
  });
}

function updateProcessingCard(step, state, message) {
  if (!processingCard) return;

  if (state === "idle") {
    processingCard.hidden = true;
    return;
  }

  processingCard.hidden = false;
  processingCard.classList.toggle("processing-card-error", state === "failed");
  processingCard.classList.toggle("processing-card-complete", state === "completed");

  if (processingTitle) {
    processingTitle.textContent = state === "failed" ? "Обработка остановлена" : stepTitles[step] || "Идет обработка";
  }
  if (processingText) {
    processingText.textContent = message || "Не закрывайте страницу. Сканированные PDF могут занять больше времени из-за OCR.";
  }
}

function setBusy(isBusy) {
  document.querySelectorAll(".inline-submit").forEach((button) => {
    button.disabled = isBusy;
    button.textContent = isBusy ? "Анализ запущен" : "Начать анализ";
  });
  if (submitButton) {
    submitButton.disabled = isBusy;
    submitButton.textContent = isBusy ? "Анализ запущен" : "Начать анализ";
  }
}

function setGenerateBusy(isBusy) {
  if (!generateButton) return;
  generateButton.disabled = isBusy;
  generateButton.textContent = isBusy ? "Формирую DOCX..." : "Подтвердить карточку и сформировать DOCX";
}

function stopPolling() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function renderFiles() {
  if (!fileList || !input) return;
  fileList.innerHTML = "";
  Array.from(input.files || []).forEach((file) => {
    const row = document.createElement("div");
    row.className = "file-item";
    const sizeMb = (file.size / 1024 / 1024).toFixed(2);
    const name = document.createElement("strong");
    const size = document.createElement("span");
    name.textContent = file.name;
    size.textContent = `${sizeMb} МБ`;
    row.append(name, size);
    fileList.appendChild(row);
  });
  if (nextStep) nextStep.hidden = !(input.files && input.files.length);
  setStepState(input.files && input.files.length ? 1 : 1, "idle", input.files && input.files.length ? "Файлы выбраны" : "");
}

pickFiles?.addEventListener("click", () => input?.click());
input?.addEventListener("change", renderFiles);

["dragenter", "dragover"].forEach((eventName) => {
  uploadZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  uploadZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadZone.classList.remove("dragover");
  });
});

uploadZone?.addEventListener("drop", (event) => {
  if (!input || !event.dataTransfer) return;
  input.files = event.dataTransfer.files;
  renderFiles();
});

clearButton?.addEventListener("click", () => {
  if (fileList) fileList.innerHTML = "";
  if (input) input.value = "";
  if (nextStep) nextStep.hidden = true;
  stopPolling();
  setBusy(false);
  updateProcessingCard(1, "idle", "");
  setStepState(1, "idle");
});

async function pollJob(statusUrl) {
  try {
    const response = await fetch(statusUrl, { headers: { Accept: "application/json" } });
    const status = await response.json();
    if (!response.ok) {
      throw new Error(status.error || "Не удалось получить статус обработки");
    }

    const step = Number(status.step || 1);
    const state = String(status.state || "running");
    const message = String(status.message || "");
    setStepState(step, state, message);
    updateProcessingCard(step, state, message);

    if (state === "completed") {
      window.location.href = status.result_url || "/bot";
      return;
    }

    if (state === "failed") {
      setBusy(false);
      setGenerateBusy(false);
      return;
    }

    pollTimer = window.setTimeout(() => pollJob(statusUrl), 1200);
  } catch (error) {
    setStepState(2, "failed", "Ошибка статуса");
    updateProcessingCard(2, "failed", error.message || "Не удалось получить статус обработки");
    setBusy(false);
    setGenerateBusy(false);
  }
}

caseForm?.addEventListener("submit", async (event) => {
  if (!window.fetch || !window.FormData) return;
  event.preventDefault();
  stopPolling();
  setBusy(true);
  setStepState(1, "running", "Загружаю файлы");
  updateProcessingCard(1, "running", "Загружаю файлы и создаю задачу обработки.");

  try {
    const response = await fetch("/cases/jobs", {
      method: "POST",
      body: new FormData(caseForm),
      headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Не удалось запустить обработку");
    }
    setStepState(1, "running", "Задача создана");
    updateProcessingCard(1, "running", "Задача создана. Жду первый статус обработки.");
    pollJob(payload.status_url);
  } catch (error) {
    setStepState(1, "failed", "Ошибка запуска");
    updateProcessingCard(1, "failed", error.message || "Не удалось запустить обработку");
    setBusy(false);
  }
});

reviewForm?.addEventListener("submit", async (event) => {
  if (!window.fetch || !window.FormData || !reviewForm.dataset.generateJobAction) return;
  event.preventDefault();
  stopPolling();
  setGenerateBusy(true);
  setStepState(4, "running", "Формирую DOCX");
  updateProcessingCard(4, "running", "Данные подтверждены. Отправляю запрос ИИ и собираю DOCX.");

  try {
    const response = await fetch(reviewForm.dataset.generateJobAction, {
      method: "POST",
      body: new FormData(reviewForm),
      headers: { Accept: "application/json" },
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Не удалось запустить генерацию DOCX");
    }
    updateProcessingCard(4, "running", "Генерация запущена. Дождитесь готового DOCX.");
    pollJob(payload.status_url);
  } catch (error) {
    setStepState(4, "failed", "Ошибка генерации");
    updateProcessingCard(4, "failed", error.message || "Не удалось запустить генерацию DOCX");
    setGenerateBusy(false);
  }
});

if (processSteps) {
  const initialStep = Number(processSteps.dataset.initialStep || 1);
  const initialState = processSteps.dataset.initialState || "idle";
  setStepState(initialStep, initialState);
}

howButton?.addEventListener("click", () => howDialog?.showModal());
closeDialog?.addEventListener("click", () => howDialog?.close());
