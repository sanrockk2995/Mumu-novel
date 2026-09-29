"""
API xác thực - Đăng nhập LinuxDO OAuth2 + đăng nhập tài khoản cục bộ + đăng ký/đăng nhập bằng mã xác minh email
"""
from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import hashlib
import secrets
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.oauth_service import LinuxDOOAuthService
from app.user_manager import user_manager, User as UserDTO
from app.user_password import password_manager
from app.logger import get_logger
from app.config import settings
from app.database import get_engine
from app.models.user import User as UserModel
from app.models.settings import Settings as SettingsModel
from app.services.email_service import email_service
from app.security import create_session_token

# Múi giờ Trung Quốc UTC+8
CHINA_TZ = timezone(timedelta(hours=8))


def get_china_now():
    """Lấy thời gian hiện tại của Trung Quốc"""
    return datetime.now(CHINA_TZ)


logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Xác thực"])

# Thể hiện dịch vụ OAuth2
oauth_service = LinuxDOOAuthService()

# Lưu trữ tạm state (môi trường production nên dùng Redis)
_state_storage = {}

# Lưu trữ tạm mã xác minh email (môi trường production nên dùng Redis)
_email_verification_storage = {}
MAX_VERIFICATION_ATTEMPTS = 5

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str


class LocalLoginRequest(BaseModel):
    """Yêu cầu đăng nhập cục bộ"""
    username: str
    password: str


class EmailLoginRequest(BaseModel):
    """Yêu cầu đăng nhập bằng mã xác minh email"""
    email: str
    code: str


class EmailSendCodeRequest(BaseModel):
    """Yêu cầu gửi mã xác minh email"""
    email: str
    scene: str = "register"


class EmailRegisterRequest(BaseModel):
    """Yêu cầu đăng ký email"""
    email: str
    code: str
    password: str
    display_name: Optional[str] = None


class EmailResetPasswordRequest(BaseModel):
    """Yêu cầu đặt lại mật khẩu bằng email"""
    email: str
    code: str
    new_password: str


class LocalLoginResponse(BaseModel):
    """Phản hồi đăng nhập"""
    success: bool
    message: str
    user: Optional[dict] = None


class SetPasswordRequest(BaseModel):
    """Yêu cầu đặt mật khẩu"""
    password: str


class SetPasswordResponse(BaseModel):
    """Phản hồi đặt mật khẩu"""
    success: bool
    message: str


class PasswordStatusResponse(BaseModel):
    """Phản hồi trạng thái mật khẩu"""
    has_password: bool
    has_custom_password: bool
    username: Optional[str] = None
    default_password: Optional[str] = None


async def _get_global_session() -> AsyncSession:
    """Lấy phiên database toàn cục"""
    engine = await get_engine("_global_users_")
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return session_maker()


async def _get_auth_runtime_settings() -> dict:
    """Lấy cấu hình runtime liên quan xác thực, ưu tiên đọc cài đặt hệ thống của quản trị viên, sau đó fallback về .env"""
    runtime = {
        "email_auth_enabled": settings.EMAIL_AUTH_ENABLED,
        "email_register_enabled": settings.EMAIL_REGISTER_ENABLED,
        "verification_code_ttl_minutes": settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES,
        "verification_resend_interval_seconds": settings.EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_username": settings.SMTP_USERNAME,
        "smtp_password": settings.SMTP_PASSWORD,
        "smtp_use_tls": settings.SMTP_USE_TLS,
        "smtp_use_ssl": settings.SMTP_USE_SSL,
        "smtp_from_email": settings.SMTP_FROM_EMAIL,
        "smtp_from_name": settings.SMTP_FROM_NAME,
    }

    async with await _get_global_session() as session:
        result = await session.execute(
            select(SettingsModel)
            .join(UserModel, UserModel.user_id == SettingsModel.user_id)
            .where(UserModel.is_admin == True)
            .order_by(SettingsModel.updated_at.desc())
            .limit(1)
        )
        admin_settings = result.scalar_one_or_none()

        if admin_settings:
            runtime.update({
                "email_auth_enabled": admin_settings.email_auth_enabled,
                "email_register_enabled": admin_settings.email_register_enabled,
                "verification_code_ttl_minutes": admin_settings.verification_code_ttl_minutes,
                "verification_resend_interval_seconds": admin_settings.verification_resend_interval_seconds,
                "smtp_host": admin_settings.smtp_host,
                "smtp_port": admin_settings.smtp_port,
                "smtp_username": admin_settings.smtp_username,
                "smtp_password": admin_settings.smtp_password,
                "smtp_use_tls": admin_settings.smtp_use_tls,
                "smtp_use_ssl": admin_settings.smtp_use_ssl,
                "smtp_from_email": admin_settings.smtp_from_email,
                "smtp_from_name": admin_settings.smtp_from_name,
            })

    return runtime


