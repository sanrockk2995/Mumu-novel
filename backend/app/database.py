"""Quản lý kết nối và session database - cách ly dữ liệu đa người dùng PostgreSQL"""
import asyncio
from typing import Dict, Any
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from fastapi import Request, HTTPException
from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

# Tạo base class
Base = declarative_base()

# Import mọi model, đảm bảo Base.metadata phát hiện được chúng
# Việc này phải import sau khi Base được tạo, trước init_db
from app.models import (
    Project, Outline, Character, Chapter, GenerationHistory,
    Settings, WritingStyle, ProjectDefaultStyle,
    RelationshipType, CharacterRelationship, Organization, OrganizationMember,
    StoryMemory, PlotAnalysis, AnalysisTask, BatchGenerationTask,
    RegenerationTask, Career, CharacterCareer, User, MCPPlugin, PromptTemplate,
    BackgroundTask, Announcement,
    AgentConversation, AgentMessage, AgentToolCall, AgentExecutionStep,
)

# Cache engine: mỗi người dùng một engine
_engine_cache: Dict[str, Any] = {}

# Quản lý lock: bảo vệ quá trình tạo engine
_engine_locks: Dict[str, asyncio.Lock] = {}
_cache_lock = asyncio.Lock()

# Thống kê session (giám sát rò rỉ kết nối)
_session_stats = {
    "created": 0,
    "closed": 0,
    "active": 0,
    "errors": 0,
    "generator_exits": 0,
    "last_check": None
}


async def get_engine(user_id: str):
    """Lấy hoặc tạo engine database riêng của người dùng (an toàn luồng)

    PostgreSQL: mọi người dùng dùng chung một database, cách ly dữ liệu qua trường user_id

    Args:
        user_id: ID người dùng

    Returns:
        Engine bất đồng bộ riêng của người dùng
    """
    # Chế độ PostgreSQL: mọi người dùng dùng chung một engine
    cache_key = "shared_postgres"
    if cache_key in _engine_cache:
        return _engine_cache[cache_key]
    
    async with _cache_lock:
        if cache_key not in _engine_cache:
            # Phát hiện loại database
            is_sqlite = 'sqlite' in settings.database_url.lower()
            
            # Tham số engine cơ bản
            engine_args = {
                "echo": settings.database_echo_pool,
                "echo_pool": settings.database_echo_pool,
                "future": True,
            }
            
            if is_sqlite:
                # Cấu hình SQLite (dùng NullPool, không hỗ trợ tham số connection pool)
                engine_args["connect_args"] = {
                    "check_same_thread": False,
                    "timeout": 30.0,  # Thời gian chờ khóa được giải phóng (giây)
                }
                # Bật kiểm tra trước kết nối để hỗ trợ đồng thời tốt hơn
                engine_args["pool_pre_ping"] = True
                
                logger.info("📊 Dùng database SQLite (NullPool, timeout 30 giây, chế độ WAL)")
            else:
                # Cấu hình PostgreSQL (hỗ trợ đầy đủ connection pool)
                connect_args = {
                    "server_settings": {
                        "application_name": settings.app_name,
                        "jit": "off",
                        "search_path": "public",
                    },
                    "command_timeout": 60,
                    "statement_cache_size": 500,
                }
                
                engine_args.update({
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                    "pool_timeout": settings.database_pool_timeout,
                    "pool_pre_ping": settings.database_pool_pre_ping,
                    "pool_recycle": settings.database_pool_recycle,
                    "pool_use_lifo": settings.database_pool_use_lifo,
                    "pool_reset_on_return": settings.database_pool_reset_on_return,
                    "max_identifier_length": settings.database_max_identifier_length,
                    "connect_args": connect_args
                })
                
                total_connections = settings.database_pool_size + settings.database_max_overflow
                estimated_concurrent_users = total_connections * 2
                
                logger.info(
                    f"📊 Cấu hình connection pool PostgreSQL:\n"
                    f"   ├─ Kết nối lõi: {settings.database_pool_size}\n"
                    f"   ├─ Kết nối tràn: {settings.database_max_overflow}\n"
                    f"   ├─ Tổng kết nối: {total_connections}\n"
                    f"   ├─ Timeout lấy: {settings.database_pool_timeout} giây\n"
                    f"   ├─ Thu hồi kết nối: {settings.database_pool_recycle} giây\n"
                    f"   └─ Ước tính đồng thời: {estimated_concurrent_users}+ người dùng"
                )
            
            engine = create_async_engine(settings.database_url, **engine_args)
            _engine_cache[cache_key] = engine
            
            # Nếu là SQLite, bật chế độ WAL để hỗ trợ đọc-ghi đồng thời
            if is_sqlite:
                try:
                    from sqlalchemy import event
                    from sqlalchemy.pool import NullPool
                    
                    @event.listens_for(engine.sync_engine, "connect")
                    def set_sqlite_pragma(dbapi_conn, connection_record):
                        cursor = dbapi_conn.cursor()
                        cursor.execute("PRAGMA journal_mode=WAL")
                        cursor.execute("PRAGMA synchronous=NORMAL")
                        cursor.execute("PRAGMA cache_size=-64000")  # Cache 64MB
                        cursor.execute("PRAGMA busy_timeout=30000")  # Timeout 30 giây
                        cursor.close()
                    
                    logger.info("✅ Chế độ WAL của SQLite đã bật (hỗ trợ đọc-ghi đồng thời)")
                except Exception as e:
                    logger.warning(f"⚠️ Bật chế độ WAL thất bại: {e}, dùng cấu hình mặc định")
        
        return _engine_cache[cache_key]


