import { VERSION_INFO } from '../config/version';

interface VersionCheckResult {
  hasUpdate: boolean;
  latestVersion: string;
  releaseUrl: string;
}

/**
 * So sánh số phiên bản
 * @returns -1: v1 < v2, 0: v1 = v2, 1: v1 > v2
 */
function compareVersion(v1: string, v2: string): number {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);
  
  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const num1 = parts1[i] || 0;
    const num2 = parts2[i] || 0;
    
    if (num1 < num2) return -1;
    if (num1 > num2) return 1;
  }
  
  return 0;
}

/**
 * Dùng shields.io Badge API để lấy phiên bản mới nhất
 * Ưu điểm: không có vấn đề CORS, tự động lấy từ GitHub, không cần bảo trì
 */
export async function checkLatestVersion(): Promise<VersionCheckResult> {
  try {
    // Dùng GitHub release badge API của shields.io
    const badgeUrl = 'https://img.shields.io/github/v/release/xiamuceer-j/MuMuAINovel';
    
    const response = await fetch(badgeUrl, {
      method: 'GET',
      cache: 'no-cache',
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    
    // shields.io trả về định dạng SVG
    const svgText = await response.text();
    
    // Trích xuất số phiên bản từ SVG
    // Số phiên bản trong SVG thường nằm trong thẻ <text>, định dạng như: v1.0.0 hoặc 1.0.0
    const versionRegex = /v?([\d.]+)/g;
    const matches = svgText.match(versionRegex);
    
    if (matches && matches.length > 0) {
      // Kết quả khớp cuối cùng thường là số phiên bản (các kết quả trước đó có thể là văn bản nhãn)
      const versionMatch = matches[matches.length - 1];
      const latestVersion = versionMatch.replace('v', '');
      
      // Kiểm tra định dạng số phiên bản (x.x.x)
      if (/^\d+\.\d+(\.\d+)?$/.test(latestVersion)) {
        const hasUpdate = compareVersion(VERSION_INFO.version, latestVersion) < 0;
        
        return {
          hasUpdate,
          latestVersion,
          releaseUrl: `https://github.com/xiamuceer-j/MuMuAINovel/releases/tag/v${latestVersion}`,
        };
      }
    }
    
    throw new Error('Không thể phân tích thông tin phiên bản từ Badge API');
  } catch {
    // Trả về trạng thái không có cập nhật khi thất bại
    return {
      hasUpdate: false,
      latestVersion: VERSION_INFO.version,
      releaseUrl: VERSION_INFO.githubUrl,
    };
  }
}

/**
 * Kiểm tra xem có nên thực hiện kiểm tra phiên bản không (tránh gửi request quá thường xuyên)
 */
export function shouldCheckVersion(): boolean {
  const lastCheck = localStorage.getItem('version_last_check');
  
  if (!lastCheck) {
    return true;
  }
  
  const lastCheckTime = new Date(lastCheck).getTime();
  const now = Date.now();
  const sixHoursMs = 6 * 60 * 60 * 1000; // 6 giờ
  
  return now - lastCheckTime >= sixHoursMs;
}

/**
 * Ghi lại thời gian kiểm tra phiên bản
 */
export function markVersionChecked(): void {
  localStorage.setItem('version_last_check', new Date().toISOString());
}

/**
 * Lấy thông tin phiên bản từ cache
 */
export function getCachedVersionInfo(): VersionCheckResult | null {
  const cached = localStorage.getItem('version_check_result');
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Lưu thông tin phiên bản vào cache
 */
export function cacheVersionInfo(info: VersionCheckResult): void {
  localStorage.setItem('version_check_result', JSON.stringify(info));
}

/**
 * Người dùng đã xem thông báo cập nhật
 */
export function markUpdateViewed(version: string): void {
  localStorage.setItem('version_viewed', version);
}

/**
 * Kiểm tra xem người dùng đã xem thông báo cập nhật của phiên bản này chưa
 */
export function hasViewedUpdate(version: string): boolean {
  const viewedVersion = localStorage.getItem('version_viewed');
  
  // Nếu phiên bản đã xem thấp hơn phiên bản mới nhất thì nên hiển thị chấm đỏ
  if (viewedVersion && version) {
    const parts1 = viewedVersion.split('.').map(Number);
    const parts2 = version.split('.').map(Number);
    
    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
      const num1 = parts1[i] || 0;
      const num2 = parts2[i] || 0;
      
      if (num1 < num2) {
        return false; // Phiên bản đã xem thấp hơn phiên bản mới nhất, cần hiển thị chấm đỏ
      }
      if (num1 > num2) {
        return true; // Phiên bản đã xem cao hơn phiên bản mới nhất
      }
    }
  }
  
  return viewedVersion === version;
}