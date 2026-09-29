"""
API quản lý cài đặt
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
import httpx
import json
import time

from app.database import get_db
from app.models.settings import Settings
from app.services.cover_generation_service import cover_generation_service
from app.schemas.settings import (
    SettingsCreate, SettingsUpdate, SettingsResponse,
    APIKeyPreset, APIKeyPresetConfig, PresetCreateRequest,
    PresetUpdateRequest, PresetResponse, PresetListResponse,
    ChapterAnalysisPresetSelectionRequest,
    SystemSMTPSettingsResponse, SystemSMTPSettingsUpdate, SMTPTestRequest
)
from app.user_manager import User
from app.logger import get_logger, safe_preview
from app.config import settings as app_settings, PROJECT_ROOT
from app.services.ai_service import AIService, create_user_ai_service, create_user_ai_service_with_mcp, normalize_provider
from app.services.email_service import email_service
from app.security import validate_ai_http_url

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["Quản lý cài đặt"])


class CoverSettingsTestRequest(BaseModel):
    cover_api_provider: str
    cover_api_key: str
    cover_api_base_url: Optional[str] = None
    cover_image_model: str


def read_env_defaults() -> Dict[str, Any]:
    """Đọc cấu hình mặc định từ file .env (chỉ đọc, không sửa)"""
    default_provider = (app_settings.default_ai_provider or "openai").lower().strip()
    provider_defaults = _resolve_provider_defaults(default_provider)
    return {
        "api_provider": default_provider,
        "api_key": "" if default_provider == "xiaomi_mimo" else provider_defaults["api_key"],
        "api_base_url": provider_defaults["api_base_url"],
        "llm_model": app_settings.default_model,
        "temperature": app_settings.default_temperature,
        "max_tokens": app_settings.default_max_tokens,
    }


def _normalize_raw_provider(provider: Optional[str]) -> str:
    """Giữ tên adapter tích hợp, chỉ chuẩn hóa chữ hoa/thường và khoảng trắng."""
    return (provider or "openai").lower().strip()


def _resolve_provider_defaults(provider: Optional[str]) -> Dict[str, str]:
    """Phân tích cấu hình mặc định từ biến môi trường theo provider, tránh hardcode key thật trong code."""
    raw_provider = _normalize_raw_provider(provider)
    if raw_provider == "xiaomi_mimo":
        return {
            "api_key": app_settings.xiaomi_mimo_api_key or "",
            "api_base_url": app_settings.xiaomi_mimo_base_url or "https://token-plan-cn.xiaomimimo.com/v1",
        }
    if raw_provider == "anthropic":
        return {
            "api_key": app_settings.anthropic_api_key or "",
            "api_base_url": app_settings.anthropic_base_url or "",
        }
    if raw_provider == "gemini":
        return {
            "api_key": app_settings.gemini_api_key or "",
            "api_base_url": app_settings.gemini_base_url or "",
        }
    return {
        "api_key": app_settings.openai_api_key or "",
        "api_base_url": app_settings.openai_base_url or "",
    }


def _apply_provider_defaults(provider: Optional[str], api_key: Optional[str], api_base_url: Optional[str]) -> Dict[str, str]:
    """Bổ sung key/base_url từ adapter tích hợp hoặc biến môi trường."""
    defaults = _resolve_provider_defaults(provider)
    return {
        "api_key": api_key or defaults["api_key"],
        "api_base_url": api_base_url or defaults["api_base_url"],
    }


def resolve_runtime_ai_config(provider: Optional[str], api_key: Optional[str], api_base_url: Optional[str]) -> Dict[str, str]:
    """Phân tích cấu hình AI runtime ở tầng API.

    Adapter tích hợp (như Xiaomi MiMo) chỉ giữ định danh provider và địa chỉ trong database/frontend, key thật
    chỉ đọc từ biến môi trường backend; khi truyền cho AIService sẽ chuyển thành provider tương thích tầng dưới (định dạng OpenAI).
    """
    raw_provider = _normalize_raw_provider(provider)
    resolved = _apply_provider_defaults(raw_provider, api_key, api_base_url)
    runtime_provider = "openai" if raw_provider == "xiaomi_mimo" else (normalize_provider(raw_provider) or "openai")
    return {
        "raw_provider": raw_provider,
        "api_provider": runtime_provider,
        "api_key": resolved["api_key"],
        "api_base_url": resolved["api_base_url"],
    }


def _safe_load_preferences(raw_preferences: Optional[str]) -> Dict[str, Any]:
    """Phân tích an toàn cài đặt tùy chọn của người dùng."""
    try:
        return json.loads(raw_preferences or '{}')
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_api_presets_payload(prefs: Dict[str, Any]) -> Dict[str, Any]:
    """Lấy cấu trúc tùy chọn preset API."""
    api_presets = prefs.get('api_presets')
    if not isinstance(api_presets, dict):
        api_presets = {'presets': [], 'version': '1.0'}
    if not isinstance(api_presets.get('presets'), list):
        api_presets['presets'] = []
    api_presets.setdefault('version', '1.0')
    return api_presets


def _get_chapter_analysis_preset_id(prefs: Dict[str, Any]) -> Optional[str]:
    """Đọc ID preset API chuyên dùng cho phân tích nội dung chương."""
    preset_id = prefs.get('chapter_analysis_preset_id')
    return preset_id if isinstance(preset_id, str) and preset_id.strip() else None


def _build_ai_service_from_config(
    *,
    config: Dict[str, Any],
    user_id: str,
    db: AsyncSession,
    enable_mcp: bool,
) -> AIService:
    """Tạo dịch vụ AI dựa trên cấu hình đã chỉ định."""
    resolved_config = resolve_runtime_ai_config(
        config.get('api_provider'),
        config.get('api_key'),
        config.get('api_base_url'),
    )
    return create_user_ai_service_with_mcp(
        api_provider=resolved_config["api_provider"],
        api_key=resolved_config["api_key"],
        api_base_url=resolved_config["api_base_url"],
        model_name=config.get('llm_model') or app_settings.default_model,
        temperature=config.get('temperature') if config.get('temperature') is not None else app_settings.default_temperature,
        max_tokens=config.get('max_tokens') if config.get('max_tokens') is not None else app_settings.default_max_tokens,
        user_id=user_id,
        db_session=db,
        system_prompt=config.get('system_prompt'),
        enable_mcp=enable_mcp,
    )


def require_login(request: Request):
    """Dependency: yêu cầu người dùng đã đăng nhập"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return request.state.user