async def get_db(request: Request):
    """Hàm dependency lấy session database

    Lấy ID người dùng từ request.state.user_id, rồi trả về session database của người dùng đó
    """
    user_id = getattr(request.state, "user_id", None)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc thiếu ID người dùng")
    
    engine = await get_engine(user_id)
    
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    session = AsyncSessionLocal()
    session_id = id(session)
    
    global _session_stats
    _session_stats["created"] += 1
    _session_stats["active"] += 1
    
    # logger.debug(f"📊 Tạo session [User:{user_id}][ID:{session_id}] - đang hoạt động:{_session_stats['active']}, tổng tạo:{_session_stats['created']}, tổng đóng:{_session_stats['closed']}")
    
    try:
        yield session
        if session.in_transaction():
            await session.rollback()
    except GeneratorExit:
        _session_stats["generator_exits"] += 1
        # logger.warning(f"⚠️ GeneratorExit [User:{user_id}][ID:{session_id}] - SSE ngắt kết nối (tổng:{_session_stats['generator_exits']} lần)")
        try:
            if session.in_transaction():
                await session.rollback()
                logger.info(f"✅ Giao dịch đã rollback [User:{user_id}][ID:{session_id}] (GeneratorExit)")
        except Exception as rollback_error:
            _session_stats["errors"] += 1
            logger.error(f"❌ GeneratorExit rollback thất bại [User:{user_id}][ID:{session_id}]: {str(rollback_error)}")
    except Exception as e:
        _session_stats["errors"] += 1
        logger.error(f"❌ Session bất thường [User:{user_id}][ID:{session_id}]: {str(e)}")
        try:
            if session.in_transaction():
                await session.rollback()
                logger.info(f"✅ Giao dịch đã rollback [User:{user_id}][ID:{session_id}] (bất thường)")
        except Exception as rollback_error:
            logger.error(f"❌ Rollback bất thường thất bại [User:{user_id}][ID:{session_id}]: {str(rollback_error)}")
        raise
    finally:
        try:
            if session.in_transaction():
                await session.rollback()
                logger.warning(f"⚠️ Trong finally phát hiện giao dịch chưa commit [User:{user_id}][ID:{session_id}], đã rollback")
            
            await session.close()
            
            _session_stats["closed"] += 1
            _session_stats["active"] -= 1
            _session_stats["last_check"] = datetime.now().isoformat()
            
            # logger.debug(f"📊 Đóng session [User:{user_id}][ID:{session_id}] - đang hoạt động:{_session_stats['active']}, tổng tạo:{_session_stats['created']}, tổng đóng:{_session_stats['closed']}, lỗi:{_session_stats['errors']}")
            
            # Dùng ngưỡng giám sát session đã tối ưu
            if _session_stats["active"] > settings.database_session_leak_threshold:
                logger.error(f"🚨 Cảnh báo nghiêm trọng: số session đang hoạt động {_session_stats['active']} vượt ngưỡng rò rỉ {settings.database_session_leak_threshold}!")
            elif _session_stats["active"] > settings.database_session_max_active:
                logger.warning(f"⚠️ Cảnh báo: số session đang hoạt động {_session_stats['active']} vượt ngưỡng cảnh báo {settings.database_session_max_active}, có thể rò rỉ kết nối!")
            elif _session_stats["active"] < 0:
                logger.error(f"🚨 Số session đang hoạt động bất thường: {_session_stats['active']}, thống kê có thể không chính xác!")
                
        except Exception as e:
            _session_stats["errors"] += 1
            logger.error(f"❌ Lỗi khi đóng session [User:{user_id}][ID:{session_id}]: {str(e)}", exc_info=True)
            try:
                await session.close()
            except Exception:
                pass

