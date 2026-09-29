"""API quản lý plugin MCP

Sau tái cấu trúc dùng MCPClientFacade thống nhất để quản lý mọi thao tác MCP.
"""
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, update
from typing import List, Optional
from datetime import datetime

from app.database import get_db, get_engine
from app.models.mcp_plugin import MCPPlugin
from app.schemas.mcp_plugin import (
    MCPPluginCreate,
    MCPPluginSimpleCreate,
    MCPPluginUpdate,
    MCPPluginResponse,
    MCPToolCall,
    MCPTestResult
)
import json
from app.user_manager import User
from app.mcp import mcp_client, MCPPluginConfig, PluginStatus
from app.services.mcp_test_service import mcp_test_service
from app.logger import get_logger
from app.security import validate_public_http_url

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp/plugins", tags=["Quản lý plugin MCP"])

HTTP_PLUGIN_TYPES = {"http", "streamable_http", "sse"}


def _validate_mcp_server_url(plugin_type: str, server_url: Optional[str]) -> Optional[str]:
    if plugin_type in HTTP_PLUGIN_TYPES:
        if not server_url:
            raise HTTPException(status_code=400, detail=f"Plugin loại {plugin_type} phải cung cấp server_url")
        return validate_public_http_url(server_url)
    return server_url


def require_login(request: Request) -> User:
    """Dependency: yêu cầu người dùng đã đăng nhập"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return request.state.user


async def _register_plugin_background(
    user_id: str,
    plugin_name: str,
    plugin_type: str,
    server_url: str,
    headers: Optional[dict],
    config: Optional[dict],
    max_retries: int = 2,
    retry_delay: float = 3.0
):
    """
    Tác vụ nền: đăng ký plugin MCP và cập nhật trạng thái database (kèm thử lại)

    Thực hiện kết nối MCP trong tác vụ độc lập để tránh chặn xử lý request.
    Khi kết nối thất bại sẽ tự động thử lại, tăng khả năng chịu lỗi với sự cố mạng tạm thời.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"Thử lại đăng ký nền plugin MCP ({attempt}/{max_retries}): {plugin_name}")
                await asyncio.sleep(retry_delay)
            else:
                logger.info(f"Đăng ký nền plugin MCP: {plugin_name}")

            if plugin_type in HTTP_PLUGIN_TYPES and server_url:
                server_url = _validate_mcp_server_url(plugin_type, server_url)
                success = await mcp_client.register(MCPPluginConfig(
                    user_id=user_id,
                    plugin_name=plugin_name,
                    url=server_url,
                    plugin_type=plugin_type,
                    headers=headers,
                    timeout=config.get('timeout', 60.0) if config else 60.0
                ))
            else:
                success = False

            if success:
                # Cập nhật trạng thái database thành active
                engine = await get_engine(user_id)
                AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with AsyncSessionLocal() as db:
                    stmt = (
                        update(MCPPlugin)
                        .where(MCPPlugin.user_id == user_id, MCPPlugin.plugin_name == plugin_name)
                        .values(status="active", last_error=None)
                    )
                    await db.execute(stmt)
                    await db.commit()
                logger.info(f"Đăng ký nền plugin MCP thành công: {plugin_name}")
                return
            else:
                last_error = "Kết nối thất bại"

        except Exception as e:
            last_error = str(e)
            logger.warning(f"Ngoại lệ khi đăng ký nền plugin MCP (lần thử {attempt + 1}/{max_retries + 1}): {plugin_name}, lỗi: {e}")

    # Tất cả lần thử lại đều thất bại, cập nhật trạng thái database thành error
    logger.error(f"Đăng ký nền plugin MCP thất bại hoàn toàn (đã thử lại {max_retries} lần): {plugin_name}, lỗi: {last_error}")
    try:
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with AsyncSessionLocal() as db:
            stmt = (
                update(MCPPlugin)
                .where(MCPPlugin.user_id == user_id, MCPPlugin.plugin_name == plugin_name)
                .values(status="error", last_error=str(last_error)[:500] if last_error else "Kết nối thất bại")
            )
            await db.execute(stmt)
            await db.commit()
    except Exception as db_error:
        logger.error(f"Cập nhật trạng thái plugin thất bại: {db_error}")


