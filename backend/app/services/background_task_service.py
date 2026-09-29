"""Dịch vụ quản lý tác vụ nền - quản lý các tác vụ tạo AI chạy dài"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import case, select, update
from app.database import get_engine
from app.models.background_task import BackgroundTask
from app.logger import get_logger

logger = get_logger(__name__)


class TaskProgressTracker:
    """Trình theo dõi tiến độ tác vụ nền (thay thế WizardProgressTracker của SSE)"""

    def __init__(self, task_id: str, user_id: str, task_name: str = "tác vụ"):
        self.task_id = task_id
        self.user_id = user_id
        self.task_name = task_name
        self.current_progress = 0
        self._last_generating_progress = 20

    async def _update_task(self, **kwargs):
        """Cập nhật trạng thái tác vụ vào cơ sở dữ liệu"""
        try:
            engine = await get_engine(self.user_id)
            AsyncSessionLocal = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BackgroundTask).where(BackgroundTask.id == self.task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    if task.status == "cancelled" or task.cancel_requested:
                        logger.debug(f"Bỏ qua cập nhật tiến độ của tác vụ đã hủy: {self.task_id[:8]}")
                        return
                    for key, value in kwargs.items():
                        setattr(task, key, value)
                    task.updated_at = datetime.now()
                    await session.commit()
        except Exception as e:
            logger.error(f"❌ Cập nhật tiến độ tác vụ thất bại: {e}")

    async def start(self, message: str = None):
        self.current_progress = 0
        msg = message or f"Bắt đầu tạo{self.task_name}..."
        await self._update_task(
            status="running", progress=0, status_message=msg,
            started_at=datetime.now(),
            progress_details={"stage": "init", "message": msg}
        )

    async def loading(self, message: str = None, sub_progress: float = 0.5):
        progress = 5 + int(10 * sub_progress)
        self.current_progress = progress
        msg = message or "Đang tải dữ liệu..."
        await self._update_task(
            progress=progress, status_message=msg,
            progress_details={"stage": "loading", "message": msg}
        )

    async def preparing(self, message: str = None):
        self.current_progress = 17
        msg = message or "Chuẩn bịAIprompt..."
        await self._update_task(
            progress=17, status_message=msg,
            progress_details={"stage": "preparing", "message": msg}
        )

    async def generating(self, current_chars: int = 0, estimated_total: int = 5000,
                         message: str = None, retry_count: int = 0, max_retries: int = 3):
        sub_progress = min(current_chars / max(estimated_total, 1), 1.0)
        progress = 20 + int(65 * sub_progress)
        if progress < self._last_generating_progress:
            progress = self._last_generating_progress
        else:
            self._last_generating_progress = progress
        self.current_progress = progress

        retry_suffix = f" (thử lại {retry_count}/{max_retries})" if retry_count > 0 else ""
        msg = message or f"Đang tạo {self.task_name}... ({current_chars} ký tự){retry_suffix}"
        await self._update_task(
            progress=progress, status_message=msg,
            progress_details={"stage": "generating", "message": msg, "current_chars": current_chars}
        )

    async def parsing(self, message: str = None):
        self.current_progress = 88
        msg = message or f"phân tích{self.task_name}dữ liệu..."
        await self._update_task(
            progress=88, status_message=msg,
            progress_details={"stage": "parsing", "message": msg}
        )

    async def saving(self, message: str = None, sub_progress: float = 0.5):
        progress = 92 + int(6 * sub_progress)
        self.current_progress = progress
        msg = message or f"lưu{self.task_name}vào cơ sở dữ liệu..."
        await self._update_task(
            progress=progress, status_message=msg,
            progress_details={"stage": "saving", "message": msg}
        )

    async def analyzing(self, analysis_progress: int = 0, message: str = None):
        """Ánh xạ tiến độ phân tích chương tới giai đoạn cuối của tác vụ tạo nền."""
        normalized_progress = max(0, min(analysis_progress, 100))
        progress = 94 + int(5 * normalized_progress / 100)
        self.current_progress = progress
        msg = message or f"Đang phân tích {self.task_name}... ({normalized_progress}%)"
        await self._update_task(
            progress=progress, status_message=msg,
            progress_details={
                "stage": "analyzing",
                "message": msg,
                "analysis_progress": normalized_progress,
            }
        )

    async def set_result(self, task_result: Dict[str, Any]):
        await self._update_task(task_result=task_result)

    async def complete(self, message: str = None):
        self.current_progress = 100
        msg = message or f"{self.task_name}Tạo hoàn tất!"
        await self._update_task(
            status="completed", progress=100, status_message=msg,
            completed_at=datetime.now(),
            progress_details={"stage": "complete", "message": msg}
        )

    async def error(self, error_message: str):
        await self._update_task(
            status="failed", error_message=error_message,
            status_message=f"thất bại: {error_message}",
            completed_at=datetime.now(),
            progress_details={"stage": "error", "message": error_message}
        )

    async def warning(self, message: str):
        await self._update_task(
            status_message=f"⚠️ {message}",
            progress_details={"stage": "warning", "message": message}
        )

    async def retry(self, retry_count: int, max_retries: int, reason: str = "Chuẩn bị thử lại"):
        msg = f"⚠️ {reason}... ({retry_count}/{max_retries})"
        await self._update_task(
            status_message=msg, retry_count=retry_count,
            progress_details={"stage": "retry", "message": msg, "retry_count": retry_count}
        )

    def reset_generating_progress(self):
        self._last_generating_progress = 20

    async def check_cancelled(self) -> bool:
        """Kiểm tra tác vụ có bị hủy không"""
        try:
            engine = await get_engine(self.user_id)
            AsyncSessionLocal = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BackgroundTask.cancel_requested)
                    .where(BackgroundTask.id == self.task_id)
                )
                cancelled = result.scalar_one_or_none()
                return bool(cancelled)
        except Exception:
            return False


class BackgroundTaskService:
    """Dịch vụ quản lý tác vụ nền (xếp hàng theo người dùng: tác vụ cùng người dùng chạy tuần tự, người dùng khác nhau có thể đồng thời)"""

    def __init__(self):
        self._user_queues: Dict[str, asyncio.Queue] = {}   # user_id -> Queue
        self._user_workers: Dict[str, bool] = {}            # user_id -> worker có đang chạy không

    def _ensure_user_queue(self, user_id: str) -> asyncio.Queue:
        """Đảm bảo hàng đợi của người dùng chỉ định đã được khởi tạo"""
        if user_id not in self._user_queues:
            self._user_queues[user_id] = asyncio.Queue()
        return self._user_queues[user_id]

    async def _start_user_worker(self, user_id: str):
        """Khởi động coroutine worker của người dùng chỉ định"""
        if self._user_workers.get(user_id, False):
            return
        self._user_workers[user_id] = True
        asyncio.create_task(self._user_worker_loop(user_id))
        logger.info(f"📋 người dùng {user_id[:8]} coroutine worker hàng đợi tác vụ đã khởi động")

    async def _user_worker_loop(self, user_id: str):
        """Lấy từng tác vụ từ hàng đợi của người dùng chỉ định và thực thi"""
        queue = self._user_queues[user_id]
        try:
            while True:
                try:
                    task_item = await queue.get()
                    task_id = task_item["task_id"]
                    task_func = task_item["task_func"]
                    args = task_item["args"]
                    kwargs = task_item["kwargs"]

                    logger.info(f"🔄 [người dùng{user_id[:8]}] Hàng đợi bắt đầu thực thi tác vụ: {task_id[:8]} (Còn lại trong hàng đợi: {queue.qsize()})")

                    try:
                        if await self._is_task_cancelled(task_id, user_id):
                            logger.info(f"🚫 [người dùng{user_id[:8]}] Bỏ qua tác vụ xếp hàng đã hủy: {task_id[:8]}")
                            continue
                        await task_func(task_id, args["user_id"], *args["extra_args"], **kwargs)
                    except Exception as e:
                        logger.error(f"❌ Tác vụ nền {task_id[:8]} ngoại lệ: {e}", exc_info=True)
                        # Đảm bảo trạng thái tác vụ được cập nhật thành thất bại
                        try:
                            engine = await get_engine(user_id)
                            AsyncSessionLocal = async_sessionmaker(
                                engine, class_=AsyncSession, expire_on_commit=False
                            )
                            async with AsyncSessionLocal() as session:
                                result = await session.execute(
                                    select(BackgroundTask).where(BackgroundTask.id == task_id)
                                )
                                task = result.scalar_one_or_none()
                                if task and task.status == "running" and not task.cancel_requested:
                                    task.status = "failed"
                                    task.error_message = str(e)
                                    task.status_message = f"Tác vụ thất bại: {str(e)}"
                                    task.completed_at = datetime.now()
                                    await session.commit()
                        except Exception as update_err:
                            logger.error(f"❌ Cập nhật trạng thái tác vụ thất bại bị lỗi: {update_err}")
                    finally:
                        queue.task_done()
                        logger.info(f"✅ [người dùng{user_id[:8]}] Tác vụ hàng đợi hoàn tất: {task_id[:8]} (Còn lại trong hàng đợi: {queue.qsize()})")

                except Exception as e:
                    logger.error(f"❌ [người dùng{user_id[:8]}] Vòng lặp worker hàng đợi gặp ngoại lệ: {e}", exc_info=True)
        finally:
            # Dọn dẹp cờ khi coroutine worker thoát
            self._user_workers.pop(user_id, None)
            logger.info(f"📋 người dùng {user_id[:8]} coroutine worker đã thoát")

    @staticmethod
    async def _is_task_cancelled(task_id: str, user_id: str) -> bool:
        """Kiểm tra tác vụ đã bị hủy trước khi thực thi hay chưa."""
        try:
            engine = await get_engine(user_id)
            AsyncSessionLocal = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BackgroundTask.status, BackgroundTask.cancel_requested)
                    .where(BackgroundTask.id == task_id)
                )
                row = result.first()
                if not row:
                    return True
                status, cancel_requested = row
                return status == "cancelled" or bool(cancel_requested)
        except Exception as e:
            logger.warning(f"Kiểm tra trạng thái hủy tác vụ thất bại: {task_id[:8]} {e}")
            return False

    @staticmethod
    async def create_task(
        user_id: str,
        project_id: str,
        task_type: str,
        task_input: Dict[str, Any] = None,
        db: AsyncSession = None
    ) -> BackgroundTask:
        """Tạo bản ghi tác vụ nền"""
        task = BackgroundTask(
            user_id=user_id,
            project_id=project_id,
            task_type=task_type,
            task_input=task_input or {},
            status="pending",
            progress=0,
            status_message="Tác vụ đã được tạo, đang chờ thực thi..."
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        logger.info(f"📋 Tạo tác vụ nền: {task.id[:8]} type={task_type} project={project_id[:8]}")
        return task

    @staticmethod
    async def get_task(task_id: str, user_id: str, db: AsyncSession) -> Optional[BackgroundTask]:
        """Lấy chi tiết tác vụ"""
        result = await db.execute(
            select(BackgroundTask).where(
                BackgroundTask.id == task_id,
                BackgroundTask.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_project_tasks(
        project_id: str, user_id: str, db: AsyncSession,
        task_type: str = None, limit: int = 20
    ) -> list:
        """Lấy danh sách tác vụ của dự án"""
        query = (
            select(BackgroundTask)
            .where(
                BackgroundTask.project_id == project_id,
                BackgroundTask.user_id == user_id
            )
            .order_by(
                case(
                    (BackgroundTask.status.in_(["pending", "running"]), 0),
                    else_=1,
                ),
                BackgroundTask.created_at.desc(),
            )
        )
        if task_type:
            query = query.where(BackgroundTask.task_type == task_type)
        query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def cancel_task(task_id: str, user_id: str, db: AsyncSession) -> bool:
        """Yêu cầu hủy tác vụ"""
        result = await db.execute(
            select(BackgroundTask).where(
                BackgroundTask.id == task_id,
                BackgroundTask.user_id == user_id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        if task.status not in ("pending", "running"):
            return False
        task.cancel_requested = True
        task.status = "cancelled"
        task.status_message = "Tác vụ đã bị hủy"
        task.completed_at = datetime.now()
        await db.commit()
        logger.info(f"🚫 Hủy tác vụ: {task_id[:8]}")
        return True

    @staticmethod
    async def cleanup_old_tasks(user_id: str, db: AsyncSession, days: int = 7):
        """Dọn dẹp bản ghi tác vụ cũ"""
        from sqlalchemy import delete as sql_delete
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        result = await db.execute(
            sql_delete(BackgroundTask).where(
                BackgroundTask.user_id == user_id,
                BackgroundTask.status.in_(["completed", "failed", "cancelled"]),
                BackgroundTask.completed_at < cutoff
            )
        )
        if result.rowcount > 0:
            await db.commit()
            logger.info(f"🧹 Dọn dẹp {result.rowcount} bản ghi tác vụ cũ của người dùng {user_id[:8]}")

    async def spawn_background_task(
        self,
        task_id: str,
        user_id: str,
        task_func: Callable[..., Awaitable],
        *args,
        **kwargs
    ):
        """
        Thêm tác vụ vào hàng đợi của người dùng này để xếp hàng thực thi (cùng người dùng FIFO, người dùng khác nhau có thể đồng thời)
        
        Args:
            task_id: tác vụID
            user_id: người dùngID
            task_func: Hàm tác vụ bất đồng bộ
            *args, **kwargs: Truyền chotask_functham số
        """
        # Đảm bảo hàng đợi và coroutine worker của người dùng này đã khởi động
        queue = self._ensure_user_queue(user_id)
        await self._start_user_worker(user_id)

        # Đưa tác vụ vào hàng đợi của người dùng này
        await queue.put({
            "task_id": task_id,
            "task_func": task_func,
            "args": {"user_id": user_id, "extra_args": args},
            "kwargs": kwargs,
        })
        queue_size = queue.qsize()
        tasks_ahead = max(queue_size - 1, 0)
        logger.info(f"📥 Tác vụ đã tham gia hàng đợi của người dùng {user_id[:8]} hàng đợi: {task_id[:8]} (Độ dài hàng đợi hiện tại: {queue_size})")

        # Cập nhật trạng thái tác vụ, hiển thị vị trí xếp hàng
        try:
            engine = await get_engine(user_id)
            AsyncSessionLocal = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(BackgroundTask).where(BackgroundTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task and task.status == "pending":
                    if tasks_ahead > 0:
                        task.status_message = f"Đang xếp hàng, phía trước còn {tasks_ahead} tác vụ đang chờ..."
                    else:
                        task.status_message = "Sắp bắt đầu thực thi..."
                    task.progress_details = {"stage": "queued", "queue_size": tasks_ahead}
                    task.updated_at = datetime.now()
                    await session.commit()
        except Exception as e:
            logger.error(f"Cập nhật thông tin vị trí hàng đợi thất bại: {e}")

    def get_queue_size(self, user_id: str = None) -> int:
        """Lấy số lượng tác vụ đang chờ trong hàng đợi"""
        if user_id:
            queue = self._user_queues.get(user_id)
            return queue.qsize() if queue else 0
        # Tổng số hàng đợi của mọi người dùng
        return sum(q.qsize() for q in self._user_queues.values())

    def get_all_queue_info(self) -> Dict[str, int]:
        """Lấy thông tin hàng đợi của mọi người dùng"""
        return {
            uid: q.qsize() for uid, q in self._user_queues.items() if q.qsize() > 0
        }


# Thể hiện đơn nhất toàn cục
background_task_service = BackgroundTaskService()