async def init_db(user_id: str = None):
    """
    Khởi tạo database (đã lỗi thời)

    ⚠️ Hàm này đã lỗi thời, chỉ giữ lại để tương thích ngược

    Thực hành tốt nhất mới:
    - Quản lý cấu trúc bảng: dùng 'alembic upgrade head'
    - Cấu hình người dùng: Settings tự tạo khi truy cập lần đầu (khởi tạo lười)

    Args:
        user_id: ID người dùng (không dùng nữa)
    """
    logger.warning(
        "⚠️ init_db() đã lỗi thời và không có tác dụng thực tế!\n"
        "   - Cấu trúc bảng: do Alembic quản lý\n"
        "   - Cấu hình người dùng: Settings API tự tạo\n"
        "   Nên xóa lời gọi này"
    )


async def close_db():
    """Đóng mọi kết nối database"""
    try:
        logger.info("Đang đóng mọi kết nối database...")
        for user_id, engine in _engine_cache.items():
            await engine.dispose()
            logger.info(f"Kết nối database của người dùng {user_id} đã đóng")
        _engine_cache.clear()
        logger.info("Mọi kết nối database đã đóng")
    except Exception as e:
        logger.error(f"Đóng kết nối database thất bại: {str(e)}", exc_info=True)
        raise

