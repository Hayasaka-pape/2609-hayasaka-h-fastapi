/**
 * 画面の状態管理・イベント・DOM 更新を担当するファイル。
 *
 * SPA なので location.reload() は使いません。
 * 操作ごとに api.js の関数で FastAPI と JSON をやり取りし、
 * 返ってきたデータを state に保存して必要な部分だけ再描画します。
 */

import {
  createAssignee,
  createCategory,
  createTask,
  deleteTask,
  getAssignees,
  getCategories,
  getTask,
  getTasks,
  updateTask,
} from "./api.js";

// API レスポンスと現在の画面条件を、1か所で管理します。
const state = {
  tasks: [],
  categories: [],
  assignees: [],
  filters: {
    status: "all",
    categoryId: null,
  },
  editingTaskId: null,
  tasksLoaded: false,
  categoryTargetSelectId: null,
  assigneeTargetSelectId: null,
};

// HTML の要素を最初に集め、以降は ID の文字列を何度も書かずに利用します。
const elements = {
  createForm: document.querySelector("#task-create-form"),
  createTitle: document.querySelector("#task-title"),
  createDescription: document.querySelector("#task-description"),
  createCategory: document.querySelector("#task-category"),
  createAssignee: document.querySelector("#task-assignee"),
  createTaskButton: document.querySelector("#create-task-button"),

  statusTabs: [...document.querySelectorAll("[data-status]")],
  filterCategory: document.querySelector("#filter-category"),
  refreshTasks: document.querySelector("#refresh-tasks"),
  feedback: document.querySelector("#feedback"),
  taskCount: document.querySelector("#task-count"),
  activeFilterLabel: document.querySelector("#active-filter-label"),
  loadingState: document.querySelector("#loading-state"),
  taskList: document.querySelector("#task-list"),
  emptyState: document.querySelector("#empty-state"),

  editDialog: document.querySelector("#edit-task-dialog"),
  editForm: document.querySelector("#task-edit-form"),
  editTitle: document.querySelector("#edit-title"),
  editDescription: document.querySelector("#edit-description"),
  editCategory: document.querySelector("#edit-category"),
  editAssignee: document.querySelector("#edit-assignee"),
  editIsDone: document.querySelector("#edit-is-done"),
  saveTaskButton: document.querySelector("#save-task-button"),

  categoryDialog: document.querySelector("#category-dialog"),
  categoryForm: document.querySelector("#category-form"),
  categoryName: document.querySelector("#category-name"),
  createCategoryButton: document.querySelector("#create-category-button"),

  assigneeDialog: document.querySelector("#assignee-dialog"),
  assigneeForm: document.querySelector("#assignee-form"),
  assigneeName: document.querySelector("#assignee-name"),
  createAssigneeButton: document.querySelector("#create-assignee-button"),
};

let feedbackTimer = null;
let latestTaskRequest = 0;

/** 初期表示: 3つの GET を並行実行し、選択肢と一覧を一度に準備します。 */
async function initialize() {
  bindEvents();
  await refreshData();
}

/** 接続失敗から再試行できるよう、再読み込みでは選択肢も取り直します。 */
async function refreshData({ announce = false } = {}) {
  const [categories, assignees, tasks] = await Promise.allSettled([
    getCategories(),
    getAssignees(),
    loadTasks(),
  ]);

  if (categories.status === "fulfilled") {
    state.categories = categories.value;
    renderCategorySelects();
  }
  if (assignees.status === "fulfilled") {
    state.assignees = assignees.value;
    renderAssigneeSelects();
  }
  elements.activeFilterLabel.textContent = buildFilterLabel();

  const failed = [categories, assignees, tasks].find((result) => result.status === "rejected");
  if (failed) {
    showFeedback(failed.reason.message, "error");
  } else if (tasks.value) {
    if (announce) {
      showFeedback("タスク一覧と選択肢を更新しました。", "success");
    }
  }
}

