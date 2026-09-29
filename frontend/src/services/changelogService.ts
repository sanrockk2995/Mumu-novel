/**
 * Dịch vụ lấy nhật ký commit GitHub
 * Dùng để lấy lịch sử commit của dự án từ GitHub API và chuyển thành nhật ký cập nhật
 */

export interface GitHubCommit {
  sha: string;
  commit: {
    author: {
      name: string;
      email: string;
      date: string;
    };
    message: string;
  };
  html_url: string;
  author: {
    login: string;
    avatar_url: string;
  } | null;
}

export interface ChangelogEntry {
  id: string;
  date: string;
  version?: string;
  author: {
    name: string;
    avatar?: string;
    username?: string;
  };
  message: string;
  commitUrl: string;
  type: 'feature' | 'fix' | 'docs' | 'style' | 'refactor' | 'perf' | 'test' | 'chore' | 'update' | 'other';
  scope?: string;
}

const GITHUB_API_BASE = 'https://api.github.com';
const REPO_OWNER = 'xiamuceer-j';
const REPO_NAME = 'MuMuAINovel';

/**
 * Bảng ánh xạ loại commit
 * Chuẩn hóa các bí danh khác nhau về loại chuẩn
 */
const TYPE_MAPPING: Record<string, ChangelogEntry['type']> = {
  // Nhóm tính năng
  'feat': 'feature',
  'feature': 'feature',
  'update': 'update',
  
  // Nhóm sửa lỗi
  'fix': 'fix',
  
  // Nhóm tài liệu
  'docs': 'docs',
  'doc': 'docs',
  
  // Nhóm kiểu dáng
  'style': 'style',
  
  // Nhóm tái cấu trúc
  'refactor': 'refactor',
  
  // Nhóm hiệu năng
  'perf': 'perf',
  
  // Nhóm kiểm thử
  'test': 'test',
  
  // Nhóm khác
  'chore': 'chore',
};

/**
 * Phân tích loại và phạm vi từ message commit
 *
 * Thứ tự ưu tiên khớp (từ cao đến thấp):
 * 1. Định dạng Conventional Commits chuẩn: type(scope): message hoặc type: message
 * 2. Định dạng ngoặc vuông: [type] message
 * 3. Định dạng tiền tố đơn giản: type: message(hỗ trợ dấu hai chấm tiếng Trung)
 * 4. Khớp mờ từ khóa (Trung-Anh)
 */
function parseCommitType(message: string): { type: ChangelogEntry['type']; scope?: string; cleanMessage: string } {
  const lowerMessage = message.toLowerCase().trim();
  
  // Ưu tiên 1: định dạng Conventional Commits chuẩn - type(scope): message hoặc type: message
  // Khớp tất cả các loại được hỗ trợ
  const conventionalPattern = new RegExp(
    `^(${Object.keys(TYPE_MAPPING).join('|')})(?:\\(([^)]+)\\))?\\s*[:\\:：]\\s*(.+)`,
    'i'
  );
  const conventionalMatch = message.match(conventionalPattern);
  if (conventionalMatch) {
    const typeStr = conventionalMatch[1].toLowerCase();
    const mappedType = TYPE_MAPPING[typeStr] || 'other';
    return {
      type: mappedType,
      scope: conventionalMatch[2],
      cleanMessage: conventionalMatch[3].trim(),
    };
  }

  // Ưu tiên 2: định dạng ngoặc vuông - [type] message
  const bracketPattern = new RegExp(
    `^\\[(${Object.keys(TYPE_MAPPING).join('|')})\\]\\s*(.+)`,
    'i'
  );
  const bracketMatch = message.match(bracketPattern);
  if (bracketMatch) {
    const typeStr = bracketMatch[1].toLowerCase();
    const mappedType = TYPE_MAPPING[typeStr] || 'other';
    return {
      type: mappedType,
      cleanMessage: bracketMatch[2].trim(),
    };
  }

  // Ưu tiên 3: định dạng tiền tố đơn giản - type: message(hỗ trợ dấu hai chấm tiếng Anh và tiếng Trung)
  for (const [key, value] of Object.entries(TYPE_MAPPING)) {
    const prefixPattern = new RegExp(`^${key}\\s*[:\\:：]\\s*`, 'i');
    if (prefixPattern.test(lowerMessage)) {
      const cleanMsg = message.replace(prefixPattern, '').trim();
      return { type: value, cleanMessage: cleanMsg };
    }
  }

  // Ưu tiên 4: khớp mờ từ khóa (chỉ khi các cách trên đều không khớp)
  const keywordMap: Array<{ keywords: string[]; type: ChangelogEntry['type'] }> = [
    { keywords: ['修复', 'fix'], type: 'fix' },
    { keywords: ['优化', 'perf'], type: 'perf' },
    { keywords: ['文档', 'document'], type: 'docs' },
    { keywords: ['新增', '添加', '增加', 'add'], type: 'feature' },
    { keywords: ['更新', 'update'], type: 'update' },
    { keywords: ['样式', 'style'], type: 'style' },
    { keywords: ['重构', 'refactor'], type: 'refactor' },
    { keywords: ['测试', 'test'], type: 'test' },
  ];

  for (const { keywords, type } of keywordMap) {
    if (keywords.some(keyword => lowerMessage.includes(keyword))) {
      return { type, cleanMessage: message };
    }
  }

  // Loại mặc định
  return { type: 'other', cleanMessage: message };
}