async def get_database_stats():
    """Lấy thông tin thống kê kết nối và session database

    Returns:
        dict: dict chứa thông tin thống kê database
    """
    from app.config import settings
    
    # Lấy trạng thái chi tiết connection pool
    pool_stats = {}
    cache_key = "shared_postgres"
    if cache_key in _engine_cache:
        engine = _engine_cache[cache_key]
        try:
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),  # Kích thước connection pool hiện tại
                "checked_in": pool.checkedin(),  # Số kết nối khả dụng
                "checked_out": pool.checkedout(),  # Số kết nối đang dùng
                "overflow": pool.overflow(),  # Số kết nối tràn
                "usage_percent": (pool.checkedout() / (settings.database_pool_size + settings.database_max_overflow)) * 100,
            }
        except Exception as e:
            logger.warning(f"Lấy trạng thái connection pool thất bại: {e}")
            pool_stats = {"error": str(e)}
    
    stats = {
        "session_stats": {
            "created": _session_stats["created"],
            "closed": _session_stats["closed"],
            "active": _session_stats["active"],
            "errors": _session_stats["errors"],
            "generator_exits": _session_stats["generator_exits"],
            "last_check": _session_stats["last_check"],
        },
        "pool_stats": pool_stats,  # Mới: trạng thái thời gian thực của connection pool
        "engine_cache": {
            "total_engines": len(_engine_cache),
            "engine_keys": list(_engine_cache.keys()),
        },
        "config": {
            "database_type": "PostgreSQL",
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "total_connections": settings.database_pool_size + settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "pool_recycle": settings.database_pool_recycle,
            "session_max_active_threshold": settings.database_session_max_active,
            "session_leak_threshold": settings.database_session_leak_threshold,
        },
        "health": {
            "status": "healthy",
            "warnings": [],
            "errors": [],
        }
    }
    
    # Kiểm tra sức khỏe
    if _session_stats["active"] > settings.database_session_leak_threshold:
        stats["health"]["status"] = "critical"
        stats["health"]["errors"].append(
            f"Số session đang hoạt động {_session_stats['active']} vượt ngưỡng rò rỉ {settings.database_session_leak_threshold}"
        )
    elif _session_stats["active"] > settings.database_session_max_active:
        stats["health"]["status"] = "warning"
        stats["health"]["warnings"].append(
            f"Số session đang hoạt động {_session_stats['active']} vượt ngưỡng cảnh báo {settings.database_session_max_active}"
        )
    
    if _session_stats["active"] < 0:
        stats["health"]["status"] = "error"
        stats["health"]["errors"].append(f"Số session đang hoạt động bất thường: {_session_stats['active']}")
    
    # Kiểm tra tỷ lệ dùng connection pool
    if pool_stats and "usage_percent" in pool_stats:
        usage = pool_stats["usage_percent"]
        if usage > 90:
            stats["health"]["status"] = "warning"
            stats["health"]["warnings"].append(f"Tỷ lệ dùng connection pool quá cao: {usage:.1f}%")
        elif usage > 95:
            stats["health"]["status"] = "critical"
            stats["health"]["errors"].append(f"Connection pool gần cạn: {usage:.1f}%")
    
    error_rate = (_session_stats["errors"] / max(_session_stats["created"], 1)) * 100
    if error_rate > 5:
        if stats["health"]["status"] == "healthy":
            stats["health"]["status"] = "warning"
        stats["health"]["warnings"].append(f"Tỷ lệ lỗi session quá cao: {error_rate:.2f}%")
    
    stats["health"]["error_rate"] = f"{error_rate:.2f}%"
    
    return stats


async def check_database_health(user_id: str = None) -> dict:
    """Kiểm tra trạng thái sức khỏe kết nối database

    Args:
        user_id: ID người dùng tùy chọn, nếu có thì kiểm tra database của người dùng cụ thể

    Returns:
        dict: kết quả kiểm tra sức khỏe
    """
    result = {
        "healthy": True,
        "checks": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Kiểm tra engine có tồn tại không
        cache_key = "shared_postgres"
        if user_id:
            engine = await get_engine(user_id)
        else:
            if cache_key not in _engine_cache:
                result["checks"]["engine"] = {"status": "not_initialized", "healthy": True}
                return result
            engine = _engine_cache[cache_key]
        
        # Thử kết nối database
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            # Chạy truy vấn đơn giản để thử kết nối
            await session.execute(text("SELECT 1"))
            result["checks"]["connection"] = {"status": "ok", "healthy": True}
            
        # Kiểm tra trạng thái connection pool (chỉ PostgreSQL)
        if hasattr(engine.pool, 'size'):
            pool_status = {
                "size": engine.pool.size(),
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "healthy": True
            }
            
            # Kiểm tra sức khỏe connection pool
            if engine.pool.overflow() >= settings.database_max_overflow:
                pool_status["healthy"] = False
                pool_status["warning"] = "Connection pool tràn đã đầy"
                result["healthy"] = False
            
            result["checks"]["pool"] = pool_status
        
    except Exception as e:
        result["healthy"] = False
        result["checks"]["error"] = {
            "status": "error",
            "message": str(e),
            "healthy": False
        }
        logger.error(f"Kiểm tra sức khỏe database thất bại: {str(e)}", exc_info=True)
    
    return result


async def reset_session_stats():
    """Đặt lại thông tin thống kê session (dùng cho test hoặc bảo trì)"""
    global _session_stats
    _session_stats = {
        "created": 0,
        "closed": 0,
        "active": 0,
        "errors": 0,
        "generator_exits": 0,
        "last_check": datetime.now().isoformat()
    }
    logger.info("✅ Thông tin thống kê session đã đặt lại")
    return _session_stats
