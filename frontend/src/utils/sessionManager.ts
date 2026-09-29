import { authApi } from '../services/api';

/**
 * Công cụ quản lý phiên
 * Chịu trách nhiệm giám sát trạng thái phiên, tự refresh và xử lý hết hạn
 */
class SessionManager {
  private checkInterval: number | null = null;
  private activityTimeout: number | null = null;
  private lastActivityTime: number = Date.now();
  
  // Tham số cấu hình
  private readonly CHECK_INTERVAL = 60 * 1000;
  private readonly REFRESH_THRESHOLD = 30 * 60 * 1000;
  private readonly ACTIVITY_TIMEOUT = 30 * 60 * 1000;
  private readonly WARNING_THRESHOLD = 5 * 60 * 1000;
  
  private warningShown = false;
  private showWarningCallback: ((message: string) => void) | null = null;

  /**
   * Bắt đầu giám sát phiên
   */
  start() {
    // Kiểm tra trước có phiên hợp lệ không
    const expireAt = this.getSessionExpireTime();
    
    if (!expireAt) {
      return;
    }
    
    const now = Date.now();
    const remaining = expireAt - now;
    const remainingMinutes = Math.floor(remaining / 60000);
    
    // Nếu phiên đã hết hạn, không bắt đầu giám sát
    if (remaining <= 0) {
      return;
    }
    
    console.log(`✅ [Phiên] Bắt đầu giám sát, còn ${remainingMinutes} phút`);
    
    // Kiểm tra ngay một lần
    this.checkSession();
    
    // Kiểm tra định kỳ trạng thái phiên
    this.checkInterval = setInterval(() => {
      this.checkSession();
    }, this.CHECK_INTERVAL);
    
    // Lắng nghe hoạt động người dùng
    this.setupActivityListeners();
  }

  /**
   * Dừng giám sát phiên
   */
  stop() {
    console.log('[SessionManager] Dừng giám sát phiên');
    
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    
    if (this.activityTimeout) {
      clearTimeout(this.activityTimeout);
      this.activityTimeout = null;
    }
    
    this.removeActivityListeners();
    this.warningShown = false;
  }

  /**
   * Kiểm tra trạng thái phiên
   */
  private async checkSession() {
    try {
      const expireAt = this.getSessionExpireTime();
      
      if (!expireAt) {
        this.stop();
        return;
      }
      
      const now = Date.now();
      const remaining = expireAt - now;
      const remainingMinutes = Math.floor(remaining / 60000);
      
      // Phiên đã hết hạn
      if (remaining <= 0) {
        console.log('⏰ [Phiên] Đã hết hạn, đăng xuất');
        this.handleSessionExpired();
        return;
      }
      
      // Hiển thị cảnh báo sắp hết hạn
      if (remaining <= this.WARNING_THRESHOLD && !this.warningShown) {
        this.warningShown = true;
        console.warn(`[Phiên] Trạng thái đăng nhập sẽ hết hạn sau ${remainingMinutes} phút`);
        this.showWarningCallback?.(`Trạng thái đăng nhập của bạn sẽ hết hạn sau ${remainingMinutes} phút, vui lòng chú ý lưu dữ liệu`);
      }
      
      // Cần refresh phiên
      if (remaining <= this.REFRESH_THRESHOLD) {
        const timeSinceLastActivity = now - this.lastActivityTime;
        
        // Kiểm tra người dùng có hoạt động không (có hoạt động trong 30 phút)
        if (timeSinceLastActivity < this.ACTIVITY_TIMEOUT) {
          await this.refreshSession();
        }
      }
    } catch {
      // Xử lý lỗi âm thầm
    }
  }

  /**
   * Refresh phiên
   */
  private async refreshSession() {
    try {
      const result = await authApi.refreshSession();
      this.warningShown = false; // Đặt lại trạng thái cảnh báo
      
      console.log(`🔄 [Phiên] Tự gia hạn thành công, kéo dài ${result.remaining_minutes} phút`);
    } catch {
      // Refresh thất bại có thể do phiên đã hết hạn
      this.handleSessionExpired();
    }
  }

  /**
   * Xử lý phiên hết hạn
   */
  private async handleSessionExpired() {
    this.stop();
    
    const currentPath = window.location.pathname;
    // Nếu đã ở trang đăng nhập hoặc trang callback, không hiển thị gợi ý lỗi
    if (currentPath === '/login' || currentPath === '/auth/callback') {
      return;
    }
    
    // Gọi API đăng xuất để xóa Cookie phía server
    try {
      await authApi.logout();
    } catch {
      // Dù đăng xuất thất bại vẫn tiếp tục chuyển
    }
    
    // Chuyển thẳng đến trang đăng nhập
    window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
  }

  /**
   * Lấy thời gian hết hạn phiên (timestamp mili giây)
   */
  private getSessionExpireTime(): number | null {
    const cookies = document.cookie.split(';');
    
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      
      if (name === 'session_expire_at') {
        const timestamp = parseInt(value, 10);
        return timestamp * 1000; // Chuyển thành mili giây
      }
    }
    
    return null;
  }

  /**
   * Đặt listener hoạt động người dùng
   */
  private setupActivityListeners() {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    
    events.forEach(event => {
      document.addEventListener(event, this.handleUserActivity, { passive: true });
    });
  }

  /**
   * Gỡ listener hoạt động người dùng
   */
  private removeActivityListeners() {
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    
    events.forEach(event => {
      document.removeEventListener(event, this.handleUserActivity);
    });
  }

  /**
   * Xử lý hoạt động người dùng
   */
  private handleUserActivity = () => {
    this.lastActivityTime = Date.now();
    
    // Đặt lại timeout hoạt động
    if (this.activityTimeout) {
      clearTimeout(this.activityTimeout);
    }
    
    this.activityTimeout = setTimeout(() => {
      // Người dùng đã hơn 30 phút không hoạt động
    }, this.ACTIVITY_TIMEOUT);
  };

  /**
   * Đặt callback cảnh báo (dùng để hiển thị thông báo trong component React)
   */
  setWarningCallback(callback: (message: string) => void) {
    this.showWarningCallback = callback;
  }

  /**
   * Refresh phiên thủ công (cho bên ngoài gọi)
   */
  async manualRefresh(): Promise<boolean> {
    try {
      await this.refreshSession();
      return true;
    } catch {
      return false;
    }
  }
}

// Xuất singleton
export const sessionManager = new SessionManager();