async def _find_user_by_email(email: str) -> Optional[UserDTO]:
    """Tìm người dùng theo email. Trường username của người dùng email chính là địa chỉ email."""
    normalized_email = email.strip().lower()
    async with await _get_global_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.username == normalized_email)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return UserDTO(**user.to_dict())


async def _create_email_user(email: str, display_name: Optional[str]) -> UserDTO:
    """Tạo người dùng đăng ký bằng email"""
    normalized_email = email.strip().lower()
    final_display_name = (display_name or normalized_email.split("@")[0]).strip()
    if not final_display_name:
        final_display_name = normalized_email.split("@")[0]

    user_id = f"email_{hashlib.md5(normalized_email.encode()).hexdigest()[:16]}"

    async with await _get_global_session() as session:
        existing = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = existing.scalar_one_or_none()

        if user:
            raise HTTPException(status_code=400, detail="Email này đã được đăng ký")

        user = UserModel(
            user_id=user_id,
            username=normalized_email,
            display_name=final_display_name,
            avatar_url=None,
            trust_level=1,
            is_admin=False,
            linuxdo_id=user_id,
            created_at=datetime.now(),
            last_login=datetime.now(),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        return UserDTO(**user.to_dict())


async def _touch_user_last_login(user_id: str):
    """Cập nhật thời gian đăng nhập gần nhất"""
    async with await _get_global_session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        user.last_login = datetime.now()
        await session.commit()


def _validate_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if not normalized_email or len(normalized_email) > 255 or not EMAIL_REGEX.match(normalized_email):
        raise HTTPException(status_code=400, detail="Vui lòng nhập địa chỉ email hợp lệ")
    return normalized_email


def _validate_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu phải dài ít nhất 6 ký tự")


def _is_session_cookie_secure() -> bool:
    """Xác định cookie phiên có bật cờ Secure không."""
    if settings.SESSION_COOKIE_SECURE is not None:
        return settings.SESSION_COOKIE_SECURE
    return not settings.debug


def _set_login_cookies(response: Response, user_id: str):
    """Đặt cookie đăng nhập"""
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    session_token = create_session_token(user_id, max_age)
    cookie_secure = _is_session_cookie_secure()
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=cookie_secure,
    )

    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())

    response.set_cookie(
        key="session_expire_at",
        value=str(expire_at),
        max_age=max_age,
        httponly=False,
        samesite="lax",
        secure=cookie_secure,
    )


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _build_verification_mail_content(scene: str, code: str, ttl_minutes: int) -> tuple[str, str, str]:
    scene_title_map = {
        "register": "Mã xác minh đăng ký email",
        "login": "Mã xác minh đăng nhập email",
        "reset_password": "Mã xác minh đặt lại mật khẩu",
    }
    scene_desc_map = {
        "register": "Chào mừng bạn đăng ký MuMuAINovel.",
        "login": "Bạn đang đăng nhập MuMuAINovel bằng mã xác minh email.",
        "reset_password": "Bạn đang đặt lại mật khẩu tài khoản MuMuAINovel.",
    }

    scene_title = scene_title_map.get(scene, "Mã xác minh email")
    scene_desc = scene_desc_map.get(scene, "Bạn đang thực hiện xác minh danh tính qua email.")
    subject = f"MuMuAINovel {scene_title}"
    text_body = (
        f"{scene_desc}\n\n"
        f"Mã xác minh của bạn là: {code}\n"
        f"Hiệu lực: {ttl_minutes} phút\n\n"
        f"Nếu đây không phải thao tác của bạn, vui lòng bỏ qua email này."
    )
    html_body = f"""
    <div style="font-family: Arial, PingFang SC, Microsoft YaHei, sans-serif; line-height: 1.8; color: #1f2937;">
      <h2 style="margin-bottom: 16px;">MuMuAINovel {scene_title}</h2>
      <p>{scene_desc}</p>
      <p>Mã xác minh của bạn là:</p>
      <div style="display: inline-block; padding: 10px 18px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; font-size: 28px; font-weight: 700; letter-spacing: 4px; color: #2563eb;">
        {code}
      </div>
      <p style="margin-top: 16px;">Hiệu lực: {ttl_minutes} phút</p>
      <p>Nếu đây không phải thao tác của bạn, vui lòng bỏ qua email này.</p>
    </div>
    """
    return subject, text_body, html_body