/** イベントは初回に一度だけ登録します。再描画時には増やしません。 */
function bindEvents() {
  elements.createForm.addEventListener("submit", handleCreateTask);
  elements.editForm.addEventListener("submit", handleUpdateTask);
  elements.categoryForm.addEventListener("submit", handleCreateCategory);
  elements.assigneeForm.addEventListener("submit", handleCreateAssignee);

  elements.statusTabs.forEach((tab) => {
    tab.addEventListener("click", () => changeStatusFilter(tab.dataset.status));
  });

  elements.filterCategory.addEventListener("change", () => {
    // select.value は文字列なので、FastAPI に送る ID は Number へ変換します。
    state.filters.categoryId = toNullableId(elements.filterCategory.value);
    loadTasks();
  });

  elements.refreshTasks.addEventListener("click", () => refreshData({ announce: true }));

  document.querySelectorAll("input[required]").forEach((input) => {
    input.addEventListener("input", () => input.setCustomValidity(""));
  });

  // 一覧のカードは毎回作り直すため、親要素でイベントを受ける方式にします。
  elements.taskList.addEventListener("click", handleTaskListClick);
  elements.taskList.addEventListener("change", handleTaskListChange);

  document.querySelectorAll("[data-open-category-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      state.categoryTargetSelectId = button.dataset.targetSelect;
      openDialog(elements.categoryDialog, elements.categoryName);
    });
  });

  document.querySelectorAll("[data-open-assignee-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      state.assigneeTargetSelectId = button.dataset.targetSelect;
      openDialog(elements.assigneeDialog, elements.assigneeName);
    });
  });

  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      const dialog = document.querySelector(`#${button.dataset.closeDialog}`);
      closeDialog(dialog);
    });
  });

  // ダイアログ外側（背景）を押した場合も閉じられるようにします。
  [elements.editDialog, elements.categoryDialog, elements.assigneeDialog].forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        closeDialog(dialog);
      }
    });
    dialog.addEventListener("cancel", (event) => {
      if (dialog.querySelector('form[aria-busy="true"]')) {
        event.preventDefault();
      }
    });
  });

  elements.editDialog.addEventListener("close", () => {
    state.editingTaskId = null;
    elements.editForm.reset();
  });

  elements.categoryDialog.addEventListener("close", () => {
    elements.categoryForm.reset();
    state.categoryTargetSelectId = null;
  });

  elements.assigneeDialog.addEventListener("close", () => {
    elements.assigneeForm.reset();
    state.assigneeTargetSelectId = null;
  });
}

/**
 * POST /tasks 用データを作る。
 * 未入力の description / category_id / assignee_id は空文字でなく null にします。
 */
function buildCreatePayload() {
  return {
    title: elements.createTitle.value.trim(),
    description: toNullableText(elements.createDescription.value),
    category_id: toNullableId(elements.createCategory.value),
    assignee_id: toNullableId(elements.createAssignee.value),
  };
}

async function handleCreateTask(event) {
  event.preventDefault();
  const payload = buildCreatePayload();

  if (!validateRequiredText(payload.title, elements.createTitle, "タイトルを入力してください。")) {
    return;
  }

  setFormBusy(elements.createForm, true);
  try {
    // FastAPI の POST /tasks は 201 と、作成後の Task オブジェクトを返します。
    await createTask(payload);
    elements.createForm.reset();
    await loadTasks({ successMessage: "タスクを追加しました。" });
    window.requestAnimationFrame(() => elements.createTitle.focus());
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setFormBusy(elements.createForm, false);
  }
}

/**
 * 現在の絞り込みを query に変換して GET /tasks を再実行します。
 * リクエスト番号により、素早く条件を変えたとき古い応答で画面が戻るのを防ぎます。
 */
async function loadTasks({ successMessage = null } = {}) {
  const requestNumber = ++latestTaskRequest;
  setTaskListLoading(true);

  try {
    const tasks = await getTasks(state.filters);
    if (requestNumber !== latestTaskRequest) {
      return false;
    }

    state.tasks = tasks;
    state.tasksLoaded = true;
    renderTasks();

    if (successMessage) {
      showFeedback(successMessage, "success");
    }
    return true;
  } catch (error) {
    if (requestNumber === latestTaskRequest) {
      state.tasks = [];
      state.tasksLoaded = false;
      renderTasks();
      const prefix = successMessage ? "変更は保存されましたが、一覧を再取得できませんでした。" : "";
      showFeedback(`${prefix}${error.message}`, "error");
    }
    return false;
  } finally {
    if (requestNumber === latestTaskRequest) {
      setTaskListLoading(false);
    }
  }
}

function changeStatusFilter(status) {
  state.filters.status = status;

  elements.statusTabs.forEach((tab) => {
    const selected = tab.dataset.status === status;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-pressed", String(selected));
  });

  loadTasks();
}