def require_admin(user: User = Depends(require_login)):
    """Dependency: yêu cầu quyền quản trị viên"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được truy cập cài đặt hệ thống")
    return user


async def get_or_create_admin_settings(db: AsyncSession, user: User) -> Settings:
    """Lấy hoặc tạo cài đặt quản trị viên, cấu hình SMTP cấp hệ thống gắn trên bản ghi cài đặt của quản trị viên"""
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        env_defaults = read_env_defaults()
        settings = Settings(
            user_id=user.user_id,
            smtp_provider=app_settings.SMTP_PROVIDER,
            smtp_host=app_settings.SMTP_HOST,
            smtp_port=app_settings.SMTP_PORT,
            smtp_username=app_settings.SMTP_USERNAME,
            smtp_password=app_settings.SMTP_PASSWORD,
            smtp_use_tls=app_settings.SMTP_USE_TLS,
            smtp_use_ssl=app_settings.SMTP_USE_SSL,
            smtp_from_email=app_settings.SMTP_FROM_EMAIL,
            smtp_from_name=app_settings.SMTP_FROM_NAME,
            email_auth_enabled=app_settings.EMAIL_AUTH_ENABLED,
            email_register_enabled=app_settings.EMAIL_REGISTER_ENABLED,
            verification_code_ttl_minutes=app_settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES,
            verification_resend_interval_seconds=app_settings.EMAIL_VERIFICATION_RESEND_INTERVAL_SECONDS,
            **env_defaults
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


async def get_user_ai_service(
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
) -> AIService:
    """
    Dependency: lấy thể hiện dịch vụ AI của người dùng hiện tại (hỗ trợ tự động tải công cụ MCP)
    
    Đọc cài đặt người dùng từ database và tạo dịch vụ AI tương ứng.
    Tự động truyền user_id và db_session để AIService có thể tải các công cụ MCP mà người dùng đã cấu hình.
    Quyết định có bật MCP không dựa trên trạng thái tất cả plugin MCP của người dùng: nếu có plugin đang bật thì bật, ngược lại tắt.
    """
    from app.models.mcp_plugin import MCPPlugin
    
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Nếu người dùng chưa có cài đặt, đọc từ .env và lưu
        env_defaults = read_env_defaults()
        settings = Settings(
            user_id=user.user_id,
            **env_defaults
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Người dùng {user.user_id} lần đầu dùng dịch vụ AI, đã đồng bộ cài đặt từ .env vào database")
    
    # Truy vấn trạng thái tất cả plugin MCP của người dùng
    mcp_result = await db.execute(
        select(MCPPlugin).where(MCPPlugin.user_id == user.user_id)
    )
    mcp_plugins = mcp_result.scalars().all()
    
    # Kiểm tra có plugin MCP nào đang bật không
    enable_mcp = any(plugin.enabled for plugin in mcp_plugins) if mcp_plugins else False
    
    if mcp_plugins:
        enabled_count = sum(1 for p in mcp_plugins if p.enabled)
        logger.info(f"Người dùng {user.user_id} có {len(mcp_plugins)} plugin MCP, {enabled_count} đang bật, {enable_mcp} quyết định dùng MCP")
    else:
        logger.debug(f"Người dùng {user.user_id} chưa cấu hình plugin MCP, tắt MCP")
    
    # ✅ Dùng hàm factory hỗ trợ MCP để tạo thể hiện dịch vụ AI
    # Truyền user_id và db_session để AIService tự động tải các công cụ MCP mà người dùng đã cấu hình
    resolved_settings = resolve_runtime_ai_config(settings.api_provider, settings.api_key, settings.api_base_url)
    return create_user_ai_service_with_mcp(
        api_provider=resolved_settings["api_provider"],
        api_key=resolved_settings["api_key"],
        api_base_url=resolved_settings["api_base_url"],
        model_name=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        user_id=user.user_id,          # ✅ Truyền user_id
        db_session=db,                 # ✅ Truyền db_session
        system_prompt=settings.system_prompt,
        enable_mcp=enable_mcp,         # Quyết định động theo trạng thái plugin MCP
        disable_thinking=bool(getattr(settings, 'disable_thinking', False)),
    )


async def get_user_ai_service_from_db(user_id: str, db: AsyncSession) -> AIService:
    """
    Tạo trực tiếp thể hiện dịch vụ AI của người dùng từ database (dùng cho tác vụ nền, không phụ thuộc Depends của FastAPI)
    """
    return await get_user_ai_service_from_db_by_usage(user_id, db, usage="default")


async def get_user_ai_service_from_db_by_usage(
    user_id: str,
    db: AsyncSession,
    usage: str = "default"
) -> AIService:
    """Tạo thể hiện dịch vụ AI của người dùng theo mục đích sử dụng."""
    from app.models.mcp_plugin import MCPPlugin

    result = await db.execute(
        select(Settings).where(Settings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        env_defaults = read_env_defaults()
        settings = Settings(user_id=user_id, **env_defaults)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    mcp_result = await db.execute(
        select(MCPPlugin).where(MCPPlugin.user_id == user_id)
    )
    mcp_plugins = mcp_result.scalars().all()
    enable_mcp = any(plugin.enabled for plugin in mcp_plugins) if mcp_plugins else False

    if usage == "chapter_analysis":
        prefs = _safe_load_preferences(settings.preferences)
        api_presets = _get_api_presets_payload(prefs)
        presets = api_presets.get('presets', [])
        preset_id = _get_chapter_analysis_preset_id(prefs)
        if preset_id:
            target_preset = next((p for p in presets if p.get('id') == preset_id), None)
            if target_preset and isinstance(target_preset.get('config'), dict):
                logger.info(f"Người dùng {user_id} dùng preset API chuyên phân tích nội dung chương: {target_preset.get('name')}")
                return _build_ai_service_from_config(
                    config=target_preset['config'],
                    user_id=user_id,
                    db=db,
                    enable_mcp=enable_mcp,
                )
            logger.warning(f"Preset phân tích nội dung chương mà người dùng {user_id} đã cấu hình không tồn tại, dùng lại cấu hình API mặc định: {preset_id}")

    resolved_settings = resolve_runtime_ai_config(settings.api_provider, settings.api_key, settings.api_base_url)
    return create_user_ai_service_with_mcp(
        api_provider=resolved_settings["api_provider"],
        api_key=resolved_settings["api_key"],
        api_base_url=resolved_settings["api_base_url"],
        model_name=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        user_id=user_id,
        db_session=db,
        system_prompt=settings.system_prompt,
        enable_mcp=enable_mcp,
        disable_thinking=bool(getattr(settings, 'disable_thinking', False)),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy cài đặt của người dùng hiện tại
    Nếu người dùng chưa từng lưu cài đặt, tự động tạo từ .env và lưu vào database
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Nếu người dùng chưa từng lưu cài đặt, đọc cấu hình mặc định từ .env và lưu vào database
        env_defaults = read_env_defaults()
        logger.info(f"Người dùng {user.user_id} lần đầu lấy cài đặt, tự động đồng bộ từ .env vào database")
        
        # Tạo cài đặt mới và lưu vào database
        settings = Settings(
            user_id=user.user_id,
            **env_defaults
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Cài đặt của người dùng {user.user_id} đã được đồng bộ từ .env vào database")
    
    logger.info(f"Người dùng {user.user_id} lấy cài đặt đã lưu")
    return settings


@router.post("/cover/test")
async def test_cover_settings(
    data: CoverSettingsTestRequest,
    user: User = Depends(require_login),
):
    result = await cover_generation_service.test_cover_settings(
        provider=data.cover_api_provider,
        api_key=data.cover_api_key,
        api_base_url=data.cover_api_base_url,
        model=data.cover_image_model,
    )
    return {
        "success": result.success,
        "message": result.message,
        "provider": result.provider,
        "model": result.model,
    }


@router.get("/system/smtp", response_model=SystemSMTPSettingsResponse)
async def get_system_smtp_settings(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Lấy cài đặt SMTP hệ thống (chỉ quản trị viên)"""
    settings = await get_or_create_admin_settings(db, user)
    return settings