def _get_verification_storage_key(scene: str, email: str) -> str:
    return f"{scene}:{email}"


def _validate_verification_scene(scene: str) -> str:
    normalized_scene = scene.strip().lower()
    allowed_scenes = {"register", "login", "reset_password"}
    if normalized_scene not in allowed_scenes:
        raise HTTPException(status_code=400, detail="Kịch bản mã xác minh không được hỗ trợ")
    return normalized_scene


@router.get("/config")
async def get_auth_config():
    """Lấy thông tin cấu hình xác thực"""
    runtime = await _get_auth_runtime_settings()
    return {
        "local_auth_enabled": settings.LOCAL_AUTH_ENABLED,
        "linuxdo_enabled": bool(settings.LINUXDO_CLIENT_ID and settings.LINUXDO_CLIENT_SECRET),
        "email_auth_enabled": runtime["email_auth_enabled"],
        "email_register_enabled": runtime["email_register_enabled"],
    }


@router.post("/local/login", response_model=LocalLoginResponse)
async def local_login(request: LocalLoginRequest, response: Response):
    """Đăng nhập tài khoản cục bộ (hỗ trợ tài khoản quản trị viên cấu hình trong .env và tài khoản đã liên kết sau khi ủy quyền Linux DO)"""
    if not settings.LOCAL_AUTH_ENABLED:
        raise HTTPException(status_code=403, detail="Đăng nhập tài khoản cục bộ chưa được bật")

    logger.info(f"[Đăng nhập cục bộ] Thử đăng nhập tên đăng nhập: {request.username}")

    all_users = await user_manager.get_all_users()
    target_user = None

    for user in all_users:
        password_username = await password_manager.get_username(user.user_id)
        if user.username == request.username or password_username == request.username:
            target_user = user
            logger.info(f"[Đăng nhập cục bộ] Tìm thấy người dùng ủy quyền Linux DO: {user.user_id}")
            break

    if target_user:
        if not await password_manager.has_password(target_user.user_id):
            logger.warning(f"[Đăng nhập cục bộ] Người dùng {target_user.user_id} chưa đặt mật khẩu")
            raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

        if not await password_manager.verify_password(target_user.user_id, request.password):
            logger.warning(f"[Đăng nhập cục bộ] Người dùng {target_user.user_id} xác minh mật khẩu thất bại")
            raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

        logger.info(f"[Đăng nhập cục bộ] Người dùng ủy quyền Linux DO {target_user.user_id} đăng nhập thành công")
        user = target_user
    else:
        logger.info(f"[Đăng nhập cục bộ] Không tìm thấy người dùng Linux DO, kiểm tra tài khoản quản trị viên .env")

        if not settings.LOCAL_AUTH_USERNAME or not settings.LOCAL_AUTH_PASSWORD:
            raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

        user_id = f"local_{hashlib.md5(request.username.encode()).hexdigest()[:16]}"
        user = await user_manager.get_user(user_id)

        if not user:
            if request.username != settings.LOCAL_AUTH_USERNAME or request.password != settings.LOCAL_AUTH_PASSWORD:
                raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

            user = await user_manager.create_or_update_from_linuxdo(
                linuxdo_id=user_id,
                username=request.username,
                display_name=settings.LOCAL_AUTH_DISPLAY_NAME,
                avatar_url=None,
                trust_level=9
            )

            await password_manager.set_password(user.user_id, request.username, request.password)
            logger.info(f"[Đăng nhập cục bộ] Mật khẩu ban đầu của người dùng quản trị viên {user.user_id} đã được đặt vào database")
        else:
            if not await password_manager.verify_password(user.user_id, request.password):
                raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

            logger.info(f"[Đăng nhập cục bộ] Người dùng quản trị viên {user.user_id} đăng nhập thành công")

    _set_login_cookies(response, user.user_id)
    logger.info(f"[Đăng nhập] Người dùng {user.user_id} đăng nhập thành công, phiên hiệu lực {settings.SESSION_EXPIRE_MINUTES} phút")

    return LocalLoginResponse(
        success=True,
        message="Đăng nhập thành công",
        user=user.dict()
    )


