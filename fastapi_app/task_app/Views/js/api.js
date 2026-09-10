/**
 * FastAPI との通信だけを担当するファイル。
 *
 * 画面の DOM 操作は app.js に置き、ここでは次の3点に集中します。
 * 1. URL / query parameter を組み立てる
 * 2. JSON を送受信する
 * 3. HTTP エラーを JavaScript の Error に変換する
 */

// 課題仕様の FastAPI 起動先。ポートを変えた場合はここだけ変更します。
export const API_BASE_URL = "http://localhost:8888";

/** API が返した status と detail を保持するエラー。 */
export class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * FastAPI / Pydantic の detail を画面で読める1つの文へ変換する。
 * 422 の detail は配列、404 などの detail は文字列になることがあります。
 */
function formatDetail(detail) {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "入力";
        return `${location || "入力"}: ${item.msg ?? "値を確認してください"}`;
      })
      .join(" / ");
  }

  return "API リクエストに失敗しました。";
}

/**
 * すべての API 呼び出しが利用する共通関数。
 * DELETE /tasks/{id} の成功は 204 No Content なので、JSON 解析を行いません。
 */
async function request(path, options = {}) {
  const hasBody = options.body !== undefined;
  const headers = {
    Accept: "application/json",
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    // サーバー停止、URL間違い、CORS ブロックなど、HTTP 応答前の失敗。
    throw new ApiError(
      `API に接続できません。FastAPI が ${API_BASE_URL} で起動しているか確認してください。`,
      0,
      error,
    );
  }

  if (!response.ok) {
    let detail = null;
    const errorText = await response.text();
    try {
      const errorBody = JSON.parse(errorText);
      detail = errorBody.detail ?? errorBody;
    } catch {
      detail = errorText || null;
    }

    throw new ApiError(formatDetail(detail), response.status, detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

/**
 * GET /tasks を呼ぶ。
 * status を API の is_done=true/false に変換し、category_id と組み合わせます。
 */
export function getTasks({ status = "all", categoryId = null } = {}) {
  const query = new URLSearchParams();

  if (status === "open") {
    query.set("is_done", "false");
  } else if (status === "done") {
    query.set("is_done", "true");
  }

  // 0 や空文字を送らず、選択済みの数値 ID だけを query に追加します。
  if (categoryId !== null && categoryId !== "") {
    query.set("category_id", String(categoryId));
  }

  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return request(`/tasks${suffix}`);
}

/** GET /tasks/{task_id}: 編集直前に最新の1件を取得する。 */
export function getTask(taskId) {
  return request(`/tasks/${taskId}`);
}

/**
 * POST /tasks: 新規タスクを作る。
 * payload は title / description / category_id / assignee_id の4項目です。
 */
export function createTask(payload) {
  return request("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * PUT /tasks/{task_id}: タスク全体を更新する。
 * payload は title / description / is_done / category_id / assignee_id の5項目です。
 */
export function updateTask(taskId, payload) {
  return request(`/tasks/${taskId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/** DELETE /tasks/{task_id}: 成功時は 204 で本文なし。 */
export function deleteTask(taskId) {
  return request(`/tasks/${taskId}`, { method: "DELETE" });
}

/** GET /categories: 新規・編集・絞り込みの選択肢に使う。 */
export function getCategories() {
  return request("/categories");
}

/** POST /categories: カテゴリ専用モーダルから {name} を送る。 */
export function createCategory(payload) {
  return request("/categories", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET /assignees: 新規・編集の選択肢に使う。 */
export function getAssignees() {
  return request("/assignees");
}

/** POST /assignees: 担当者専用モーダルから {name} を送る。 */
export function createAssignee(payload) {
  return request("/assignees", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
