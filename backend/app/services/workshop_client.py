"""API client của Xưởng prompt đám mây (dùng ở chế độ đám mây)"""
import httpx
from typing import Optional, Dict, Any
from app.config import settings, INSTANCE_ID
from app.logger import get_logger, safe_preview

logger = get_logger(__name__)


class WorkshopClientError(Exception):
    """Lỗi client xưởng"""
    pass


class WorkshopClient:
    """API client đám mây"""
    
    def __init__(self):
        self.base_url = settings.WORKSHOP_CLOUD_URL
        self.timeout = settings.WORKSHOP_API_TIMEOUT
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        user_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Gửi yêu cầu tới đám mây"""
        headers = {
            "X-Instance-ID": INSTANCE_ID,
            "Content-Type": "application/json"
        }
        if user_identifier:
            headers["X-User-ID"] = user_identifier
        
        url = f"{self.base_url}/api/prompt-workshop{path}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logger.error(f"Không thể kết nối tới dịch vụ đám mây: {self.base_url}, lỗi: {e}")
            raise WorkshopClientError("Không thể kết nối tới dịch vụ đám mây, vui lòng kiểm tra kết nối mạng")
        except httpx.TimeoutException:
            logger.error(f"Yêu cầu dịch vụ đám mây hết thời gian chờ: {url}")
            raise WorkshopClientError("Yêu cầu dịch vụ đám mây hết thời gian chờ, vui lòng thử lại sau")
        except httpx.HTTPStatusError as e:
            logger.error(f"Dịch vụ đám mây trả về lỗi: {e.response.status_code}, response={safe_preview(e.response.text, 500)}")
            raise WorkshopClientError(f"Lỗi dịch vụ đám mây: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Yêu cầu dịch vụ đám mây gặp ngoại lệ: {e}")
            raise WorkshopClientError(f"Yêu cầu dịch vụ đám mây thất bại: {str(e)}")
    
    async def check_connection(self) -> bool:
        """Kiểm tra trạng thái kết nối đám mây"""
        try:
            await self._request("GET", "/status")
            return True
        except Exception as e:
            logger.warning(f"Kiểm tra kết nối đám mây thất bại: {e}")
            return False
    
    async def get_items(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[str] = None,
        sort: str = "newest",
        page: int = 1,
        limit: int = 20,
        user_identifier: Optional[str] = None
    ) -> Dict:
        """Lấy danh sách prompt"""
        params = {
            "sort": sort,
            "page": page,
            "limit": limit
        }
        if category:
            params["category"] = category
        if search:
            params["search"] = search
        if tags:
            params["tags"] = tags
        
        return await self._request(
            "GET", "/items",
            params=params,
            user_identifier=user_identifier
        )
    
    async def get_item(self, item_id: str, user_identifier: Optional[str] = None) -> Dict:
        """Lấy chi tiết một prompt"""
        return await self._request("GET", f"/items/{item_id}", user_identifier=user_identifier)
    
    async def record_download(self, item_id: str, user_identifier: str) -> Dict:
        """Ghi nhận lượt tải"""
        return await self._request(
            "POST",
            f"/items/{item_id}/download",
            json={
                "instance_id": INSTANCE_ID,
                "user_identifier": user_identifier
            },
            user_identifier=user_identifier
        )
    
    async def toggle_like(self, item_id: str, user_identifier: str) -> Dict:
        """thích/bỏ thích"""
        return await self._request(
            "POST",
            f"/items/{item_id}/like",
            user_identifier=user_identifier
        )
    
    async def submit(
        self,
        user_identifier: str,
        submitter_name: str,
        data: Dict
    ) -> Dict:
        """Gửi prompt"""
        payload = {
            "instance_id": INSTANCE_ID,
            "submitter_id": user_identifier,
            "submitter_name": submitter_name,
            **data
        }
        # Lưu ý: phải truyền user_identifier để thiết lập X-User-ID Header
        return await self._request("POST", "/submit", json=payload, user_identifier=user_identifier)
    
    async def get_submissions(
        self,
        user_identifier: str,
        status: Optional[str] = None
    ) -> Dict:
        """Lấy lịch sử gửi của người dùng"""
        params = {}
        if status:
            params["status"] = status
        return await self._request(
            "GET", "/my-submissions",
            params=params,
            user_identifier=user_identifier
        )
    
    async def withdraw_submission(
        self,
        submission_id: str,
        user_identifier: str,
        force: bool = False
    ) -> Dict:
        """rút lại/xóa bài gửi"""
        params = {}
        if force:
            params["force"] = "true"
        return await self._request(
            "DELETE",
            f"/submissions/{submission_id}",
            params=params if params else None,
            user_identifier=user_identifier
        )


# Thể hiện client toàn cục
workshop_client = WorkshopClient()