@router.post("/email/send-code")
async def send_email_verification_code(request: EmailSendCodeRequest):
    """Gửi mã xác minh email (đăng ký / đăng nhập / đặt lại mật khẩu)"""
    runtime = await _get_auth_runtime_settings()
    if not runtime["email_auth_enabled"]:
        raise HTTPException(status_code=403, detail="Xác thực email chưa được bật")

    email = _validate_email(request.email)
    scene = _validate_verification_scene(request.scene)
    existing_user = await _find_user_by_email(email)

    if scene == "register":
        if not runtime["email_register_enabled"]:
            raise HTTPException(status_code=403, detail="Đăng ký email chưa được bật")
        if existing_user:
            raise HTTPException(status_code=400, detail="Email này đã được đăng ký")
    else:
        if not existing_user:
            raise HTTPException(status_code=404, detail="Email này chưa được đăng ký")

    if not runtime["smtp_host"] or not runtime["smtp_username"] or not runtime["smtp_password"]:
        raise HTTPException(status_code=400, detail="SMTP hệ thống chưa được cấu hình đầy đủ, tạm thời không thể gửi mã xác minh")

    now = get_china_now()
    storage_key = _get_verification_storage_key(scene, email)
    cached = _email_verification_storage.get(storage_key)
    resend_interval = runtime["verification_resend_interval_seconds"]
    ttl_minutes = runtime["verification_code_ttl_minutes"]

    if cached and cached["last_sent_at"] + timedelta(seconds=resend_interval) > now:
        remain_seconds = int((cached["last_sent_at"] + timedelta(seconds=resend_interval) - now).total_seconds())
        raise HTTPException(status_code=429, detail=f"Gửi mã xác minh quá thường xuyên, vui lòng thử lại sau {remain_seconds} giây")

    code = _generate_verification_code()
    expires_at = now + timedelta(minutes=ttl_minutes)
    subject, text_body, html_body = _build_verification_mail_content(scene, code, ttl_minutes)
    from_email = runtime["smtp_from_email"] or runtime["smtp_username"]

    await email_service.send_mail(
        host=runtime["smtp_host"],
        port=runtime["smtp_port"],
        username=runtime["smtp_username"],
        password=runtime["smtp_password"],
        use_tls=runtime["smtp_use_tls"],
        use_ssl=runtime["smtp_use_ssl"],
        from_email=from_email,
        from_name=runtime["smtp_from_name"],
        to_email=email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    _email_verification_storage[storage_key] = {
        "code": code,
        "expires_at": expires_at,
        "last_sent_at": now,
        "attempts": 0,
    }

    logger.info(f"[Mã xác minh email] Kịch bản={scene} đã gửi đến {email}")
    return {
        "success": True,
        "message": "Đã gửi mã xác minh, vui lòng kiểm tra email",
        "expire_in_seconds": ttl_minutes * 60,
        "resend_interval_seconds": resend_interval,
    }


@router.post("/email/register", response_model=LocalLoginResponse)
async def email_register(request: EmailRegisterRequest, response: Response):
    """Đăng ký bằng mã xác minh email và tự động đăng nhập"""
    runtime = await _get_auth_runtime_settings()
    if not runtime["email_auth_enabled"]:
        raise HTTPException(status_code=403, detail="Xác thực email chưa được bật")
    if not runtime["email_register_enabled"]:
        raise HTTPException(status_code=403, detail="Đăng ký email chưa được bật")

    email = _validate_email(request.email)
    code = request.code.strip()
    _validate_password(request.password)

    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Vui lòng nhập mã xác minh 6 chữ số")

    cached = _email_verification_storage.get(_get_verification_storage_key("register", email))
    if not cached:
        raise HTTPException(status_code=400, detail="Vui lòng gửi mã xác minh trước")

    now = get_china_now()
    if cached["expires_at"] < now:
        _email_verification_storage.pop(_get_verification_storage_key("register", email), None)
        raise HTTPException(status_code=400, detail="Mã xác minh đã hết hạn, vui lòng gửi lại")

    if cached["code"] != code:
        cached["attempts"] = cached.get("attempts", 0) + 1
        if cached["attempts"] >= MAX_VERIFICATION_ATTEMPTS:
            _email_verification_storage.pop(_get_verification_storage_key("register", email), None)
            raise HTTPException(status_code=429, detail="Nhập sai mã xác minh quá nhiều lần, vui lòng gửi lại")
        raise HTTPException(status_code=400, detail="Mã xác minh sai")

    existing_user = await _find_user_by_email(email)
    if existing_user:
        _email_verification_storage.pop(_get_verification_storage_key("register", email), None)
        raise HTTPException(status_code=400, detail="Email này đã được đăng ký")

    user = await _create_email_user(email, request.display_name)
    await password_manager.set_password(user.user_id, email, request.password)
    _email_verification_storage.pop(_get_verification_storage_key("register", email), None)

    _set_login_cookies(response, user.user_id)
    logger.info(f"[Đăng ký email] Người dùng {user.user_id} đăng ký và đăng nhập thành công")

    return LocalLoginResponse(
        success=True,
        message="Đăng ký thành công",
        user=user.dict()
    )


@router.post("/email/login", response_model=LocalLoginResponse)
async def email_login(request: EmailLoginRequest, response: Response):
    """Đăng nhập bằng mã xác minh email"""
    runtime = await _get_auth_runtime_settings()
    if not runtime["email_auth_enabled"]:
        raise HTTPException(status_code=403, detail="Xác thực email chưa được bật")

    email = _validate_email(request.email)
    code = request.code.strip()
    user = await _find_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Email này chưa được đăng ký")

    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Vui lòng nhập mã xác minh 6 chữ số")

    storage_key = _get_verification_storage_key("login", email)
    cached = _email_verification_storage.get(storage_key)
    if not cached:
        raise HTTPException(status_code=400, detail="Vui lòng gửi mã xác minh đăng nhập trước")

    now = get_china_now()
    if cached["expires_at"] < now:
        _email_verification_storage.pop(storage_key, None)
        raise HTTPException(status_code=400, detail="Mã xác minh đăng nhập đã hết hạn, vui lòng gửi lại")

    if cached["code"] != code:
        cached["attempts"] = cached.get("attempts", 0) + 1
        if cached["attempts"] >= MAX_VERIFICATION_ATTEMPTS:
            _email_verification_storage.pop(storage_key, None)
            raise HTTPException(status_code=429, detail="Nhập sai mã xác minh quá nhiều lần, vui lòng gửi lại")
        raise HTTPException(status_code=400, detail="Mã xác minh đăng nhập sai")

    _email_verification_storage.pop(storage_key, None)
    await _touch_user_last_login(user.user_id)
    latest_user = await user_manager.get_user(user.user_id)
    if latest_user:
        user = latest_user

    _set_login_cookies(response, user.user_id)
    logger.info(f"[Đăng nhập email] Người dùng {user.user_id} đăng nhập thành công")

    return LocalLoginResponse(
        success=True,
        message="Đăng nhập thành công",
        user=user.dict()
    )


@router.post("/email/reset-password")
async def email_reset_password(request: EmailResetPasswordRequest):
    """Đặt lại mật khẩu qua mã xác minh email"""
    runtime = await _get_auth_runtime_settings()
    if not runtime["email_auth_enabled"]:
        raise HTTPException(status_code=403, detail="Xác thực email chưa được bật")

    email = _validate_email(request.email)
    code = request.code.strip()
    _validate_password(request.new_password)

    user = await _find_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Email này chưa được đăng ký")

    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Vui lòng nhập mã xác minh 6 chữ số")

    storage_key = _get_verification_storage_key("reset_password", email)
    cached = _email_verification_storage.get(storage_key)
    if not cached:
        raise HTTPException(status_code=400, detail="Vui lòng gửi mã xác minh đặt lại mật khẩu trước")

    now = get_china_now()
    if cached["expires_at"] < now:
        _email_verification_storage.pop(storage_key, None)
        raise HTTPException(status_code=400, detail="Mã xác minh đặt lại mật khẩu đã hết hạn, vui lòng gửi lại")

    if cached["code"] != code:
        cached["attempts"] = cached.get("attempts", 0) + 1
        if cached["attempts"] >= MAX_VERIFICATION_ATTEMPTS:
            _email_verification_storage.pop(storage_key, None)
            raise HTTPException(status_code=429, detail="Nhập sai mã xác minh quá nhiều lần, vui lòng gửi lại")
        raise HTTPException(status_code=400, detail="Mã xác minh đặt lại mật khẩu sai")

    await password_manager.set_password(user.user_id, email, request.new_password)
    _email_verification_storage.pop(storage_key, None)
    logger.info(f"[Đặt lại mật khẩu email] Người dùng {user.user_id} đặt lại mật khẩu thành công")

    return {
        "success": True,
        "message": "Đặt lại mật khẩu thành công, vui lòng dùng mã xác minh mới để đăng nhập lại",
    }


@router.get("/linuxdo/url", response_model=AuthUrlResponse)
async def get_linuxdo_auth_url():
    """Lấy URL ủy quyền LinuxDO"""
    state = oauth_service.generate_state()
    auth_url = oauth_service.get_authorization_url(state)

    _state_storage[state] = True

    return AuthUrlResponse(auth_url=auth_url, state=state)


async def _handle_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """
    Xử lý callback LinuxDO OAuth2

    Sau khi thành công chuyển hướng về trang chủ frontend và đặt cookie user_id
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Ủy quyền thất bại: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Thiếu tham số code hoặc state")

    if state not in _state_storage:
        raise HTTPException(status_code=400, detail="Tham số state không hợp lệ")

    del _state_storage[state]

    token_data = await oauth_service.get_access_token(code)
    if not token_data or "access_token" not in token_data:
        raise HTTPException(status_code=400, detail="Lấy access token thất bại")

    access_token = token_data["access_token"]

    user_info = await oauth_service.get_user_info(access_token)
    if not user_info:
        raise HTTPException(status_code=400, detail="Lấy thông tin người dùng thất bại")

    linuxdo_id = str(user_info.get("id"))
    username = user_info.get("username", "")
    display_name = user_info.get("name", username)
    avatar_url = user_info.get("avatar_url")
    trust_level = user_info.get("trust_level", 0)

    user = await user_manager.create_or_update_from_linuxdo(
        linuxdo_id=linuxdo_id,
        username=username,
        display_name=display_name,
        avatar_url=avatar_url,
        trust_level=trust_level
    )

    is_first_login = not await password_manager.has_password(user.user_id)
    if is_first_login:
        logger.info(f"Người dùng {user.user_id} ({username}) đăng nhập lần đầu, cần khởi tạo mật khẩu")

    frontend_url = settings.FRONTEND_URL.rstrip('/')
    redirect_url = f"{frontend_url}/auth/callback"
    logger.info(f"OAuth callback thành công, chuyển hướng về frontend: {redirect_url}")
    redirect_response = RedirectResponse(url=redirect_url)

    _set_login_cookies(redirect_response, user.user_id)
    logger.info(f"[Đăng nhập OAuth] Người dùng {user.user_id} đăng nhập thành công, phiên hiệu lực {settings.SESSION_EXPIRE_MINUTES} phút")

    if is_first_login:
        redirect_response.set_cookie(
            key="first_login",
            value="true",
            max_age=300,
            httponly=False,
            samesite="lax",
            secure=_is_session_cookie_secure(),
        )
        logger.info(f"[Đăng nhập OAuth] Người dùng {user.user_id} đăng nhập lần đầu, đã đặt cờ first_login")

    return redirect_response


@router.get("/linuxdo/callback")
async def linuxdo_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """Xử lý callback LinuxDO OAuth2 (đường dẫn chuẩn)"""
    return await _handle_callback(code, state, error, response)


@router.get("/callback")
async def callback_alias(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    response: Response = None
):
    """Xử lý callback LinuxDO OAuth2 (đường dẫn tương thích)"""
    return await _handle_callback(code, state, error, response)


@router.post("/refresh")
async def refresh_session(request: Request, response: Response):
    """Làm mới phiên - kéo dài trạng thái đăng nhập"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập, không thể làm mới phiên")

    user = request.state.user

    session_expire_at = request.cookies.get("session_expire_at")
    if session_expire_at:
        try:
            expire_timestamp = int(session_expire_at)
            current_timestamp = int(get_china_now().timestamp())
            remaining_minutes = (expire_timestamp - current_timestamp) / 60

            if remaining_minutes > settings.SESSION_REFRESH_THRESHOLD_MINUTES:
                logger.info(f"[Làm mới phiên] Người dùng {user.user_id} phiên vẫn hiệu lực, còn {int(remaining_minutes)} phút")
                return {
                    "message": "Phiên vẫn hiệu lực, không cần làm mới",
                    "remaining_minutes": int(remaining_minutes),
                    "expire_at": expire_timestamp
                }
        except (ValueError, TypeError):
            pass

    _set_login_cookies(response, user.user_id)

    china_now = get_china_now()
    expire_time = china_now + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    expire_at = int(expire_time.timestamp())

    logger.info(f"[Làm mới phiên] Người dùng: {user.user_id}")
    logger.info(f"[Làm mới phiên] Thời gian hiện tại Trung Quốc: {china_now.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    logger.info(f"[Làm mới phiên] Thời gian hết hạn Trung Quốc: {expire_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    logger.info(f"[Làm mới phiên] Timestamp hết hạn (giây): {expire_at}")
    logger.info(f"[Làm mới phiên] Cookie max_age (giây): {settings.SESSION_EXPIRE_MINUTES * 60}")

    logger.info(f"Người dùng {user.user_id} làm mới phiên thành công")
    return {
        "message": "Làm mới phiên thành công",
        "expire_at": expire_at,
        "remaining_minutes": settings.SESSION_EXPIRE_MINUTES
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Đăng xuất"""
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        logger.info(f"[Đăng xuất] Người dùng {user_id} đăng xuất")

    response.delete_cookie("user_id")
    response.delete_cookie("session_token")
    response.delete_cookie("session_expire_at")
    return {"message": "Đăng xuất thành công"}


@router.get("/user")
async def get_current_user(request: Request):
    """Lấy thông tin người dùng đang đăng nhập"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    return request.state.user.dict()


@router.get("/password/status", response_model=PasswordStatusResponse)
async def get_password_status(request: Request):
    """Lấy trạng thái mật khẩu của người dùng hiện tại"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user = request.state.user
    has_password = await password_manager.has_password(user.user_id)
    has_custom = await password_manager.has_custom_password(user.user_id)
    username = await password_manager.get_username(user.user_id)

    default_password = None

    return PasswordStatusResponse(
        has_password=has_password,
        has_custom_password=has_custom,
        username=username or user.username,
        default_password=default_password
    )


@router.post("/password/set", response_model=SetPasswordResponse)
async def set_user_password(request: Request, password_req: SetPasswordRequest):
    """Đặt mật khẩu cho người dùng hiện tại"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user = request.state.user
    _validate_password(password_req.password)

    await password_manager.set_password(user.user_id, user.username, password_req.password)
    logger.info(f"Người dùng {user.user_id} ({user.username}) đã đặt mật khẩu tùy chỉnh")

    return SetPasswordResponse(
        success=True,
        message="Đặt mật khẩu thành công"
    )


@router.post("/password/initialize", response_model=SetPasswordResponse)
async def initialize_user_password(request: Request, password_req: SetPasswordRequest):
    """
    Khởi tạo mật khẩu cho người dùng đăng nhập lần đầu

    Dành cho người dùng lần đầu đăng nhập qua ủy quyền Linux DO, có thể chọn đặt mật khẩu tùy chỉnh hoặc dùng mật khẩu mặc định
    """
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user = request.state.user

    if await password_manager.has_password(user.user_id):
        raise HTTPException(status_code=400, detail="Mật khẩu đã được khởi tạo, vui lòng dùng chức năng đổi mật khẩu")

    _validate_password(password_req.password)

    await password_manager.set_password(user.user_id, user.username, password_req.password)
    logger.info(f"Người dùng {user.user_id} ({user.username}) khởi tạo mật khẩu thành công")

    return SetPasswordResponse(
        success=True,
        message="Khởi tạo mật khẩu thành công"
    )


@router.post("/bind/login", response_model=LocalLoginResponse)
async def bind_account_login(request: LocalLoginRequest, response: Response):
    """Đăng nhập bằng tài khoản mật khẩu đã liên kết (tài khoản liên kết sau khi ủy quyền LinuxDO)"""
    all_users = await user_manager.get_all_users()
    target_user = None

    logger.info(f"[Đăng nhập tài khoản liên kết] Thử đăng nhập tên đăng nhập: {request.username}")
    logger.info(f"[Đăng nhập tài khoản liên kết] Hiện có {len(all_users)} người dùng")

    for user in all_users:
        password_username = await password_manager.get_username(user.user_id)
        logger.info(f"[Đăng nhập tài khoản liên kết] Kiểm tra người dùng {user.user_id}: users.username={user.username}, passwords.username={password_username}")

        if user.username == request.username or password_username == request.username:
            target_user = user
            logger.info(f"[Đăng nhập tài khoản liên kết] Tìm thấy người dùng khớp: {user.user_id}")
            break

    if not target_user:
        logger.warning(f"[Đăng nhập tài khoản liên kết] Tên đăng nhập {request.username} không tìm thấy")
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

    has_pwd = await password_manager.has_password(target_user.user_id)
    if not has_pwd:
        logger.warning(f"[Đăng nhập tài khoản liên kết] Người dùng {target_user.user_id} chưa đặt mật khẩu")
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

    is_valid = await password_manager.verify_password(target_user.user_id, request.password)
    logger.info(f"[Đăng nhập tài khoản liên kết] Người dùng {target_user.user_id} kết quả xác minh mật khẩu: {is_valid}")

    if not is_valid:
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu sai")

    _set_login_cookies(response, target_user.user_id)
    logger.info(f"[Đăng nhập tài khoản liên kết] Người dùng {target_user.user_id} ({request.username}) đăng nhập thành công, phiên hiệu lực {settings.SESSION_EXPIRE_MINUTES} phút")

    return LocalLoginResponse(
        success=True,
        message="Đăng nhập thành công",
        user=target_user.dict()
    )