/** GET /tasks の配列を、ユーザー入力を innerHTML に入れず安全にカードへ変換します。 */
function renderTasks() {
  elements.taskList.replaceChildren();
  elements.taskCount.textContent = state.tasksLoaded
    ? `${state.tasks.length} 件を表示`
    : "一覧を取得できませんでした";
  elements.activeFilterLabel.textContent = buildFilterLabel();

  if (!state.tasksLoaded) {
    elements.emptyState.hidden = true;
    return;
  }

  elements.emptyState.hidden = state.tasks.length !== 0;
  state.tasks.forEach((task) => elements.taskList.append(createTaskCard(task)));
}

function createTaskCard(task) {
  const item = document.createElement("li");
  item.className = "task-card";
  item.dataset.taskId = String(task.id);
  item.classList.toggle("is-done", task.is_done);

  const checkLabel = document.createElement("label");
  checkLabel.className = "task-check";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = task.is_done;
  checkbox.dataset.action = "toggle";
  checkbox.dataset.taskId = String(task.id);
  checkbox.setAttribute(
    "aria-label",
    `${task.title}を${task.is_done ? "未完了" : "完了"}にする`,
  );
  checkLabel.append(checkbox);

  const content = document.createElement("div");
  content.className = "task-card__content";

  const titleRow = document.createElement("div");
  titleRow.className = "task-card__title-row";

  const title = document.createElement("h3");
  title.className = "task-card__title";
  title.textContent = task.title;

  const status = document.createElement("span");
  status.className = `status-pill ${task.is_done ? "status-pill--done" : "status-pill--open"}`;
  status.textContent = task.is_done ? "完了" : "未完了";
  titleRow.append(title, status);

  const description = document.createElement("p");
  description.className = "task-card__description";
  description.textContent = task.description || "説明はありません";
  description.classList.toggle("is-placeholder", !task.description);

  const meta = document.createElement("div");
  meta.className = "task-card__meta";
  meta.append(
    createTag(task.category?.name ?? "カテゴリ未設定", "category", !task.category),
    createTag(task.assignee?.name ?? "担当者未設定", "assignee", !task.assignee),
  );

  if (task.updated_at) {
    const updated = document.createElement("time");
    updated.className = "task-card__updated";
    updated.dateTime = task.updated_at;
    updated.textContent = `更新 ${formatDateTime(task.updated_at)}`;
    meta.append(updated);
  }

  content.append(titleRow, description, meta);

  const actions = document.createElement("div");
  actions.className = "task-card__actions";
  actions.append(
    createActionButton("編集", "edit", task, "button--secondary"),
    createActionButton("削除", "delete", task, "button--danger"),
  );

  item.append(checkLabel, content, actions);
  return item;
}

function createTag(label, kind, isEmpty) {
  const tag = document.createElement("span");
  tag.className = `tag tag--${kind}`;
  tag.classList.toggle("tag--empty", isEmpty);
  tag.textContent = label;
  return tag;
}

function createActionButton(label, action, task, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `button button--small ${className}`;
  button.dataset.action = action;
  button.dataset.taskId = String(task.id);
  button.textContent = label;
  button.setAttribute("aria-label", `${task.title}を${label}`);
  return button;
}

function handleTaskListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const taskId = Number(button.dataset.taskId);
  if (button.dataset.action === "edit") {
    openEditDialog(taskId);
  } else if (button.dataset.action === "delete") {
    handleDeleteTask(taskId);
  }
}

function handleTaskListChange(event) {
  const checkbox = event.target.closest('input[data-action="toggle"]');
  if (!checkbox) {
    return;
  }

  handleToggleTask(Number(checkbox.dataset.taskId), checkbox.checked);
}

/**
 * チェック変更も PUT なので is_done だけは送りません。
 * GET の category / assignee オブジェクトから ID を取り出し、全5項目を送ります。
 */
async function handleToggleTask(taskId, nextDoneValue) {
  const task = state.tasks.find((candidate) => candidate.id === taskId);
  if (!task) {
    return;
  }

  setTaskCardBusy(taskId, true);
  try {
    await updateTask(taskId, taskToUpdatePayload(task, nextDoneValue));
    await loadTasks({
      successMessage: nextDoneValue ? "タスクを完了にしました。" : "タスクを未完了に戻しました。",
    });
  } catch (error) {
    // API 更新に失敗した場合、state の元データから再描画してチェックを戻します。
    renderTasks();
    showFeedback(error.message, "error");
  } finally {
    setTaskCardBusy(taskId, false);
  }
}

