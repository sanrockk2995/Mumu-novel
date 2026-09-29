/**
 * Event bus - dùng để đồng bộ dữ liệu giữa các component/trang
 * 
 * Cách dùng:
 * - eventBus.on('eventName', callback) - Lắng nghe sự kiện
 * - eventBus.off('eventName', callback) - Hủy lắng nghe
 * - eventBus.emit('eventName', data) - Kích hoạt sự kiện
 * - eventBus.once('eventName', callback) - Lắng nghe một lần
 */

type EventCallback = (data?: unknown) => void;

class EventBus {
  private events: Map<string, EventCallback[]> = new Map();

  /**
   * Lắng nghe sự kiện
   */
  on(event: string, callback: EventCallback): void {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event)!.push(callback);
  }

  /**
   * Hủy lắng nghe sự kiện
   */
  off(event: string, callback: EventCallback): void {
    const callbacks = this.events.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * Kích hoạt sự kiện
   */
  emit(event: string, data?: unknown): void {
    const callbacks = this.events.get(event);
    if (callbacks) {
      callbacks.forEach(cb => {
        try {
          cb(data);
        } catch (error) {
          console.error(`Handler sự kiện thực thi thất bại [${event}]:`, error);
        }
      });
    }
  }

  /**
   * Lắng nghe sự kiện một lần
   */
  once(event: string, callback: EventCallback): void {
    const onceCallback: EventCallback = (data) => {
      callback(data);
      this.off(event, onceCallback);
    };
    this.on(event, onceCallback);
  }

  /**
   * Gỡ tất cả listener của một sự kiện
   */
  removeAllListeners(event?: string): void {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
  }

  /**
   * Lấy số lượng listener của sự kiện
   */
  listenerCount(event: string): number {
    return this.events.get(event)?.length || 0;
  }
}

// Xuất singleton
export const eventBus = new EventBus();

// Xuất hằng số tên sự kiện, tránh gõ sai chuỗi
export const EventNames = {
  // Sự kiện liên quan dự án
  PROJECT_CREATED: 'project:created',
  PROJECT_UPDATED: 'project:updated',
  PROJECT_DELETED: 'project:deleted',
  PROJECT_NEEDS_REFRESH: 'project:needsRefresh',

  // Sự kiện liên quan nhân vật
  CHARACTER_CREATED: 'character:created',
  CHARACTER_UPDATED: 'character:updated',
  CHARACTER_DELETED: 'character:deleted',
  CHARACTER_NEEDS_REFRESH: 'character:needsRefresh',

  // Sự kiện liên quan đề cương
  OUTLINE_CREATED: 'outline:created',
  OUTLINE_UPDATED: 'outline:updated',
  OUTLINE_DELETED: 'outline:deleted',
  OUTLINE_REORDERED: 'outline:reordered',
  OUTLINE_GENERATED: 'outline:generated',
  OUTLINE_NEEDS_REFRESH: 'outline:needsRefresh',

  // Sự kiện liên quan chương
  CHAPTER_CREATED: 'chapter:created',
  CHAPTER_UPDATED: 'chapter:updated',
  CHAPTER_DELETED: 'chapter:deleted',
  CHAPTER_NEEDS_REFRESH: 'chapter:needsRefresh',

  // Sự kiện refresh chung sau khi agent dự án xác nhận ghi
  AGENT_DATA_CHANGED: 'agent:dataChanged',

  // Sự kiện vòng đời task nền chung
  BACKGROUND_TASK_CREATED: 'backgroundTask:created',
  BACKGROUND_TASK_SETTLED: 'backgroundTask:settled',

  // Sự kiện chuyển view
  SWITCH_TO_MCP_VIEW: 'view:switchToMcp',
} as const;
