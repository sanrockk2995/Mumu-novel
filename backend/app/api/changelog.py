"""
API nhật ký cập nhật
Cung cấp dịch vụ cache và proxy cho lịch sử commit GitHub
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from typing import List, Optional
import httpx
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def require_login(request: Request):
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return request.state.user

# Cấu hình GitHub API
GITHUB_API_BASE = "https://api.github.com"
REPO_OWNER = "xiamuceer-j"
REPO_NAME = "MuMuAINovel"

# Cấu hình cache
_cache = {
    "data": None,
    "timestamp": None,
    "ttl": timedelta(hours=1)  # Cache 1 giờ
}


class GitHubAuthor(BaseModel):
    """Thông tin tác giả GitHub"""
    name: str
    email: str
    date: str


class GitHubCommitInfo(BaseModel):
    """Thông tin commit GitHub"""
    author: GitHubAuthor
    message: str


class GitHubUser(BaseModel):
    """Thông tin người dùng GitHub"""
    login: str
    avatar_url: str


class GitHubCommit(BaseModel):
    """Dữ liệu commit GitHub"""
    sha: str
    commit: GitHubCommitInfo
    html_url: str
    author: Optional[GitHubUser] = None


class ChangelogResponse(BaseModel):
    """Response nhật ký cập nhật"""
    commits: List[GitHubCommit]
    cached: bool
    cache_time: Optional[str] = None


def is_cache_valid() -> bool:
    """Kiểm tra cache còn hiệu lực không"""
    if _cache["data"] is None or _cache["timestamp"] is None:
        return False

    now = datetime.now()
    cache_age = now - _cache["timestamp"]

    return cache_age < _cache["ttl"]


async def fetch_github_commits(page: int = 1, per_page: int = 30) -> List[dict]:
    """Lấy lịch sử commit từ GitHub API"""
    url = f"{GITHUB_API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/commits"
    params = {
        "author": REPO_OWNER,
        "page": page,
        "per_page": per_page
    }

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MuMuAINovel-App"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Yêu cầu GitHub API thất bại: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Lấy lịch sử commit GitHub thất bại: {str(e)}"
        )


@router.get("/changelog", response_model=ChangelogResponse)
async def get_changelog(
    page: int = Query(1, ge=1, description="Số trang"),
    per_page: int = Query(30, ge=1, le=100, description="Số lượng mỗi trang")
):
    """
    Lấy nhật ký cập nhật

    Lấy lịch sử commit của dự án từ GitHub, hỗ trợ cache để giảm số lần gọi API

    - **page**: số trang, bắt đầu từ 1
    - **per_page**: số commit trả về mỗi trang, tối đa 100
    """
    try:
        # Chỉ cache trang đầu tiên
        if page == 1 and is_cache_valid():
            logger.info("Sử dụng nhật ký cập nhật từ cache")
            return ChangelogResponse(
                commits=_cache["data"],
                cached=True,
                cache_time=_cache["timestamp"].isoformat()
            )

        # Lấy dữ liệu từ GitHub
        logger.info(f"Lấy nhật ký cập nhật từ GitHub (page={page}, per_page={per_page})")
        commits_data = await fetch_github_commits(page, per_page)

        # Phân tích dữ liệu
        commits = []
        for commit_data in commits_data:
            try:
                commit = GitHubCommit(
                    sha=commit_data["sha"],
                    commit=GitHubCommitInfo(
                        author=GitHubAuthor(
                            name=commit_data["commit"]["author"]["name"],
                            email=commit_data["commit"]["author"]["email"],
                            date=commit_data["commit"]["author"]["date"]
                        ),
                        message=commit_data["commit"]["message"]
                    ),
                    html_url=commit_data["html_url"],
                    author=GitHubUser(
                        login=commit_data["author"]["login"],
                        avatar_url=commit_data["author"]["avatar_url"]
                    ) if commit_data.get("author") else None
                )
                commits.append(commit)
            except (KeyError, TypeError) as e:
                logger.warning(f"Phân tích dữ liệu commit thất bại: {str(e)}")
                continue

        # Cache dữ liệu trang đầu
        if page == 1:
            _cache["data"] = commits
            _cache["timestamp"] = datetime.now()
            logger.info("Đã cache nhật ký cập nhật")

        return ChangelogResponse(
            commits=commits,
            cached=False,
            cache_time=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Đã xảy ra lỗi khi lấy nhật ký cập nhật: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Lấy nhật ký cập nhật thất bại: {str(e)}"
        )


@router.post("/changelog/refresh")
async def refresh_changelog(user=Depends(require_login)):
    """
    Làm mới cache nhật ký cập nhật

    Buộc lấy lại lịch sử commit mới nhất từ GitHub
    """
    try:
        logger.info("Làm mới cache nhật ký cập nhật")

        # Xóa cache
        _cache["data"] = None
        _cache["timestamp"] = None

        # Lấy lại
        commits_data = await fetch_github_commits(1, 30)

        # Phân tích dữ liệu
        commits = []
        for commit_data in commits_data:
            try:
                commit = GitHubCommit(
                    sha=commit_data["sha"],
                    commit=GitHubCommitInfo(
                        author=GitHubAuthor(
                            name=commit_data["commit"]["author"]["name"],
                            email=commit_data["commit"]["author"]["email"],
                            date=commit_data["commit"]["author"]["date"]
                        ),
                        message=commit_data["commit"]["message"]
                    ),
                    html_url=commit_data["html_url"],
                    author=GitHubUser(
                        login=commit_data["author"]["login"],
                        avatar_url=commit_data["author"]["avatar_url"]
                    ) if commit_data.get("author") else None
                )
                commits.append(commit)
            except (KeyError, TypeError) as e:
                logger.warning(f"Phân tích dữ liệu commit thất bại: {str(e)}")
                continue

        # Cập nhật cache
        _cache["data"] = commits
        _cache["timestamp"] = datetime.now()

        return {
            "success": True,
            "message": "Đã làm mới cache",
            "commit_count": len(commits),
            "cache_time": _cache["timestamp"].isoformat()
        }

    except Exception as e:
        logger.error(f"Đã xảy ra lỗi khi làm mới cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Làm mới cache thất bại: {str(e)}"
        )
