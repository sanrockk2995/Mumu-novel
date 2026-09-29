"""Dịch vụ đồng bộ trạng thái plugin MCP

Đồng bộ thay đổi trạng thái session trong bộ nhớ vào database, đảm bảo tính nhất quán trạng thái.
"""

import asyncio
from typing import Dict, Any
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.mcp_plugin import MCPPlugin
from app.logger import get_logger

logger = get_logger(__name__)

# Hàng đợi đồng bộ trạng thái
_sync_queue: asyncio.Queue = None
_sync_task: asyncio.Task = None


async def _sync_worker():
    """Luồng worker đồng bộ trạng thái nền"""
    global _sync_queue

    while True:
        try:
            event = await _sync_queue.get()
            if event is None:  # Tín hiệu dừng
                break

            await _do_sync_status(event)
            _sync_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Luồng worker đồng bộ trạng thái bất thường: {e}")


async def _do_sync_status(event: Dict[str, Any]):
    """Thực hiện đồng bộ trạng thái"""
    user_id = event["user_id"]
    plugin_name = event["plugin_name"]
    new_status = event["new_status"]
    reason = event.get("reason", "")

    try:
        from app.database import get_engine

        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with AsyncSessionLocal() as db:
            stmt = (
                update(MCPPlugin)
                .where(MCPPlugin.user_id == user_id, MCPPlugin.plugin_name == plugin_name)
                .values(status=new_status, last_error=reason if new_status == "error" else None)
            )
            await db.execute(stmt)
            await db.commit()

            logger.debug(f"✅ Trạng thái đã đồng bộ vào database: {plugin_name} -> {new_status}")

    except Exception as e:
        logger.error(f"❌ Đồng bộ trạng thái thất bại: {plugin_name}, lỗi: {e}")


async def sync_status_to_db(event: Dict[str, Any]):
    """
    Callback thay đổi trạng thái - đưa sự kiện vào hàng đợi để đồng bộ bất đồng bộ vào database

    Dùng hàng đợi xử lý bất đồng bộ, tránh chặn hoặc gây xung đột kết nối database trong quá trình xử lý request
    """
    global _sync_queue, _sync_task

    # Khởi tạo lười hàng đợi và luồng worker
    if _sync_queue is None:
        _sync_queue = asyncio.Queue()

    if _sync_task is None or _sync_task.done():
        _sync_task = asyncio.create_task(_sync_worker())
        logger.info("✅ Luồng worker đồng bộ trạng thái MCP đã khởi động")

    # Đưa sự kiện vào hàng đợi (không chặn)
    try:
        _sync_queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning(f"Hàng đợi đồng bộ trạng thái đã đầy, loại bỏ sự kiện: {event['plugin_name']}")


def register_status_sync():
    """Đăng ký callback đồng bộ trạng thái vào MCP client"""
    from app.mcp import mcp_client
    mcp_client.register_status_callback(sync_status_to_db)
    logger.info("✅ Dịch vụ đồng bộ trạng thái MCP đã đăng ký")
