"""API client thông báo cloud (dùng ở chế độ client)"""
import httpx
from typing import Optional, Dict, Any
from app.config import settings, INSTANCE_ID
from app.logger import get_logger, safe_preview

logger = get_logger(__name__)


class AnnouncementClientError(Exception):
    """Lỗi client thông báo"""
    pass


class AnnouncementClient:
    """API client thông báo cloud"""

    def __init__(self):
        self.base_url = settings.WORKSHOP_CLOUD_URL
        self.timeout = settings.WORKSHOP_API_TIMEOUT

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Gửi request tới dịch vụ thông báo cloud"""
        headers = {
            "X-Instance-ID": INSTANCE_ID,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/api/announcements{path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Không thể kết nối tới dịch vụ thông báo cloud: {self.base_url}, lỗi: {e}")
            raise AnnouncementClientError("Không thể kết nối tới dịch vụ thông báo cloud, vui lòng kiểm tra kết nối mạng")
        except httpx.TimeoutException:
            logger.error(f"Request tới dịch vụ thông báo cloud bị timeout: {url}")
            raise AnnouncementClientError("Request tới dịch vụ thông báo cloud bị timeout, vui lòng thử lại sau")
        except httpx.HTTPStatusError as e:
            logger.error(f"Dịch vụ thông báo cloud trả về lỗi: {e.response.status_code}, response={safe_preview(e.response.text, 500)}")
            raise AnnouncementClientError(f"Lỗi dịch vụ thông báo cloud: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Request tới dịch vụ thông báo cloud gặp ngoại lệ: {e}")
            raise AnnouncementClientError(f"Request tới dịch vụ thông báo cloud thất bại: {str(e)}")

    async def check_connection(self) -> bool:
        """Kiểm tra trạng thái kết nối cloud"""
        try:
            await self._request("GET", "/status")
            return True
        except Exception as e:
            logger.warning(f"Kiểm tra kết nối thông báo cloud thất bại: {e}")
            return False

    async def get_announcements(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """Lấy danh sách thông báo"""
        return await self._request("GET", "", params={"page": page, "limit": limit})

    async def sync(self, since: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Đồng bộ thông báo"""
        params: Dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since
        return await self._request("GET", "/sync", params=params)


announcement_client = AnnouncementClient()