@router.put("/system/smtp", response_model=SystemSMTPSettingsResponse)
async def update_system_smtp_settings(
    data: SystemSMTPSettingsUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật cài đặt SMTP hệ thống (chỉ quản trị viên)"""
    settings = await get_or_create_admin_settings(db, user)
    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("smtp_provider") == "qq":
        update_data.setdefault("smtp_host", "smtp.qq.com")
        update_data.setdefault("smtp_port", 465)
        update_data.setdefault("smtp_use_ssl", True)
        update_data.setdefault("smtp_use_tls", False)

    if update_data.get("smtp_use_ssl") and update_data.get("smtp_use_tls"):
        raise HTTPException(status_code=400, detail="SSL và TLS không thể bật đồng thời")

    for key, value in update_data.items():
        setattr(settings, key, value)

    await db.commit()
    await db.refresh(settings)
    logger.info(f"Quản trị viên {user.user_id} cập nhật cài đặt SMTP hệ thống")
    return settings


@router.post("/system/smtp/test")
async def test_system_smtp_settings(
    data: SMTPTestRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Kiểm tra cài đặt SMTP hệ thống (gửi thật email kiểm tra)"""
    settings = await get_or_create_admin_settings(db, user)

    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(status_code=400, detail="Vui lòng hoàn thiện máy chủ SMTP, tên đăng nhập và mã ủy quyền trước")

    if settings.smtp_provider == "qq" and settings.smtp_host != "smtp.qq.com":
        raise HTTPException(status_code=400, detail="Máy chủ SMTP của email QQ phải là smtp.qq.com")

    if "@" not in data.to_email or "." not in data.to_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Định dạng email nhận kiểm tra không đúng")

    from_email = settings.smtp_from_email or settings.smtp_username
    if not from_email:
        raise HTTPException(status_code=400, detail="Vui lòng cấu hình email người gửi hoặc tên đăng nhập SMTP trước")

    subject = "Email kiểm tra SMTP của MuMuAINovel"
    text_body = (
        "Đây là email kiểm tra SMTP từ trang cài đặt hệ thống của MuMuAINovel.\n\n"
        f"Thời gian gửi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Nhà cung cấp SMTP: {settings.smtp_provider}\n"
        f"Máy chủ SMTP: {settings.smtp_host}:{settings.smtp_port}\n"
        "Nếu bạn nhận được email này, nghĩa là cấu hình SMTP hiện tại có thể gửi email bình thường."
    )
    html_body = f"""
    <div style=\"font-family: Arial, sans-serif; line-height: 1.7; color: #1f1f1f;\">
      <h2 style=\"margin-bottom: 12px;\">Email kiểm tra SMTP của MuMuAINovel</h2>
      <p>Đây là email kiểm tra SMTP từ trang cài đặt hệ thống.</p>
      <ul>
        <li><strong>Thời gian gửi:</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
        <li><strong>Nhà cung cấp SMTP:</strong>{settings.smtp_provider}</li>
        <li><strong>Máy chủ SMTP:</strong>{settings.smtp_host}:{settings.smtp_port}</li>
      </ul>
      <p>Nếu bạn nhận được email này, nghĩa là cấu hình SMTP hiện tại có thể gửi email bình thường.</p>
    </div>
    """

    try:
        await email_service.send_mail(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
            from_email=from_email,
            from_name=settings.smtp_from_name,
            to_email=data.to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    except Exception as exc:
        logger.exception(f"Gửi email kiểm tra SMTP thất bại: {exc}")
        raise HTTPException(status_code=400, detail=f"Gửi email kiểm tra SMTP thất bại: {str(exc)}") from exc

    return {
        "success": True,
        "message": f"Đã gửi email kiểm tra đến {data.to_email}, vui lòng kiểm tra hộp thư đến và thư rác",
        "provider": settings.smtp_provider,
        "host": settings.smtp_host,
        "port": settings.smtp_port,
    }


@router.post("", response_model=SettingsResponse)
async def save_settings(
    data: SettingsCreate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo hoặc cập nhật cài đặt của người dùng hiện tại (Upsert)
    Nếu cài đặt đã tồn tại thì cập nhật, ngược lại tạo cài đặt mới
    Chỉ lưu vào database
    
    Lưu ý: sau khi lưu cấu hình thủ công sẽ tự động hủy trạng thái kích hoạt của preset trước đó,
    vì cấu hình sửa thủ công có thể không nhất quán với preset
    """
    # Tìm cài đặt hiện có
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()
    
    # Chuẩn bị dữ liệu
    settings_dict = data.model_dump(exclude_unset=True)
    
    if settings:
        # Cập nhật cài đặt hiện có
        for key, value in settings_dict.items():
            setattr(settings, key, value)
        
        # Kiểm tra và hủy trạng thái kích hoạt preset
        # Vì người dùng đã sửa cấu hình thủ công, có thể không nhất quán với preset đã kích hoạt trước đó
        try:
            prefs = json.loads(settings.preferences or '{}')
            api_presets = prefs.get('api_presets', {'presets': [], 'version': '1.0'})
            presets = api_presets.get('presets', [])
            
            # Tìm preset đang kích hoạt và kiểm tra có nhất quán với cấu hình đang lưu không
            active_preset = next((p for p in presets if p.get('is_active')), None)
            if active_preset:
                preset_config = active_preset.get('config', {})
                # Kiểm tra cấu hình có thay đổi không
                config_changed = (
                    preset_config.get('api_provider') != settings_dict.get('api_provider', settings.api_provider) or
                    preset_config.get('api_key') != settings_dict.get('api_key', settings.api_key) or
                    preset_config.get('api_base_url') != settings_dict.get('api_base_url', settings.api_base_url) or
                    preset_config.get('llm_model') != settings_dict.get('llm_model', settings.llm_model) or
                    preset_config.get('temperature') != settings_dict.get('temperature', settings.temperature) or
                    preset_config.get('max_tokens') != settings_dict.get('max_tokens', settings.max_tokens)
                )
                
                if config_changed:
                    # Hủy trạng thái kích hoạt
                    active_preset['is_active'] = False
                    prefs['api_presets'] = api_presets
                    settings.preferences = json.dumps(prefs, ensure_ascii=False)
                    logger.info(f"Người dùng {user.user_id} sửa cấu hình thủ công, đã hủy trạng thái kích hoạt của preset {active_preset.get('name')}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Phân tích preferences của người dùng {user.user_id} thất bại: {e}")
        
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Người dùng {user.user_id} cập nhật cài đặt")
    else:
        # Tạo cài đặt mới
        settings = Settings(
            user_id=user.user_id,
            **settings_dict
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Người dùng {user.user_id} tạo cài đặt")
    
    return settings


@router.put("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật cài đặt của người dùng hiện tại
    Chỉ lưu vào database
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Cài đặt không tồn tại, vui lòng tạo cài đặt trước")
    
    # Cập nhật cài đặt
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    await db.commit()
    await db.refresh(settings)
    logger.info(f"Người dùng {user.user_id} cập nhật cài đặt")
    
    return settings


@router.delete("")
async def delete_settings(
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa cài đặt của người dùng hiện tại
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == user.user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Cài đặt không tồn tại")
    
    await db.delete(settings)
    await db.commit()
    logger.info(f"Người dùng {user.user_id} xóa cài đặt")
    
    return {"message": "Đã xóa cài đặt", "user_id": user.user_id}


@router.get("/models")
async def get_available_models(
    api_key: Optional[str] = "",
    api_base_url: Optional[str] = "",
    provider: str = "openai",
    user: User = Depends(require_login)
):
    """
    Lấy danh sách model khả dụng từ API đã cấu hình
    
    Args:
        api_key: Khóa API
        api_base_url: URL cơ sở của API
        provider: Nhà cung cấp API (openai, anthropic, azure, custom)
    
    Returns:
        Danh sách model
    """
    try:
        raw_provider = _normalize_raw_provider(provider)
        resolved_config = resolve_runtime_ai_config(raw_provider, api_key, api_base_url)
        provider = resolved_config["api_provider"]
        api_key = resolved_config["api_key"]
        api_base_url = validate_ai_http_url(resolved_config["api_base_url"])
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "openai" or provider == "azure" or provider == "custom":
                # Lấy danh sách model qua giao diện tương thích OpenAI
                url = f"{api_base_url.rstrip('/')}/models"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                logger.info(f"Đang lấy danh sách model từ {url}")
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                models = []
                
                if "data" in data and isinstance(data["data"], list):
                    for model in data["data"]:
                        model_id = model.get("id", "")
                        # Trả về tất cả model, không lọc
                        if model_id:
                            models.append({
                                "value": model_id,
                                "label": model_id,
                                "description": model.get("description", "") or f"Created: {model.get('created', 'N/A')}"
                            })
                
                if not models:
                    raise HTTPException(
                        status_code=404,
                        detail="Không lấy được danh sách model khả dụng từ API"
                    )
                
                logger.info(f"Lấy thành công {len(models)} model")
                return {
                    "provider": provider,
                    "models": models,
                    "count": len(models)
                }
                
            elif provider == "anthropic":
                # Anthropic models API
                url = f"{api_base_url.rstrip('/')}/v1/models"
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = [{"value": m["id"], "label": m["id"], "description": m.get("display_name", "")} for m in data.get("data", [])]
                return {"provider": provider, "models": models, "count": len(models)}
            
            elif provider == "gemini":
                # Gemini models API
                url = f"{api_base_url.rstrip('/')}/models?key={api_key}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        mid = m.get("name", "").replace("models/", "")
                        models.append({"value": mid, "label": m.get("displayName", mid), "description": ""})
                return {"provider": provider, "models": models, "count": len(models)}
            
            else:
                raise HTTPException(status_code=400, detail=f"Nhà cung cấp không được hỗ trợ: {provider}")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Lấy danh sách model thất bại (HTTP {e.response.status_code}): {safe_preview(e.response.text, 500)}")
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"Nhà cung cấp API này không hỗ trợ giao diện truy vấn danh sách model (/models trả về 404), vui lòng nhập tên model thủ công. Địa chỉ request hiện tại: {api_base_url.rstrip('/')}/models"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Không thể lấy danh sách model từ API (HTTP {e.response.status_code})"
        )
    except httpx.RequestError as e:
        logger.error(f"Request danh sách model thất bại: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Không thể kết nối đến API: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xảy ra lỗi khi lấy danh sách model: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Lấy danh sách model thất bại: {str(e)}"
        )


class ApiTestRequest(BaseModel):
    """Model request kiểm tra API"""
    api_key: Optional[str] = ""
    api_base_url: Optional[str] = ""
    provider: str
    llm_model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.post("/check-function-calling")
async def check_function_calling_support(data: ApiTestRequest):
    """
    Kiểm tra model có hỗ trợ Function Calling (gọi công cụ) không
    
    Phương pháp kiểm tra dựa trên best practice của ngành:
    1. Gửi request chứa định nghĩa công cụ
    2. Kiểm tra finish_reason của response có phải "tool_calls" không
    3. Xác minh response có chứa dữ liệu tool_calls hợp lệ không
    
    Args:
        data: Dữ liệu request chứa cấu hình API
    
    Returns:
        Kết quả kiểm tra bao gồm trạng thái hỗ trợ, thông tin chi tiết và gợi ý
    """
    raw_provider = _normalize_raw_provider(data.provider)
    resolved_config = resolve_runtime_ai_config(raw_provider, data.api_key, data.api_base_url)
    api_key = resolved_config["api_key"]
    api_base_url = resolved_config["api_base_url"]
    provider = resolved_config["api_provider"]
    llm_model = data.llm_model
    
    try:
        start_time = time.time()
        
        # Định nghĩa một công cụ kiểm tra đơn giản (tra cứu thời tiết)
        test_tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Lấy thông tin thời tiết hiện tại của thành phố đã chỉ định",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "Tên thành phố, ví dụ: Bắc Kinh, Thượng Hải, Thâm Quyến"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Đơn vị nhiệt độ"
                        }
                    },
                    "required": ["city"]
                }
            }
        }]
        
        # Prompt kiểm tra: cố ý thiết kế câu hỏi cần gọi công cụ
        test_prompt = "Cho tôi biết thời tiết hiện tại ở Bắc Kinh như thế nào?"
        
        logger.info(f"🧪 Bắt đầu kiểm tra hỗ trợ Function Calling")
        logger.info(f"  - Nhà cung cấp: {provider}")
        logger.info(f"  - Model: {llm_model}")
        logger.info(f"  - Công cụ kiểm tra: get_weather")
        
        # Tạo thể hiện dịch vụ AI tạm thời để kiểm tra
        test_service = AIService(
            api_provider=provider,
            api_key=api_key,
            api_base_url=api_base_url,
            default_model=llm_model,
            default_temperature=0.3,  # Dùng nhiệt độ thấp hơn để hành vi xác định hơn
            default_max_tokens=200
        )
        
        # Gửi request kiểm tra kèm công cụ
        response = await test_service.generate_text(
            prompt=test_prompt,
            provider=provider,
            model=llm_model,
            temperature=0.3,
            max_tokens=200,
            tools=test_tools,
            tool_choice="auto",  # Để model tự quyết định có dùng công cụ không
            auto_mcp=False  # Tắt tự động tải MCP
        )
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        # Phân tích response để xác định có hỗ trợ Function Calling không
        supported = False
        finish_reason = None
        tool_calls = None
        response_content = None
        
        if isinstance(response, dict):
            # Kiểm tra finish_reason (chuẩn OpenAI)
            finish_reason = response.get("finish_reason")
            
            # Kiểm tra có tool_calls không
            if "tool_calls" in response and response["tool_calls"]:
                supported = True
                tool_calls = response["tool_calls"]
                logger.info(f"✅ Phát hiện gọi công cụ: {len(tool_calls)} cái")
            
            # Ghi lại nội dung trả về (nếu có)
            if "content" in response:
                response_content = response["content"]
        elif isinstance(response, str):
            # Nếu chỉ trả về chuỗi, nghĩa là không hỗ trợ gọi công cụ
            response_content = response
        
        logger.info(f"  - Thời gian response: {response_time}ms")
        logger.info(f"  - finish_reason: {finish_reason}")
        logger.info(f"  - Trạng thái hỗ trợ: {'✅ Hỗ trợ' if supported else '❌ Không hỗ trợ'}")
        
        # Xây dựng thông tin trả về chi tiết
        result = {
            "success": True,
            "supported": supported,
            "message": "✅ Model hỗ trợ Function Calling" if supported else "❌ Model không hỗ trợ Function Calling",
            "response_time_ms": response_time,
            "provider": provider,
            "model": llm_model,
            "details": {
                "finish_reason": finish_reason,
                "has_tool_calls": bool(tool_calls),
                "tool_call_count": len(tool_calls) if tool_calls else 0,
                "test_tool": "get_weather",
                "test_prompt": test_prompt,
                "response_type": "tool_calls" if supported else "text"
            }
        }
        
        # Thêm chi tiết gọi công cụ
        if tool_calls:
            result["tool_calls"] = tool_calls
            result["suggestions"] = [
                "✅ Model này hỗ trợ Function Calling, có thể dùng plugin MCP bình thường",
                "Gợi ý: bật các plugin MCP cần thiết để mở rộng khả năng AI",
                "Nhắc: kiểm tra thành công phát hiện gọi công cụ, model có thể phân tích và dùng công cụ ngoài đúng cách"
            ]
        else:
            result["response_preview"] = response_content[:200] if response_content else None
            result["suggestions"] = [
                "❌ Model này không hỗ trợ Function Calling, không thể dùng tính năng plugin MCP",
                "Gợi ý: đổi sang model hỗ trợ gọi công cụ",
                "Model gợi ý: dòng GPT-4, GPT-4-turbo, Claude 3 Opus/Sonnet, Gemini 1.5 Pro, v.v.",
                "Giải thích: model trả về text thay vì gọi công cụ, cho thấy không hỗ trợ tính năng này"
            ]
        
        return result
        
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"❌ Lỗi cấu hình kiểm tra Function Calling: {error_msg}")
        return {
            "success": False,
            "supported": False,
            "message": "Lỗi cấu hình",
            "error": error_msg,
            "error_type": "ConfigurationError",
            "suggestions": [
                "Vui lòng kiểm tra API Key có đúng không",
                "Vui lòng xác nhận định dạng API Base URL có đúng không",
                "Vui lòng xác minh nhà cung cấp đã chọn có khớp với cấu hình không"
            ]
        }
        
    except TimeoutError as e:
        error_msg = str(e)
        logger.error(f"❌ Kiểm tra Function Calling hết thời gian: {error_msg}")
        return {
            "success": False,
            "supported": None,
            "message": "Kiểm tra hết thời gian",
            "error": error_msg,
            "error_type": "TimeoutError",
            "suggestions": [
                "Vui lòng kiểm tra kết nối mạng có bình thường không",
                "Vui lòng xác nhận dịch vụ API có truy cập được không",
                "Gợi ý: thử lại sau hoặc dùng môi trường mạng khác"
            ]
        }
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        logger.error(f"❌ Kiểm tra Function Calling thất bại: {error_msg}")
        logger.error(f"  - Loại lỗi: {error_type}")
        
        # Phân tích thông minh nguyên nhân lỗi
        suggestions = []
        if "tool" in error_msg.lower() or "function" in error_msg.lower():
            suggestions = [
                "Model này có thể không hỗ trợ tính năng Function Calling",
                "API trả về lỗi liên quan đến gọi công cụ",
                "Gợi ý: đổi sang model hỗ trợ gọi công cụ hoặc liên hệ nhà cung cấp API"
            ]
        elif "unauthorized" in error_msg.lower() or "401" in error_msg:
            suggestions = [
                "Xác thực API Key thất bại",
                "Vui lòng kiểm tra API Key có đúng và còn hiệu lực không",
                "Vui lòng xác nhận API Key có đủ quyền không"
            ]
        elif "not found" in error_msg.lower() or "404" in error_msg:
            suggestions = [
                "Model không tồn tại hoặc không khả dụng",
                "Vui lòng kiểm tra tên model có đúng không",
                "Vui lòng xác nhận model này có khả dụng trong API hiện tại không"
            ]
        else:
            suggestions = [
                "Gặp lỗi không xác định trong quá trình kiểm tra",
                "Gợi ý: kiểm tra tất cả tham số cấu hình có đúng không",
                "Nhắc: xem thông tin lỗi chi tiết để biết thêm"
            ]
        
        return {
            "success": False,
            "supported": False,
            "message": "Kiểm tra Function Calling thất bại",
            "error": error_msg,
            "error_type": error_type,
            "suggestions": suggestions
        }


@router.post("/test")
async def test_api_connection(data: ApiTestRequest):
    """
    Kiểm tra kết nối API và cấu hình có đúng không
    
    Args:
        data: Dữ liệu request chứa cấu hình API (bao gồm temperature và max_tokens)
    
    Returns:
        Kết quả kiểm tra bao gồm trạng thái, thời gian response và thông tin chi tiết
    """
    raw_provider = _normalize_raw_provider(data.provider)
    resolved_config = resolve_runtime_ai_config(raw_provider, data.api_key, data.api_base_url)
    api_key = resolved_config["api_key"]
    api_base_url = resolved_config["api_base_url"]
    provider = resolved_config["api_provider"]
    llm_model = data.llm_model
    # Dùng tham số frontend truyền sang, nếu không truyền thì dùng giá trị mặc định
    temperature = data.temperature if data.temperature is not None else 0.7
    max_tokens = data.max_tokens if data.max_tokens is not None else 2000
    import time
    
    try:
        start_time = time.time()
        
        # Tạo thể hiện dịch vụ AI tạm thời, dùng tham số frontend truyền sang
        test_service = AIService(
            api_provider=provider,
            api_key=api_key,
            api_base_url=api_base_url,
            default_model=llm_model,
            default_temperature=temperature,
            default_max_tokens=max_tokens
        )
        
        # Gửi request kiểm tra đơn giản
        test_prompt = "Vui lòng trả lời bằng một câu: kiểm tra thành công"
        
        logger.info(f"🧪 Bắt đầu kiểm tra kết nối API")
        logger.info(f"  - Nhà cung cấp: {provider}")
        logger.info(f"  - Model: {llm_model}")
        logger.info(f"  - Base URL: {api_base_url}")
        logger.info(f"  - Temperature: {temperature}")
        logger.info(f"  - Max Tokens: {max_tokens}")
        
        response = await test_service.generate_text(
            prompt=test_prompt,
            provider=provider,
            model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
            auto_mcp=False  # Khi kiểm tra không tải công cụ MCP
        )
        
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)  # Chuyển thành mili giây
        
        logger.info(f"✅ Kiểm tra API thành công")
        logger.info(f"  - Thời gian response: {response_time}ms")
        
        # Xử lý an toàn nội dung response (đảm bảo là chuỗi)
        response_str = str(response) if response else 'N/A'
        logger.info(f"  - Độ dài nội dung response: {len(response_str)}")
        
        return {
            "success": True,
            "message": "Kiểm tra kết nối API thành công",
            "response_time_ms": response_time,
            "provider": provider,
            "model": llm_model,
            "response_preview": response_str[:100] if len(response_str) > 100 else response_str,
            "details": {
                "api_available": True,
                "model_accessible": True,
                "response_valid": bool(response),
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        }
        
    except json.JSONDecodeError as e:
        # API upstream trả về HTTP thành công, nhưng body response không phải JSON hợp lệ.
        error_msg = str(e)
        logger.error(f"❌ Phân tích response API thất bại: {error_msg}")
        logger.error(f"  - Loại lỗi: {type(e).__name__}")
        return {
            "success": False,
            "message": "Phân tích response API thất bại",
            "error": error_msg,
            "error_type": "JSONDecodeError",
            "suggestions": [
                "Dịch vụ upstream có thể trả về response rỗng, trang lỗi HTML hoặc JSON không tương thích OpenAI",
                "Vui lòng xem log backend về lỗi phân tích JSON response AI HTTP, xác nhận status, content-type và body_preview",
                "Vui lòng xác nhận API Base URL có trỏ đúng giao diện /v1 tương thích OpenAI không"
            ]
        }

    except ValueError as e:
        # Lỗi cấu hình
        error_msg = str(e)
        logger.error(f"❌ Lỗi cấu hình API: {error_msg}")
        return {
            "success": False,
            "message": "Lỗi cấu hình API",
            "error": error_msg,
            "error_type": "ConfigurationError",
            "suggestions": [
                "Vui lòng kiểm tra API Key có đúng không",
                "Vui lòng xác nhận định dạng API Base URL đúng",
                "Vui lòng xác minh nhà cung cấp đã chọn có khớp không"
            ]
        }
        
    except TimeoutError as e:
        # Lỗi hết thời gian
        error_msg = str(e)
        logger.error(f"❌ Request API hết thời gian: {error_msg}")
        return {
            "success": False,
            "message": "Request API hết thời gian",
            "error": error_msg,
            "error_type": "TimeoutError",
            "suggestions": [
                "Vui lòng kiểm tra kết nối mạng",
                "Vui lòng xác nhận API Base URL có truy cập được không",
                "Nếu dùng proxy, vui lòng kiểm tra cài đặt proxy"
            ]
        }
        
    except Exception as e:
        # Lỗi khác
        error_msg = str(e)
        error_type = type(e).__name__
        
        logger.error(f"❌ Kiểm tra API thất bại: {error_msg}")
        logger.error(f"  - Loại lỗi: {error_type}")
        
        # Phân tích nguyên nhân lỗi và đưa gợi ý
        suggestions = []
        if "blocked" in error_msg.lower():
            suggestions = [
                "Request bị nhà cung cấp API chặn",
                "Nguyên nhân có thể: API Key bị giới hạn hoặc giới hạn khu vực",
                "Gợi ý: kiểm tra trạng thái API Key và số dư tài khoản",
                "Gợi ý: thử đổi API Base URL hoặc dùng proxy"
            ]
        elif "unauthorized" in error_msg.lower() or "401" in error_msg:
            suggestions = [
                "Xác thực API Key thất bại",
                "Gợi ý: kiểm tra API Key có đúng không",
                "Gợi ý: xác nhận API Key có hết hạn không"
            ]
        elif "not found" in error_msg.lower() or "404" in error_msg:
            suggestions = [
                "Endpoint API không tồn tại hoặc model không khả dụng",
                "Gợi ý: kiểm tra API Base URL có đúng không",
                "Gợi ý: xác nhận tên model có đúng không"
            ]
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            suggestions = [
                "Vượt giới hạn tần suất request API",
                "Gợi ý: thử lại sau",
                "Gợi ý: nâng cấp gói API"
            ]
        elif "insufficient" in error_msg.lower() or "quota" in error_msg.lower():
            suggestions = [
                "Không đủ quota API",
                "Gợi ý: kiểm tra số dư tài khoản",
                "Gợi ý: nạp tiền hoặc nâng cấp gói"
            ]
        else:
            suggestions = [
                "Vui lòng kiểm tra tất cả tham số cấu hình có đúng không",
                "Vui lòng xác nhận kết nối mạng bình thường",
                "Vui lòng xem thông tin lỗi chi tiết"
            ]
        
        return {
            "success": False,
            "message": "Kiểm tra API thất bại",
            "error": error_msg,
            "error_type": error_type,
            "suggestions": suggestions
        }


# ========== Quản lý preset cấu hình API (phương án không đổi database) ==========

async def get_user_settings(user_id: str, db: AsyncSession) -> Settings:
    """Lấy settings của người dùng, nếu không tồn tại thì tạo"""
    result = await db.execute(
        select(Settings).where(Settings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Tạo cài đặt mặc định
        env_defaults = read_env_defaults()
        settings = Settings(
            user_id=user_id,
            **env_defaults,
            preferences='{}'  # Khởi tạo là JSON rỗng
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info(f"Người dùng {user_id} truy cập lần đầu, đã tạo cài đặt mặc định")
    
    return settings


@router.get("/presets", response_model=PresetListResponse)
async def get_presets(
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả preset cấu hình API
    
    Đọc danh sách preset từ trường preferences
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        logger.warning(f"Trường preferences của người dùng {user.user_id} sai định dạng JSON, đặt lại thành rỗng")
        prefs = {}
    
    api_presets = _get_api_presets_payload(prefs)
    presets = api_presets.get('presets', [])
    chapter_analysis_preset_id = _get_chapter_analysis_preset_id(prefs)
    if chapter_analysis_preset_id and not any(p.get('id') == chapter_analysis_preset_id for p in presets):
        chapter_analysis_preset_id = None
    
    # Tìm preset đang kích hoạt
    active_preset_id = next(
        (p['id'] for p in presets if p.get('is_active')),
        None
    )
    
    logger.info(f"Người dùng {user.user_id} lấy danh sách preset, tổng {len(presets)} cái")
    
    return {
        "presets": presets,
        "total": len(presets),
        "active_preset_id": active_preset_id,
        "chapter_analysis_preset_id": chapter_analysis_preset_id
    }


@router.post("/presets", response_model=PresetResponse)
async def create_preset(
    data: PresetCreateRequest,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo preset mới
    
    Thêm preset vào JSON của trường preferences
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        prefs = {}
    
    api_presets = prefs.get('api_presets', {'presets': [], 'version': '1.0'})
    presets = api_presets.get('presets', [])
    
    # Tạo preset mới
    new_preset = {
        "id": f"preset_{int(datetime.now().timestamp() * 1000)}",
        "name": data.name,
        "description": data.description,
        "is_active": False,
        "created_at": datetime.now().isoformat(),
        "config": {
            **data.config.model_dump(),
            "api_provider": _normalize_raw_provider(data.config.api_provider)
        }
    }
    
    presets.append(new_preset)
    
    # Lưu lại vào preferences
    api_presets['presets'] = presets
    prefs['api_presets'] = api_presets
    settings.preferences = json.dumps(prefs, ensure_ascii=False)
    
    await db.commit()
    
    logger.info(f"Người dùng {user.user_id} tạo preset: {data.name}")
    return new_preset


@router.put("/presets/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: str,
    data: PresetUpdateRequest,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật preset
    
    Cập nhật preset đã chỉ định trong JSON của trường preferences
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Sai định dạng dữ liệu cấu hình")
    
    api_presets = prefs.get('api_presets', {'presets': [], 'version': '1.0'})
    presets = api_presets.get('presets', [])
    
    # Tìm và cập nhật preset
    target_preset = next((p for p in presets if p['id'] == preset_id), None)
    if not target_preset:
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
    
    # Cập nhật các trường
    if data.name is not None:
        target_preset['name'] = data.name
    if data.description is not None:
        target_preset['description'] = data.description
    if data.config is not None:
        target_preset['config'] = {
            **data.config.model_dump(),
            'api_provider': _normalize_raw_provider(data.config.api_provider)
        }
    
    # Lưu lại vào preferences
    prefs['api_presets'] = api_presets
    settings.preferences = json.dumps(prefs, ensure_ascii=False)
    
    await db.commit()
    
    logger.info(f"Người dùng {user.user_id} cập nhật preset: {preset_id}")
    return target_preset


@router.delete("/presets/{preset_id}")
async def delete_preset(
    preset_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa preset
    
    Xóa preset đã chỉ định khỏi JSON của trường preferences
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Sai định dạng dữ liệu cấu hình")
    
    api_presets = _get_api_presets_payload(prefs)
    presets = api_presets.get('presets', [])
    
    # Tìm preset
    target_preset = next((p for p in presets if p['id'] == preset_id), None)
    if not target_preset:
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
    
    # Kiểm tra có phải preset đang kích hoạt không
    if target_preset.get('is_active'):
        raise HTTPException(status_code=400, detail="Không thể xóa preset đang kích hoạt, vui lòng kích hoạt preset khác trước")
    
    # Xóa preset
    presets = [p for p in presets if p['id'] != preset_id]
    if prefs.get('chapter_analysis_preset_id') == preset_id:
        prefs.pop('chapter_analysis_preset_id', None)
    
    # Lưu lại vào preferences
    api_presets['presets'] = presets
    prefs['api_presets'] = api_presets
    settings.preferences = json.dumps(prefs, ensure_ascii=False)
    
    await db.commit()
    
    logger.info(f"Người dùng {user.user_id} xóa preset: {preset_id}")
    return {"message": "Đã xóa preset", "preset_id": preset_id}


@router.post("/presets/{preset_id}/activate")
async def activate_preset(
    preset_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Kích hoạt preset
    
    Áp dụng cấu hình của preset vào các trường chính của Settings
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Sai định dạng dữ liệu cấu hình")
    
    api_presets = prefs.get('api_presets', {'presets': [], 'version': '1.0'})
    presets = api_presets.get('presets', [])
    
    # Tìm preset mục tiêu
    target_preset = next((p for p in presets if p['id'] == preset_id), None)
    if not target_preset:
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
    
    # Áp dụng cấu hình vào các trường chính của Settings
    config = target_preset['config']
    resolved_config = _apply_provider_defaults(config.get('api_provider'), config.get('api_key'), config.get('api_base_url'))
    settings.api_provider = _normalize_raw_provider(config['api_provider'])
    settings.api_key = config.get('api_key') or ""
    settings.api_base_url = resolved_config["api_base_url"]
    settings.llm_model = config['llm_model']
    settings.temperature = config['temperature']
    settings.max_tokens = config['max_tokens']
    settings.system_prompt = config.get('system_prompt')
    
    # Cập nhật trạng thái is_active của tất cả preset
    for preset in presets:
        preset['is_active'] = (preset['id'] == preset_id)
    
    # Lưu lại vào preferences
    prefs['api_presets'] = api_presets
    settings.preferences = json.dumps(prefs, ensure_ascii=False)
    
    await db.commit()
    
    logger.info(f"Người dùng {user.user_id} kích hoạt preset: {target_preset['name']}")
    return {
        "message": "Đã kích hoạt preset",
        "preset_id": preset_id,
        "preset_name": target_preset['name']
    }


@router.put("/presets/usage/chapter-analysis")
async def set_chapter_analysis_preset_selection(
    data: ChapterAnalysisPresetSelectionRequest,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """Đặt preset API chuyên dùng cho phân tích nội dung chương; để trống thì dùng cấu hình API mặc định."""
    settings = await get_user_settings(user.user_id, db)
    prefs = _safe_load_preferences(settings.preferences)
    api_presets = _get_api_presets_payload(prefs)
    presets = api_presets.get('presets', [])

    preset_id = data.preset_id.strip() if data.preset_id else None
    preset_name = None
    if preset_id:
        target_preset = next((p for p in presets if p.get('id') == preset_id), None)
        if not target_preset:
            raise HTTPException(status_code=404, detail="Preset không tồn tại")
        prefs['chapter_analysis_preset_id'] = preset_id
        preset_name = target_preset.get('name')
    else:
        prefs.pop('chapter_analysis_preset_id', None)

    prefs['api_presets'] = api_presets
    settings.preferences = json.dumps(prefs, ensure_ascii=False)
    await db.commit()

    logger.info(f"Người dùng {user.user_id} đặt preset API phân tích nội dung chương: {preset_id or 'Cấu hình mặc định'}")
    return {
        "message": "Đã cập nhật cấu hình API phân tích nội dung chương",
        "chapter_analysis_preset_id": preset_id,
        "preset_name": preset_name
    }


@router.post("/presets/{preset_id}/test")
async def test_preset(
    preset_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Kiểm tra kết nối API của preset
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Phân tích preferences
    try:
        prefs = json.loads(settings.preferences or '{}')
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Sai định dạng dữ liệu cấu hình")
    
    api_presets = prefs.get('api_presets', {'presets': [], 'version': '1.0'})
    presets = api_presets.get('presets', [])
    
    # Tìm preset
    target_preset = next((p for p in presets if p['id'] == preset_id), None)
    if not target_preset:
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
    
    # Dùng logic test_api_connection hiện có
    # Đảm bảo truyền đầy đủ tham số, nhất quán với kiểm tra cấu hình hiện tại
    config = target_preset['config']
    test_request = ApiTestRequest(
        api_key=config['api_key'],
        api_base_url=config.get('api_base_url', ''),
        provider=config['api_provider'],
        llm_model=config['llm_model'],
        temperature=config.get('temperature'),   # Dùng tham số nhiệt độ trong preset
        max_tokens=config.get('max_tokens')      # Dùng tham số max tokens trong preset
    )
    
    logger.info(f"Người dùng {user.user_id} kiểm tra preset: {target_preset['name']}")
    return await test_api_connection(test_request)


@router.post("/presets/from-current", response_model=PresetResponse)
async def create_preset_from_current(
    name: str,
    description: Optional[str] = None,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo preset mới từ cấu hình hiện tại
    
    Phím tắt: lưu cấu hình đang kích hoạt thành preset mới
    """
    settings = await get_user_settings(user.user_id, db)
    
    # Đọc cấu hình từ các trường chính của Settings hiện tại
    current_config = APIKeyPresetConfig(
        api_provider=_normalize_raw_provider(settings.api_provider),
        api_key=settings.api_key,
        api_base_url=settings.api_base_url,
        llm_model=settings.llm_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        system_prompt=settings.system_prompt
    )
    
    # Tạo preset
    create_request = PresetCreateRequest(
        name=name,
        description=description,
        config=current_config
    )
    
    logger.info(f"Người dùng {user.user_id} tạo preset từ cấu hình hiện tại: {name}")
    return await create_preset(create_request, user, db)
