"""
Dịch vụ LinuxDO OAuth2
"""
import httpx
import secrets
from typing import Optional, Dict, Any
from app.config import settings
from app.logger import get_logger, safe_json_preview, safe_preview

logger = get_logger(__name__)


class LinuxDOOAuthService:
    """Lớp dịch vụ LinuxDO OAuth2"""
    
    # Endpoint LinuxDO OAuth2
    AUTHORIZE_URL = "https://connect.linux.do/oauth2/authorize"
    TOKEN_URL = "https://connect.linux.do/oauth2/token"
    USERINFO_URL = "https://connect.linux.do/api/user"  # Fix: dùng endpoint thông tin người dùng đúng
    
    def __init__(self):
        self.client_id = settings.LINUXDO_CLIENT_ID
        self.client_secret = settings.LINUXDO_CLIENT_SECRET
        self.redirect_uri = settings.LINUXDO_REDIRECT_URI
        self.proxy_url = settings.LINUXDO_PROXY_URL
        
        # Nếu chưa cấu hình, dùng giá trị mặc định (phát triển local)
        if not self.redirect_uri:
            self.redirect_uri = "http://localhost:8000/api/auth/callback"
            logger.warning(
                "⚠️  LINUXDO_REDIRECT_URI chưa được cấu hình, dùng giá trị mặc định: http://localhost:8000/api/auth/callback\n"
                "Nếu cần đăng nhập OAuth, vui lòng cấu hình trong file .env:\n"
                "Phát triển local: LINUXDO_REDIRECT_URI=http://localhost:8000/api/auth/callback\n"
                "Triển khai Docker: LINUXDO_REDIRECT_URI=https://your-domain.com/api/auth/callback"
            )
        
        # Cảnh báo: kiểm tra có đang dùng localhost không (ở môi trường không phải dev)
        if not settings.debug and "localhost" in self.redirect_uri.lower():
            logger.warning(
                f"⚠️  Môi trường production phát hiện dùng localhost làm địa chỉ callback: {self.redirect_uri}\n"
                "Điều này có thể khiến callback OAuth thất bại! Vui lòng dùng tên miền thực tế hoặc IP server."
            )

        if self.proxy_url:
            logger.info("LinuxDO OAuth đã bật proxy chuyên dụng: %s", self.proxy_url)

    def _client_options(self, **overrides) -> Dict[str, Any]:
        """Xây dựng tham số HTTP client chuyên dụng cho LinuxDO."""
        options: Dict[str, Any] = {
            "trust_env": False,
        }
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        options.update(overrides)
        return options
        
    def generate_state(self) -> str:
        """Sinh tham số state ngẫu nhiên"""
        return secrets.token_urlsafe(32)
    
    def get_authorization_url(self, state: str) -> str:
        """
        Lấy URL ủy quyền

        Args:
            state: tham số state ngẫu nhiên

        Returns:
            URL ủy quyền
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read",
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.AUTHORIZE_URL}?{query_string}"
    
    async def get_access_token(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Lấy access token bằng mã ủy quyền

        Args:
            code: mã ủy quyền

        Returns:
            dict chứa access_token, thất bại trả về None
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }
        
        try:
            async with httpx.AsyncClient(**self._client_options(timeout=30.0)) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error("Lấy access token thất bại: status=%s response=%s", response.status_code, safe_preview(response.text, 500))
                    return None
                     
        except Exception as e:
            logger.error("Lấy access token gặp ngoại lệ: %s", e)
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin người dùng bằng access token

        Args:
            access_token: access token

        Returns:
            dict thông tin người dùng, thất bại trả về None
        """
        try:
            # Thêm header request trình duyệt thật, tránh bị Cloudflare chặn
            headers = {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            
            # Không tự xử lý encoding, để httpx tự giải nén
            async with httpx.AsyncClient(**self._client_options(follow_redirects=True, timeout=30.0)) as client:
                response = await client.get(
                    self.USERINFO_URL,
                    headers=headers
                )
                
                logger.debug(
                    "Response lấy thông tin người dùng: status=%s headers=%s",
                    response.status_code,
                    safe_json_preview(dict(response.headers), 500),
                )
                
                if response.status_code == 200:
                    try:
                        user_data = response.json()
                        logger.debug("Lấy thông tin người dùng thành công: %s", safe_json_preview(user_data, 500))
                        return user_data
                    except Exception as json_error:
                        logger.error("Parse JSON thông tin người dùng thất bại: %s, response=%s", json_error, safe_preview(response.text, 300))
                        return None
                else:
                    logger.error("Lấy thông tin người dùng thất bại: status=%s response=%s", response.status_code, safe_preview(response.text, 300))
                    return None
                     
        except Exception as e:
            logger.error("Lấy thông tin người dùng gặp ngoại lệ: %s: %s", type(e).__name__, e, exc_info=True)
            return None
