/**
 * Cấu hình thông tin phiên bản ứng dụng
 * Số phiên bản tuân theo quy chuẩn Semantic Versioning (Semantic Versioning)
 *
 * Lưu ý: số phiên bản được package.json tự động đọc, không cần bảo trì thủ công
 */

export const VERSION_INFO = {
  // Số phiên bản ứng dụng (được package.json đọc, inject lúc build)
  version: import.meta.env.VITE_APP_VERSION || '1.5.6',
  
  // Thời gian build (sẽ được inject lúc build bởi Vite )
  buildTime: import.meta.env.VITE_BUILD_TIME || new Date().toISOString().split('T')[0],
  
  // Thông tin dự án
  projectName: 'MuMuAINovel',
  projectFullName: 'MuMu AI Trợ lý sáng tác tiểu thuyết',
  
  // Thông tin liên kết
  githubUrl: 'https://github.com/xiamuceer-j/MuMuAINovel',
  linuxDoUrl: 'https://linux.do/t/topic/1106333',
  
  // Giấy phép
  license: 'GPL v3.0',
  licenseUrl: 'https://www.gnu.org/licenses/gpl-3.0.html',
  
  // Thông tin tác giả
  author: 'xiamuceer-j',
};

/**
 * Lấy thông tin phiên bản đã định dạng
 */
export const getVersionString = () => {
  return `v${VERSION_INFO.version}`;
};

/**
 * Lấy mô tả đầy đủ của phiên bản
 */
export const getFullVersionInfo = () => {
  return `${VERSION_INFO.projectName} ${getVersionString()} - Build ${VERSION_INFO.buildTime}`;
};