function taskToUpdatePayload(task, isDone = task.is_done) {
  return {
    title: task.title,
    description: task.description,
    is_done: isDone,
    category_id: task.category?.id ?? null,
    assignee_id: task.assignee?.id ?? null,
  };
}

/** 編集ボタン: GET /tasks/{id} で最新値を取り、PUT 用フォームに設定します。 */
async function openEditDialog(taskId) {
  setTaskCardBusy(taskId, true);
  try {
    const [task, categories, assignees] = await Promise.all([
      getTask(taskId),
      getCategories(),
      getAssignees(),
    ]);
    state.categories = categories;
    state.assignees = assignees;
    state.editingTaskId = task.id;

    // 動的 option を用意してから ID を設定します。
    renderCategorySelects();
    renderAssigneeSelects();
    elements.editTitle.value = task.title;
    elements.editDescription.value = task.description ?? "";
    elements.editCategory.value = task.category ? String(task.category.id) : "";
    elements.editAssignee.value = task.assignee ? String(task.assignee.id) : "";
    elements.editIsDone.checked = task.is_done;

    openDialog(elements.editDialog, elements.editTitle);
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setTaskCardBusy(taskId, false);
  }
}

async function handleUpdateTask(event) {
  event.preventDefault();
  if (state.editingTaskId === null) {
    return;
  }

  const payload = {
    title: elements.editTitle.value.trim(),
    description: toNullableText(elements.editDescription.value),
    is_done: elements.editIsDone.checked,
    category_id: toNullableId(elements.editCategory.value),
    assignee_id: toNullableId(elements.editAssignee.value),
  };

  if (!validateRequiredText(payload.title, elements.editTitle, "タイトルを入力してください。")) {
    return;
  }

  const taskId = state.editingTaskId;
  setFormBusy(elements.editForm, true);
  try {
    // PUT /tasks/{id} は全項目更新。成功時は 200 と更新後の Task が返ります。
    await updateTask(taskId, payload);
    elements.editDialog.close();
    await loadTasks({ successMessage: "タスクを更新しました。" });
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setFormBusy(elements.editForm, false);
  }
}

async function handleDeleteTask(taskId) {
  const task = state.tasks.find((candidate) => candidate.id === taskId);
  if (!task) {
    return;
  }

  if (!window.confirm(`「${task.title}」を削除しますか？`)) {
    return;
  }

  setTaskCardBusy(taskId, true);
  try {
    // DELETE /tasks/{id} は成功時 204。api.js は本文を JSON 解析しません。
    await deleteTask(taskId);
    await loadTasks({ successMessage: "タスクを削除しました。" });
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setTaskCardBusy(taskId, false);
  }
}

/** カテゴリ用モーダルだけが POST /categories を呼びます。 */
async function handleCreateCategory(event) {
  event.preventDefault();
  const name = elements.categoryName.value.trim();
  if (!validateRequiredText(name, elements.categoryName, "カテゴリ名を入力してください。")) {
    return;
  }

  const targetSelectId = state.categoryTargetSelectId;
  setFormBusy(elements.categoryForm, true);
  try {
    const created = await createCategory({ name });
    state.categories = upsertAndSort(state.categories, created);
    renderCategorySelects(targetSelectId, created.id);
    elements.categoryDialog.close();
    showFeedback(`カテゴリ「${created.name}」を追加しました。`, "success");
    focusSelectLater(targetSelectId);
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setFormBusy(elements.categoryForm, false);
  }
}

/** 担当者用モーダルだけが POST /assignees を呼びます。 */
async function handleCreateAssignee(event) {
  event.preventDefault();
  const name = elements.assigneeName.value.trim();
  if (!validateRequiredText(name, elements.assigneeName, "担当者名を入力してください。")) {
    return;
  }

  const targetSelectId = state.assigneeTargetSelectId;
  setFormBusy(elements.assigneeForm, true);
  try {
    const created = await createAssignee({ name });
    state.assignees = upsertAndSort(state.assignees, created);
    renderAssigneeSelects(targetSelectId, created.id);
    elements.assigneeDialog.close();
    showFeedback(`担当者「${created.name}」を追加しました。`, "success");
    focusSelectLater(targetSelectId);
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setFormBusy(elements.assigneeForm, false);
  }
}

/**
 * Category は新規用・編集用・絞り込み用の3か所へ反映します。
 * 追加元の select には作成された ID を自動選択します。
 */