async def _unregister_plugin_safe(user_id: str, plugin_name: str):
    """Hủy đăng ký plugin MCP một cách an toàn trong nền"""
    try:
        await mcp_client.unregister(user_id, plugin_name)
        logger.info(f"Hủy đăng ký nền plugin MCP thành công: {plugin_name}")
    except Exception as e:
        logger.warning(f"Hủy đăng ký nền plugin MCP lỗi: {plugin_name}, lỗi: {e}")


async def _register_plugin_to_facade(plugin: MCPPlugin, user_id: str) -> bool:
    """
    Đăng ký plugin vào facade thống nhất

    Args:
        plugin: Đối tượng plugin
        user_id: ID người dùng

    Returns:
        Đăng ký có thành công không
    """
    if plugin.plugin_type in HTTP_PLUGIN_TYPES and plugin.server_url:
        server_url = _validate_mcp_server_url(plugin.plugin_type, plugin.server_url)
        return await mcp_client.register(MCPPluginConfig(
            user_id=user_id,
            plugin_name=plugin.plugin_name,
            url=server_url,
            plugin_type=plugin.plugin_type,
            headers=plugin.headers,
            timeout=plugin.config.get('timeout', 60.0) if plugin.config else 60.0
        ))
    else:
        logger.warning(f"Loại plugin tạm thời chưa hỗ trợ: {plugin.plugin_type}")
        return False


@router.get("", response_model=List[MCPPluginResponse])
async def list_plugins(
    enabled_only: bool = Query(False, description="Chỉ trả về plugin đã bật"),
    category: Optional[str] = Query(None, description="Lọc theo danh mục"),
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả plugin MCP của người dùng
    """
    query = select(MCPPlugin).where(MCPPlugin.user_id == user.user_id)

    if enabled_only:
        query = query.where(MCPPlugin.enabled == True)

    if category:
        query = query.where(MCPPlugin.category == category)

    query = query.order_by(MCPPlugin.sort_order, MCPPlugin.created_at)

    result = await db.execute(query)
    plugins = result.scalars().all()

    logger.info(f"Người dùng {user.user_id} truy vấn danh sách plugin, tổng cộng {len(plugins)} plugin")
    return plugins


@router.post("", response_model=MCPPluginResponse)
async def create_plugin(
    data: MCPPluginCreate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo plugin MCP mới
    """
    # Kiểm tra tên plugin đã tồn tại chưa
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.user_id == user.user_id,
            MCPPlugin.plugin_name == data.plugin_name
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail=f"Tên plugin đã tồn tại: {data.plugin_name}")

    # Tạo dữ liệu plugin
    plugin_data = data.model_dump()
    plugin_data["server_url"] = _validate_mcp_server_url(
        plugin_data.get("plugin_type", "http"),
        plugin_data.get("server_url")
    )

    # Nếu không cung cấp display_name, dùng plugin_name làm mặc định
    if not plugin_data.get("display_name"):
        plugin_data["display_name"] = plugin_data["plugin_name"]

    # Tạo plugin
    plugin = MCPPlugin(
        user_id=user.user_id,
        **plugin_data
    )

    # Nếu bật, đặt trạng thái pending chờ kết nối nền
    if plugin.enabled:
        plugin.status = "pending"

    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)

    # Nếu bật, đăng ký nền vào facade thống nhất (tránh thao tác MCP chặn gây timeout)
    if plugin.enabled:
        asyncio.create_task(_register_plugin_background(
            user_id=user.user_id,
            plugin_name=plugin.plugin_name,
            plugin_type=plugin.plugin_type,
            server_url=plugin.server_url,
            headers=plugin.headers,
            config=plugin.config
        ))

    logger.info(f"Người dùng {user.user_id} tạo plugin: {plugin.plugin_name} (đăng ký MCP thực hiện trong nền)")
    return plugin


