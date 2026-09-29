/**
 * Dịch vụ task chạy nền - poll tiến trình task, thay thế SSE
 */

const API_BASE = '/api/tasks';

export interface TaskStatus {
  id: string;
  task_type: string;
  project_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  status_message: string | null;
  progress_details: {
    stage?: string;
    message?: string;
    current_chars?: number;
    retry_count?: number;
    queue_size?: number;
    chapter_id?: string;
    chapter_number?: number | null;
    chapter_title?: string | null;
    completed?: number;
    total?: number;
    current_chapter_number?: number | null;
  } | null;
  error_message: string | null;
  task_result: Record<string, unknown> | null;
  retry_count: number;
  cancel_requested: boolean;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
  archived_at?: string | null;
  affected_resources: string[];
  can_cancel: boolean;
  can_delete: boolean;
}

export interface TaskListResponse {
  items: TaskStatus[];
}

/**
 * Trạng thái task tạo hàng loạt
 */
export interface BatchTaskStatus {
  batch_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  total: number;
  completed: number;
  current_chapter_id: string | null;
  current_chapter_number: number | null;
  created_at: string | null;
  started_at: string | null;
}

interface ActiveBatchTaskResponse {
  has_active_task: boolean;
  task: BatchTaskStatus | null;
}

/**
 * Truy vấn trạng thái task
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await fetch(`${API_BASE}/${taskId}`);
  if (!response.ok) {
    throw new Error(`Truy vấn trạng thái task thất bại: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Lấy danh sách task của dự án
 */
export async function getProjectTasks(
  projectId: string,
  taskType?: string,
  limit: number = 20
): Promise<TaskListResponse> {
  const params = new URLSearchParams({ project_id: projectId, limit: String(limit) });
  if (taskType) params.set('task_type', taskType);
  const response = await fetch(`${API_BASE}?${params}`);
  if (!response.ok) {
    throw new Error(`Lấy danh sách task thất bại: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Lấy các task tạo hàng loạt đang hoạt động của dự án
 */
export async function getActiveBatchTasks(projectId: string): Promise<BatchTaskStatus[]> {
  const response = await fetch(`/api/chapters/project/${projectId}/batch-generate/active`);
  if (!response.ok) {
    throw new Error(`Lấy task tạo hàng loạt thất bại: ${response.statusText}`);
  }
  const data: ActiveBatchTaskResponse = await response.json();
  return data.has_active_task && data.task ? [data.task] : [];
}

/**
 * Hủy task tạo hàng loạt
 */
export async function cancelBatchTask(batchId: string): Promise<void> {
  const response = await fetch(`/api/chapters/batch-generate/${batchId}/cancel`, { method: 'POST' });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(`Hủy task tạo hàng loạt thất bại: ${err.detail || response.statusText}`);
  }
}

/**
 * Hủy task
 */
export async function cancelTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${taskId}/cancel`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Hủy task thất bại: ${response.statusText}`);
  }
}

/**
 * Dọn dẹp bản ghi task đã kết thúc của dự án
 */
export async function clearProjectTasks(projectId: string): Promise<{ deleted_count: number }> {
  const response = await fetch(`${API_BASE}/project/${projectId}/clear`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(`Dọn dẹp bản ghi task thất bại: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Xóa bản ghi task
 */
export async function deleteTask(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${taskId}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(`Xóa task thất bại: ${response.statusText}`);
  }
}

export type TaskProgressCallback = (status: TaskStatus) => void;
export type TaskCompleteCallback = (result: TaskStatus) => void;
export type TaskErrorCallback = (error: string, status: TaskStatus) => void;

/**
 * Poll task cho đến khi hoàn thành
 * 
 * @param taskId ID của task
 * @param onProgress callback tiến trình
 * @param onComplete callback hoàn thành
 * @param onError callback lỗi
 * @param intervalMs khoảng poll (ms), mặc định2000
 * @returns hàm hủy poll
 */
export function pollTaskUntilComplete(
  taskId: string,
  onProgress: TaskProgressCallback,
  onComplete: TaskCompleteCallback,
  onError: TaskErrorCallback,
  intervalMs: number = 2000
): () => void {
  let cancelled = false;
  let timerId: ReturnType<typeof setTimeout>;

  const poll = async () => {
    if (cancelled) return;

    try {
      const status = await getTaskStatus(taskId);

      if (cancelled) return;

      onProgress(status);

      if (status.status === 'completed') {
        onComplete(status);
        return;
      }

      if (status.status === 'failed') {
        onError(status.error_message || 'Task thất bại', status);
        return;
      }

      if (status.status === 'cancelled') {
        onError('Task đã bị hủy', status);
        return;
      }

      // Tiếp tục poll (tăng tần suất poll khi đang chạy)
      const nextInterval = status.status === 'running' ? intervalMs : intervalMs * 2;
      timerId = setTimeout(poll, nextInterval);
    } catch (err) {
      if (!cancelled) {
        onError(err instanceof Error ? err.message : 'Truy vấn trạng thái task thất bại', {} as TaskStatus);
      }
    }
  };

  // Bắt đầu poll lần đầu ngay lập tức
  timerId = setTimeout(poll, 0);

  // Trả về hàm hủy
  return () => {
    cancelled = true;
    clearTimeout(timerId);
  };
}

/**
 * Yêu cầu tạo dàn ý ở chế độ nền và poll tiến trình
 * 
 * @param data tham số request (giốnggenerate-stream)
 * @param onProgress callback tiến trình
 * @param onComplete callback hoàn thành
 * @param onError callback lỗi
 * @returns Hàm hủy (đồng thời hủy poll và task nền)
 */
export async function generateOutlineBackground(
  data: unknown,
  onProgress: TaskProgressCallback,
  onComplete: TaskCompleteCallback,
  onError: TaskErrorCallback
): Promise<() => void> {
  // 1. Tạo task nền
  const response = await fetch('/api/outlines/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    onError(err.detail || 'Tạo task thất bại', {} as TaskStatus);
    return () => {};
  }

  const { task_id } = await response.json();

  // 2. Bắt đầu poll
  const cancelPolling = pollTaskUntilComplete(task_id, onProgress, onComplete, onError);

  // 3. Trả về hàm hủy thống nhất (hủy poll + hủy task nền)
  return () => {
    cancelPolling();
    cancelTask(task_id).catch(() => {});
  };
}

/**
 * Yêu cầu tạo nội dung chương ở chế độ nền và poll tiến trình
 * Đóng trình duyệt không ảnh hưởng đến việc tạo, sau khi tạo xong nội dung tự động lưu vào database
 */
export async function generateChapterBackground(
  chapterId: string,
  options: {
    style_id?: number | null;
    target_word_count?: number;
    model?: string | null;
    narrative_perspective?: string | null;
    enable_mcp?: boolean;
  },
  onProgress: TaskProgressCallback,
  onComplete: TaskCompleteCallback,
  onError: TaskErrorCallback
): Promise<() => void> {
  const response = await fetch(`/api/chapters/${chapterId}/generate-background`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    onError(err.detail || 'Tạo task sinh chương thất bại', {} as TaskStatus);
    return () => {};
  }

  const { task_id } = await response.json();
  const cancelPolling = pollTaskUntilComplete(task_id, onProgress, onComplete, onError);

  return () => {
    cancelPolling();
    cancelTask(task_id).catch(() => {});
  };
}