function renderCategorySelects(targetSelectId = null, createdId = null) {
  replaceSelectOptions(elements.createCategory, state.categories, "未設定");
  replaceSelectOptions(elements.editCategory, state.categories, "未設定");
  replaceSelectOptions(
    elements.filterCategory,
    state.categories,
    "すべてのカテゴリ",
    state.filters.categoryId,
  );

  selectCreatedOption(targetSelectId, createdId);
}

/** Assignee は新規用・編集用の2か所へ反映します。 */
function renderAssigneeSelects(targetSelectId = null, createdId = null) {
  replaceSelectOptions(elements.createAssignee, state.assignees, "未設定");
  replaceSelectOptions(elements.editAssignee, state.assignees, "未設定");
  selectCreatedOption(targetSelectId, createdId);
}

function replaceSelectOptions(select, items, placeholder, desiredValue = select.value) {
  const previousValue = desiredValue === null ? "" : String(desiredValue);
  const placeholderOption = new Option(placeholder, "");
  const options = items.map((item) => new Option(item.name, String(item.id)));
  select.replaceChildren(placeholderOption, ...options);

  const valueStillExists = [...select.options].some((option) => option.value === previousValue);
  select.value = valueStillExists ? previousValue : "";
}

function selectCreatedOption(targetSelectId, createdId) {
  if (!targetSelectId || createdId === null) {
    return;
  }

  const target = document.querySelector(`#${targetSelectId}`);
  if (target) {
    target.value = String(createdId);
  }
}

function upsertAndSort(items, created) {
  return [...items.filter((item) => item.id !== created.id), created].sort((a, b) => a.id - b.id);
}

function openDialog(dialog, initialFocus) {
  dialog.querySelector("[data-dialog-feedback]").hidden = true;
  if (!dialog.open) {
    dialog.showModal();
  }
  window.requestAnimationFrame(() => initialFocus?.focus());
}

function closeDialog(dialog) {
  if (dialog && !dialog.querySelector('form[aria-busy="true"]')) {
    dialog.close();
  }
}

function focusSelectLater(selectId) {
  if (!selectId) {
    return;
  }
  window.requestAnimationFrame(() => document.querySelector(`#${selectId}`)?.focus());
}

function toNullableId(value) {
  return value === "" || value === null ? null : Number(value);
}

function toNullableText(value) {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function validateRequiredText(value, input, message) {
  input.setCustomValidity(value ? "" : message);
  if (!value) {
    input.reportValidity();
    input.focus();
    return false;
  }
  return true;
}

function setFormBusy(form, busy) {
  form.setAttribute("aria-busy", String(busy));
  form.querySelectorAll("input, textarea, select, button").forEach((control) => {
    control.disabled = busy;
  });
  form.closest("dialog")?.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.disabled = busy;
  });
}

function setTaskListLoading(loading) {
  elements.loadingState.hidden = !loading;
  elements.refreshTasks.disabled = loading;
  elements.taskList.setAttribute("aria-busy", String(loading));
}

function setTaskCardBusy(taskId, busy) {
  const card = elements.taskList.querySelector(`[data-task-id="${taskId}"]`);
  if (!card) {
    return;
  }

  card.setAttribute("aria-busy", String(busy));
  card.querySelectorAll("input, button").forEach((control) => {
    control.disabled = busy;
  });
}

function buildFilterLabel() {
  const statusLabels = {
    all: "すべての状態",
    open: "未完了",
    done: "完了",
  };
  const category = state.categories.find((item) => item.id === state.filters.categoryId);
  return category
    ? `${statusLabels[state.filters.status]}・${category.name}`
    : statusLabels[state.filters.status];
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ja-JP", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function showFeedback(message, type = "success") {
  window.clearTimeout(feedbackTimer);
  // showModal 中は背面が操作・読み上げ対象外になるため、通知も開いているモーダルへ出します。
  const activeDialog = [...document.querySelectorAll("dialog[open]")].at(-1);
  const feedback = activeDialog?.querySelector("[data-dialog-feedback]") ?? elements.feedback;
  document.querySelectorAll(".feedback").forEach((item) => {
    item.hidden = item !== feedback;
  });
  feedback.textContent = message;
  feedback.classList.remove("feedback--success", "feedback--error");
  feedback.classList.add(`feedback--${type}`);
  feedback.hidden = false;

  // エラーは原因確認のため残し、成功通知だけを数秒後に閉じます。
  if (type !== "error") {
    feedbackTimer = window.setTimeout(() => {
      feedback.hidden = true;
    }, 5000);
  }
}

initialize();