/**
 * Lấy lịch sử commit GitHub
 */
export async function fetchGitHubCommits(page: number = 1, perPage: number = 30): Promise<GitHubCommit[]> {
  try {
    const url = `${GITHUB_API_BASE}/repos/${REPO_OWNER}/${REPO_NAME}/commits?author=${REPO_OWNER}&page=${page}&per_page=${perPage}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/vnd.github.v3+json',
      },
      cache: 'no-cache',
    });

    if (!response.ok) {
      throw new Error(`Request GitHub API thất bại: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Lấy lịch sử commit GitHub thất bại:', error);
    throw error;
  }
}

/**
 * Chuyển commit GitHub thành các mục nhật ký cập nhật
 */
export function convertCommitsToChangelog(commits: GitHubCommit[]): ChangelogEntry[] {
  return commits.map(commit => {
    const { type, scope, cleanMessage } = parseCommitType(commit.commit.message);
    
    return {
      id: commit.sha,
      date: commit.commit.author.date,
      author: {
        name: commit.commit.author.name,
        avatar: commit.author?.avatar_url,
        username: commit.author?.login,
      },
      message: cleanMessage,
      commitUrl: commit.html_url,
      type,
      scope,
    };
  });
}

/**
 * Lấy nhật ký cập nhật đã định dạng
 */
export async function fetchChangelog(page: number = 1, perPage: number = 30): Promise<ChangelogEntry[]> {
  const commits = await fetchGitHubCommits(page, perPage);
  return convertCommitsToChangelog(commits);
}

/**
 * Nhóm nhật ký cập nhật theo ngày
 */
export function groupChangelogByDate(entries: ChangelogEntry[]): Map<string, ChangelogEntry[]> {
  const grouped = new Map<string, ChangelogEntry[]>();
  
  entries.forEach(entry => {
    const date = new Date(entry.date).toISOString().split('T')[0];
    const existing = grouped.get(date) || [];
    existing.push(entry);
    grouped.set(date, existing);
  });
  
  return grouped;
}

/**
 * Kiểm tra có nên lấy nhật ký cập nhật không (tránh request quá thường xuyên)
 */
export function shouldFetchChangelog(): boolean {
  const lastFetch = localStorage.getItem('changelog_last_fetch');
  
  if (!lastFetch) {
    return true;
  }
  
  const lastFetchTime = new Date(lastFetch).getTime();
  const now = Date.now();
  const oneHourMs = 60 * 60 * 1000; // 1 giờ
  
  return now - lastFetchTime >= oneHourMs;
}

/**
 * Ghi lại thời gian lấy nhật ký cập nhật
 */
export function markChangelogFetched(): void {
  localStorage.setItem('changelog_last_fetch', new Date().toISOString());
}

/**
 * Lấy nhật ký cập nhật từ cache
 */
export function getCachedChangelog(): ChangelogEntry[] | null {
  const cached = localStorage.getItem('changelog_cache');
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
 * Lưu nhật ký cập nhật vào cache
 */
export function cacheChangelog(entries: ChangelogEntry[]): void {
  localStorage.setItem('changelog_cache', JSON.stringify(entries));
}

/**
 * Xóa cache nhật ký cập nhật
 * Dùng để buộc refresh dữ liệu
 */
export function clearChangelogCache(): void {
  localStorage.removeItem('changelog_cache');
  localStorage.removeItem('changelog_last_fetch');
}