@router.post("/simple", response_model=MCPPluginResponse)
async def create_plugin_simple(
    data: MCPPluginSimpleCreate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo hoặc cập nhật plugin qua JSON cấu hình MCP chuẩn (bản đơn giản)

    Định dạng chấp nhận:
    {
      "config_json": '{"mcpServers": {"exa": {"type": "http", "url": "...", "headers": {}}}}',
      "category": "search"
    }

    Tự động trích tên plugin từ mcpServers (lấy key đầu tiên)
    Nếu plugin đã tồn tại thì cập nhật; nếu không thì tạo mới
    """
    try:
        # Phân tích JSON cấu hình
        config = json.loads(data.config_json)

        # Kiểm tra định dạng
        if "mcpServers" not in config:
            raise HTTPException(status_code=400, detail="JSON cấu hình phải chứa trường mcpServers")

        servers = config["mcpServers"]
        if not servers or len(servers) == 0:
            raise HTTPException(status_code=400, detail="mcpServers không được để trống")

        # Tự động trích tên plugin đầu tiên
        plugin_name = list(servers.keys())[0]
        server_config = servers[plugin_name]

        logger.info(f"Trích tên plugin từ cấu hình: {plugin_name}")

        # Trích cấu hình
        server_type = server_config.get("type", "http")

        if server_type not in ["http", "stdio", "streamable_http", "sse"]:
            raise HTTPException(status_code=400, detail=f"Loại server không được hỗ trợ: {server_type}")

        # Kiểm tra tên plugin đã tồn tại chưa
        result = await db.execute(
            select(MCPPlugin).where(
                MCPPlugin.user_id == user.user_id,
                MCPPlugin.plugin_name == plugin_name
            )
        )
        existing = result.scalar_one_or_none()

        # Xây dựng dữ liệu plugin
        plugin_data = {
            "plugin_name": plugin_name,
            "display_name": plugin_name,
            "plugin_type": server_type,
            "enabled": data.enabled,
            "category": data.category,
            "sort_order": 0
        }

        if server_type in HTTP_PLUGIN_TYPES:
            plugin_data["server_url"] = _validate_mcp_server_url(server_type, server_config.get("url"))
            plugin_data["headers"] = server_config.get("headers", {})

        elif server_type == "stdio":
            plugin_data["command"] = server_config.get("command")
            plugin_data["args"] = server_config.get("args", [])
            plugin_data["env"] = server_config.get("env", {})

            if not plugin_data["command"]:
                raise HTTPException(status_code=400, detail="Plugin loại Stdio phải cung cấp trường command")

        if existing:
            # Cập nhật plugin hiện có
            logger.info(f"Plugin {plugin_name} đã tồn tại, thực hiện cập nhật")

            # Lưu trạng thái cũ
            old_enabled = existing.enabled
            old_plugin_name = existing.plugin_name

            # Cập nhật các trường
            for key, value in plugin_data.items():
                setattr(existing, key, value)

            # Đặt trạng thái pending, chờ kết nối nền
            if plugin_data.get("enabled"):
                existing.status = "pending"

            plugin = existing
            await db.commit()
            await db.refresh(plugin)

            # Thực hiện thao tác MCP trong nền (không chặn request)
            if old_enabled:
                # Hủy đăng ký plugin cũ (dùng create_task chạy nền)
                asyncio.create_task(_unregister_plugin_safe(user.user_id, old_plugin_name))

            if plugin.enabled:
                # Đăng ký nền plugin mới
                asyncio.create_task(_register_plugin_background(
                    user_id=user.user_id,
                    plugin_name=plugin.plugin_name,
                    plugin_type=plugin.plugin_type,
                    server_url=plugin.server_url,
                    headers=plugin.headers,
                    config=plugin.config
                ))

            logger.info(f"Người dùng {user.user_id} cập nhật plugin: {plugin_name}")
        else:
            # Tạo plugin mới
            plugin = MCPPlugin(
                user_id=user.user_id,
                **plugin_data
            )

            # Đặt trạng thái pending, chờ kết nối nền
            if plugin_data.get("enabled"):
                plugin.status = "pending"

            db.add(plugin)
            await db.commit()
            await db.refresh(plugin)

            # Đăng ký MCP trong nền (không chặn request)
            if plugin.enabled:
                asyncio.create_task(_register_plugin_background(
                    user_id=user.user_id,
                    plugin_name=plugin.plugin_name,
                    plugin_type=plugin.plugin_type,
                    server_url=plugin.server_url,
                    headers=plugin.headers,
                    config=plugin.config
                ))

            logger.info(f"Người dùng {user.user_id} tạo plugin qua cấu hình đơn giản: {plugin_name}")

        return plugin

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Định dạng JSON cấu hình sai: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tạo plugin thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tạo plugin thất bại: {str(e)}")


@router.get("/{plugin_id}", response_model=MCPPluginResponse)
async def get_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy chi tiết plugin
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    return plugin


@router.put("/{plugin_id}", response_model=MCPPluginResponse)
async def update_plugin(
    plugin_id: str,
    data: MCPPluginUpdate,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật cấu hình plugin
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    # Cập nhật các trường
    update_data = data.model_dump(exclude_unset=True)
    target_type = update_data.get("plugin_type", plugin.plugin_type)
    if "server_url" in update_data or target_type in HTTP_PLUGIN_TYPES:
        update_data["server_url"] = _validate_mcp_server_url(
            target_type,
            update_data.get("server_url", plugin.server_url)
        )
    for key, value in update_data.items():
        setattr(plugin, key, value)

    # Nếu bật, đặt trạng thái pending chờ kết nối nền
    if plugin.enabled:
        plugin.status = "pending"
        plugin.last_error = None

    await db.commit()
    await db.refresh(plugin)

    # Nếu plugin đã bật, đăng ký lại kết nối MCP trong nền
    if plugin.enabled:
        # Hủy đăng ký nền kết nối cũ trước
        asyncio.create_task(_unregister_plugin_safe(user.user_id, plugin.plugin_name))
        # Sau đó đăng ký nền kết nối mới
        asyncio.create_task(_register_plugin_background(
            user_id=user.user_id,
            plugin_name=plugin.plugin_name,
            plugin_type=plugin.plugin_type,
            server_url=plugin.server_url,
            headers=plugin.headers,
            config=plugin.config
        ))

    logger.info(f"Người dùng {user.user_id} cập nhật plugin: {plugin.plugin_name} (thao tác MCP thực hiện trong nền)")
    return plugin


@router.delete("/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa plugin
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    # Lưu thông tin plugin để hủy đăng ký trong nền
    plugin_name = plugin.plugin_name
    user_id = user.user_id

    # Xóa bản ghi database trước
    await db.delete(plugin)
    await db.commit()

    # Hủy đăng ký nền khỏi facade thống nhất (tránh thao tác MCP chặn gây timeout)
    asyncio.create_task(_unregister_plugin_safe(user_id, plugin_name))

    logger.info(f"Người dùng {user.user_id} xóa plugin: {plugin_name} (hủy đăng ký MCP thực hiện trong nền)")
    return {"message": "Đã xóa plugin", "plugin_name": plugin_name}


@router.post("/{plugin_id}/toggle", response_model=MCPPluginResponse)
async def toggle_plugin(
    plugin_id: str,
    enabled: bool = Query(..., description="Bật hoặc tắt"),
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Bật hoặc tắt plugin

    Khi bật: cập nhật trạng thái database thành pending trước, sau đó đăng ký kết nối MCP qua tác vụ nền,
    tránh giữ phiên database quá lâu gây timeout.
    Khi tắt: cập nhật trạng thái database trước, sau đó hủy đăng ký kết nối MCP qua tác vụ nền.
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    # Lưu thông tin plugin để thao tác MCP sau
    plugin_name = plugin.plugin_name
    plugin_type = plugin.plugin_type
    server_url = plugin.server_url
    headers = plugin.headers
    config = plugin.config

    # Cập nhật trạng thái database
    plugin.enabled = enabled
    if enabled:
        # Khi bật đặt trạng thái pending trước, chờ kết nối MCP nền hoàn thành
        plugin.status = "pending"
        plugin.last_error = None
    else:
        plugin.status = "inactive"

    await db.commit()
    await db.refresh(plugin)

    # Sau khi thao tác database hoàn tất, thực hiện thao tác MCP qua tác vụ nền (tránh giữ phiên database quá lâu)
    if enabled:
        # Bật: đăng ký nền vào facade thống nhất
        asyncio.create_task(_register_plugin_background(
            user_id=user.user_id,
            plugin_name=plugin_name,
            plugin_type=plugin_type,
            server_url=server_url,
            headers=headers,
            config=config
        ))
    else:
        # Tắt: hủy đăng ký nền khỏi facade thống nhất (không ảnh hưởng trạng thái database)
        asyncio.create_task(_unregister_plugin_safe(user.user_id, plugin_name))

    action = "Bật" if enabled else "Tắt"
    logger.info(f"Người dùng {user.user_id} {action} plugin: {plugin_name} (thao tác MCP thực hiện trong nền)")
    return plugin


@router.post("/{plugin_id}/test", response_model=MCPTestResult)
async def test_plugin(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Kiểm tra kết nối plugin và gọi công cụ để xác minh chức năng

    Dùng MCPTestService để kiểm tra.
    Nếu phiên plugin chưa được thiết lập, sẽ đăng ký trong nền trước, cần gọi lại kiểm tra.
    """

    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    if not plugin.enabled:
        return MCPTestResult(
            success=False,
            message="Plugin chưa được bật",
            error="Vui lòng bật plugin trước",
            suggestions=["Nhấn nút công tắc để bật plugin"]
        )

    # Kiểm tra phiên đã đăng ký chưa
    is_registered = mcp_client.is_registered(user.user_id, plugin.plugin_name)
    session_status = mcp_client.get_session_status(user.user_id, plugin.plugin_name)

    if not is_registered:
        # Phiên không tồn tại hoặc trạng thái bất thường, cần đăng ký trong nền
        logger.info(f"Phiên plugin {plugin.plugin_name} không tồn tại (trạng thái: {session_status}), khởi động đăng ký nền")

        # Cập nhật trạng thái database thành pending
        plugin.status = "pending"
        plugin.last_error = None
        await db.commit()

        # Đăng ký plugin trong nền
        asyncio.create_task(_register_plugin_background(
            user_id=user.user_id,
            plugin_name=plugin.plugin_name,
            plugin_type=plugin.plugin_type,
            server_url=plugin.server_url,
            headers=plugin.headers,
            config=plugin.config
        ))

        return MCPTestResult(
            success=False,
            message="Đang thiết lập kết nối...",
            error="Phiên plugin đang khởi tạo, vui lòng thử lại sau",
            suggestions=[
                "Plugin đang kết nối đến server MCP",
                "Vui lòng chờ 2-3 giây rồi nhấn kiểm tra lại",
                "Nếu tiếp tục thất bại, vui lòng kiểm tra địa chỉ server có đúng không"
            ]
        )

    # Phiên đã tồn tại, thực hiện kiểm tra trực tiếp
    try:
        test_result = await mcp_test_service.test_plugin_with_ai(plugin, user, db)

        # Cập nhật trạng thái plugin
        if test_result.success:
            plugin.status = "active"
            plugin.last_error = None
        else:
            plugin.status = "error"
            plugin.last_error = test_result.error

        plugin.last_test_at = datetime.now()
        await db.commit()

        return test_result

    except Exception as e:
        logger.error(f"Kiểm tra plugin thất bại: {plugin.plugin_name}, lỗi: {e}")
        plugin.status = "error"
        plugin.last_error = str(e)
        plugin.last_test_at = datetime.now()
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Kiểm tra thất bại: {str(e)}")


async def _ensure_plugin_registered(
    plugin: MCPPlugin,
    user_id: str
) -> bool:
    """
    Đảm bảo plugin đã đăng ký vào facade thống nhất

    Args:
        plugin: Đối tượng plugin
        user_id: ID người dùng

    Returns:
        Có thành công không

    Raises:
        HTTPException: Đăng ký thất bại
    """
    try:
        # Dùng phương thức ensure_registered, nó sẽ kiểm tra đã đăng ký chưa
        if plugin.plugin_type in HTTP_PLUGIN_TYPES and plugin.server_url:
            server_url = _validate_mcp_server_url(plugin.plugin_type, plugin.server_url)
            return await mcp_client.ensure_registered(
                user_id=user_id,
                plugin_name=plugin.plugin_name,
                url=server_url,
                plugin_type=plugin.plugin_type,
                headers=plugin.headers
            )
        return False
    except ValueError as e:
        logger.info(f"Plugin {plugin.plugin_name} chưa đăng ký, đang tự động đăng ký...")
        success = await _register_plugin_to_facade(plugin, user_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Đăng ký plugin thất bại: {plugin.plugin_name}"
            )
        return True


@router.get("/{plugin_id}/status")
async def get_plugin_status(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """Lấy trạng thái thời gian thực của plugin (bao gồm trạng thái phiên trong bộ nhớ)"""
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    session_stats = mcp_client.get_session_stats()
    session_key = f"{user.user_id}:{plugin.plugin_name}"
    session_info = next((s for s in session_stats.get("sessions", []) if s["key"] == session_key), None)

    return {
        "plugin_id": plugin_id,
        "plugin_name": plugin.plugin_name,
        "db_status": plugin.status,
        "session_status": session_info["status"] if session_info else None,
        "is_registered": session_info is not None,
        "error_rate": session_info["error_rate"] if session_info else 0,
        "in_sync": (plugin.status == session_info["status"]) if session_info else (plugin.status == "inactive"),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/metrics")
async def get_metrics(
    tool_name: Optional[str] = Query(None, description="Tên công cụ (tùy chọn, lấy chỉ số của công cụ cụ thể)"),
    user: User = Depends(require_login)
):
    """
    Lấy chỉ số lời gọi công cụ MCP

    Tham số Query:
        - tool_name: tùy chọn, tên công cụ cụ thể để lấy chỉ số

    Returns:
        Dict chỉ số lời gọi công cụ, bao gồm:
        - total_calls: tổng số lần gọi
        - success_calls: số lần gọi thành công
        - failed_calls: số lần gọi thất bại
        - success_rate: tỷ lệ thành công
        - avg_duration_ms: thời gian trung bình (mili giây)
        - last_call_time: thời gian gọi gần nhất
    """
    # Dùng facade thống nhất để lấy chỉ số
    metrics = mcp_client.get_metrics(tool_name)

    return {
        "metrics": metrics,
        "tool_name": tool_name,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/cache/stats")
async def get_cache_stats(
    user: User = Depends(require_login)
):
    """
    Lấy thống kê cache công cụ

    Returns:
        Thống kê cache, bao gồm:
        - total_entries: tổng số mục cache
        - total_hits: tổng số lần trúng cache
        - cache_ttl_minutes: TTL cache (phút)
        - entries: chi tiết từng mục cache
    """
    # Dùng facade thống nhất để lấy thống kê cache
    stats = mcp_client.get_cache_stats()

    return {
        "cache_stats": stats,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/sessions/stats")
async def get_session_stats(
    user: User = Depends(require_login)
):
    """
    Lấy thống kê phiên MCP

    Returns:
        Thống kê phiên, bao gồm:
        - total_sessions: tổng số phiên
        - sessions: chi tiết từng phiên
    """
    # Dùng facade thống nhất để lấy thống kê phiên
    stats = mcp_client.get_session_stats()

    return {
        "session_stats": stats,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/cache/clear")
async def clear_cache(
    user_id: Optional[str] = Query(None, description="ID người dùng (tùy chọn)"),
    plugin_name: Optional[str] = Query(None, description="Tên plugin (tùy chọn)"),
    user: User = Depends(require_login)
):
    """
    Xóa cache công cụ

    Tham số Query:
        - user_id: tùy chọn, xóa cache của người dùng cụ thể
        - plugin_name: tùy chọn, xóa cache của plugin cụ thể

    Ghi chú:
        - Không truyền tham số nào: xóa toàn bộ cache
        - Chỉ truyền user_id: xóa toàn bộ cache của người dùng đó
        - Truyền cả user_id và plugin_name: xóa cache của plugin cụ thể
    """
    # Người không phải quản trị viên chỉ được xóa cache của mình
    if user_id and user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Không có quyền xóa cache của người dùng khác")

    # Nếu không chỉ định user_id, dùng người dùng hiện tại
    target_user_id = user_id or user.user_id

    # Dùng facade thống nhất để xóa cache
    mcp_client.clear_cache(target_user_id, plugin_name)

    message = "Đã xóa"
    if plugin_name:
        message += f"cache của plugin {plugin_name}"
    elif target_user_id:
        message += f"toàn bộ cache của người dùng {target_user_id}"
    else:
        message += "toàn bộ cache"

    logger.info(f"Người dùng {user.user_id} {message}")

    return {
        "success": True,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/{plugin_id}/tools")
async def get_plugin_tools(
    plugin_id: str,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy danh sách công cụ mà plugin cung cấp
    """
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="Plugin chưa được bật")

    try:
        # Đảm bảo plugin đã đăng ký
        await _ensure_plugin_registered(plugin, user.user_id)

        # Dùng facade thống nhất để lấy danh sách công cụ
        tools = await mcp_client.get_tools(user.user_id, plugin.plugin_name)

        # Cập nhật cache công cụ trong database
        plugin.tools = tools
        await db.commit()

        return {
            "plugin_name": plugin.plugin_name,
            "tools": tools,
            "count": len(tools)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lấy danh sách công cụ thất bại: {plugin.plugin_name}, lỗi: {e}")
        raise HTTPException(status_code=500, detail=f"Lấy danh sách công cụ thất bại: {str(e)}")


@router.post("/call")
async def call_mcp_tool(
    data: MCPToolCall,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db)
):
    """
    Gọi công cụ MCP
    """
    # Lấy plugin
    result = await db.execute(
        select(MCPPlugin).where(
            MCPPlugin.id == data.plugin_id,
            MCPPlugin.user_id == user.user_id
        )
    )
    plugin = result.scalar_one_or_none()

    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin không tồn tại")

    if not plugin.enabled:
        raise HTTPException(status_code=400, detail="Plugin chưa được bật")

    try:
        # Đảm bảo plugin đã đăng ký
        await _ensure_plugin_registered(plugin, user.user_id)

        # Dùng facade thống nhất để gọi công cụ
        tool_result = await mcp_client.call_tool(
            user_id=user.user_id,
            plugin_name=plugin.plugin_name,
            tool_name=data.tool_name,
            arguments=data.arguments
        )

        return {
            "success": True,
            "plugin_name": plugin.plugin_name,
            "tool_name": data.tool_name,
            "result": tool_result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gọi công cụ thất bại: {plugin.plugin_name}.{data.tool_name}, lỗi: {e}")
        raise HTTPException(status_code=500, detail=f"Gọi công cụ thất bại: {str(e)}")
