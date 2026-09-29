"""API quản lý chương"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
import json
import asyncio
from typing import Awaitable, Callable, Optional
from datetime import datetime, timedelta
from asyncio import Queue, Lock

from app.database import get_db, get_engine
from app.api.common import verify_project_access
from app.services.chapter_context_service import (
    OneToManyContextBuilder,
    OneToOneContextBuilder
)
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.outline import Outline
from app.models.character import Character
from app.models.career import Career, CharacterCareer
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.models.generation_history import GenerationHistory
from app.models.writing_style import WritingStyle
from app.models.analysis_task import AnalysisTask
from app.models.memory import PlotAnalysis, StoryMemory
from app.models.batch_generation_task import BatchGenerationTask
from app.models.regeneration_task import RegenerationTask
from app.models.background_task import BackgroundTask
from app.schemas.chapter import (
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterListResponse,
    AnalysisTaskStatusResponse,
    BatchAnalysisStatusRequest,
    BatchAnalysisStatusResponse,
    BatchAnalyzeUnanalyzedRequest,
    BatchAnalyzeUnanalyzedResponse,
    ChapterGenerateRequest,
    BatchGenerateRequest,
    BatchGenerateResponse,
    BatchGenerateStatusResponse,
    ExpansionPlanUpdate,
    PartialRegenerateRequest
)
from app.schemas.regeneration import (
    ChapterRegenerateRequest,
    RegenerationTaskResponse,
    RegenerationTaskStatus
)
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service, PromptService, WritingStyleManager
from app.services.plot_analyzer import PlotAnalyzer
from app.services.memory_service import memory_service
from app.services.foreshadow_service import foreshadow_service
from app.services.chapter_regenerator import ChapterRegenerator
from app.logger import get_logger
from app.api.settings import get_user_ai_service, get_user_ai_service_from_db_by_usage
from app.utils.sse_response import SSEResponse, create_sse_response

router = APIRouter(prefix="/chapters", tags=["Quản lý chương"])
logger = get_logger(__name__)

# Khóa ghi database toàn cục (mỗi người dùng một khóa, để bảo vệ thao tác ghi SQLite)
db_write_locks: dict[str, Lock] = {}
analysis_background_tasks: set[asyncio.Task] = set()

ANALYSIS_TASK_TIMEOUT_SECONDS = 600
ANALYSIS_TASK_STALE_SECONDS = 720


def _schedule_analysis_background(coroutine) -> asyncio.Task:
    """Giữ tham chiếu tác vụ nền cho đến khi tác vụ kết thúc."""
    task = asyncio.create_task(coroutine)
    analysis_background_tasks.add(task)
    task.add_done_callback(analysis_background_tasks.discard)
    return task


def _build_lightweight_chapter_summary(content: str, max_length: int = 300) -> str:
    """Tạo bản tóm tắt nhẹ dự phòng, có thể dùng ngay cho phần nối tiếp chương sau."""
    if not content:
        return ""
    normalized = " ".join(content.split())
    return normalized[:max_length]


async def get_db_write_lock(user_id: str) -> Lock:
    """Lấy hoặc tạo khóa ghi database của người dùng"""
    if user_id not in db_write_locks:
        db_write_locks[user_id] = Lock()
        logger.debug(f"🔒 Tạo khóa ghi database cho người dùng {user_id}")
    return db_write_locks[user_id]


async def _set_analysis_task_terminal_state(
    user_id: str,
    task_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> bool:
    """Ghi trạng thái cuối bằng transaction độc lập, tránh không cập nhật được tác vụ khi session phân tích thất bại."""
    engine = await get_engine(user_id)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    completed_at = datetime.now()

    for attempt in range(1, 4):
        async with session_factory() as terminal_db:
            try:
                result = await terminal_db.execute(
                    update(AnalysisTask)
                    .where(
                        AnalysisTask.id == task_id,
                        AnalysisTask.status.in_(["pending", "running"]),
                    )
                    .values(
                        status=status,
                        progress=100 if status == "completed" else 0,
                        error_message=error_message if status == "failed" else None,
                        completed_at=completed_at,
                    )
                )
                await terminal_db.commit()
                if result.rowcount == 0:
                    logger.info(f"Tác vụ phân tích đã ở trạng thái cuối, không cần cập nhật lại: {task_id}")
                    return False
                return True
            except Exception as exc:
                await terminal_db.rollback()
                logger.error(f"Cập nhật trạng thái cuối tác vụ phân tích thất bại ({attempt}/3): {task_id}, {exc}")
                if attempt < 3:
                    await asyncio.sleep(0.1)

    return False


@router.post("", response_model=ChapterResponse, summary="Tạo chương")
async def create_chapter(
    chapter: ChapterCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tạo chương mới"""
    # Xác minh quyền người dùng và dự án có tồn tại không
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(chapter.project_id, user_id, db)
    
    # Tính số từ (xử lý trường hợp content có thể là None)
    word_count = len(chapter.content) if chapter.content else 0
    
    db_chapter = Chapter(
        **chapter.model_dump(),
        word_count=word_count
    )
    db.add(db_chapter)
    
    # Cập nhật số từ hiện tại của dự án
    project.current_words = project.current_words + word_count
    
    await db.commit()
    await db.refresh(db_chapter)
    return db_chapter


@router.get("/project/{project_id}", response_model=ChapterListResponse, summary="Lấy tất cả chương của dự án")
async def get_project_chapters(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy tất cả chương của dự án đã chỉ định (kèm thông tin đề cương)"""
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # Lấy tổng số
    count_result = await db.execute(
        select(func.count(Chapter.id)).where(Chapter.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # Lấy danh sách chương, đồng thời tải thông tin đề cương liên kết
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    
    # Lấy tất cả thông tin đề cương (để điền outline_title)
    outline_ids = [ch.outline_id for ch in chapters if ch.outline_id]
    outlines_map = {}
    if outline_ids:
        outlines_result = await db.execute(
            select(Outline).where(Outline.id.in_(outline_ids))
        )
        outlines_map = {o.id: o for o in outlines_result.scalars().all()}
    
    # Thêm thông tin đề cương cho tất cả chương (xử lý thống nhất)
    chapters_with_outline = []
    for chapter in chapters:
        chapter_dict = {
            "id": chapter.id,
            "project_id": chapter.project_id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "content": chapter.content,
            "summary": chapter.summary,
            "word_count": chapter.word_count,
            "status": chapter.status,
            "outline_id": chapter.outline_id,
            "sub_index": chapter.sub_index,
            "expansion_plan": chapter.expansion_plan,
            "created_at": chapter.created_at,
            "updated_at": chapter.updated_at,
        }
        
        # Thêm thông tin đề cương
        if chapter.outline_id and chapter.outline_id in outlines_map:
            outline = outlines_map[chapter.outline_id]
            chapter_dict["outline_title"] = outline.title
            chapter_dict["outline_order"] = outline.order_index
        else:
            chapter_dict["outline_title"] = None
            chapter_dict["outline_order"] = None
        
        chapters_with_outline.append(chapter_dict)
    
    return ChapterListResponse(total=total, items=chapters_with_outline)


@router.get("/{chapter_id}", response_model=ChapterResponse, summary="Lấy chi tiết chương")
async def get_chapter(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết chương theo ID"""
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    return chapter


@router.get("/{chapter_id}/navigation", summary="Lấy thông tin điều hướng chương")
async def get_chapter_navigation(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy thông tin điều hướng của chương (chương trước/chương sau)
    Dùng cho chức năng lật trang của trình đọc chương
    """
    # Lấy chương hiện tại
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    current_chapter = result.scalar_one_or_none()
    
    if not current_chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(current_chapter.project_id, user_id, db)
    
    # Lấy chương trước
    prev_result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == current_chapter.project_id)
        .where(Chapter.chapter_number < current_chapter.chapter_number)
        .order_by(Chapter.chapter_number.desc())
        .limit(1)
    )
    prev_chapter = prev_result.scalar_one_or_none()
    
    # Lấy chương sau
    next_result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == current_chapter.project_id)
        .where(Chapter.chapter_number > current_chapter.chapter_number)
        .order_by(Chapter.chapter_number.asc())
        .limit(1)
    )
    next_chapter = next_result.scalar_one_or_none()
    
    return {
        "current": {
            "id": current_chapter.id,
            "chapter_number": current_chapter.chapter_number,
            "title": current_chapter.title
        },
        "previous": {
            "id": prev_chapter.id,
            "chapter_number": prev_chapter.chapter_number,
            "title": prev_chapter.title
        } if prev_chapter else None,
        "next": {
            "id": next_chapter.id,
            "chapter_number": next_chapter.chapter_number,
            "title": next_chapter.title
        } if next_chapter else None
    }


@router.put("/{chapter_id}", response_model=ChapterResponse, summary="Cập nhật chương")
async def update_chapter(
    chapter_id: str,
    chapter_update: ChapterUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thông tin chương"""
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Ghi lại số từ cũ
    old_word_count = chapter.word_count or 0
    
    # Cập nhật các trường
    update_data = chapter_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)
    
    # Nếu nội dung được cập nhật, tính lại số từ (kể cả trường hợp xóa sạch nội dung)
    if "content" in update_data:
        new_word_count = len(chapter.content) if chapter.content else 0
        chapter.word_count = new_word_count
        
        # Cập nhật số từ của dự án
        result = await db.execute(
            select(Project).where(Project.id == chapter.project_id)
        )
        project = result.scalar_one_or_none()
        if project:
            project.current_words = project.current_words - old_word_count + new_word_count
        
        # Nếu nội dung bị xóa sạch, dọn dữ liệu liên quan
            if not chapter.content or chapter.content.strip() == "":
                chapter.status = "draft"
                
                # Dọn tác vụ phân tích
                analysis_tasks_result = await db.execute(
                    select(AnalysisTask).where(AnalysisTask.chapter_id == chapter_id)
                )
                analysis_tasks = analysis_tasks_result.scalars().all()
                for task in analysis_tasks:
                    await db.delete(task)
                
                # Dọn kết quả phân tích
                plot_analysis_result = await db.execute(
                    select(PlotAnalysis).where(PlotAnalysis.chapter_id == chapter_id)
                )
                plot_analyses = plot_analysis_result.scalars().all()
                for analysis in plot_analyses:
                    await db.delete(analysis)
                
                # Dọn ký ức truyện (database quan hệ)
                story_memories_result = await db.execute(
                    select(StoryMemory).where(StoryMemory.chapter_id == chapter_id)
                )
                story_memories = story_memories_result.scalars().all()
                for memory in story_memories:
                    await db.delete(memory)
                
                # Dọn dữ liệu ký ức trong database vector
                try:
                    await memory_service.delete_chapter_memories(
                        user_id=user_id,
                        project_id=chapter.project_id,
                        chapter_id=chapter_id
                    )
                    logger.info(f"✅ Đã dọn dữ liệu ký ức vector của chương {chapter_id[:8]}")
                except Exception as e:
                    logger.warning(f"⚠️ Dọn dữ liệu ký ức vector thất bại: {str(e)}")
                
                # 🔮 Dọn dữ liệu nút thắt phân tích liên quan đến chương
                try:
                    foreshadow_result = await foreshadow_service.delete_chapter_foreshadows(
                        db=db,
                        project_id=chapter.project_id,
                        chapter_id=chapter_id,
                        only_analysis_source=True  # Chỉ xóa nút thắt từ nguồn phân tích, giữ lại nút thắt tạo thủ công
                    )
                    if foreshadow_result['deleted_count'] > 0:
                        logger.info(f"🔮 Đã dọn {foreshadow_result['deleted_count']} dữ liệu nút thắt của chương {chapter_id[:8]}")
                except Exception as e:
                    logger.warning(f"⚠️ Dọn dữ liệu nút thắt thất bại: {str(e)}")
                
                logger.info(f"🗑️ Nội dung chương {chapter_id[:8]} đã xóa sạch, đã dọn dữ liệu phân tích, ký ức và nút thắt")
    
    await db.commit()
    await db.refresh(chapter)
    
    chapter_dict = {
        "id": chapter.id,
        "project_id": chapter.project_id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "content": chapter.content,
        "summary": chapter.summary,
        "word_count": chapter.word_count,
        "status": chapter.status,
        "outline_id": chapter.outline_id,
        "sub_index": chapter.sub_index,
        "expansion_plan": chapter.expansion_plan,
        "created_at": chapter.created_at,
        "updated_at": chapter.updated_at,
        "outline_title": None,
        "outline_order": None
    }
    
    # Nếu chương liên kết với đề cương, truy vấn thông tin đề cương
    if chapter.outline_id:
        outline_result = await db.execute(
            select(Outline).where(Outline.id == chapter.outline_id)
        )
        outline = outline_result.scalar_one_or_none()
        if outline:
            chapter_dict["outline_title"] = outline.title
            chapter_dict["outline_order"] = outline.order_index
    
    return chapter_dict


@router.delete("/{chapter_id}", summary="Xóa chương")
async def delete_chapter(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa chương"""
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Cập nhật số từ của dự án
    result = await db.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = result.scalar_one_or_none()
    if project:
        # Xử lý trường hợp word_count và current_words có thể là None
        chapter_word_count = chapter.word_count or 0
        project.current_words = max(0, (project.current_words or 0) - chapter_word_count)
    
    # 🗑️ Dọn dữ liệu ký ức trong database vector
    try:
        await memory_service.delete_chapter_memories(
            user_id=user_id,
            project_id=chapter.project_id,
            chapter_id=chapter_id
        )
        logger.info(f"✅ Đã dọn dữ liệu ký ức vector của chương {chapter_id[:8]}")
    except Exception as e:
        logger.warning(f"⚠️ Dọn dữ liệu ký ức vector thất bại: {str(e)}")
        # Không chặn quy trình xóa, tiếp tục thực hiện
    
    # 🔮 Dọn dữ liệu nút thắt liên quan đến chương này (chỉ nút thắt từ nguồn phân tích)
    try:
        foreshadow_result = await foreshadow_service.delete_chapter_foreshadows(
            db=db,
            project_id=chapter.project_id,
            chapter_id=chapter_id,
            only_analysis_source=True  # Chỉ xóa nút thắt từ nguồn phân tích, giữ lại nút thắt tạo thủ công
        )
        if foreshadow_result['deleted_count'] > 0:
            logger.info(f"🔮 Đã dọn {foreshadow_result['deleted_count']} dữ liệu nút thắt của chương {chapter_id[:8]}")
    except Exception as e:
        logger.warning(f"⚠️ Dọn dữ liệu nút thắt thất bại: {str(e)}")
        # Không chặn quy trình xóa, tiếp tục thực hiện
    
    # Xóa chương (ký ức trong database quan hệ sẽ bị xóa cascade)
    await db.delete(chapter)
    await db.commit()
    
    return {"message": "Xóa chương thành công"}


async def check_prerequisites(db: AsyncSession, chapter: Chapter) -> tuple[bool, str, list[Chapter]]:
    """
    Kiểm tra điều kiện tiên quyết của chương
    
    Args:
        db: Session database
        chapter: Chương hiện tại
        
    Returns:
        (có thể tạo không, thông tin lỗi, danh sách chương tiên quyết)
    """
    # Nếu là chương đầu, không cần kiểm tra tiên quyết
    if chapter.chapter_number == 1:
        return True, "", []
    
    # Truy vấn tất cả chương tiên quyết (số thứ tự nhỏ hơn chương hiện tại)
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == chapter.project_id)
        .where(Chapter.chapter_number < chapter.chapter_number)
        .order_by(Chapter.chapter_number)
    )
    previous_chapters = result.scalars().all()
    
    # Kiểm tra tất cả chương tiên quyết đã có nội dung chưa
    incomplete_chapters = [
        ch for ch in previous_chapters
        if not ch.content or ch.content.strip() == ""
    ]
    
    if incomplete_chapters:
        missing_numbers = [str(ch.chapter_number) for ch in incomplete_chapters]
        error_msg = f"Cần hoàn thành chương tiên quyết trước: chương {', '.join(missing_numbers)}"
        return False, error_msg, previous_chapters
    
    return True, "", previous_chapters


async def check_previous_analysis_ready(db: AsyncSession, chapter: Chapter) -> tuple[bool, str]:
    """Kiểm tra phân tích chương trước đã xong chưa, tránh chương sau dùng ký ức và trạng thái nhân vật cũ."""
    if chapter.chapter_number <= 1:
        return True, ""

    prev_result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == chapter.project_id)
        .where(Chapter.chapter_number < chapter.chapter_number)
        .order_by(Chapter.chapter_number.desc())
        .limit(1)
    )
    prev_chapter = prev_result.scalar_one_or_none()
    if not prev_chapter or not prev_chapter.content:
        return True, ""

    # Chỉ truy vấn trường scalar, tránh tái dùng thể hiện ORM cũ trong identity map của Session hiện tại.
    analysis_result = await db.execute(
        select(AnalysisTask.id, AnalysisTask.status)
        .where(AnalysisTask.chapter_id == prev_chapter.id)
        .order_by(AnalysisTask.created_at.desc())
        .limit(1)
    )
    analysis_task = analysis_result.first()
    if analysis_task and analysis_task.status == 'completed':
        return True, ""

    return False, f"Phân tích nội dung chương trước (chương {prev_chapter.chapter_number}) chưa xong, vui lòng đợi phân tích xong rồi mới tạo chương sau, để đảm bảo trạng thái nhân vật, ký ức và nút thắt liền mạch"


async def build_characters_info_with_careers(
    db: AsyncSession,
    project_id: str,
    characters: list[Character],
    filter_character_names: Optional[list[str]] = None
) -> str:
    """
    Xây dựng ngữ cảnh nhân vật bao gồm thông tin nghề nghiệp
    
    Args:
        db: Session database
        project_id: ID dự án
        characters: Danh sách nhân vật
        filter_character_names: Tùy chọn, lọc danh sách tên nhân vật cụ thể (dùng cho structure.characters của mode 1-1 hoặc expansion_plan.character_focus của mode 1-n)
        
    Returns:
        Chuỗi thông tin nhân vật đã định dạng, bao gồm thông tin nghề nghiệp
    """
    if not characters:
        return 'Chưa có thông tin nhân vật'
    
    # Nếu có danh sách lọc, chỉ giữ nhân vật khớp
    if filter_character_names:
        filtered_characters = [c for c in characters if c.name in filter_character_names]
        if not filtered_characters:
            logger.warning(f"Lọc xong không có nhân vật khớp, dùng tất cả nhân vật. Danh sách lọc: {filter_character_names}")
            filtered_characters = characters
        else:
            logger.info(f"Theo danh sách lọc giữ lại {len(filtered_characters)}/{len(characters)} nhân vật: {[c.name for c in filtered_characters]}")
        characters = filtered_characters
    
    # Lấy tất cả thông tin nghề nghiệp (truy vấn một lần, tăng hiệu quả)
    careers_result = await db.execute(
        select(Career).where(Career.project_id == project_id)
    )
    careers_map = {c.id: c for c in careers_result.scalars().all()}
    
    # Lấy liên kết nghề nghiệp của tất cả nhân vật (truy vấn một lần)
    character_ids = [c.id for c in characters]
    if not character_ids:
        return 'Chưa có thông tin nhân vật'
    
    # Xây dựng map tên nhân vật toàn cục (để hiển thị quan hệ)
    all_chars_result = await db.execute(
        select(Character.id, Character.name).where(Character.project_id == project_id)
    )
    all_char_name_map = {row.id: row.name for row in all_chars_result.all()}
        
    character_careers_result = await db.execute(
        select(CharacterCareer).where(CharacterCareer.character_id.in_(character_ids))
    )
    character_careers = character_careers_result.scalars().all()
    
    # Lấy quan hệ của tất cả nhân vật (truy vấn một lần)
    from sqlalchemy import or_
    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.project_id == project_id,
            or_(
                CharacterRelationship.character_from_id.in_(character_ids),
                CharacterRelationship.character_to_id.in_(character_ids)
            )
        )
    )
    all_relationships = rels_result.scalars().all()
    
    # Nhóm quan hệ theo ID nhân vật
    char_rels_map: dict[str, list] = {cid: [] for cid in character_ids}
    for r in all_relationships:
        if r.character_from_id in char_rels_map:
            char_rels_map[r.character_from_id].append(r)
        if r.character_to_id in char_rels_map:
            char_rels_map[r.character_to_id].append(r)
    
    # Lấy tất cả tổ chức và quan hệ thành viên (truy vấn một lần)
    orgs_result = await db.execute(
        select(Organization).where(Organization.project_id == project_id)
    )
    all_orgs = orgs_result.scalars().all()
    
    # Xây dựng map từ ID tổ chức sang tên tổ chức (qua bản ghi Character liên kết)
    org_name_map = {}  # org_id -> org_name
    char_id_to_org = {}  # character_id -> Organization (để bổ sung chi tiết cho thực thể tổ chức)
    for org in all_orgs:
        org_name_map[org.id] = all_char_name_map.get(org.character_id, 'Tổ chức chưa rõ')
        char_id_to_org[org.character_id] = org
    
    # Lấy quan hệ thành viên của tất cả tổ chức (truy vấn một lần)
    org_ids = [org.id for org in all_orgs]
    all_org_members = []
    if org_ids:
        all_org_members_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id.in_(org_ids)
            )
        )
        all_org_members = all_org_members_result.scalars().all()
    
    # Nhóm thành viên theo ID tổ chức (để thực thể tổ chức hiển thị danh sách thành viên)
    org_members_map: dict[str, list] = {oid: [] for oid in org_ids}
    for m in all_org_members:
        if m.organization_id in org_members_map:
            org_members_map[m.organization_id].append(m)
    
    # Lấy quan hệ thành viên liên quan đến nhân vật phi tổ chức hiện tại
    non_org_char_ids = [c.id for c in characters if not c.is_organization]
    char_org_map: dict[str, list] = {cid: [] for cid in non_org_char_ids}
    for m in all_org_members:
        if m.character_id in char_org_map:
            char_org_map[m.character_id].append(m)
    
    # Xây dựng map từ ID nhân vật sang thông tin nghề nghiệp
    char_career_map = {}
    for cc in character_careers:
        if cc.character_id not in char_career_map:
            char_career_map[cc.character_id] = {'main': None, 'sub': []}
        
        career = careers_map.get(cc.career_id)
        if not career:
            continue
            
        career_info = {
            'name': career.name,
            'stage': cc.current_stage,
            'max_stage': career.max_stage,
            'stage_progress': cc.stage_progress
        }
        
        if cc.career_type == 'main':
            char_career_map[cc.character_id]['main'] = career_info
        else:
            char_career_map[cc.character_id]['sub'].append(career_info)
    
    # Xây dựng chuỗi thông tin nhân vật
    characters_info_parts = []
    for c in characters:
        # Thông tin cơ bản (kèm đánh dấu trạng thái sống)
        entity_type = 'Tổ chức' if c.is_organization else 'Nhân vật'
        status_marker = ""
        char_status = getattr(c, 'status', None) or 'active'
        if char_status != 'active':
            STATUS_MARKERS = {
                'deceased': '💀Đã chết',
                'missing': '❓Đã mất tích',
                'retired': '📤Đã rời sân khấu',
                'destroyed': '💀Đã diệt vong'
            }
            status_marker = f" [{STATUS_MARKERS.get(char_status, char_status)}]"
        base_info = f"- {c.name}({entity_type}, {c.role_type}){status_marker}"
        
        # Thực thể tổ chức: bổ sung chi tiết tổ chức
        org_detail_str = ""
        if c.is_organization and c.id in char_id_to_org:
            org = char_id_to_org[c.id]
            org_detail_parts = []
            if c.organization_type:
                org_detail_parts.append(f"Loại:{c.organization_type}")
            if c.organization_purpose:
                purpose_preview = c.organization_purpose[:60] if len(c.organization_purpose) > 60 else c.organization_purpose
                org_detail_parts.append(f"Tôn chỉ:{purpose_preview}")
            if org.power_level is not None:
                org_detail_parts.append(f"Cấp thế lực:{org.power_level}")
            if org.location:
                org_detail_parts.append(f"Căn cứ:{org.location}")
            if org.motto:
                org_detail_parts.append(f"Khẩu hiệu:{org.motto}")
            if org.member_count:
                org_detail_parts.append(f"Số thành viên:{org.member_count}")
            if org_detail_parts:
                org_detail_str = f" | {', '.join(org_detail_parts)}"
            
            # Hiển thị danh sách thành viên nòng cốt của tổ chức (tối đa 5)
            if org.id in org_members_map and org_members_map[org.id]:
                member_parts = []
                for m in sorted(org_members_map[org.id], key=lambda x: -(x.rank or 0))[:5]:
                    m_name = all_char_name_map.get(m.character_id, 'Chưa rõ')
                    m_desc = f"{m_name}({m.position})"
                    if m.status and m.status != 'active':
                        m_desc += f"[{m.status}]"
                    member_parts.append(m_desc)
                if member_parts:
                    org_detail_str += f" | Thành viên: {', '.join(member_parts)}"
        
        # Thông tin nghề nghiệp
        career_info_str = ""
        if c.id in char_career_map:
            career_data = char_career_map[c.id]
            
            # Nghề chính
            if career_data['main']:
                main = career_data['main']
                stage_desc = f"{main['stage']}/{main['max_stage']} giai"
                career_info_str += f" | Nghề chính: {main['name']}({stage_desc})"
            
            # Nghề phụ
            if career_data['sub']:
                sub_list = []
                for sub in career_data['sub']:
                    stage_desc = f"{sub['stage']}/{sub['max_stage']} giai"
                    sub_list.append(f"{sub['name']}({stage_desc})")
                career_info_str += f" | Nghề phụ: {', '.join(sub_list)}"
        
        # Trạng thái tâm lý (do phân tích chương tự động cập nhật)
        state_str = ""
        if c.current_state:
            state_preview = c.current_state[:50] if len(c.current_state) > 50 else c.current_state
            state_str = f" | Trạng thái hiện tại: {state_preview}"
            if c.state_updated_chapter:
                state_str += f"(chương {c.state_updated_chapter})"
        
        # Thông tin thành viên tổ chức (chỉ nhân vật phi tổ chức mới hiển thị tổ chức trực thuộc)
        org_str = ""
        if not c.is_organization and c.id in char_org_map and char_org_map[c.id]:
            org_parts = []
            for m in char_org_map[c.id][:3]:  # Hiển thị tối đa 3 tổ chức
                o_name = org_name_map.get(m.organization_id, 'Tổ chức chưa rõ')
                o_desc = f"{o_name}({m.position})"
                if m.loyalty is not None and m.loyalty != 50:
                    o_desc += f"[Độ trung thành:{m.loyalty}]"
                if m.status and m.status != 'active':
                    o_desc += f"[{m.status}]"
                org_parts.append(o_desc)
            if org_parts:
                org_str = f" | Tổ chức trực thuộc: {', '.join(org_parts)}"
        
        # Thông tin quan hệ
        rel_str = ""
        if c.id in char_rels_map and char_rels_map[c.id]:
            rel_parts = []
            seen_pairs = set()  # Tránh hiển thị trùng cùng một cặp quan hệ
            for r in char_rels_map[c.id][:5]:  # Hiển thị tối đa 5 quan hệ
                # Xác định tên nhân vật đối phương
                if r.character_from_id == c.id:
                    other_name = all_char_name_map.get(r.character_to_id, 'Chưa rõ')
                else:
                    other_name = all_char_name_map.get(r.character_from_id, 'Chưa rõ')
                
                pair_key = tuple(sorted([c.id, r.character_from_id if r.character_from_id != c.id else r.character_to_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                rel_name = r.relationship_name or 'Liên quan'
                rel_desc = f"{other_name}({rel_name})"
                if r.intimacy_level is not None and r.intimacy_level != 50:
                    rel_desc += f"[Mức thân mật:{r.intimacy_level}]"
                rel_parts.append(rel_desc)
            
            if rel_parts:
                rel_str = f" | Quan hệ: {', '.join(rel_parts)}"
        
        # Mô tả tính cách
        personality_str = ""
        if c.personality:
            personality_preview = c.personality[:100] if len(c.personality) > 100 else c.personality
            personality_str = f": {personality_preview}"
        
        # Kết hợp thông tin đầy đủ
        full_info = base_info + org_detail_str + career_info_str + state_str + org_str + rel_str + personality_str
        characters_info_parts.append(full_info)
    
    return "\n".join(characters_info_parts)


@router.get("/{chapter_id}/can-generate", summary="Kiểm tra chương có thể tạo không")
async def check_can_generate(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Kiểm tra chương có đáp ứng điều kiện tạo không
    Trả về trạng thái có thể tạo và thông tin chương tiên quyết
    """
    # Lấy chương
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Kiểm tra điều kiện tiên quyết
    can_generate, error_msg, previous_chapters = await check_prerequisites(db, chapter)
    
    # Xây dựng thông tin chương tiên quyết
    previous_info = [
        {
            "id": ch.id,
            "chapter_number": ch.chapter_number,
            "title": ch.title,
            "has_content": bool(ch.content and ch.content.strip()),
            "word_count": ch.word_count or 0
        }
        for ch in previous_chapters
    ]
    
    return {
        "can_generate": can_generate,
        "reason": error_msg if not can_generate else "",
        "previous_chapters": previous_info,
        "chapter_number": chapter.chapter_number
    }


async def analyze_chapter_background(
    chapter_id: str,
    user_id: str,
    project_id: str,
    task_id: str,
    ai_service: Optional[AIService] = None,
    progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
) -> bool:
    """Thực hiện phân tích chương có đảm bảo timeout cứng, và đảm bảo tác vụ vào trạng thái cuối sau khi bị ngắt."""
    try:
        return await asyncio.wait_for(
            _analyze_chapter_background_impl(
                chapter_id=chapter_id,
                user_id=user_id,
                project_id=project_id,
                task_id=task_id,
                ai_service=ai_service,
                progress_callback=progress_callback,
            ),
            timeout=ANALYSIS_TASK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        error_message = f"Tác vụ phân tích hết thời gian (quá {ANALYSIS_TASK_TIMEOUT_SECONDS // 60} phút)"
        logger.error(f"❌ {error_message}: chapter_id={chapter_id}, task_id={task_id}")
        await _set_analysis_task_terminal_state(user_id, task_id, "failed", error_message)
        return False
    except asyncio.CancelledError:
        terminal_update = asyncio.create_task(
            _set_analysis_task_terminal_state(
                user_id,
                task_id,
                "failed",
                "Tác vụ phân tích bị hủy hoặc dịch vụ đã tắt",
            )
        )
        await asyncio.shield(terminal_update)
        raise


async def _analyze_chapter_background_impl(
    chapter_id: str,
    user_id: str,
    project_id: str,
    task_id: str,
    ai_service: Optional[AIService] = None,
    progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
) -> bool:
    """
    Phân tích chương bất đồng bộ ở nền (hỗ trợ đồng thời, dùng khóa bảo vệ ghi database)
    
    Args:
        chapter_id: ID chương
        user_id: ID người dùng
        project_id: ID dự án
        task_id: ID tác vụ
        ai_service: Thể hiện dịch vụ AI
        
    Returns:
        bool: True nghĩa là phân tích thành công, False nghĩa là phân tích thất bại
    """
    db_session = None
    write_lock = await get_db_write_lock(user_id)

    async def report_progress(progress: int) -> None:
        if not progress_callback:
            return
        try:
            await progress_callback(progress)
        except Exception as callback_error:
            logger.warning(f"⚠️ Đồng bộ tiến độ phân tích chương thất bại: {callback_error}")
    
    try:
        logger.info(f"🔍 Bắt đầu phân tích chương: {chapter_id}, ID tác vụ: {task_id}")
        
        # Tạo session database độc lập
        from app.database import get_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        db_session = AsyncSessionLocal()
        
        # 1. Lấy tác vụ (thao tác đọc)
        task_result = await db_session.execute(
            select(AnalysisTask).where(AnalysisTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        
        if not task:
            logger.error(f"❌ Tác vụ không tồn tại: {task_id}")
            return False
        if task.status not in ("pending", "running"):
            logger.warning(f"Tác vụ phân tích đã kết thúc, bỏ qua thực hiện: {task_id}, status={task.status}")
            return False
        
        # Cập nhật trạng thái tác vụ (thao tác ghi, cần khóa)
        async with write_lock:
            task.status = 'running'
            task.started_at = datetime.now()
            task.progress = 10
            await db_session.commit()
        await report_progress(10)
        
        # 2. Lấy thông tin chương (thao tác đọc)
        chapter_result = await db_session.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter or not chapter.content:
            async with write_lock:
                task.status = 'failed'
                task.error_message = 'Chương không tồn tại hoặc nội dung rỗng'
                task.completed_at = datetime.now()
                await db_session.commit()
            logger.error(f"❌ Chương không tồn tại hoặc nội dung rỗng: {chapter_id}")
            return False
        
        async with write_lock:
            task.progress = 20
            await db_session.commit()
        await report_progress(20)
        
        if ai_service is None:
            ai_service = await get_user_ai_service_from_db_by_usage(
                user_id=user_id,
                db=db_session,
                usage="chapter_analysis"
            )

        # Lấy danh sách nút thắt đã gài (để khớp thu hồi, truyền số chương hiện tại để bật đánh dấu thông minh)
        existing_foreshadows = await foreshadow_service.get_planted_foreshadows_for_analysis(
            db=db_session,
            project_id=project_id,
            current_chapter_number=chapter.chapter_number  # Truyền số chương hiện tại để bật đánh dấu thông minh
        )
        logger.info(f"📋 Phân tích nền - đã lấy {len(existing_foreshadows)} nút thắt đã gài để khớp (kèm đánh dấu thu hồi thông minh)")
        
        # Lấy thông tin nhân vật của dự án (lọc nhân vật liên quan chương này theo đề cương/kế hoạch triển khai)
        filter_character_names = None
        
        # Mode 1-N: trích character_focus từ expansion_plan
        if chapter.expansion_plan:
            try:
                plan = json.loads(chapter.expansion_plan)
                focus_names = plan.get('character_focus', [])
                if focus_names:
                    filter_character_names = focus_names
                    logger.info(f"📋 Trích tiêu điểm nhân vật từ expansion_plan: {filter_character_names}")
            except (json.JSONDecodeError, Exception):
                pass
        
        # Mode 1-1: trích characters từ outline.structure
        if not filter_character_names and chapter.outline_id:
            try:
                outline_result = await db_session.execute(
                    select(Outline).where(Outline.id == chapter.outline_id)
                )
                chapter_outline = outline_result.scalar_one_or_none()
                if chapter_outline and chapter_outline.structure:
                    structure = json.loads(chapter_outline.structure)
                    raw_characters = structure.get('characters', [])
                    if raw_characters:
                        filter_character_names = [
                            c['name'] if isinstance(c, dict) else c
                            for c in raw_characters
                        ]
                        logger.info(f"📋 Trích nhân vật từ outline.structure: {filter_character_names}")
            except (json.JSONDecodeError, Exception):
                pass
        
        # Truy vấn nhân vật (theo danh sách lọc hoặc tất cả)
        characters_query = select(Character).where(Character.project_id == project_id)
        if filter_character_names:
            characters_query = characters_query.where(Character.name.in_(filter_character_names))
        characters_result = await db_session.execute(characters_query)
        project_characters = characters_result.scalars().all()
        
        # Nếu lọc xong không có nhân vật, hạ cấp về tất cả nhân vật
        if not project_characters and filter_character_names:
            logger.warning(f"⚠️ Lọc xong không có nhân vật khớp, hạ cấp về tất cả nhân vật")
            characters_result = await db_session.execute(
                select(Character).where(Character.project_id == project_id)
            )
            project_characters = characters_result.scalars().all()
            filter_character_names = None
        
        characters_info = await build_characters_info_with_careers(
            db=db_session,
            project_id=project_id,
            characters=project_characters,
            filter_character_names=filter_character_names
        )
        logger.info(f"📋 Phân tích nền - đã lấy thông tin {len(project_characters)} nhân vật để phân tích")
        
        # Định nghĩa callback thử lại, để cập nhật trạng thái tác vụ khi thử lại
        async def on_retry_callback(attempt: int, max_retries: int, wait_time: int, error_reason: str):
            """Cập nhật trạng thái tác vụ khi thử lại, để frontend cảm nhận được tiến độ thử lại"""
            try:
                async with write_lock:
                    # Lấy lại tác vụ (đảm bảo lấy trạng thái mới nhất)
                    task_result_retry = await db_session.execute(
                        select(AnalysisTask).where(AnalysisTask.id == task_id)
                    )
                    task_retry = task_result_retry.scalar_one_or_none()
                    if task_retry:
                        # Cập nhật trạng thái tác vụ, giữ running nhưng cập nhật started_at để đặt lại bộ đếm timeout
                        task_retry.status = 'running'
                        task_retry.started_at = datetime.now()  # Đặt lại thời gian bắt đầu, tránh phát hiện timeout sai
                        task_retry.progress = 25 + attempt * 5  # Cập nhật tiến độ theo số lần thử lại
                        task_retry.error_message = f"Đang thử lại ({attempt}/{max_retries}): {error_reason[:100]}"
                        await db_session.commit()
                        logger.info(f"🔄 Trạng thái thử lại tác vụ phân tích đã cập nhật: lần {attempt}/{max_retries}, đợi {wait_time}s, lý do: {error_reason[:50]}...")
                await report_progress(25 + attempt * 5)
            except Exception as callback_error:
                logger.warning(f"⚠️ Cập nhật trạng thái thử lại thất bại: {callback_error}")
        
        # 3. Dùng PlotAnalyzer phân tích chương (truyền danh sách nút thắt đã có, thông tin nhân vật và callback thử lại)
        analyzer = PlotAnalyzer(ai_service)
        analysis_result = await analyzer.analyze_chapter(
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            content=chapter.content,
            word_count=chapter.word_count or len(chapter.content),
            existing_foreshadows=existing_foreshadows,
            on_retry=on_retry_callback,
            characters_info=characters_info
        )
        
        if not analysis_result:
            async with write_lock:
                task.status = 'failed'
                task.error_message = 'AI phân tích thất bại, vui lòng kiểm tra log'
                task.completed_at = datetime.now()
                await db_session.commit()
            logger.error(f"❌ AI phân tích thất bại: {chapter_id}")
            return False
        
        async with write_lock:
            task.progress = 60
            await db_session.commit()
        await report_progress(60)
        
        # 4. Lưu kết quả phân tích vào database (thao tác ghi, cần khóa)
        async with write_lock:
            existing_analysis_result = await db_session.execute(
                select(PlotAnalysis).where(PlotAnalysis.chapter_id == chapter_id)
            )
            existing_analysis = existing_analysis_result.scalar_one_or_none()
            
            if existing_analysis:
                # Cập nhật bản ghi hiện có
                logger.info(f"  Cập nhật bản ghi phân tích hiện có: {existing_analysis.id}")
                existing_analysis.plot_stage = analysis_result.get('plot_stage', '发展')
                existing_analysis.conflict_level = analysis_result.get('conflict', {}).get('level', 0)
                existing_analysis.conflict_types = analysis_result.get('conflict', {}).get('types', [])
                existing_analysis.emotional_tone = analysis_result.get('emotional_arc', {}).get('primary_emotion', '')
                existing_analysis.emotional_intensity = analysis_result.get('emotional_arc', {}).get('intensity', 0) / 10.0
                existing_analysis.hooks = analysis_result.get('hooks', [])
                existing_analysis.hooks_count = len(analysis_result.get('hooks', []))
                existing_analysis.foreshadows = analysis_result.get('foreshadows', [])
                existing_analysis.foreshadows_planted = sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'planted')
                existing_analysis.foreshadows_resolved = sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'resolved')
                existing_analysis.plot_points = analysis_result.get('plot_points', [])
                existing_analysis.plot_points_count = len(analysis_result.get('plot_points', []))
                existing_analysis.character_states = analysis_result.get('character_states', [])
                existing_analysis.scenes = analysis_result.get('scenes', [])
                existing_analysis.pacing = analysis_result.get('pacing', 'moderate')
                existing_analysis.overall_quality_score = analysis_result.get('scores', {}).get('overall', 0)
                existing_analysis.pacing_score = analysis_result.get('scores', {}).get('pacing', 0)
                existing_analysis.engagement_score = analysis_result.get('scores', {}).get('engagement', 0)
                existing_analysis.coherence_score = analysis_result.get('scores', {}).get('coherence', 0)
                existing_analysis.analysis_report = analyzer.generate_analysis_summary(analysis_result)
                existing_analysis.suggestions = analysis_result.get('suggestions', [])
                existing_analysis.dialogue_ratio = analysis_result.get('dialogue_ratio', 0)
                existing_analysis.description_ratio = analysis_result.get('description_ratio', 0)
            else:
                # Tạo bản ghi mới
                logger.info(f"  Tạo bản ghi phân tích mới")
                plot_analysis = PlotAnalysis(
                    chapter_id=chapter_id,
                    project_id=project_id,
                    plot_stage=analysis_result.get('plot_stage', '发展'),
                    conflict_level=analysis_result.get('conflict', {}).get('level', 0),
                    conflict_types=analysis_result.get('conflict', {}).get('types', []),
                    emotional_tone=analysis_result.get('emotional_arc', {}).get('primary_emotion', ''),
                    emotional_intensity=analysis_result.get('emotional_arc', {}).get('intensity', 0) / 10.0,
                    hooks=analysis_result.get('hooks', []),
                    hooks_count=len(analysis_result.get('hooks', [])),
                    foreshadows=analysis_result.get('foreshadows', []),
                    foreshadows_planted=sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'planted'),
                    foreshadows_resolved=sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'resolved'),
                    plot_points=analysis_result.get('plot_points', []),
                    plot_points_count=len(analysis_result.get('plot_points', [])),
                    character_states=analysis_result.get('character_states', []),
                    scenes=analysis_result.get('scenes', []),
                    pacing=analysis_result.get('pacing', 'moderate'),
                    overall_quality_score=analysis_result.get('scores', {}).get('overall', 0),
                    pacing_score=analysis_result.get('scores', {}).get('pacing', 0),
                    engagement_score=analysis_result.get('scores', {}).get('engagement', 0),
                    coherence_score=analysis_result.get('scores', {}).get('coherence', 0),
                    analysis_report=analyzer.generate_analysis_summary(analysis_result),
                    suggestions=analysis_result.get('suggestions', []),
                    dialogue_ratio=analysis_result.get('dialogue_ratio', 0),
                    description_ratio=analysis_result.get('description_ratio', 0)
                )
                db_session.add(plot_analysis)
            
            await db_session.commit()
            
            task.progress = 80
            await db_session.commit()
        await report_progress(80)
        
        # 5. Dọn nút thắt phân tích cũ (phân tích lại cần dọn trước)
        try:
            async with write_lock:
                clean_result = await foreshadow_service.clean_chapter_analysis_foreshadows(
                    db=db_session,
                    project_id=project_id,
                    chapter_id=chapter_id
                )
            if clean_result['cleaned_count'] > 0:
                logger.info(f"🧹 Trước khi phân tích lại đã dọn {clean_result['cleaned_count']} nút thắt cũ")
        except Exception as clean_error:
            logger.warning(f"⚠️ Dọn nút thắt cũ thất bại (tiếp tục phân tích): {str(clean_error)}")
        
        # 6. Trích ký ức và lưu vào database vector (truyền nội dung chương để tính vị trí)
        memories = analyzer.extract_memories_from_analysis(
            analysis=analysis_result,
            chapter_id=chapter_id,
            chapter_number=chapter.chapter_number,
            chapter_content=chapter.content or "",
            chapter_title=chapter.title or ""
        )
        
        # Xóa ký ức cũ của chương này trước (thao tác ghi, cần khóa)
        async with write_lock:
            old_memories_result = await db_session.execute(
                select(StoryMemory).where(StoryMemory.chapter_id == chapter_id)
            )
            old_memories = old_memories_result.scalars().all()
            for old_mem in old_memories:
                await db_session.delete(old_mem)
            await db_session.commit()
            logger.info(f"  Đã xóa {len(old_memories)} ký ức cũ")
        
        # Chuẩn bị dữ liệu ký ức thêm hàng loạt (không cần khóa)
        memory_records = []
        for mem in memories:
            memory_id = f"{chapter_id}_{mem['type']}_{len(memory_records)}"
            memory_records.append({
                'id': memory_id,
                'content': mem['content'],
                'type': mem['type'],
                'metadata': mem['metadata']
            })
            
        # Lưu vào database quan hệ (thao tác ghi, cần khóa)
        async with write_lock:
            for index, mem in enumerate(memories):
                memory_id = memory_records[index]['id']
                text_position = mem['metadata'].get('text_position', -1)
                text_length = mem['metadata'].get('text_length', 0)
                
                story_memory = StoryMemory(
                    id=memory_id,
                    project_id=project_id,
                    chapter_id=chapter_id,
                    memory_type=mem['type'],
                    content=mem['content'],
                    title=mem['title'],
                    importance_score=mem['metadata'].get('importance_score', 0.5),
                    tags=mem['metadata'].get('tags', []),
                    is_foreshadow=mem['metadata'].get('is_foreshadow', 0),
                    story_timeline=chapter.chapter_number,
                    chapter_position=text_position,
                    text_length=text_length,
                    related_characters=mem['metadata'].get('related_characters', []),
                    related_locations=mem['metadata'].get('related_locations', [])
                )
                db_session.add(story_memory)
                
                if text_position >= 0:
                    logger.debug(f"  Lưu ký ức {memory_id}: position={text_position}, length={text_length}")
            
            await db_session.commit()
        
        # Thêm hàng loạt vào database vector
        if memory_records:
            added_count = await memory_service.batch_add_memories(
                user_id=user_id,
                project_id=project_id,
                memories=memory_records
            )
            logger.info(f"✅ Đã thêm {added_count} ký ức vào kho vector")
        
        # 💼 Cập nhật nghề nghiệp nhân vật (theo kết quả phân tích)
        if analysis_result.get('character_states'):
            try:
                from app.services.career_update_service import CareerUpdateService
                
                logger.info(f"💼 Bắt đầu cập nhật nghề nghiệp nhân vật theo kết quả phân tích...")
                career_update_result = await CareerUpdateService.update_careers_from_analysis(
                    db=db_session,
                    project_id=project_id,
                    character_states=analysis_result.get('character_states', []),
                    chapter_id=chapter_id,
                    chapter_number=chapter.chapter_number
                )
                
                if career_update_result['updated_count'] > 0:
                    logger.info(
                        f"✅ Đã cập nhật thông tin nghề nghiệp của {career_update_result['updated_count']} nhân vật"
                    )
                    if career_update_result['changes']:
                        for change in career_update_result['changes']:
                            logger.info(f"  - {change}")
                else:
                    logger.info("ℹ️ Chương này không có thay đổi nghề nghiệp nhân vật")
                    
            except Exception as career_error:
                # Cập nhật nghề nghiệp thất bại không nên ảnh hưởng toàn bộ quy trình phân tích
                logger.error(f"⚠️ Cập nhật nghề nghiệp nhân vật thất bại: {str(career_error)}", exc_info=True)
        else:
            logger.debug("📋 Kết quả phân tích không có thông tin trạng thái nhân vật, bỏ qua cập nhật nghề nghiệp")
        
        # 👤 Cập nhật trạng thái tâm lý và quan hệ nhân vật (theo kết quả phân tích)
        if analysis_result.get('character_states'):
            try:
                from app.services.character_state_update_service import CharacterStateUpdateService
                
                logger.info(f"👤 Bắt đầu cập nhật trạng thái nhân vật, quan hệ và thành viên tổ chức theo kết quả phân tích...")
                async with write_lock:
                    state_update_result = await CharacterStateUpdateService.update_from_analysis(
                        db=db_session,
                        project_id=project_id,
                        character_states=analysis_result.get('character_states', []),
                        chapter_id=chapter_id,
                        chapter_number=chapter.chapter_number
                    )
                
                total_state_changes = (
                    state_update_result['state_updated_count'] +
                    state_update_result['relationship_created_count'] +
                    state_update_result['relationship_updated_count'] +
                    state_update_result.get('org_updated_count', 0)
                )
                if total_state_changes > 0:
                    logger.info(
                        f"✅ Cập nhật trạng thái nhân vật: trạng thái tâm lý {state_update_result['state_updated_count']}, "
                        f"tạo mới {state_update_result['relationship_created_count']} quan hệ, "
                        f"cập nhật {state_update_result['relationship_updated_count']} quan hệ, "
                        f"thay đổi tổ chức {state_update_result.get('org_updated_count', 0)}"
                    )
                    if state_update_result['changes']:
                        for change in state_update_result['changes'][:8]:
                            logger.info(f"  - {change}")
                else:
                    logger.info("ℹ️ Chương này không có thay đổi trạng thái nhân vật, quan hệ hay tổ chức")
                    
            except Exception as state_error:
                # Cập nhật trạng thái nhân vật thất bại không nên ảnh hưởng toàn bộ quy trình phân tích
                logger.error(f"⚠️ Cập nhật trạng thái nhân vật, quan hệ và tổ chức thất bại: {str(state_error)}", exc_info=True)
        
        # 🏛️ Cập nhật trạng thái bản thân tổ chức (theo kết quả phân tích)
        if analysis_result.get('organization_states'):
            try:
                from app.services.character_state_update_service import CharacterStateUpdateService
                
                logger.info(f"🏛️ Bắt đầu cập nhật trạng thái bản thân tổ chức theo kết quả phân tích...")
                async with write_lock:
                    org_state_result = await CharacterStateUpdateService.update_organization_states(
                        db=db_session,
                        project_id=project_id,
                        organization_states=analysis_result.get('organization_states', []),
                        chapter_number=chapter.chapter_number
                    )
                
                if org_state_result['updated_count'] > 0:
                    logger.info(
                        f"✅ Cập nhật trạng thái tổ chức: {org_state_result['updated_count']} tổ chức"
                    )
                    if org_state_result['changes']:
                        for change in org_state_result['changes'][:5]:
                            logger.info(f"  - {change}")
                else:
                    logger.info("ℹ️ Chương này không có thay đổi trạng thái bản thân tổ chức")
                    
            except Exception as org_state_error:
                # Cập nhật trạng thái tổ chức thất bại không nên ảnh hưởng toàn bộ quy trình phân tích
                logger.error(f"⚠️ Cập nhật trạng thái bản thân tổ chức thất bại: {str(org_state_error)}", exc_info=True)
        
        # 🔮 Tự động cập nhật trạng thái nút thắt (theo kết quả phân tích)
        if analysis_result.get('foreshadows'):
            try:
                logger.info(f"🔮 Bắt đầu tự động cập nhật trạng thái nút thắt theo kết quả phân tích...")
                async with write_lock:
                    foreshadow_stats = await foreshadow_service.auto_update_from_analysis(
                        db=db_session,
                        project_id=project_id,
                        chapter_id=chapter_id,
                        chapter_number=chapter.chapter_number,
                        analysis_foreshadows=analysis_result.get('foreshadows', [])
                    )
                
                if foreshadow_stats['planted_count'] > 0 or foreshadow_stats['resolved_count'] > 0:
                    logger.info(
                        f"✅ Tự động cập nhật nút thắt: đã gài {foreshadow_stats['planted_count']}, "
                        f"thu hồi {foreshadow_stats['resolved_count']}"
                    )
                else:
                    logger.info("ℹ️ Chương này không có thay đổi trạng thái nút thắt mới")
                    
            except Exception as foreshadow_error:
                # Cập nhật nút thắt thất bại không nên ảnh hưởng toàn bộ quy trình phân tích
                logger.error(f"⚠️ Tự động cập nhật nút thắt thất bại: {str(foreshadow_error)}", exc_info=True)
        else:
            logger.debug("📋 Kết quả phân tích không có thông tin nút thắt, bỏ qua tự động cập nhật nút thắt")
        
        update_success = await _set_analysis_task_terminal_state(
            user_id, task_id, "completed"
        )
        if update_success:
            await report_progress(100)
            logger.info(f"✅ Phân tích chương xong: {chapter_id}, trích {len(memories)} ký ức")
        else:
            logger.error(f"❌ Phân tích chương xong nhưng không thể cập nhật trạng thái cuối tác vụ: {chapter_id}")
        return update_success
        
    except Exception as e:
        logger.error(f"❌ Phân tích nền bất thường: {str(e)}", exc_info=True)
        if db_session:
            try:
                await db_session.rollback()
            except Exception as rollback_error:
                logger.warning(f"Rollback transaction phân tích thất bại: {rollback_error}")
        await _set_analysis_task_terminal_state(
            user_id, task_id, "failed", str(e)[:500]
        )
        return False
        
    finally:
        if db_session:
            await db_session.close()


@router.post("/{chapter_id}/generate-stream", summary="AI sáng tác nội dung chương (streaming)")
async def generate_chapter_content_stream(
    chapter_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    generate_request: ChapterGenerateRequest = ChapterGenerateRequest(),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dựa trên đề cương, nội dung chương tiên quyết và thông tin dự án, AI sáng tác nội dung đầy đủ của chương (trả về streaming)
    Yêu cầu: phải tạo theo thứ tự, đảm bảo các chương tiên quyết đều đã xong
    
    Tham số body request:
    - style_id: tùy chọn, chỉ định ID phong cách viết dùng. Không cung cấp thì không dùng phong cách nào
    - target_word_count: tùy chọn, số từ mục tiêu, mặc định 3000 từ, phạm vi 500-10000 từ
    - enable_mcp: tùy chọn, có bật tăng cường công cụ MCP không, mặc định True
    
    Lưu ý: hàm này không dùng db từ dependency injection, mà tạo session database độc lập bên trong generator
    để tránh rò rỉ kết nối trong thời gian response streaming
    """
    style_id = generate_request.style_id
    target_word_count = generate_request.target_word_count or 3000
    custom_model = generate_request.model if hasattr(generate_request, 'model') else None
    temp_narrative_perspective = generate_request.narrative_perspective if hasattr(generate_request, 'narrative_perspective') else None
    skill_key = generate_request.skill_key if hasattr(generate_request, 'skill_key') else None
    # Xác minh trước chương có tồn tại không (dùng session tạm)
    async for temp_db in get_db(request):
        try:
            result = await temp_db.execute(
                select(Chapter).where(Chapter.id == chapter_id)
            )
            chapter = result.scalar_one_or_none()
            if not chapter:
                raise HTTPException(status_code=404, detail="Chương không tồn tại")
            
            # Kiểm tra điều kiện tiên quyết
            can_generate, error_msg, previous_chapters = await check_prerequisites(temp_db, chapter)
            if not can_generate:
                raise HTTPException(status_code=400, detail=error_msg)
            analysis_ready, analysis_msg = await check_previous_analysis_ready(temp_db, chapter)
            if not analysis_ready:
                raise HTTPException(status_code=409, detail=analysis_msg)
            
            # Lưu dữ liệu chương tiên quyết để generator dùng
            previous_chapters_data = [
                {
                    'id': ch.id,
                    'chapter_number': ch.chapter_number,
                    'title': ch.title,
                    'content': ch.content
                }
                for ch in previous_chapters
            ]
        finally:
            await temp_db.close()
        break
    
    async def event_generator():
        # Tạo session database độc lập bên trong generator
        db_session = None
        db_committed = False
        # Lấy ID người dùng hiện tại (cần ngay bên ngoài generator)
        current_user_id = getattr(request.state, "user_id", "system")
        
        # Khởi tạo tracker tiến độ chuẩn
        from app.utils.sse_response import WizardProgressTracker
        tracker = WizardProgressTracker("Chương")
        
        try:
            yield await tracker.start()
            
            # Tạo session database mới
            async for db_session in get_db(request):
                # === Giai đoạn tải ===
                yield await tracker.loading("Đang tải thông tin chương...", 0.2)
                
                # Lấy lại thông tin chương
                chapter_result = await db_session.execute(
                    select(Chapter).where(Chapter.id == chapter_id)
                )
                current_chapter = chapter_result.scalar_one_or_none()
                if not current_chapter:
                    yield await tracker.error("Chương không tồn tại", 404)
                    return
            
                yield await tracker.loading("Đang tải thông tin dự án...", 0.4)
                
                # Lấy thông tin dự án
                project_result = await db_session.execute(
                    select(Project).where(Project.id == current_chapter.project_id)
                )
                project = project_result.scalar_one_or_none()
                if not project:
                    yield await tracker.error("Dự án không tồn tại", 404)
                    return
                
                # Lấy mode đề cương của dự án
                outline_mode = project.outline_mode if project else 'one-to-many'
                logger.info(f"📋 Mode đề cương dự án: {outline_mode}")
                
                # Lấy đề cương tương ứng (ưu tiên liên kết trực tiếp bằng chapter.outline_id)
                if current_chapter.outline_id:
                    outline_result = await db_session.execute(
                        select(Outline)
                        .where(Outline.id == current_chapter.outline_id)
                        .execution_options(populate_existing=True)
                    )
                else:
                    # Dự phòng tìm theo số thứ tự
                    outline_result = await db_session.execute(
                        select(Outline)
                        .where(Outline.project_id == current_chapter.project_id)
                        .where(Outline.order_index == current_chapter.chapter_number)
                        .execution_options(populate_existing=True)
                    )
                outline = outline_result.scalar_one_or_none()
                
                # Lấy phong cách viết
                style_content = ""
                if style_id:
                    # Dùng phong cách đã chỉ định
                    style_result = await db_session.execute(
                        select(WritingStyle).where(WritingStyle.id == style_id)
                    )
                    style = style_result.scalar_one_or_none()
                    if style:
                        # Xác minh phong cách có dùng được không: phong cách preset toàn cục (user_id là NULL) hoặc phong cách tùy chỉnh của người dùng hiện tại
                        if style.user_id is None or style.user_id == current_user_id:
                            style_content = style.prompt_content or ""
                            style_type = "Preset toàn cục" if style.user_id is None else "Tùy chỉnh của người dùng"
                            logger.info(f"Dùng phong cách đã chỉ định: {style.name} ({style_type})")
                        else:
                            logger.warning(f"Phong cách {style_id} không thuộc dự án hiện tại, không thể dùng")
                    else:
                        logger.warning(f"Không tìm thấy phong cách {style_id}")
                else:
                    logger.info("Chưa chỉ định phong cách viết, dùng prompt gốc")
                
                # 🚀 Chọn context builder độc lập theo mode đề cương
                if outline_mode == 'one-to-one':
                    # ========== Mode 1-1: dùng builder rút gọn độc lập ==========
                    logger.info(f"🔧 [Mode 1-1] dùng OneToOneContextBuilder")
                    context_builder = OneToOneContextBuilder(
                        memory_service=memory_service,
                        foreshadow_service=foreshadow_service
                    )
                    chapter_context = await context_builder.build(
                        chapter=current_chapter,
                        project=project,
                        outline=outline,
                        user_id=current_user_id,
                        db=db_session,
                        target_word_count=target_word_count
                    )
                    
                    # Log thống kê
                    logger.info(f"📊 [Mode 1-1] Thống kê ngữ cảnh:")
                    logger.info(f" - Số thứ tự chương: {current_chapter.chapter_number}")
                    logger.info(f" - Độ dài đề cương: {chapter_context.context_stats.get('outline_length', 0)} ký tự")
                    logger.info(f" - Nội dung chương trước: {chapter_context.context_stats.get('previous_content_length', 0)} ký tự")
                    logger.info(f" - Thông tin nhân vật: {chapter_context.context_stats.get('characters_length', 0)} ký tự")
                    logger.info(f" - Nhắc nút thắt: {chapter_context.context_stats.get('foreshadow_length', 0)} ký tự")
                    logger.info(f" - Ký ức liên quan: {chapter_context.context_stats.get('memories_length', 0)} ký tự")
                    logger.info(f" - Tổng độ dài: {chapter_context.context_stats.get('total_length', 0)} ký tự")
                else:
                    # ========== Mode 1-N: dùng builder đầy đủ độc lập ==========
                    logger.info(f"🔧 [Mode 1-N] dùng OneToManyContextBuilder")
                    context_builder = OneToManyContextBuilder(
                        memory_service=memory_service,
                        foreshadow_service=foreshadow_service
                    )
                    chapter_context = await context_builder.build(
                        chapter=current_chapter,
                        project=project,
                        outline=outline,
                        user_id=current_user_id,
                        db=db_session,
                        style_content=style_content,
                        target_word_count=target_word_count,
                        temp_narrative_perspective=temp_narrative_perspective
                    )
                    
                    # Log thống kê
                    logger.info(f"📊 [Mode 1-N] Thống kê ngữ cảnh:")
                    logger.info(f" - Số thứ tự chương: {current_chapter.chapter_number}")
                    logger.info(f" - Điểm nối tiếp: {chapter_context.context_stats.get('continuation_length', 0)} ký tự")
                    logger.info(f" - Thông tin nhân vật: {chapter_context.context_stats.get('characters_length', 0)} ký tự")
                    logger.info(f" - Ký ức liên quan: {chapter_context.context_stats.get('memories_length', 0)} ký tự")
                    logger.info(f" - Khung truyện: {chapter_context.context_stats.get('skeleton_length', 0)} ký tự")
                    logger.info(f" - Nhắc nút thắt: {chapter_context.context_stats.get('foreshadow_length', 0)} ký tự")
                    logger.info(f" - Tổng độ dài: {chapter_context.context_stats.get('total_length', 0)} ký tự")
            
                yield await tracker.loading("Xây dựng ngữ cảnh xong", 0.8)
                
                # 🎭 Xác định ngôi kể dùng (chỉ định tạm > mặc định dự án > mặc định hệ thống)
                chapter_perspective = (
                    temp_narrative_perspective or
                    project.narrative_perspective or
                    'Ngôi thứ ba'
                )
                logger.info(f"📝 Dùng ngôi kể: {chapter_perspective}")
                
                # 🚀 Chọn template prompt và tham số theo mode đề cương
                if outline_mode == 'one-to-one':
                    # Mode 1-1
                    if chapter_context.continuation_point:
                        # Có nội dung chương trước
                        template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE_NEXT", current_user_id, db_session)
                        base_prompt = PromptService.format_prompt(
                            template,
                            project_title=project.title,
                            chapter_number=current_chapter.chapter_number,
                            chapter_title=current_chapter.title,
                            chapter_outline=chapter_context.chapter_outline,
                            target_word_count=target_word_count,
                            genre=project.genre or 'Chưa đặt',
                            narrative_perspective=chapter_perspective,
                            previous_chapter_content=chapter_context.continuation_point,
                            previous_chapter_summary=chapter_context.previous_chapter_summary or '(Không có tóm tắt chương trước)',
                            recent_chapters_context=chapter_context.recent_chapters_context or 'Chưa có tóm tắt chương gần đây',
                            characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                            chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                            foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                            relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
                        )
                        logger.debug(f"Tạo prompt chương {current_chapter.chapter_number} xong: prompt_length={len(base_prompt)}")
                    else:
                        # Chương đầu
                        template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE", current_user_id, db_session)
                        base_prompt = PromptService.format_prompt(
                            template,
                            project_title=project.title,
                            chapter_number=current_chapter.chapter_number,
                            chapter_title=current_chapter.title,
                            chapter_outline=chapter_context.chapter_outline,
                            target_word_count=target_word_count,
                            genre=project.genre or 'Chưa đặt',
                            narrative_perspective=chapter_perspective,
                            characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                            chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                            foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                            relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
                        )
                        logger.debug(f"Tạo prompt chương đầu xong: prompt_length={len(base_prompt)}")
                else:
                    # ========== Mode 1-n: dùng template đầy đủ ==========
                    if chapter_context.continuation_point:
                        # Có nội dung tiên quyết, dùng template WITH_CONTEXT
                        logger.info(f"📝 [Mode 1-n] dùng template có ngữ cảnh (chương {current_chapter.chapter_number})")
                        
                        # Trích tóm tắt chương trước
                        previous_summary = "(Không có tóm tắt chương trước, vui lòng viết tiếp theo điểm neo)"
                        if chapter_context.previous_chapter_summary:
                            previous_summary = chapter_context.previous_chapter_summary
                        
                        template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY_NEXT", current_user_id, db_session)
                        base_prompt = PromptService.format_prompt(
                            template,
                            project_title=project.title,
                            chapter_number=current_chapter.chapter_number,
                            chapter_title=current_chapter.title,
                            chapter_outline=chapter_context.chapter_outline,
                            target_word_count=target_word_count,
                            continuation_point=chapter_context.continuation_point,
                            genre=project.genre or 'Chưa đặt',
                            narrative_perspective=chapter_perspective,
                            characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                            chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                            foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                            previous_chapter_summary=previous_summary,
                            recent_chapters_context=chapter_context.recent_chapters_context or '',
                            relevant_memories=chapter_context.relevant_memories or ''
                        )
                        logger.debug(f"Tạo prompt chương {current_chapter.chapter_number} xong: prompt_length={len(base_prompt)}")
                    else:
                        # Chương 1, dùng template không có nội dung tiên quyết
                        logger.info(f"📝 [Mode 1-n] dùng template chương đầu")
                        template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY", current_user_id, db_session)
                        base_prompt = PromptService.format_prompt(
                            template,
                            project_title=project.title,
                            chapter_number=current_chapter.chapter_number,
                            chapter_title=current_chapter.title,
                            chapter_outline=chapter_context.chapter_outline,
                            target_word_count=target_word_count,
                            genre=project.genre or 'Chưa đặt',
                            narrative_perspective=chapter_perspective,
                            characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                            chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                            foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                            relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
                        )
                        logger.debug(f"Tạo prompt chương đầu xong: prompt_length={len(base_prompt)}")
                
                # Áp dụng phong cách viết
                if style_content:
                    prompt = WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
                else:
                    prompt = base_prompt
                
                # === Giai đoạn chuẩn bị ===
                yield await tracker.preparing("Đang chuẩn bị prompt AI...")
                
                logger.info(f"Bắt đầu AI sáng tác streaming chương {chapter_id}")
                
                # 🎨 Phương án 1: inject phong cách viết vào system prompt (ưu tiên cao nhất)
                system_prompt_with_style = None
                
                # ⚡ Hỗ trợ Skill: khi chỉ định skill_key, inject workflow Skill vào system prompt
                if skill_key:
                    try:
                        from app.services.skill_loader import get_all_skills_cached
                        skills = get_all_skills_cached()
                        skill = next((s for s in skills if s["template_key"] == skill_key), None)
                        if skill:
                            skill_content = skill["content"]
                            skill_name = skill["template_name"]
                            system_prompt_with_style = f"""

{skill_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt chỉ dẫn workflow Skill ở trên để sáng tác!"""
                            if style_content:
                                system_prompt_with_style += f"""

【🎨 Yêu cầu phong cách viết - bổ sung】

{style_content}"""
                            logger.info(f"⚡ Đã inject Skill '{skill_name}' vào system prompt ({len(skill_content)} ký tự)")
                        else:
                            logger.warning(f"⚠️ Không tìm thấy Skill: {skill_key}")
                    except Exception as skill_err:
                        logger.warning(f"⚠️ Tải Skill thất bại: {skill_err}")
                
                if not system_prompt_with_style and style_content:
                    system_prompt_with_style = f"""

{style_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt yêu cầu phong cách viết ở trên để sáng tác, đây là chỉ dẫn quan trọng nhất!
Đảm bảo giữ nhất quán phong cách trong toàn bộ quá trình sáng tác chương."""
                    logger.info(f"✅ Đã inject phong cách viết vào system prompt ({len(style_content)} ký tự)")
                
                # 🔢 Tính giới hạn max_tokens
                # Ký tự tiếng Trung khoảng 1.5-2 token, dùng hệ số 2.5 lần để đảm bảo đủ không gian hoàn thành đoạn văn
                # Đồng thời đặt giới hạn trên chống quá dài, giới hạn dưới đảm bảo dùng được cơ bản
                calculated_max_tokens = int(target_word_count * 3)
                calculated_max_tokens = max(2000, min(calculated_max_tokens, 16000)) # Giới hạn trong khoảng 2000-16000
                logger.info(f"📊 Số từ mục tiêu: {target_word_count}, max_tokens tính được: {calculated_max_tokens}")
                
                # 🔢 Tính giới hạn max_tokens
                # Ký tự tiếng Trung khoảng 1.5-2 token, dùng hệ số 2.5 lần để đảm bảo đủ không gian hoàn thành đoạn văn
                # Đồng thời đặt giới hạn trên chống quá dài, giới hạn dưới đảm bảo dùng được cơ bản
                calculated_max_tokens = int(target_word_count * 3)
                calculated_max_tokens = max(2000, min(calculated_max_tokens, 16000)) # Giới hạn trong khoảng 2000-16000
                logger.info(f"📊 Số từ mục tiêu: {target_word_count}, max_tokens tính được: {calculated_max_tokens}")
                
                # Chuẩn bị tham số tạo
                generate_kwargs = {
                    "prompt": prompt,
                    "system_prompt": system_prompt_with_style,
                    "tool_choice": "required",
                    "max_tokens": calculated_max_tokens,
                    "auto_mcp": bool(generate_request.enable_mcp)
                }
                if custom_model:
                    logger.info(f" Dùng model tùy chỉnh: {custom_model}")
                    generate_kwargs["model"] = custom_model
                    # Lưu ý: ở đây dùng dịch vụ AI do người dùng cấu hình, tham số model sẽ ghi đè model mặc định
                    # Nếu cần đổi provider, phải truyền tham số provider ở frontend
                
                # === Giai đoạn tạo ===
                full_content = ""
                chunk_count = 0
                
                yield await tracker.generating(
                    current_chars=0,
                    estimated_total=target_word_count
                )
                
                async for chunk in user_ai_service.generate_text_stream(**generate_kwargs):
                    full_content += chunk
                    chunk_count += 1
                    
                    # Gửi khối nội dung
                    yield await tracker.generating_chunk(chunk)
                    
                    # Mỗi 5 chunk gửi một cập nhật tiến độ
                    if chunk_count % 5 == 0:
                        yield await tracker.generating(
                            current_chars=len(full_content),
                            estimated_total=target_word_count,
                            message=f'Đang sáng tác... đã tạo {len(full_content)} từ'
                        )
                    
                    # Mỗi 20 chunk gửi heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()
                    
                    await asyncio.sleep(0) # Nhường quyền điều khiển
                
                # === Giai đoạn lưu ===
                yield await tracker.saving("Đang lưu chương...", 0.3)
                
                # Cập nhật nội dung chương vào database
                old_word_count = current_chapter.word_count or 0
                current_chapter.content = full_content
                new_word_count = len(full_content)
                current_chapter.word_count = new_word_count
                current_chapter.status = "completed"
                current_chapter.summary = _build_lightweight_chapter_summary(full_content)
                
                # Cập nhật số từ của dự án
                project.current_words = project.current_words - old_word_count + new_word_count
                
                # Ghi lịch sử tạo
                history = GenerationHistory(
                    project_id=current_chapter.project_id,
                    chapter_id=current_chapter.id,
                    prompt=f"Sáng tác chương: chương {current_chapter.chapter_number} {current_chapter.title}",
                    generated_content=full_content[:500] if len(full_content) > 500 else full_content,
                    model="default"
                )
                db_session.add(history)
                
                await db_session.commit()
                db_committed = True
                await db_session.refresh(current_chapter)
                
                logger.info(f"Sáng tác chương {chapter_id} thành công, tổng {new_word_count} từ")
                
                # 🔮 Sau khi tạo chương tự động đánh dấu nút thắt dự kiến gài trong chương này
                try:
                    plant_result = await foreshadow_service.auto_plant_pending_foreshadows(
                        db=db_session,
                        project_id=project.id,
                        chapter_id=chapter_id,
                        chapter_number=current_chapter.chapter_number,
                        chapter_content=full_content
                    )
                    if plant_result.get('planted_count', 0) > 0:
                        logger.info(f"🔮 Tự động đánh dấu nút thắt đã gài: {plant_result['planted_count']}")
                except Exception as plant_error:
                    logger.warning(f"⚠️ Tự động đánh dấu gài nút thắt thất bại: {str(plant_error)}")
                
                # Tạo tác vụ phân tích
                analysis_task = AnalysisTask(
                    chapter_id=chapter_id,
                    user_id=current_user_id,
                    project_id=project.id,
                    status='pending',
                    progress=0
                )
                db_session.add(analysis_task)
                await db_session.commit()
                await db_session.refresh(analysis_task)
                
                task_id = analysis_task.id
                logger.info(f"📋 Đã tạo tác vụ phân tích: {task_id}")
                
                # Trì hoãn ngắn để đảm bảo SQLite WAL ghi xong
                await asyncio.sleep(0.05)
                
                # Khởi động trực tiếp phân tích nền (thực hiện đồng thời)
                background_tasks.add_task(
                    analyze_chapter_background,
                    chapter_id=chapter_id,
                    user_id=current_user_id,
                    project_id=project.id,
                    task_id=task_id,
                    ai_service=user_ai_service
                )
                
                yield await tracker.saving("Lưu chương xong", 0.8)
                
                # === Giai đoạn hoàn thành ===
                yield await tracker.complete("Sáng tác xong!")
                
                # Gửi dữ liệu kết quả
                yield await tracker.result({
                    'word_count': new_word_count,
                    'analysis_task_id': task_id
                })
                
                # Gửi sự kiện bắt đầu phân tích (dùng sự kiện tùy chỉnh)
                yield await SSEResponse.send_event(
                    event='analysis_started',
                    data={
                        'task_id': task_id,
                        'message': 'Phân tích chương đã bắt đầu'
                    }
                )
                
                # Gửi tín hiệu hoàn thành
                yield await tracker.done()
                
                break # Thoát vòng lặp async for db_session
        
        except GeneratorExit:
            # Kết nối SSE bị ngắt
            logger.warning("Generator tạo chương bị đóng sớm (SSE ngắt)")
            if db_session and not db_committed:
                try:
                    if db_session.in_transaction():
                        await db_session.rollback()
                        logger.info("Transaction tạo chương đã rollback (GeneratorExit)")
                except Exception as e:
                    logger.error(f"GeneratorExit rollback thất bại: {str(e)}")
        except Exception as e:
            logger.error(f"Sáng tác streaming chương thất bại: {str(e)}")
            if db_session and not db_committed:
                try:
                    if db_session.in_transaction():
                        await db_session.rollback()
                        logger.info("Transaction tạo chương đã rollback (ngoại lệ)")
                except Exception as rollback_error:
                    logger.error(f"Rollback thất bại: {str(rollback_error)}")
            yield await tracker.error(str(e))
        finally:
            # Đảm bảo session database được đóng đúng
            if db_session:
                try:
                    # Kiểm tra cuối: đảm bảo không còn transaction chưa commit
                    if not db_committed and db_session.in_transaction():
                        await db_session.rollback()
                        logger.warning("Phát hiện transaction chưa commit trong finally, đã rollback")
                    
                    await db_session.close()
                    logger.info("Session database đã đóng")
                except Exception as close_error:
                    logger.error(f"Đóng session database thất bại: {str(close_error)}")
                    # Buộc đóng
                    try:
                        await db_session.close()
                    except Exception:
                        pass
    
    return create_sse_response(event_generator())


@router.post("/{chapter_id}/generate-background", summary="AI sáng tác nội dung chương (tác vụ nền)")
async def generate_chapter_content_background(
    chapter_id: str,
    request: Request,
    generate_request: ChapterGenerateRequest = ChapterGenerateRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo tác vụ nền để tạo nội dung chương.
    Sau khi tạo tác vụ trả ngay task_id, frontend poll tiến độ qua GET /api/tasks/{task_id}.
    Đóng trình duyệt không ảnh hưởng việc tạo, sau khi tạo xong nội dung tự động lưu vào database.
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Xác minh chương tồn tại
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")

    # Xác minh quyền dự án
    project = await verify_project_access(chapter.project_id, user_id, db)

    # Kiểm tra điều kiện tiên quyết
    can_generate, error_msg, _ = await check_prerequisites(db, chapter)
    if not can_generate:
        raise HTTPException(status_code=400, detail=error_msg)
    analysis_ready, analysis_msg = await check_previous_analysis_ready(db, chapter)
    if not analysis_ready:
        raise HTTPException(status_code=409, detail=analysis_msg)

    # Tạo tác vụ nền
    from app.services.background_task_service import background_task_service, TaskProgressTracker
    task = await background_task_service.create_task(
        user_id=user_id,
        project_id=chapter.project_id,
        task_type="chapter_generate",
        task_input={
            "chapter_id": chapter_id,
            "style_id": generate_request.style_id,
            "target_word_count": generate_request.target_word_count or 3000,
            "enable_mcp": generate_request.enable_mcp,
            "model": generate_request.model,
            "narrative_perspective": generate_request.narrative_perspective,
            "skill_key": generate_request.skill_key,
        },
        db=db
    )

    # Hàm thực hiện ở nền
    async def _run_chapter_generation(task_id: str, bg_user_id: str):
        from app.database import get_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as BgAsyncSession

        engine = await get_engine(bg_user_id)
        AsyncSessionLocal = async_sessionmaker(engine, class_=BgAsyncSession, expire_on_commit=False)

        async with AsyncSessionLocal() as bg_db:
            tracker = TaskProgressTracker(task_id, bg_user_id, "Chương")
            try:
                await tracker.start()

                # Lấy dịch vụ AI
                from app.api.settings import get_user_ai_service_from_db
                bg_ai_service = await get_user_ai_service_from_db(bg_user_id, bg_db)

                await _run_chapter_generation_bg(
                    task_input={
                        "chapter_id": chapter_id,
                        "style_id": generate_request.style_id,
                        "target_word_count": generate_request.target_word_count or 3000,
                        "enable_mcp": generate_request.enable_mcp,
                        "model": generate_request.model,
                        "narrative_perspective": generate_request.narrative_perspective,
                        "skill_key": generate_request.skill_key,
                    },
                    db=bg_db,
                    ai_service=bg_ai_service,
                    tracker=tracker,
                    user_id=bg_user_id,
                    task_id=task_id,
                )

            except Exception as e:
                logger.error(f"❌ Tạo chương ở nền thất bại: {e}", exc_info=True)
                await tracker.error(str(e))

    await background_task_service.spawn_background_task(
        task.id, user_id, _run_chapter_generation
    )

    return {
        "task_id": task.id,
        "task_type": "chapter_generate",
        "status": "pending",
        "message": "Đã tạo tác vụ, vui lòng truy vấn tiến độ qua GET /api/tasks/{task_id}"
    }


async def _run_chapter_generation_bg(
    task_input: dict,
    db: AsyncSession,
    ai_service: AIService,
    tracker,
    user_id: str,
    task_id: str,
):
    """Thực hiện tạo chương ở nền (không dùng SSE, tạo trực tiếp và lưu)"""
    from app.services.chapter_context_service import (
        OneToManyContextBuilder,
        OneToOneContextBuilder
    )

    chapter_id = task_input["chapter_id"]
    style_id = task_input.get("style_id")
    target_word_count = task_input.get("target_word_count", 3000)
    custom_model = task_input.get("model")
    temp_narrative_perspective = task_input.get("narrative_perspective")
    enable_mcp = task_input.get("enable_mcp", True)
    write_lock = await get_db_write_lock(user_id)

    # === Giai đoạn tải ===
    await tracker.loading("Đang tải thông tin chương...", 0.2)

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    current_chapter = chapter_result.scalar_one_or_none()
    if not current_chapter:
        await tracker.error("Chương không tồn tại")
        return

    await tracker.loading("Đang tải thông tin dự án...", 0.4)

    project_result = await db.execute(
        select(Project).where(Project.id == current_chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        await tracker.error("Dự án không tồn tại")
        return

    outline_mode = project.outline_mode if project else 'one-to-many'

    # Lấy đề cương
    if current_chapter.outline_id:
        outline_result = await db.execute(
            select(Outline).where(Outline.id == current_chapter.outline_id)
        )
    else:
        outline_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == current_chapter.project_id)
            .where(Outline.order_index == current_chapter.chapter_number)
        )
    outline = outline_result.scalar_one_or_none()

    # Lấy phong cách viết
    style_content = ""
    if style_id:
        style_result = await db.execute(
            select(WritingStyle).where(WritingStyle.id == style_id)
        )
        style = style_result.scalar_one_or_none()
        if style and (style.user_id is None or style.user_id == user_id):
            style_content = style.prompt_content or ""

    # Lấy phong cách viết
    if outline_mode == 'one-to-one':
        context_builder = OneToOneContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=current_chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db,
            target_word_count=target_word_count
        )
    else:
        context_builder = OneToManyContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=current_chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db,
            style_content=style_content,
            target_word_count=target_word_count,
            temp_narrative_perspective=temp_narrative_perspective
        )

    await tracker.loading("Xây dựng ngữ cảnh xong", 0.8)

    # Xác định ngôi kể
    chapter_perspective = (
        temp_narrative_perspective or
        project.narrative_perspective or
        'Ngôi thứ ba'
    )

    # === Chuẩn bị prompt ===
    if outline_mode == 'one-to-one':
        if chapter_context.continuation_point:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE_NEXT", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                previous_chapter_content=chapter_context.continuation_point,
                previous_chapter_summary=chapter_context.previous_chapter_summary or '(Không có tóm tắt chương trước)',
                recent_chapters_context=chapter_context.recent_chapters_context or 'Chưa có tóm tắt chương gần đây',
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
        else:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
    else:
        if chapter_context.continuation_point:
            previous_summary = chapter_context.previous_chapter_summary or "(Không có tóm tắt chương trước, vui lòng viết tiếp theo điểm neo)"
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY_NEXT", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                continuation_point=chapter_context.continuation_point,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                previous_chapter_summary=previous_summary,
                recent_chapters_context=chapter_context.recent_chapters_context or '',
                relevant_memories=chapter_context.relevant_memories or ''
            )
        else:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )

    # Áp dụng phong cách viết
    if style_content:
        prompt = WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
    else:
        prompt = base_prompt

    # === Giai đoạn chuẩn bị ===
    await tracker.preparing("Đang chuẩn bị prompt AI...")

    system_prompt_with_style = None
    if style_content:
        system_prompt_with_style = f"""

{style_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt yêu cầu phong cách viết ở trên để sáng tác, đây là chỉ dẫn quan trọng nhất!
Đảm bảo giữ nhất quán phong cách trong toàn bộ quá trình sáng tác chương."""

    calculated_max_tokens = int(target_word_count * 3)
    calculated_max_tokens = max(2000, min(calculated_max_tokens, 16000))

    generate_kwargs = {
        "prompt": prompt,
        "system_prompt": system_prompt_with_style,
        "tool_choice": "required",
        "max_tokens": calculated_max_tokens,
        "auto_mcp": bool(enable_mcp)
    }
    if custom_model:
        generate_kwargs["model"] = custom_model

    # === Giai đoạn tạo ===
    full_content = ""
    chunk_count = 0

    await tracker.generating(
        current_chars=0,
        estimated_total=target_word_count
    )

    async for chunk in ai_service.generate_text_stream(**generate_kwargs):
        # Kiểm tra có bị hủy không
        if chunk_count % 10 == 0 and await tracker.check_cancelled():
            logger.info(f"🚫 Tạo chương ở nền bị hủy: {chapter_id}")
            return

        full_content += chunk
        chunk_count += 1

        # Mỗi 10 chunk cập nhật tiến độ một lần
        if chunk_count % 10 == 0:
            await tracker.generating(
                current_chars=len(full_content),
                estimated_total=target_word_count,
                message=f'Đang sáng tác... đã tạo {len(full_content)} từ'
            )

        await asyncio.sleep(0)

    # === Giai đoạn lưu ===
    if await tracker.check_cancelled():
        logger.info(f"🚫 Tạo chương ở nền bị hủy trước khi lưu: {chapter_id}")
        return

    await tracker.saving("Đang lưu chương...", 0.3)

    async with write_lock:
        # Lấy lại chương (đảm bảo trạng thái mới nhất)
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        current_chapter = chapter_result.scalar_one_or_none()
        if not current_chapter:
            await tracker.error("Khi lưu chương không tồn tại")
            return

        old_word_count = current_chapter.word_count or 0
        current_chapter.content = full_content
        new_word_count = len(full_content)
        current_chapter.word_count = new_word_count
        current_chapter.status = "completed"
        current_chapter.summary = _build_lightweight_chapter_summary(full_content)

        # Cập nhật số từ của dự án
        project_result = await db.execute(
            select(Project).where(Project.id == current_chapter.project_id)
        )
        project_obj = project_result.scalar_one_or_none()
        if project_obj:
            project_obj.current_words = (project_obj.current_words or 0) - old_word_count + new_word_count

        # Ghi lịch sử tạo
        history = GenerationHistory(
            project_id=current_chapter.project_id,
            chapter_id=current_chapter.id,
            prompt=f"Sáng tác chương: chương {current_chapter.chapter_number} {current_chapter.title}",
            generated_content=full_content[:500] if len(full_content) > 500 else full_content,
            model="default"
        )
        db.add(history)

        await db.commit()

    logger.info(f"✅ Tạo chương ở nền {chapter_id} xong, tổng {new_word_count} từ")

    # 🔮 Tự động đánh dấu nút thắt
    try:
        plant_result = await foreshadow_service.auto_plant_pending_foreshadows(
            db=db,
            project_id=current_chapter.project_id,
            chapter_id=chapter_id,
            chapter_number=current_chapter.chapter_number,
            chapter_content=full_content
        )
        if plant_result.get('planted_count', 0) > 0:
            logger.info(f"🔮 Tự động đánh dấu nút thắt đã gài: {plant_result['planted_count']}")
    except Exception as plant_error:
        logger.warning(f"⚠️ Tự động đánh dấu gài nút thắt thất bại: {str(plant_error)}")

    # Tạo tác vụ phân tích
    analysis_task = AnalysisTask(
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=current_chapter.project_id,
        status='pending',
        progress=0
    )
    db.add(analysis_task)
    await db.commit()
    await db.refresh(analysis_task)

    logger.info(f"📋 Tạo ở nền: đã tạo tác vụ phân tích: {analysis_task.id}")

    await tracker.set_result({
        "chapter_id": chapter_id,
        "word_count": new_word_count,
        "analysis_task_id": analysis_task.id,
    })
    await tracker.analyzing(0, "Sáng tác chương xong, chuẩn bị phân tích...")

    analysis_success = await analyze_chapter_background(
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=current_chapter.project_id,
        task_id=analysis_task.id,
        progress_callback=tracker.analyzing,
    )
    if not analysis_success:
        raise RuntimeError("Nội dung chương đã tạo, nhưng phân tích chương thất bại")

    # === Hoàn thành ===
    await tracker.complete(f"Sáng tác và phân tích xong! Tổng {new_word_count} từ")


def _build_analysis_task_status_payload(
    chapter_id: str,
    task: Optional[AnalysisTask],
    auto_recovered: bool = False
) -> dict:
    """Xây dựng thống nhất response trạng thái tác vụ phân tích"""
    if not task:
        return {
            "has_task": False,
            "chapter_id": chapter_id,
            "status": "none",
            "progress": 0,
            "error_message": None,
            "auto_recovered": False,
            "task_id": None,
            "created_at": None,
            "started_at": None,
            "completed_at": None
        }

    return {
        "has_task": True,
        "task_id": task.id,
        "chapter_id": task.chapter_id,
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "auto_recovered": auto_recovered,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }


async def _recover_stale_analysis_tasks(
    db: AsyncSession,
    tasks: list[AnalysisTask],
) -> set[str]:
    """Khôi phục nguyên tử các tác vụ cũ đã mất coroutine thực thi về trạng thái thất bại."""
    now = datetime.now()
    recovered_ids: set[str] = set()

    for task in tasks:
        error_message: Optional[str] = None
        if task.status == "running":
            reference_time = task.started_at or task.created_at
            if reference_time and (now - reference_time) > timedelta(seconds=ANALYSIS_TASK_STALE_SECONDS):
                error_message = "Tác vụ thực thi hết thời gian, đã tự động khôi phục"
        if not error_message:
            continue

        result = await db.execute(
            update(AnalysisTask)
            .where(
                AnalysisTask.id == task.id,
                AnalysisTask.status == task.status,
            )
            .values(
                status="failed",
                error_message=error_message,
                completed_at=now,
                progress=0,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount:
            recovered_ids.add(task.id)

    if recovered_ids:
        await db.commit()
        for task in tasks:
            if task.id in recovered_ids:
                await db.refresh(task)
        logger.warning(f"Tự động khôi phục tác vụ phân tích chương cũ: {len(recovered_ids)}")

    return recovered_ids


@router.post("/{chapter_id}/generate-background-legacy", summary="AI sáng tác nội dung chương (tác vụ nền, implementation lặp lại cũ)")
async def generate_chapter_content_background_legacy(
    chapter_id: str,
    request: Request,
    generate_request: ChapterGenerateRequest = ChapterGenerateRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo tác vụ nền để tạo nội dung chương.
    Sau khi tạo tác vụ trả ngay task_id, frontend poll tiến độ qua GET /api/tasks/{task_id}.
    Đóng trình duyệt không ảnh hưởng việc tạo, sau khi tạo xong nội dung tự động lưu vào database.
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Xác minh chương tồn tại
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")

    # Xác minh quyền dự án
    project = await verify_project_access(chapter.project_id, user_id, db)

    # Kiểm tra điều kiện tiên quyết
    can_generate, error_msg, _ = await check_prerequisites(db, chapter)
    if not can_generate:
        raise HTTPException(status_code=400, detail=error_msg)

    # Tạo tác vụ nền
    from app.services.background_task_service import background_task_service, TaskProgressTracker
    task = await background_task_service.create_task(
        user_id=user_id,
        project_id=chapter.project_id,
        task_type="chapter_generate",
        task_input={
            "chapter_id": chapter_id,
            "style_id": generate_request.style_id,
            "target_word_count": generate_request.target_word_count or 3000,
            "enable_mcp": generate_request.enable_mcp,
            "model": generate_request.model,
            "narrative_perspective": generate_request.narrative_perspective,
        },
        db=db
    )

    # Hàm thực hiện ở nền
    async def _run_chapter_generation(task_id: str, bg_user_id: str):
        from app.database import get_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as BgAsyncSession

        engine = await get_engine(bg_user_id)
        AsyncSessionLocal = async_sessionmaker(engine, class_=BgAsyncSession, expire_on_commit=False)

        async with AsyncSessionLocal() as bg_db:
            tracker = TaskProgressTracker(task_id, bg_user_id, "Chương")
            try:
                await tracker.start()

                # Lấy dịch vụ AI
                from app.api.settings import get_user_ai_service_from_db
                bg_ai_service = await get_user_ai_service_from_db(bg_user_id, bg_db)

                await _run_chapter_generation_bg(
                    task_input={
                        "chapter_id": chapter_id,
                        "style_id": generate_request.style_id,
                        "target_word_count": generate_request.target_word_count or 3000,
                        "enable_mcp": generate_request.enable_mcp,
                        "model": generate_request.model,
                        "narrative_perspective": generate_request.narrative_perspective,
                    },
                    db=bg_db,
                    ai_service=bg_ai_service,
                    tracker=tracker,
                    user_id=bg_user_id,
                    task_id=task_id,
                )

            except Exception as e:
                logger.error(f"❌ Tạo chương ở nền thất bại: {e}", exc_info=True)
                await tracker.error(str(e))

    await background_task_service.spawn_background_task(
        task.id, user_id, _run_chapter_generation
    )

    return {
        "task_id": task.id,
        "task_type": "chapter_generate",
        "status": "pending",
        "message": "Đã tạo tác vụ, vui lòng truy vấn tiến độ qua GET /api/tasks/{task_id}"
    }


async def _run_chapter_generation_bg(
    task_input: dict,
    db: AsyncSession,
    ai_service: AIService,
    tracker,
    user_id: str,
    task_id: str,
):
    """Thực hiện tạo chương ở nền (không dùng SSE, tạo trực tiếp và lưu)"""
    from app.services.chapter_context_service import (
        OneToManyContextBuilder,
        OneToOneContextBuilder
    )

    chapter_id = task_input["chapter_id"]
    style_id = task_input.get("style_id")
    target_word_count = task_input.get("target_word_count", 3000)
    custom_model = task_input.get("model")
    temp_narrative_perspective = task_input.get("narrative_perspective")
    enable_mcp = task_input.get("enable_mcp", True)
    skill_key = task_input.get("skill_key")
    write_lock = await get_db_write_lock(user_id)

    # === Giai đoạn tải ===
    await tracker.loading("Đang tải thông tin chương...", 0.2)

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    current_chapter = chapter_result.scalar_one_or_none()
    if not current_chapter:
        await tracker.error("Chương không tồn tại")
        return

    await tracker.loading("Đang tải thông tin dự án...", 0.4)

    project_result = await db.execute(
        select(Project).where(Project.id == current_chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        await tracker.error("Dự án không tồn tại")
        return

    outline_mode = project.outline_mode if project else 'one-to-many'

    # Lấy đề cương
    if current_chapter.outline_id:
        outline_result = await db.execute(
            select(Outline).where(Outline.id == current_chapter.outline_id)
        )
    else:
        outline_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == current_chapter.project_id)
            .where(Outline.order_index == current_chapter.chapter_number)
        )
    outline = outline_result.scalar_one_or_none()

    # Lấy phong cách viết
    style_content = ""
    if style_id:
        style_result = await db.execute(
            select(WritingStyle).where(WritingStyle.id == style_id)
        )
        style = style_result.scalar_one_or_none()
        if style and (style.user_id is None or style.user_id == user_id):
            style_content = style.prompt_content or ""

    # === Xây dựng ngữ cảnh ===
    if outline_mode == 'one-to-one':
        context_builder = OneToOneContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=current_chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db,
            target_word_count=target_word_count
        )
    else:
        context_builder = OneToManyContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=current_chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db,
            style_content=style_content,
            target_word_count=target_word_count,
            temp_narrative_perspective=temp_narrative_perspective
        )

    await tracker.loading("Xây dựng ngữ cảnh xong", 0.8)

    # Xác định ngôi kể
    chapter_perspective = (
        temp_narrative_perspective or
        project.narrative_perspective or
        'Ngôi thứ ba'
    )

    # === Chuẩn bị prompt ===
    if outline_mode == 'one-to-one':
        if chapter_context.continuation_point:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE_NEXT", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                previous_chapter_content=chapter_context.continuation_point,
                previous_chapter_summary=chapter_context.previous_chapter_summary or '(Không có tóm tắt chương trước)',
                recent_chapters_context=chapter_context.recent_chapters_context or 'Chưa có tóm tắt chương gần đây',
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
        else:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
    else:
        if chapter_context.continuation_point:
            previous_summary = chapter_context.previous_chapter_summary or "(Không có tóm tắt chương trước, vui lòng viết tiếp theo điểm neo)"
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY_NEXT", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                continuation_point=chapter_context.continuation_point,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                previous_chapter_summary=previous_summary,
                recent_chapters_context=chapter_context.recent_chapters_context or '',
                relevant_memories=chapter_context.relevant_memories or ''
            )
        else:
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY", user_id, db)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=current_chapter.chapter_number,
                chapter_title=current_chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=chapter_perspective,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )

    # Áp dụng phong cách viết
    if style_content:
        prompt = WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
    else:
        prompt = base_prompt

    # === Giai đoạn chuẩn bị ===
    await tracker.preparing("Đang chuẩn bị prompt AI...")

    system_prompt_with_style = None
    if skill_key:
        try:
            from app.services.skill_loader import get_all_skills_cached
            skills = get_all_skills_cached()
            skill = next((s for s in skills if s["template_key"] == skill_key), None)
            if skill:
                skill_content = skill["content"]
                skill_name = skill["template_name"]
                system_prompt_with_style = f"""

{skill_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt chỉ dẫn workflow Skill ở trên để sáng tác!"""
                if style_content:
                    system_prompt_with_style += f"""

【🎨 Yêu cầu phong cách viết - bổ sung】

{style_content}"""
                logger.info(f"⚡ Tạo ở nền - đã inject Skill '{skill_name}' vào system prompt ({len(skill_content)} ký tự)")
            else:
                logger.warning(f"⚠️ Tạo ở nền - không tìm thấy Skill: {skill_key}")
        except Exception as skill_err:
            logger.warning(f"⚠️ Tạo ở nền - tải Skill thất bại: {skill_err}")

    if not system_prompt_with_style and style_content:
        system_prompt_with_style = f"""

{style_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt yêu cầu phong cách viết ở trên để sáng tác, đây là chỉ dẫn quan trọng nhất!
Đảm bảo giữ nhất quán phong cách trong toàn bộ quá trình sáng tác chương."""

    calculated_max_tokens = int(target_word_count * 3)
    calculated_max_tokens = max(2000, min(calculated_max_tokens, 16000))

    generate_kwargs = {
        "prompt": prompt,
        "system_prompt": system_prompt_with_style,
        "tool_choice": "required",
        "max_tokens": calculated_max_tokens,
        "auto_mcp": bool(enable_mcp)
    }
    if custom_model:
        generate_kwargs["model"] = custom_model

    # === Giai đoạn tạo ===
    full_content = ""
    chunk_count = 0

    await tracker.generating(
        current_chars=0,
        estimated_total=target_word_count
    )

    async for chunk in ai_service.generate_text_stream(**generate_kwargs):
        # Kiểm tra có bị hủy không
        if chunk_count % 10 == 0 and await tracker.check_cancelled():
            logger.info(f"🚫 Tạo chương ở nền bị hủy: {chapter_id}")
            return

        full_content += chunk
        chunk_count += 1

        # Mỗi 10 chunk cập nhật tiến độ một lần
        if chunk_count % 10 == 0:
            await tracker.generating(
                current_chars=len(full_content),
                estimated_total=target_word_count,
                message=f'Đang sáng tác... đã tạo {len(full_content)} từ'
            )

        await asyncio.sleep(0)

    # === Giai đoạn lưu ===
    await tracker.saving("Đang lưu chương...", 0.3)

    async with write_lock:
        # Lấy lại chương (đảm bảo trạng thái mới nhất)
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        current_chapter = chapter_result.scalar_one_or_none()
        if not current_chapter:
            await tracker.error("Khi lưu chương không tồn tại")
            return

        old_word_count = current_chapter.word_count or 0
        current_chapter.content = full_content
        new_word_count = len(full_content)
        current_chapter.word_count = new_word_count
        current_chapter.status = "completed"
        current_chapter.summary = _build_lightweight_chapter_summary(full_content)

        # Cập nhật số từ của dự án
        project_result = await db.execute(
            select(Project).where(Project.id == current_chapter.project_id)
        )
        project_obj = project_result.scalar_one_or_none()
        if project_obj:
            project_obj.current_words = (project_obj.current_words or 0) - old_word_count + new_word_count

        # Ghi lịch sử tạo
        history = GenerationHistory(
            project_id=current_chapter.project_id,
            chapter_id=current_chapter.id,
            prompt=f"Sáng tác chương: chương {current_chapter.chapter_number} {current_chapter.title}",
            generated_content=full_content[:500] if len(full_content) > 500 else full_content,
            model="default"
        )
        db.add(history)

        await db.commit()

    logger.info(f"✅ Tạo chương ở nền {chapter_id} xong, tổng {new_word_count} từ")

    # 🔮 Tự động đánh dấu nút thắt
    try:
        plant_result = await foreshadow_service.auto_plant_pending_foreshadows(
            db=db,
            project_id=current_chapter.project_id,
            chapter_id=chapter_id,
            chapter_number=current_chapter.chapter_number,
            chapter_content=full_content
        )
        if plant_result.get('planted_count', 0) > 0:
            logger.info(f"🔮 Tự động đánh dấu nút thắt đã gài: {plant_result['planted_count']}")
    except Exception as plant_error:
        logger.warning(f"⚠️ Tự động đánh dấu gài nút thắt thất bại: {str(plant_error)}")

    # Tạo tác vụ phân tích
    analysis_task = AnalysisTask(
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=current_chapter.project_id,
        status='pending',
        progress=0
    )
    db.add(analysis_task)
    await db.commit()
    await db.refresh(analysis_task)

    logger.info(f"📋 Tạo ở nền: đã tạo tác vụ phân tích: {analysis_task.id}")

    await tracker.set_result({
        "chapter_id": chapter_id,
        "word_count": new_word_count,
        "analysis_task_id": analysis_task.id,
    })
    await tracker.analyzing(0, "Sáng tác chương xong, chuẩn bị phân tích...")

    analysis_success = await analyze_chapter_background(
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=current_chapter.project_id,
        task_id=analysis_task.id,
        ai_service=ai_service,
        progress_callback=tracker.analyzing,
    )
    if not analysis_success:
        raise RuntimeError("Nội dung chương đã tạo, nhưng phân tích chương thất bại")

    # === Hoàn thành ===
    await tracker.complete(f"Sáng tác và phân tích xong! Tổng {new_word_count} từ")


def _build_analysis_task_status_payload(
    chapter_id: str,
    task: Optional[AnalysisTask],
    auto_recovered: bool = False
) -> dict:
    """Xây dựng thống nhất response trạng thái tác vụ phân tích"""
    if not task:
        return {
            "has_task": False,
            "chapter_id": chapter_id,
            "status": "none",
            "progress": 0,
            "error_message": None,
            "auto_recovered": False,
            "task_id": None,
            "created_at": None,
            "started_at": None,
            "completed_at": None
        }

    return {
        "has_task": True,
        "task_id": task.id,
        "chapter_id": task.chapter_id,
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "auto_recovered": auto_recovered,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }


@router.get("/{chapter_id}/analysis/status", summary="Truy vấn trạng thái tác vụ phân tích chương", response_model=AnalysisTaskStatusResponse)
async def get_analysis_task_status(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Truy vấn trạng thái tác vụ phân tích mới nhất của chương đã chỉ định
    
    Cơ chế tự động khôi phục:
    - Nếu trạng thái tác vụ là running và quá 1 phút chưa cập nhật, tự động đánh dấu failed
    - Nếu trạng thái tác vụ là pending và quá 2 phút chưa khởi động, tự động đánh dấu failed
    
    Trả về:
    - has_task: có tồn tại tác vụ phân tích không
    - task_id: ID tác vụ (nếu tồn tại)
    - status: pending/running/completed/failed/none (nếu không tồn tại thì là none)
    - progress: 0-100
    - error_message: thông tin lỗi (nếu thất bại)
    - auto_recovered: có được tự động khôi phục không
    - created_at: thời gian tạo
    - completed_at: thời gian hoàn thành
    
    Lưu ý: khi chương không tồn tại hoặc không có quyền truy cập trả về 404, khi không có tác vụ phân tích trả về has_task=false
    """
    from datetime import timedelta
    
    # Lấy chương trước để xác minh tồn tại và quyền
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Lấy tác vụ phân tích mới nhất của chương này
    result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.chapter_id == chapter_id)
        .order_by(AnalysisTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        # Trả về trạng thái không có tác vụ, thay vì ném lỗi 404
        return _build_analysis_task_status_payload(chapter_id, None)
    
    recovered_ids = await _recover_stale_analysis_tasks(db, [task])
    auto_recovered = task.id in recovered_ids
    
    return _build_analysis_task_status_payload(chapter_id, task, auto_recovered)


@router.post("/project/{project_id}/analysis/statuses", summary="Truy vấn hàng loạt trạng thái tác vụ phân tích chương", response_model=BatchAnalysisStatusResponse)
async def get_project_analysis_task_statuses(
    project_id: str,
    payload: BatchAnalysisStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Truy vấn hàng loạt trạng thái phân tích chương của dự án, tránh frontend request từng chương gây bão request"""
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    # Lấy danh sách chương của dự án trước
    chapter_query = select(Chapter.id).where(Chapter.project_id == project_id)
    if payload.chapter_ids and len(payload.chapter_ids) > 0:
        chapter_query = chapter_query.where(Chapter.id.in_(payload.chapter_ids))

    chapter_result = await db.execute(chapter_query)
    chapter_ids = [row[0] for row in chapter_result.all()]

    if not chapter_ids:
        return {
            "project_id": project_id,
            "total": 0,
            "items": {}
        }

    # Truy vấn hàng loạt tất cả tác vụ phân tích tương ứng các chương này, sau đó lấy bản mới nhất trong bộ nhớ
    tasks_result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.chapter_id.in_(chapter_ids))
        .order_by(AnalysisTask.chapter_id, AnalysisTask.created_at.desc())
    )
    all_tasks = tasks_result.scalars().all()

    latest_task_map: dict[str, AnalysisTask] = {}
    for task in all_tasks:
        if task.chapter_id not in latest_task_map:
            latest_task_map[task.chapter_id] = task

    recovered_ids = await _recover_stale_analysis_tasks(
        db, list(latest_task_map.values())
    )

    items: dict[str, dict] = {}
    for chapter_id in chapter_ids:
        task = latest_task_map.get(chapter_id)
        items[chapter_id] = _build_analysis_task_status_payload(
            chapter_id,
            task,
            task.id in recovered_ids if task else False,
        )

    return {
        "project_id": project_id,
        "total": len(chapter_ids),
        "items": items
    }


async def _run_batch_analysis_in_sequence(
    tasks_queue: list[dict[str, int | str]],
    user_id: str,
    project_id: str,
    ai_service: Optional[AIService] = None
) -> None:
    """Thực hiện từng tác vụ phân tích theo thứ tự chương."""
    for index, task_item in enumerate(tasks_queue, start=1):
        chapter_id = str(task_item["chapter_id"])
        chapter_number = int(task_item["chapter_number"])
        task_id = str(task_item["task_id"])

        logger.info(f"🔁 Phân tích một chạm đang thực hiện tuần tự [{index}/{len(tasks_queue)}]: chương {chapter_number}")
        try:
            success = await analyze_chapter_background(
                chapter_id=chapter_id,
                user_id=user_id,
                project_id=project_id,
                task_id=task_id,
                ai_service=ai_service
            )
            if not success:
                logger.warning(f"⚠️ Phân tích tuần tự một chạm trả về thất bại: chapter_id={chapter_id}, task_id={task_id}")
        except Exception as e:
            # analyze_chapter_background đã xử lý trạng thái thất bại tác vụ bên trong, ở đây chỉ bảo vệ hàng đợi tuần tự không bị ngắt
            logger.error(
                f"❌ Phân tích tuần tự một chạm bất thường (đã tiếp tục chương sau) chapter_id={chapter_id}, task_id={task_id}: {str(e)}",
                exc_info=True
            )


@router.post(
    "/project/{project_id}/analysis/analyze-unanalyzed",
    summary="Một chạm phân tích các chương chưa phân tích theo thứ tự chương",
    response_model=BatchAnalyzeUnanalyzedResponse
)
async def batch_analyze_unanalyzed_chapters(
    project_id: str,
    payload: BatchAnalyzeUnanalyzedRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tự động nhận diện các chương chưa hoàn thành phân tích trong dự án, và khởi động phân tích từng chương theo thứ tự."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Xác minh quyền dự án
    await verify_project_access(project_id, user_id, db)

    # Truy vấn chương mục tiêu (tùy chọn giới hạn chapter_ids)
    chapter_query = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number)
    if payload.chapter_ids and len(payload.chapter_ids) > 0:
        chapter_query = chapter_query.where(Chapter.id.in_(payload.chapter_ids))

    chapter_result = await db.execute(chapter_query)
    chapters = chapter_result.scalars().all()

    if not chapters:
        return {
            "project_id": project_id,
            "total_candidates": 0,
            "total_started": 0,
            "total_skipped_no_content": 0,
            "total_skipped_running": 0,
            "total_already_completed": 0,
            "started_tasks": {}
        }

    chapter_ids = [chapter.id for chapter in chapters]

    # Truy vấn tác vụ phân tích mới nhất của mỗi chương
    tasks_result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.chapter_id.in_(chapter_ids))
        .order_by(AnalysisTask.chapter_id, AnalysisTask.created_at.desc())
    )
    all_tasks = tasks_result.scalars().all()

    latest_task_map: dict[str, AnalysisTask] = {}
    for task in all_tasks:
        if task.chapter_id not in latest_task_map:
            latest_task_map[task.chapter_id] = task

    total_candidates = 0
    total_skipped_no_content = 0
    total_skipped_running = 0
    total_already_completed = 0
    started_tasks: dict[str, dict] = {}
    tasks_to_start: list[tuple[Chapter, AnalysisTask]] = []

    for chapter in chapters:
        # Chương không có nội dung bỏ qua trực tiếp
        if not chapter.content or chapter.content.strip() == "":
            total_skipped_no_content += 1
            continue

        total_candidates += 1
        latest_task = latest_task_map.get(chapter.id)

        # Đã trong hàng đợi/đang phân tích, bỏ qua
        if latest_task and latest_task.status in ("pending", "running"):
            total_skipped_running += 1
            continue

        # Đã phân tích xong, bỏ qua
        if latest_task and latest_task.status == "completed":
            total_already_completed += 1
            continue

        # Không có tác vụ/thất bại/trạng thái không rõ, khởi động lại phân tích
        analysis_task = AnalysisTask(
            chapter_id=chapter.id,
            user_id=user_id,
            project_id=project_id,
            status='pending',
            progress=0
        )
        db.add(analysis_task)
        tasks_to_start.append((chapter, analysis_task))

    if tasks_to_start:
        try:
            await db.flush()

            for chapter, analysis_task in tasks_to_start:
                started_tasks[chapter.id] = _build_analysis_task_status_payload(chapter.id, analysis_task)

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Phân tích một chạm tạo tác vụ thất bại: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Phân tích một chạm tạo tác vụ thất bại: {str(e)}")

        # Sau khi commit lập tức điều độ phân tích nền theo thứ tự chương (thực hiện từng chương)
        tasks_queue = [
            {
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "task_id": analysis_task.id
            }
            for chapter, analysis_task in tasks_to_start
        ]
        _schedule_analysis_background(
            _run_batch_analysis_in_sequence(
                tasks_queue=tasks_queue,
                user_id=user_id,
                project_id=project_id
            )
        )

    return {
        "project_id": project_id,
        "total_candidates": total_candidates,
        "total_started": len(tasks_to_start),
        "total_skipped_no_content": total_skipped_no_content,
        "total_skipped_running": total_skipped_running,
        "total_already_completed": total_already_completed,
        "started_tasks": started_tasks
    }


@router.get("/{chapter_id}/analysis", summary="Lấy kết quả phân tích chương")
async def get_chapter_analysis(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy kết quả phân tích đầy đủ của chương
    
    Trả về:
    - analysis_data: dữ liệu phân tích đầy đủ (JSON)
    - summary: text tóm tắt phân tích
    - memories: danh sách ký ức đã trích
    - created_at: thời gian phân tích
    """
    # Lấy chương trước để xác minh quyền
    chapter_result_check = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter_check = chapter_result_check.scalar_one_or_none()
    if chapter_check:
        # Xác minh quyền người dùng
        user_id = getattr(request.state, 'user_id', None)
        await verify_project_access(chapter_check.project_id, user_id, db)
    
    # Lấy kết quả phân tích
    analysis_result = await db.execute(
        select(PlotAnalysis)
        .where(PlotAnalysis.chapter_id == chapter_id)
        .order_by(PlotAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Chương này chưa có kết quả phân tích")
    
    # Lấy ký ức liên quan
    memories_result = await db.execute(
        select(StoryMemory)
        .where(StoryMemory.chapter_id == chapter_id)
        .order_by(StoryMemory.importance_score.desc())
    )
    memories = memories_result.scalars().all()
    
    return {
        "chapter_id": chapter_id,
        "analysis": analysis.to_dict(), # Dùng phương thức to_dict()
        "memories": [
            {
                "id": mem.id,
                "type": mem.memory_type,
                "title": mem.title,
                "content": mem.content,
                "importance": mem.importance_score,
                "tags": mem.tags,
                "is_foreshadow": mem.is_foreshadow,
                "position": mem.chapter_position,
                "related_characters": mem.related_characters
            }
            for mem in memories
        ],
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None
    }


@router.get("/{chapter_id}/annotations", summary="Lấy dữ liệu chú thích chương")
async def get_chapter_annotations(
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy dữ liệu chú thích của chương (để frontend hiển thị chú thích)
    
    Trả về danh sách chú thích đã định dạng, bao gồm thông tin vị trí chính xác
    Phù hợp hiển thị chú thích trực quan cho nội dung chương
    """
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    
    # Lấy chương
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền truy cập dự án
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Lấy kết quả phân tích
    analysis_result = await db.execute(
        select(PlotAnalysis)
        .where(PlotAnalysis.chapter_id == chapter_id)
        .order_by(PlotAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    
    # Lấy ký ức
    memories_result = await db.execute(
        select(StoryMemory)
        .where(StoryMemory.chapter_id == chapter_id)
        .order_by(StoryMemory.importance_score.desc())
    )
    memories = memories_result.scalars().all()
    
    # Xây dựng dữ liệu chú thích
    annotations = []
    
    for mem in memories:
        # Ưu tiên đọc thông tin vị trí từ database
        position = mem.chapter_position if mem.chapter_position is not None else -1
        length = mem.text_length if hasattr(mem, 'text_length') and mem.text_length is not None else 0
        metadata_extra = {}
        
        # Nếu database không có thông tin vị trí, thử tính lại từ dữ liệu phân tích
        if position == -1 and analysis and chapter.content:
            # Tìm mục tương ứng từ dữ liệu phân tích theo loại ký ức
            if mem.memory_type == 'hook' and analysis.hooks:
                for hook in analysis.hooks:
                    # Khớp qua tiêu đề hoặc nội dung
                    if mem.title and hook.get('type') in mem.title:
                        keyword = hook.get('keyword', '')
                        if keyword:
                            pos = chapter.content.find(keyword)
                            if pos != -1:
                                position = pos
                                length = len(keyword)
                        metadata_extra["strength"] = hook.get('strength', 5)
                        metadata_extra["position_desc"] = hook.get('position', '')
                        break
            
            elif mem.memory_type == 'foreshadow' and analysis.foreshadows:
                for foreshadow in analysis.foreshadows:
                    if foreshadow.get('content') in mem.content:
                        keyword = foreshadow.get('keyword', '')
                        if keyword:
                            pos = chapter.content.find(keyword)
                            if pos != -1:
                                position = pos
                                length = len(keyword)
                        metadata_extra["foreshadow_type"] = foreshadow.get('type', 'planted')
                        metadata_extra["strength"] = foreshadow.get('strength', 5)
                        break
            
            elif mem.memory_type == 'plot_point' and analysis.plot_points:
                for plot_point in analysis.plot_points:
                    if plot_point.get('content') in mem.content:
                        keyword = plot_point.get('keyword', '')
                        if keyword:
                            pos = chapter.content.find(keyword)
                            if pos != -1:
                                position = pos
                                length = len(keyword)
                        break
        else:
            # Nếu database có vị trí, cũng trích metadata bổ sung từ dữ liệu phân tích
            if analysis:
                if mem.memory_type == 'hook' and analysis.hooks:
                    for hook in analysis.hooks:
                        if mem.title and hook.get('type') in mem.title:
                            metadata_extra["strength"] = hook.get('strength', 5)
                            metadata_extra["position_desc"] = hook.get('position', '')
                            break
                
                elif mem.memory_type == 'foreshadow' and analysis.foreshadows:
                    for foreshadow in analysis.foreshadows:
                        if foreshadow.get('content') in mem.content:
                            metadata_extra["foreshadow_type"] = foreshadow.get('type', 'planted')
                            metadata_extra["strength"] = foreshadow.get('strength', 5)
                            break
        
        annotation = {
            "id": mem.id,
            "type": mem.memory_type,
            "title": mem.title,
            "content": mem.content,
            "importance": mem.importance_score or 0.5,
            "position": position,
            "length": length,
            "tags": mem.tags or [],
            "metadata": {
                "is_foreshadow": mem.is_foreshadow,
                "related_characters": mem.related_characters or [],
                "related_locations": mem.related_locations or [],
                **metadata_extra
            }
        }
        
        annotations.append(annotation)
    
    return {
        "chapter_id": chapter_id,
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "word_count": chapter.word_count or 0,
        "annotations": annotations,
        "has_analysis": analysis is not None,
        "summary": {
            "total_annotations": len(annotations),
            "hooks": len([a for a in annotations if a["type"] == "hook"]),
            "foreshadows": len([a for a in annotations if a["type"] == "foreshadow"]),
            "plot_points": len([a for a in annotations if a["type"] == "plot_point"]),
            "character_events": len([a for a in annotations if a["type"] == "character_event"])
        }
    }


@router.post("/{chapter_id}/analyze", summary="Kích hoạt thủ công phân tích chương")
async def trigger_chapter_analysis(
    chapter_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Kích hoạt thủ công phân tích chương (để phân tích lại hoặc phân tích chương cũ)
    """
    # Lấy ID người dùng từ request
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Xác minh chương tồn tại
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    if not chapter.content or chapter.content.strip() == "":
        raise HTTPException(status_code=400, detail="Nội dung chương rỗng, không thể phân tích")
    
    # Lấy thông tin dự án
    project_result = await db.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # Tránh tạo tác vụ phân tích đồng thời do click lặp hoặc phán đoán sai khi poll trạng thái.
    existing_task_result = await db.execute(
        select(AnalysisTask)
        .where(AnalysisTask.chapter_id == chapter_id)
        .order_by(AnalysisTask.created_at.desc())
        .limit(1)
    )
    existing_task = existing_task_result.scalar_one_or_none()
    if existing_task and existing_task.status in ("pending", "running"):
        return {
            "task_id": existing_task.id,
            "chapter_id": chapter_id,
            "status": existing_task.status,
            "message": "Đã có tác vụ phân tích đang thực hiện"
        }
    
    # Tạo tác vụ phân tích
    analysis_task = AnalysisTask(
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=project.id,
        status='pending',
        progress=0
    )
    db.add(analysis_task)
    await db.commit()
    
    task_id = analysis_task.id
    logger.info(f"📋 Tạo tác vụ phân tích: {task_id}, chương: {chapter_id}")
    
    # Refresh session database, đảm bảo các session khác thấy được tác vụ mới
    await db.refresh(analysis_task)
    
    # Trì hoãn ngắn để đảm bảo SQLite WAL ghi xong (cho session khác thấy được)
    await asyncio.sleep(3)
    
    # Khởi động trực tiếp phân tích nền (thực hiện đồng thời)
    background_tasks.add_task(
        analyze_chapter_background,
        chapter_id=chapter_id,
        user_id=user_id,
        project_id=project.id,
        task_id=task_id
    )
    
    return {
        "task_id": task_id,
        "chapter_id": chapter_id,
        "status": "pending",
        "message": "Đã tạo tác vụ phân tích và bắt đầu thực hiện"
    }



def calculate_estimated_time(
    chapter_count: int,
    target_word_count: int,
    enable_analysis: bool
) -> int:
    """
    Tính thời gian ước tính (phút)
    
    Cơ sở:
    - Tạo 3000 từ mất khoảng 2 phút
    - Phân tích mất khoảng 1 phút
    """
    generation_time_per_chapter = (target_word_count / 3000) * 2
    analysis_time_per_chapter = 1 if enable_analysis else 0
    
    total_time = chapter_count * (generation_time_per_chapter + analysis_time_per_chapter)
    
    return max(1, int(total_time))


@router.post("/project/{project_id}/batch-generate", response_model=BatchGenerateResponse, summary="Tạo hàng loạt nội dung chương theo thứ tự")
async def batch_generate_chapters_in_order(
    project_id: str,
    batch_request: BatchGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Bắt đầu từ chương đã chỉ định, tạo hàng loạt số chương đã định theo thứ tự
    
    Đặc điểm:
    1. Tạo nghiêm ngặt theo số thứ tự chương (không được bỏ qua)
    2. Tự động phát hiện chương bắt đầu có tạo được không
    3. Tùy chọn phân tích đồng bộ (ảnh hưởng thời gian và chất lượng)
    4. Thất bại thì dừng, không tiếp tục chương sau
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Xác minh dự án tồn tại và quyền người dùng
    project = await verify_project_access(project_id, user_id, db)
    
    # Lấy tất cả chương của dự án, sắp xếp theo số thứ tự
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    all_chapters = result.scalars().all()
    
    if not all_chapters:
        raise HTTPException(status_code=404, detail="Dự án không có chương")
    
    # Tính phạm vi chương cần tạo
    start_number = batch_request.start_chapter_number
    end_number = start_number + batch_request.count - 1
    
    # Lọc ra các chương cần tạo
    chapters_to_generate = [
        ch for ch in all_chapters
        if start_number <= ch.chapter_number <= end_number
    ]
    
    if not chapters_to_generate:
        raise HTTPException(status_code=404, detail="Trong phạm vi đã chỉ định không có chương")
    
    # Xác minh điều kiện tiên quyết của chương bắt đầu
    first_chapter = chapters_to_generate[0]
    can_generate, error_msg, _ = await check_prerequisites(db, first_chapter)
    if not can_generate:
        raise HTTPException(status_code=400, detail=f"Chương bắt đầu không thể tạo: {error_msg}")

    # Tạo hàng loạt phải phân tích đồng bộ, nếu không chương sau không lấy được ngữ cảnh trạng thái nhân vật, ký ức và nút thắt mới nhất.
    enable_analysis = True
    
    # Tạo tác vụ tạo hàng loạt
    batch_task = BatchGenerationTask(
        project_id=project_id,
        user_id=user_id,
        start_chapter_number=start_number,
        chapter_count=len(chapters_to_generate),
        chapter_ids=[ch.id for ch in chapters_to_generate],
        style_id=batch_request.style_id,
        target_word_count=batch_request.target_word_count,
        enable_analysis=enable_analysis,
        max_retries=batch_request.max_retries,
        status='pending',
        total_chapters=len(chapters_to_generate),
        completed_chapters=0,
        failed_chapters=[],
        current_retry_count=0
    )
    db.add(batch_task)
    await db.commit()
    await db.refresh(batch_task)
    
    batch_id = batch_task.id
    
    # Tính thời gian ước tính
    estimated_time = calculate_estimated_time(
        chapter_count=len(chapters_to_generate),
        target_word_count=batch_request.target_word_count,
        enable_analysis=enable_analysis
    )
    
    logger.info(f"📦 Tạo tác vụ tạo hàng loạt: {batch_id}, chương: chương {start_number}-{end_number}, ước tính: {estimated_time} phút")
    
    # Khởi động tác vụ tạo hàng loạt ở nền, truyền tham số model và skill_key
    background_tasks.add_task(
        execute_batch_generation_in_order,
        batch_id=batch_id,
        user_id=user_id,
        ai_service=user_ai_service,
        custom_model=batch_request.model,
        skill_key=batch_request.skill_key,
        enable_mcp=batch_request.enable_mcp,
        narrative_perspective=batch_request.narrative_perspective
    )
    
    return BatchGenerateResponse(
        batch_id=batch_id,
        message=f"Đã tạo tác vụ tạo hàng loạt, sẽ tạo {len(chapters_to_generate)} chương",
        chapters_to_generate=[
            {
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "title": ch.title
            }
            for ch in chapters_to_generate
        ],
        estimated_time_minutes=estimated_time
    )


@router.get("/batch-generate/{batch_id}/status", response_model=BatchGenerateStatusResponse, summary="Truy vấn trạng thái tác vụ tạo hàng loạt")
async def get_batch_generation_status(
    batch_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Truy vấn trạng thái và tiến độ của tác vụ tạo hàng loạt"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    result = await db.execute(
        select(BatchGenerationTask).where(
            BatchGenerationTask.id == batch_id,
            BatchGenerationTask.user_id == user_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Tác vụ tạo hàng loạt không tồn tại")
    
    return BatchGenerateStatusResponse(
        batch_id=task.id,
        status=task.status,
        total=task.total_chapters,
        completed=task.completed_chapters,
        current_chapter_id=task.current_chapter_id,
        current_chapter_number=task.current_chapter_number,
        current_retry_count=task.current_retry_count,
        max_retries=task.max_retries,
        failed_chapters=task.failed_chapters or [],
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        error_message=task.error_message
    )


@router.get("/project/{project_id}/batch-generate/active", summary="Lấy tác vụ tạo hàng loạt đang chạy của dự án")
async def get_active_batch_generation(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tác vụ tạo hàng loạt đang chạy của dự án
    Dùng để khôi phục trạng thái tác vụ sau khi refresh trang
    """
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    await verify_project_access(project_id, user_id, db)
    
    result = await db.execute(
        select(BatchGenerationTask)
        .where(BatchGenerationTask.project_id == project_id)
        .where(BatchGenerationTask.user_id == user_id)
        .where(BatchGenerationTask.status.in_(['pending', 'running']))
        .order_by(BatchGenerationTask.created_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        return {
            "has_active_task": False,
            "task": None
        }
    
    return {
        "has_active_task": True,
        "task": {
            "batch_id": task.id,
            "status": task.status,
            "total": task.total_chapters,
            "completed": task.completed_chapters,
            "current_chapter_id": task.current_chapter_id,
            "current_chapter_number": task.current_chapter_number,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None
        }
    }


@router.post("/batch-generate/{batch_id}/cancel", summary="Hủy tác vụ tạo hàng loạt")
async def cancel_batch_generation(
    batch_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Hủy tác vụ tạo hàng loạt đang tiến hành"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    result = await db.execute(
        select(BatchGenerationTask).where(
            BatchGenerationTask.id == batch_id,
            BatchGenerationTask.user_id == user_id
        )
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Tác vụ tạo hàng loạt không tồn tại")
    
    if task.status in ['completed', 'failed', 'cancelled']:
        raise HTTPException(status_code=400, detail=f"Tác vụ đã ở trạng thái {task.status}, không thể hủy")
    
    task.status = 'cancelled'
    task.completed_at = datetime.now()
    await db.commit()
    
    logger.info(f"🛑 Tác vụ tạo hàng loạt đã hủy: {batch_id}")
    
    return {
        "message": "Đã hủy tác vụ tạo hàng loạt",
        "batch_id": batch_id,
        "completed_chapters": task.completed_chapters,
        "total_chapters": task.total_chapters
    }


async def execute_batch_generation_in_order(
    batch_id: str,
    user_id: str,
    ai_service: AIService,
    custom_model: Optional[str] = None,
    skill_key: Optional[str] = None,
    enable_mcp: bool = True,
    narrative_perspective: Optional[str] = None
):
    """
    Thực hiện tác vụ tạo hàng loạt theo thứ tự (tác vụ nền)
    - Nghiêm ngặt theo số thứ tự chương
    - Bất kỳ chương nào thất bại thì dừng việc tạo tiếp theo
    - Tùy chọn phân tích đồng bộ
    """
    db_session = None
    task = None
    write_lock = await get_db_write_lock(user_id)
    
    try:
        logger.info(f"📦 Bắt đầu thực hiện tác vụ tạo hàng loạt theo thứ tự: {batch_id}")
        
        # Tạo session database độc lập
        from app.database import get_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        db_session = AsyncSessionLocal()
        
        # Lấy tác vụ
        task_result = await db_session.execute(
            select(BatchGenerationTask).where(BatchGenerationTask.id == batch_id)
        )
        task = task_result.scalar_one_or_none()
        
        if not task:
            logger.error(f"❌ Tác vụ tạo hàng loạt không tồn tại: {batch_id}")
            return

        if task.status == 'cancelled':
            logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy trước khi khởi động: {batch_id}")
            return
        
        # Cập nhật trạng thái tác vụ thành đang chạy
        async with write_lock:
            await db_session.refresh(task)
            if task.status == 'cancelled':
                logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy trước khi khởi động: {batch_id}")
                return
            task.status = 'running'
            task.started_at = datetime.now()
            await db_session.commit()
        
        # Duy trì tóm tắt chương trước, để truyền cho chương sau (chống trùng ngữ cảnh)
        last_generated_summary = None

        # Tạo từng chương theo thứ tự
        for idx, chapter_id in enumerate(task.chapter_ids, 1):
            # Kiểm tra tác vụ có bị hủy không
            await db_session.refresh(task)
            if task.status == 'cancelled':
                logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy: {batch_id}")
                return
            
            # Cập nhật chương hiện tại
            async with write_lock:
                task.current_chapter_id = chapter_id
                task.current_retry_count = 0 # Đặt lại bộ đếm thử lại
                await db_session.commit()
            
            # Vòng lặp thử lại
            retry_count = 0
            chapter_success = False
            chapter = None
            last_error = None
            
            while retry_count <= task.max_retries and not chapter_success:
                try:
                    await db_session.refresh(task)
                    if task.status == 'cancelled':
                        logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy: {batch_id}")
                        return

                    # Lấy thông tin chương
                    chapter_result = await db_session.execute(
                        select(Chapter).where(Chapter.id == chapter_id)
                    )
                    chapter = chapter_result.scalar_one_or_none()
                    
                    if not chapter:
                        raise Exception(f"Chương {chapter_id} không tồn tại")
                    
                    # Cập nhật số thứ tự chương hiện tại và số lần thử lại
                    async with write_lock:
                        task.current_chapter_number = chapter.chapter_number
                        task.current_retry_count = retry_count
                        await db_session.commit()
                    
                    if retry_count > 0:
                        logger.info(f"🔄 [{idx}/{task.total_chapters}] Thử lại tạo chương (lần {retry_count}): chương {chapter.chapter_number} 《{chapter.title}》")
                    else:
                        logger.info(f"📝 [{idx}/{task.total_chapters}] Bắt đầu tạo chương: chương {chapter.chapter_number} 《{chapter.title}》")
                    
                    # Kiểm tra điều kiện tiên quyết (kiểm tra mỗi lần, đảm bảo tính tuần tự)
                    can_generate, error_msg, _ = await check_prerequisites(db_session, chapter)
                    if not can_generate:
                        raise Exception(f"Điều kiện tiên quyết không đáp ứng: {error_msg}")
                    analysis_ready, analysis_msg = await check_previous_analysis_ready(db_session, chapter)
                    if not analysis_ready:
                        raise Exception(analysis_msg)
                    
                    # Tạo nội dung chương (tái dùng phần lõi logic tạo streaming hiện có), truyền tham số model
                    # Và lấy tóm tắt sau khi tạo (nếu hàm tạo hỗ trợ trả về)
                    generated_summary = await generate_single_chapter_for_batch(
                        db_session=db_session,
                        chapter=chapter,
                        user_id=user_id,
                        style_id=task.style_id,
                        target_word_count=task.target_word_count,
                        ai_service=ai_service,
                        write_lock=write_lock,
                        custom_model=custom_model,
                        previous_summary_context=last_generated_summary,
                        skill_key=skill_key,
                        batch_id=batch_id,
                        enable_mcp=enable_mcp,
                        temp_narrative_perspective=narrative_perspective
                    )

                    await db_session.refresh(task)
                    if task.status == 'cancelled':
                        logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy, bỏ qua xử lý tiếp theo: {batch_id}")
                        return
                    
                    # Cập nhật tóm tắt chương trước, để chương sau dùng
                    if generated_summary:
                        last_generated_summary = f"Chương {chapter.chapter_number}《{chapter.title}》: {generated_summary}"
                        logger.info(f"📝 Đã cập nhật ngữ cảnh tóm tắt chương trước: {last_generated_summary[:50]}...")
                    
                    logger.info(f"✅ Tạo chương xong: chương {chapter.chapter_number}")
                    
                    # Nếu bật phân tích đồng bộ
                    if task.enable_analysis:
                        await db_session.refresh(task)
                        if task.status == 'cancelled':
                            logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy, bỏ qua phân tích đồng bộ: {batch_id}")
                            return
                        logger.info(f"🔍 Bắt đầu phân tích đồng bộ chương: chương {chapter.chapter_number}")

                        async with write_lock:
                            analysis_task = AnalysisTask(
                                chapter_id=chapter_id,
                                user_id=user_id,
                                project_id=task.project_id,
                                status='pending',
                                progress=0
                            )
                            db_session.add(analysis_task)
                            await db_session.commit()
                            await db_session.refresh(analysis_task)

                        analysis_result = await analyze_chapter_background(
                            chapter_id=chapter_id,
                            user_id=user_id,
                            project_id=task.project_id,
                            task_id=analysis_task.id
                        )

                        if not analysis_result:
                            error_message = "Hàm phân tích trả về thất bại"
                            logger.error(f"❌ Phân tích chương thất bại, tạo hàng loạt bị ngắt: chương {chapter.chapter_number}")

                            failed_info = {
                                'chapter_id': chapter_id,
                                'chapter_number': chapter.chapter_number,
                                'title': chapter.title,
                                'error': f"Phân tích thất bại: {error_message}",
                                'retry_count': 1
                            }

                            async with write_lock:
                                if task.failed_chapters is None:
                                    task.failed_chapters = []
                                task.failed_chapters.append(failed_info)

                                task.status = 'failed'
                                task.error_message = f"Chương {chapter.chapter_number} phân tích thất bại: {error_message}"[:500]
                                task.completed_at = datetime.now()
                                task.current_retry_count = 0
                                await db_session.commit()

                            return

                        logger.info(f"✅ Phân tích chương thành công: chương {chapter.chapter_number}")
                    
                    # Đánh dấu thành công
                    chapter_success = True
                    
                    # Cập nhật số đã xong
                    async with write_lock:
                        task.completed_chapters += 1
                        task.current_retry_count = 0 # Đặt lại bộ đếm thử lại
                        await db_session.commit()
                    
                    logger.info(f"✅ Tiến độ: {task.completed_chapters}/{task.total_chapters}")
                    
                except Exception as e:
                    last_error = str(e)
                    await db_session.refresh(task)
                    if task.status == 'cancelled':
                        logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy: {batch_id}")
                        return
                    error_msg = f"Chương {chapter.chapter_number if chapter else '?'} lỗi: {last_error}"
                    logger.error(f"❌ {error_msg}")
                    
                    retry_count += 1
                    
                    # Nếu còn cơ hội thử lại, đợi một lúc rồi thử lại
                    if retry_count <= task.max_retries:
                        wait_time = min(2 ** retry_count, 10) # Backoff mũ, đợi tối đa 10 giây
                        logger.info(f"⏳ Đợi {wait_time} giây rồi thử lại...")
                        await asyncio.sleep(wait_time)
                    else:
                        # Đạt số lần thử lại tối đa, ghi thông tin thất bại
                        logger.error(f"❌ Tạo chương thất bại, đã đạt số lần thử lại tối đa ({task.max_retries}): chương {chapter.chapter_number if chapter else '?'}")
                        
                        failed_info = {
                            'chapter_id': chapter_id,
                            'chapter_number': chapter.chapter_number if chapter else -1,
                            'title': chapter.title if chapter else 'Chưa rõ',
                            'error': last_error,
                            'retry_count': retry_count - 1
                        }
                        
                        async with write_lock:
                            if task.failed_chapters is None:
                                task.failed_chapters = []
                            task.failed_chapters.append(failed_info)
                            
                            # Đánh dấu tác vụ thất bại và dừng
                            task.status = 'failed'
                            task.error_message = f"Chương {chapter.chapter_number} tạo thất bại (thử lại {retry_count-1} lần): {last_error}"[:500]
                            task.completed_at = datetime.now()
                            task.current_retry_count = 0
                            await db_session.commit()
                        
                        # ⚠️ Nếu bật phân tích đồng bộ, bất kỳ lỗi nào cũng nên ngắt tác vụ
                        # Vì tạo chương hoặc phân tích thất bại sẽ ảnh hưởng cập nhật nghề nghiệp và tính liền mạch cốt truyện của chương sau
                        if task.enable_analysis:
                            logger.error(f"🛑 Tạo hàng loạt bị ngắt: vì bật phân tích đồng bộ, bất kỳ lỗi nào cũng ngắt tác vụ để đảm bảo thông tin nghề nghiệp và tính liền mạch cốt truyện")
                        else:
                            logger.error(f"🛑 Tạo hàng loạt dừng tại chương {chapter.chapter_number}")
                        
                        return
        
        # Tất cả xong
        async with write_lock:
            await db_session.refresh(task)
            if task.status == 'cancelled':
                logger.info(f"🛑 Tác vụ tạo hàng loạt đã bị hủy, bỏ qua ghi đè trạng thái hoàn thành: {batch_id}")
                return
            task.status = 'completed'
            task.completed_at = datetime.now()
            task.current_chapter_id = None
            task.current_chapter_number = None
            await db_session.commit()
        
        logger.info(f"✅ Tác vụ tạo hàng loạt xong toàn bộ: {batch_id}, đã tạo thành công {task.completed_chapters} chương")
        
    except Exception as e:
        logger.error(f"❌ Tác vụ tạo hàng loạt bất thường: {str(e)}", exc_info=True)
        if db_session and task:
            try:
                async with write_lock:
                    await db_session.refresh(task)
                    if task.status != 'cancelled':
                        task.status = 'failed'
                        task.error_message = str(e)[:500]
                        task.completed_at = datetime.now()
                        await db_session.commit()
            except Exception as commit_error:
                logger.error(f"❌ Cập nhật trạng thái thất bại của tác vụ thất bại: {str(commit_error)}")
    finally:
        if db_session:
            await db_session.close()


async def generate_single_chapter_for_batch(
    db_session: AsyncSession,
    chapter: Chapter,
    user_id: str,
    style_id: Optional[int],
    target_word_count: int,
    ai_service: AIService,
    write_lock: Lock,
    custom_model: Optional[str] = None,
    previous_summary_context: Optional[str] = None,
    skill_key: Optional[str] = None,
    batch_id: Optional[str] = None,
    enable_mcp: bool = True,
    temp_narrative_perspective: Optional[str] = None
) -> Optional[str]:
    """
    Thực hiện tạo một chương cho tạo hàng loạt (không streaming)
    Tái dùng phần lõi của logic tạo hiện có
    
    Returns:
        Tạo tóm tắt của chương (200 từ đầu)
    """
    # Lấy thông tin dự án
    project_result = await db_session.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise Exception("Dự án không tồn tại")
    
    # Lấy mode đề cương của dự án
    outline_mode = project.outline_mode if project else 'one-to-many'
    logger.info(f"📋 Tạo hàng loạt - mode đề cương dự án: {outline_mode}")
    
    # Lấy đề cương tương ứng (ưu tiên liên kết trực tiếp bằng chapter.outline_id)
    if chapter.outline_id:
        outline_result = await db_session.execute(
            select(Outline).where(Outline.id == chapter.outline_id)
        )
    else:
        # Dự phòng tìm theo số thứ tự
        outline_result = await db_session.execute(
            select(Outline)
            .where(Outline.project_id == chapter.project_id)
            .where(Outline.order_index == chapter.chapter_number)
        )
    outline = outline_result.scalar_one_or_none()
    
    # Lấy phong cách viết
    style_content = ""
    if style_id:
        style_result = await db_session.execute(
            select(WritingStyle).where(WritingStyle.id == style_id)
        )
        style = style_result.scalar_one_or_none()
        if style:
            if style.user_id is None or style.user_id == user_id:
                style_content = style.prompt_content or ""
    
    # 🚀 Chọn context builder độc lập theo mode đề cương (tạo hàng loạt)
    if outline_mode == 'one-to-one':
        # Mode 1-1
        logger.info(f"🔧 Tạo hàng loạt - [mode 1-1] dùng OneToOneContextBuilder")
        context_builder = OneToOneContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db_session,
            target_word_count=target_word_count
        )
    else:
        # Mode 1-N: dùng builder đầy đủ độc lập
        logger.info(f"🔧 Tạo hàng loạt - [mode 1-N] dùng OneToManyContextBuilder")
        context_builder = OneToManyContextBuilder(
            memory_service=memory_service,
            foreshadow_service=foreshadow_service
        )
        chapter_context = await context_builder.build(
            chapter=chapter,
            project=project,
            outline=outline,
            user_id=user_id,
            db=db_session,
            style_content=style_content,
            target_word_count=target_word_count,
            temp_narrative_perspective=temp_narrative_perspective
        )
    
    # Log thống kê
    logger.info(f"📊 Tạo hàng loạt - thống kê ngữ cảnh tối ưu:")
    logger.info(f" - Số thứ tự chương: {chapter.chapter_number}")
    logger.info(f" - Độ dài điểm nối tiếp: {len(chapter_context.continuation_point or '')} ký tự")
    logger.info(f" - Ký ức liên quan: {chapter_context.context_stats.get('memory_count', 0)}")
    logger.info(f" - Tổng độ dài ngữ cảnh: {chapter_context.context_stats.get('total_length', 0)} ký tự")
    
    # 🚀 Chọn template prompt theo mode đề cương (tạo hàng loạt)
    # Thống nhất dùng kết quả chapter_context do context_builder xây dựng, nhất quán với tạo đơn chương
    if outline_mode == 'one-to-one':
        # Mode 1-1
        if chapter_context.continuation_point:
            # Có nội dung chương trước
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE_NEXT", user_id, db_session)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=temp_narrative_perspective or project.narrative_perspective or 'Ngôi thứ ba',
                previous_chapter_content=chapter_context.continuation_point,
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan',
                previous_chapter_summary=chapter_context.previous_chapter_summary or '',
                recent_chapters_context=chapter_context.recent_chapters_context or 'Chưa có tóm tắt chương gần đây'
            )
        else:
            # Chương đầu
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_ONE", user_id, db_session)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=temp_narrative_perspective or project.narrative_perspective or 'Ngôi thứ ba',
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
    else:
        # Mode 1-n: dùng kết quả do context_builder xây dựng, nhất quán với tạo đơn chương
        if chapter_context.continuation_point:
            # Có nội dung tiên quyết, dùng template WITH_CONTEXT
            # Ưu tiên dùng tóm tắt của context_builder, sau đó dùng previous_summary_context được truyền vào
            final_prev_summary = "(Không có tóm tắt chương trước, vui lòng viết tiếp theo điểm neo)"
            
            if chapter_context.previous_chapter_summary:
                final_prev_summary = chapter_context.previous_chapter_summary
            elif previous_summary_context:
                final_prev_summary = previous_summary_context
                    
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY_NEXT", user_id, db_session)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                continuation_point=chapter_context.continuation_point,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=temp_narrative_perspective or project.narrative_perspective or 'Ngôi thứ ba',
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                previous_chapter_summary=final_prev_summary,
                recent_chapters_context=chapter_context.recent_chapters_context or '',
                relevant_memories=chapter_context.relevant_memories or ''
            )
        else:
            # Chương đầu, dùng template không có nội dung tiên quyết
            template = await PromptService.get_template("CHAPTER_GENERATION_ONE_TO_MANY", user_id, db_session)
            base_prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                chapter_number=chapter.chapter_number,
                chapter_title=chapter.title,
                chapter_outline=chapter_context.chapter_outline,
                target_word_count=target_word_count,
                genre=project.genre or 'Chưa đặt',
                narrative_perspective=temp_narrative_perspective or project.narrative_perspective or 'Ngôi thứ ba',
                characters_info=chapter_context.chapter_characters or 'Chưa có thông tin nhân vật',
                chapter_careers=chapter_context.chapter_careers or 'Chưa có thông tin nghề nghiệp',
                foreshadow_reminders=chapter_context.foreshadow_reminders or 'Chưa có nút thắt cần chú ý',
                relevant_memories=chapter_context.relevant_memories or 'Chưa có ký ức liên quan'
            )
    
    # Áp dụng phong cách viết
    if style_content:
        prompt = WritingStyleManager.apply_style_to_prompt(base_prompt, style_content)
    else:
        prompt = base_prompt
    
    # 🎨 Inject Skill / phong cách viết vào system prompt (tạo hàng loạt)
    system_prompt_with_style = None

    # ⚡ Hỗ trợ Skill
    if skill_key:
        try:
            from app.services.skill_loader import get_all_skills_cached
            skills = get_all_skills_cached()
            skill = next((s for s in skills if s["template_key"] == skill_key), None)
            if skill:
                skill_content = skill["content"]
                skill_name = skill["template_name"]
                system_prompt_with_style = f"""

{skill_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt chỉ dẫn workflow Skill ở trên để sáng tác!"""
                if style_content:
                    system_prompt_with_style += f"""

【🎨 Yêu cầu phong cách viết - bổ sung】

{style_content}"""
                logger.info(f"⚡ Tạo hàng loạt - đã inject Skill '{skill_name}' vào system prompt ({len(skill_content)} ký tự)")
            else:
                logger.warning(f"⚠️ Tạo hàng loạt - không tìm thấy Skill: {skill_key}")
        except Exception as skill_err:
            logger.warning(f"⚠️ Tạo hàng loạt - tải Skill thất bại: {skill_err}")

    if not system_prompt_with_style and style_content:
        system_prompt_with_style = f"""

{style_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt yêu cầu phong cách viết ở trên để sáng tác, đây là chỉ dẫn quan trọng nhất!
Đảm bảo giữ nhất quán phong cách trong toàn bộ quá trình sáng tác chương."""
        logger.info(f"✅ Tạo hàng loạt - đã inject phong cách viết vào system prompt ({len(style_content)} ký tự)")
    
    # 🔢 Tính giới hạn max_tokens (tạo hàng loạt)
    # Ký tự tiếng Trung khoảng 1.5-2 token, dùng hệ số 2.5 lần để đảm bảo đủ không gian hoàn thành đoạn văn
    # Đồng thời đặt giới hạn trên chống quá dài, giới hạn dưới đảm bảo dùng được cơ bản
    calculated_max_tokens = int(target_word_count * 3)
    calculated_max_tokens = max(2000, min(calculated_max_tokens, 16000)) # Giới hạn trong khoảng 2000-16000
    logger.info(f"📊 Tạo hàng loạt - số từ mục tiêu: {target_word_count}, max_tokens tính được: {calculated_max_tokens}")
    
    # Tạo nội dung không streaming
    full_content = ""
    # Chuẩn bị tham số tạo
    generate_kwargs = {
        "prompt": prompt,
        "system_prompt": system_prompt_with_style,
        "tool_choice": "required",
        "max_tokens": calculated_max_tokens,
        "auto_mcp": bool(enable_mcp)
    }
    # Nếu truyền model tùy chỉnh, dùng model đã chỉ định
    if custom_model:
        generate_kwargs["model"] = custom_model
        logger.info(f" Tạo hàng loạt dùng model tùy chỉnh: {custom_model}")
    
    async def _is_batch_cancelled() -> bool:
        if not batch_id:
            return False
        result = await db_session.execute(
            select(BatchGenerationTask.status).where(BatchGenerationTask.id == batch_id)
        )
        return result.scalar_one_or_none() == 'cancelled'

    # Tạo streaming trong tạo hàng loạt (không phải SSE, không cần sửa hiển thị tiến độ)
    chunk_count = 0
    async for chunk in ai_service.generate_text_stream(**generate_kwargs):
        if chunk_count % 10 == 0 and await _is_batch_cancelled():
            logger.info(f"🛑 Tạo streaming đơn chương trong tạo hàng loạt bị hủy: batch={batch_id}, chapter={chapter.id}")
            raise Exception("Tác vụ tạo hàng loạt đã bị hủy")
        full_content += chunk
        chunk_count += 1

    if await _is_batch_cancelled():
        logger.info(f"🛑 Tạo hàng loạt bị hủy trước khi lưu: batch={batch_id}, chapter={chapter.id}")
        raise Exception("Tác vụ tạo hàng loạt đã bị hủy")
    
    # Cập nhật nội dung chương vào database (dùng khóa bảo vệ)
    async with write_lock:
        old_word_count = chapter.word_count or 0
        chapter.content = full_content
        new_word_count = len(full_content)
        chapter.word_count = new_word_count
        chapter.status = "completed"
        chapter.summary = _build_lightweight_chapter_summary(full_content)
        
        # Cập nhật số từ của dự án
        project.current_words = project.current_words - old_word_count + new_word_count
        
        # Ghi lịch sử tạo
        history = GenerationHistory(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            prompt=f"Tạo hàng loạt: chương {chapter.chapter_number} {chapter.title}",
            generated_content=full_content[:500] if len(full_content) > 500 else full_content,
            model="default"
        )
        db_session.add(history)
        
        await db_session.commit()
        await db_session.refresh(chapter)
    
    logger.info(f"✅ Tạo đơn chương xong: chương {chapter.chapter_number}, tổng {new_word_count} từ")
    
    # Tạo tóm tắt ngắn trả về
    summary_preview = _build_lightweight_chapter_summary(full_content)
    
    # 🔮 Sau tạo hàng loạt tự động đánh dấu nút thắt dự kiến gài trong chương này
    try:
        async with write_lock:
            plant_result = await foreshadow_service.auto_plant_pending_foreshadows(
                db=db_session,
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                chapter_content=full_content
            )
        if plant_result.get('planted_count', 0) > 0:
            logger.info(f"🔮 Tạo hàng loạt - tự động đánh dấu nút thắt đã gài: {plant_result['planted_count']}")
    except Exception as plant_error:
        logger.warning(f"⚠️ Tạo hàng loạt - tự động đánh dấu gài nút thắt thất bại: {str(plant_error)}")
        
    return summary_preview




# ==================== API liên quan tạo lại chương ====================

@router.post("/{chapter_id}/regenerate-stream", summary="Tạo lại streaming nội dung chương")
async def regenerate_chapter_stream(
    chapter_id: str,
    request: Request,
    regenerate_request: ChapterRegenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Tạo lại nội dung chương theo gợi ý phân tích hoặc chỉ dẫn tùy chỉnh (trả về streaming)
    
    Quy trình:
    1. Xác minh chương và kết quả phân tích
    2. Tạo tác vụ tạo lại
    3. Xây dựng chỉ dẫn sửa
    4. Tạo streaming nội dung mới
    5. Lưu thành lịch sử phiên bản
    6. Tùy chọn tự động áp dụng
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Xác minh chương tồn tại
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    if not chapter.content or chapter.content.strip() == "":
        raise HTTPException(status_code=400, detail="Nội dung chương rỗng, không thể tạo lại")
    
    # Xác minh quyền người dùng
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Lấy kết quả phân tích (nếu dùng gợi ý phân tích)
    analysis = None
    if regenerate_request.modification_source in ['analysis_suggestions', 'mixed']:
        analysis_result = await db.execute(
            select(PlotAnalysis)
            .where(PlotAnalysis.chapter_id == chapter_id)
            .order_by(PlotAnalysis.created_at.desc())
            .limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Chương này chưa có kết quả phân tích")
    
    # Lấy trước dữ liệu ngữ cảnh dự án và phong cách viết
    async for temp_db in get_db(request):
        try:
            # Lấy thông tin dự án
            project_result = await temp_db.execute(
                select(Project).where(Project.id == chapter.project_id)
            )
            project = project_result.scalar_one_or_none()
            
            # Lấy thông tin nhân vật (bao gồm thông tin nghề nghiệp)
            characters_result = await temp_db.execute(
                select(Character).where(Character.project_id == chapter.project_id)
            )
            characters = characters_result.scalars().all()
            
            # 📝 Lọc thông minh nhân vật liên quan theo mode đề cương (tạo lại)
            outline_mode_result = await temp_db.execute(
                select(Project.outline_mode).where(Project.id == chapter.project_id)
            )
            outline_mode = outline_mode_result.scalar_one_or_none() or 'one-to-many'
            
            filter_character_names = None
            if outline_mode == 'one-to-one':
                # Mode 1-1: trích trường characters từ outline.structure (ưu tiên dùng outline_id)
                if chapter.outline_id:
                    outline_result_temp = await temp_db.execute(
                        select(Outline.structure)
                        .where(Outline.id == chapter.outline_id)
                    )
                else:
                    outline_result_temp = await temp_db.execute(
                        select(Outline.structure)
                        .where(Outline.project_id == chapter.project_id)
                        .where(Outline.order_index == chapter.chapter_number)
                    )
                outline_structure = outline_result_temp.scalar_one_or_none()
                if outline_structure:
                    try:
                        structure = json.loads(outline_structure)
                        filter_character_names = structure.get('characters', [])
                        if filter_character_names:
                            logger.info(f"📋 Tạo lại - mode 1-1: trích danh sách nhân vật từ structure {filter_character_names}")
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Tạo lại - phân tích outline.structure thất bại, dùng tất cả nhân vật")
            else:
                # Mode 1-n: trích trường character_focus từ chapter.expansion_plan
                if chapter.expansion_plan:
                    try:
                        plan = json.loads(chapter.expansion_plan)
                        filter_character_names = plan.get('character_focus', [])
                        if filter_character_names:
                            logger.info(f"📋 Tạo lại - mode 1-n: trích tiêu điểm nhân vật từ expansion_plan {filter_character_names}")
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Tạo lại - phân tích expansion_plan thất bại, dùng tất cả nhân vật")
            
            characters_info_with_careers = await build_characters_info_with_careers(
                db=temp_db,
                project_id=chapter.project_id,
                characters=characters,
                filter_character_names=filter_character_names
            )
            
            # Lấy đề cương chương (ưu tiên liên kết trực tiếp bằng chapter.outline_id)
            if chapter.outline_id:
                outline_result = await temp_db.execute(
                    select(Outline).where(Outline.id == chapter.outline_id)
                )
            else:
                # Dự phòng tìm theo số thứ tự
                outline_result = await temp_db.execute(
                    select(Outline)
                    .where(Outline.project_id == chapter.project_id)
                    .where(Outline.order_index == chapter.chapter_number)
                )
            outline = outline_result.scalar_one_or_none()
            
            # Lấy phong cách viết
            style_content = ""
            style_id = regenerate_request.style_id
            
            # Nếu chưa chỉ định phong cách, thử dùng phong cách mặc định của dự án
            if not style_id:
                from app.models.project_default_style import ProjectDefaultStyle
                default_style_result = await temp_db.execute(
                    select(ProjectDefaultStyle.style_id)
                    .where(ProjectDefaultStyle.project_id == chapter.project_id)
                )
                default_style_id = default_style_result.scalar_one_or_none()
                if default_style_id:
                    style_id = default_style_id
                    logger.info(f"📝 Dùng phong cách viết mặc định của dự án: {style_id}")
            
            # Lấy nội dung phong cách
            if style_id:
                style_result = await temp_db.execute(
                    select(WritingStyle).where(WritingStyle.id == style_id)
                )
                style = style_result.scalar_one_or_none()
                if style:
                    # Xác minh phong cách có dùng được không: phong cách preset toàn cục (user_id là NULL) hoặc phong cách tùy chỉnh của người dùng hiện tại
                    if style.user_id is None or style.user_id == user_id:
                        style_content = style.prompt_content or ""
                        style_type = "Preset toàn cục" if style.user_id is None else "Tùy chỉnh của người dùng"
                        logger.info(f"✅ Dùng phong cách viết: {style.name} ({style_type})")
                    else:
                        logger.warning(f"⚠️ Phong cách {style_id} không thuộc dự án hiện tại, bỏ qua")
                else:
                    logger.warning(f"⚠️ Không tìm thấy phong cách {style_id}")
            else:
                logger.info("ℹ️ Chưa chỉ định phong cách viết, dùng prompt mặc định")
            
            # Xây dựng ngữ cảnh dự án
            project_context = {
                'project_title': project.title if project else 'Chưa rõ',
                'genre': project.genre if project else 'Chưa đặt',
                'theme': project.theme if project else 'Chưa đặt',
                'narrative_perspective': project.narrative_perspective if project else 'Ngôi thứ ba',
                'time_period': project.world_time_period if project else 'Chưa đặt',
                'location': project.world_location if project else 'Chưa đặt',
                'atmosphere': project.world_atmosphere if project else 'Chưa đặt',
                'characters_info': characters_info_with_careers,
                'chapter_outline': outline.content if outline else chapter.summary or 'Chưa có đề cương',
                'previous_context': ''  # Có thể mở rộng thêm ngữ cảnh chương tiên quyết sau
            }
        finally:
            await temp_db.close()
        break
    
    async def event_generator():
        """Generator sự kiện tạo streaming"""
        db_session = None
        db_committed = False
        
        # Khởi tạo tracker tiến độ chuẩn
        from app.utils.sse_response import WizardProgressTracker
        tracker = WizardProgressTracker("Tạo lại chương")
        
        try:
            yield await tracker.start()
            
            # Tạo session database độc lập
            async for db_session in get_db(request):
                yield await tracker.loading("Đang tải thông tin chương...", 0.5)
                
                # Tạo tác vụ tạo lại
                regen_task = RegenerationTask(
                    chapter_id=chapter_id,
                    analysis_id=analysis.id if analysis else None,
                    user_id=user_id,
                    project_id=chapter.project_id,
                    modification_instructions="",  # Điền sau
                    original_suggestions=analysis.suggestions if analysis else None,
                    selected_suggestion_indices=regenerate_request.selected_suggestion_indices,
                    custom_instructions=regenerate_request.custom_instructions,
                    style_id=regenerate_request.style_id,
                    target_word_count=regenerate_request.target_word_count,
                    focus_areas=regenerate_request.focus_areas,
                    preserve_elements=regenerate_request.preserve_elements.model_dump() if regenerate_request.preserve_elements else None,
                    status='running',
                    original_content=chapter.content,
                    original_word_count=chapter.word_count or len(chapter.content),
                    version_note=regenerate_request.version_note,
                    started_at=datetime.now()
                )
                db_session.add(regen_task)
                await db_session.commit()
                await db_session.refresh(regen_task)
                
                task_id = regen_task.id
                logger.info(f"📝 Tạo tác vụ tạo lại: {task_id}")
                
                yield await tracker.preparing("Đang chuẩn bị tạo lại...")
                
                yield await SSEResponse.send_event(
                    event='task_created',
                    data={'task_id': task_id}
                )
                
                # Khởi tạo bộ tạo lại
                regenerator = ChapterRegenerator(user_ai_service)
                
                # === Giai đoạn tạo ===
                full_content = ""
                estimated_total = regenerate_request.target_word_count or len(chapter.content)
                
                yield await tracker.generating(
                    current_chars=0,
                    estimated_total=estimated_total
                )
                
                async for event in regenerator.regenerate_with_feedback(
                    chapter=chapter,
                    analysis=analysis,
                    regenerate_request=regenerate_request,
                    project_context=project_context,
                    style_content=style_content,
                    user_id=user_id,
                    db=db_session
                ):
                    # Xử lý các loại sự kiện khác nhau
                    if event['type'] == 'chunk':
                        # Khối nội dung
                        chunk = event['content']
                        full_content += chunk
                        yield await tracker.generating_chunk(chunk)
                        
                        # Cập nhật tiến độ định kỳ
                        if len(full_content) % 500 == 0:
                            yield await tracker.generating(
                                current_chars=len(full_content),
                                estimated_total=estimated_total,
                                message=f'Đang tạo lại... đã tạo {len(full_content)} từ'
                            )
                    elif event['type'] == 'progress':
                        # Cập nhật tiến độ - ánh xạ sang giai đoạn tương ứng
                        progress = event.get('progress', 0)
                        message = event.get('message', '')
                        if progress < 20:
                            yield await tracker.preparing(message)
                        elif progress < 85:
                            yield await tracker.generating(
                                current_chars=len(full_content),
                                estimated_total=estimated_total,
                                message=message
                            )
                        else:
                            yield await tracker.parsing(message)
                    
                    await asyncio.sleep(0)
                
                # === Giai đoạn lưu ===
                yield await tracker.saving("Đang lưu nội dung tạo lại...", 0.5)
                
                # Cập nhật trạng thái tác vụ
                regen_task.status = 'completed'
                regen_task.regenerated_content = full_content
                regen_task.regenerated_word_count = len(full_content)
                regen_task.completed_at = datetime.now()
                
                # Tính thống kê khác biệt
                diff_stats = regenerator.calculate_content_diff(chapter.content, full_content)
                
                await db_session.commit()
                db_committed = True
                
                yield await tracker.saving("Lưu xong", 0.9)
                
                # === Giai đoạn hoàn thành ===
                yield await tracker.complete("Tạo lại xong!")
                
                # Gửi dữ liệu kết quả
                yield await tracker.result({
                    'task_id': task_id,
                    'word_count': len(full_content),
                    'version_number': regen_task.version_number,
                    'auto_applied': regenerate_request.auto_apply,
                    'diff_stats': diff_stats
                })
                
                # Gửi tín hiệu hoàn thành
                yield await tracker.done()
                
                logger.info(f"✅ Tạo lại chương xong: {chapter_id}, tác vụ: {task_id}")
                
                break
        
        except Exception as e:
            logger.error(f"❌ Tạo lại thất bại: {str(e)}", exc_info=True)
            
            # Cập nhật trạng thái tác vụ thành thất bại
            if db_session and not db_committed:
                try:
                    task_result = await db_session.execute(
                        select(RegenerationTask).where(RegenerationTask.chapter_id == chapter_id)
                        .order_by(RegenerationTask.created_at.desc()).limit(1)
                    )
                    task = task_result.scalar_one_or_none()
                    if task:
                        task.status = 'failed'
                        task.error_message = str(e)[:500]
                        task.completed_at = datetime.now()
                        await db_session.commit()
                except Exception as update_error:
                    logger.error(f"Cập nhật trạng thái thất bại của tác vụ thất bại: {str(update_error)}")
            
            yield await tracker.error(str(e))
        
        finally:
            if db_session:
                try:
                    if not db_committed and db_session.in_transaction():
                        await db_session.rollback()
                    await db_session.close()
                except Exception as close_error:
                    logger.error(f"Đóng session database thất bại: {str(close_error)}")
    
    return create_sse_response(event_generator())


@router.get("/{chapter_id}/regeneration/tasks", summary="Lấy danh sách tác vụ tạo lại của chương")
async def get_regeneration_tasks(
    chapter_id: str,
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Lấy lịch sử tác vụ tạo lại của chương đã chỉ định"""
    user_id = getattr(request.state, 'user_id', None)
    
    # Xác minh chương tồn tại và quyền
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Lấy danh sách tác vụ
    result = await db.execute(
        select(RegenerationTask)
        .where(RegenerationTask.chapter_id == chapter_id)
        .order_by(RegenerationTask.created_at.desc())
        .limit(limit)
    )
    tasks = result.scalars().all()
    
    return {
        "chapter_id": chapter_id,
        "total": len(tasks),
        "tasks": [
            {
                "task_id": task.id,
                "status": task.status,
                "version_number": task.version_number,
                "version_note": task.version_note,
                "original_word_count": task.original_word_count,
                "regenerated_word_count": task.regenerated_word_count,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            for task in tasks
        ]
    }


@router.put("/{chapter_id}/expansion-plan", response_model=dict, summary="Cập nhật thông tin kế hoạch chương")
async def update_chapter_expansion_plan(
    chapter_id: str,
    expansion_plan: ExpansionPlanUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật thông tin kế hoạch triển khai và tóm tắt cốt truyện của chương
    
    Args:
        chapter_id: ID chương
        expansion_plan: dữ liệu cập nhật thông tin kế hoạch (bao gồm trường summary và expansion_plan)
    
    Returns:
        Thông tin kế hoạch chương sau khi cập nhật
    """
    # Lấy chương
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Chuẩn bị dữ liệu cập nhật (loại trừ giá trị None)
    plan_data = expansion_plan.model_dump(exclude_unset=True, exclude_none=True)
    
    # Tách dữ liệu summary và expansion_plan
    summary_value = plan_data.pop('summary', None)
    
    # Cập nhật trường summary (nếu có)
    if summary_value is not None:
        chapter.summary = summary_value
        logger.info(f"Cập nhật tóm tắt chương: {chapter_id}")
    
    # Cập nhật trường expansion_plan (nếu có trường khác)
    if plan_data:
        if chapter.expansion_plan:
            try:
                existing_plan = json.loads(chapter.expansion_plan)
                # Gộp cập nhật
                existing_plan.update(plan_data)
                chapter.expansion_plan = json.dumps(existing_plan, ensure_ascii=False)
            except json.JSONDecodeError:
                logger.warning(f"expansion_plan của chương {chapter_id} sai định dạng, sẽ ghi đè")
                chapter.expansion_plan = json.dumps(plan_data, ensure_ascii=False)
        else:
            chapter.expansion_plan = json.dumps(plan_data, ensure_ascii=False)
    
    await db.commit()
    await db.refresh(chapter)
    
    logger.info(f"Cập nhật kế hoạch chương thành công: {chapter_id}")
    
    # Trả về dữ liệu kế hoạch sau khi cập nhật
    updated_plan = json.loads(chapter.expansion_plan) if chapter.expansion_plan else None
    
    return {
        "id": chapter.id,
        "summary": chapter.summary,
        "expansion_plan": updated_plan,
        "message": "Cập nhật thông tin kế hoạch thành công"
    }


# ==================== API liên quan viết lại cục bộ ====================

@router.post("/{chapter_id}/partial-regenerate-stream", summary="Viết lại cục bộ streaming nội dung đã chọn")
async def partial_regenerate_stream(
    chapter_id: str,
    request: Request,
    partial_request: PartialRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Viết lại streaming phần nội dung được chọn trong chương
    
    Quy trình:
    1. Xác minh tính hợp lệ của chương và nội dung đã chọn
    2. Cắt ngữ cảnh (văn trước và sau)
    3. Xây dựng prompt theo yêu cầu người dùng
    4. Tạo streaming kết quả viết lại
    5. Trả về kết quả viết lại (không tự động lưu, frontend quyết định có áp dụng không)
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Xác minh chương tồn tại
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    if not chapter.content or chapter.content.strip() == "":
        raise HTTPException(status_code=400, detail="Nội dung chương rỗng")
    
    # Xác minh quyền người dùng
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Xác minh tham số vị trí
    content_length = len(chapter.content)
    if partial_request.start_position >= content_length:
        raise HTTPException(status_code=400, detail="Vị trí bắt đầu vượt phạm vi nội dung")
    if partial_request.end_position > content_length:
        raise HTTPException(status_code=400, detail="Vị trí kết thúc vượt phạm vi nội dung")
    if partial_request.start_position >= partial_request.end_position:
        raise HTTPException(status_code=400, detail="Vị trí bắt đầu phải nhỏ hơn vị trí kết thúc")
    
    # Xác minh text đã chọn có khớp không
    actual_selected = chapter.content[partial_request.start_position:partial_request.end_position]
    if actual_selected != partial_request.selected_text:
        # Vị trí có thể lệch, thử tìm ở gần đó
        search_start = max(0, partial_request.start_position - 50)
        search_end = min(content_length, partial_request.end_position + 50)
        search_area = chapter.content[search_start:search_end]
        
        if partial_request.selected_text in search_area:
            # Tìm thấy, cập nhật vị trí
            offset = search_area.find(partial_request.selected_text)
            partial_request.start_position = search_start + offset
            partial_request.end_position = partial_request.start_position + len(partial_request.selected_text)
            logger.info(f"⚠️ Hiệu chỉnh vị trí text đã chọn: {partial_request.start_position}-{partial_request.end_position}")
        else:
            raise HTTPException(
                status_code=400,
                detail="Text đã chọn không khớp với nội dung chương, vui lòng refresh trang rồi thử lại"
            )
    
    # Lấy trước thông tin dự án và phong cách viết
    project_result = await db.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    
    # Lấy phong cách viết
    style_content = ""
    style_id = partial_request.style_id
    
    # Nếu chưa chỉ định phong cách, thử dùng phong cách mặc định của dự án
    if not style_id:
        from app.models.project_default_style import ProjectDefaultStyle
        default_style_result = await db.execute(
            select(ProjectDefaultStyle.style_id)
            .where(ProjectDefaultStyle.project_id == chapter.project_id)
        )
        default_style_id = default_style_result.scalar_one_or_none()
        if default_style_id:
            style_id = default_style_id
            logger.info(f"📝 Viết lại cục bộ - dùng phong cách viết mặc định của dự án: {style_id}")
    
    # Lấy nội dung phong cách
    if style_id:
        style_result = await db.execute(
            select(WritingStyle).where(WritingStyle.id == style_id)
        )
        style = style_result.scalar_one_or_none()
        if style:
            if style.user_id is None or style.user_id == user_id:
                style_content = style.prompt_content or ""
                style_type = "Preset toàn cục" if style.user_id is None else "Tùy chỉnh của người dùng"
                logger.info(f"✅ Viết lại cục bộ - dùng phong cách viết: {style.name} ({style_type})")
            else:
                logger.warning(f"⚠️ Phong cách {style_id} không thuộc người dùng hiện tại, bỏ qua")
    
    async def event_generator():
        """Generator sự kiện tạo streaming"""
        from app.utils.sse_response import WizardProgressTracker
        tracker = WizardProgressTracker("Viết lại cục bộ")
        
        try:
            yield await tracker.start()
            yield await tracker.loading("Đang chuẩn bị ngữ cảnh viết lại...", 0.3)
            
            # Cắt ngữ cảnh
            context_chars = partial_request.context_chars
            start_pos = partial_request.start_position
            end_pos = partial_request.end_position
            
            # Văn trước: từ start_pos cắt ngược về trước context_chars ký tự
            context_before_start = max(0, start_pos - context_chars)
            context_before = chapter.content[context_before_start:start_pos]
            
            # Văn sau: từ end_pos cắt xuôi về sau context_chars ký tự
            context_after_end = min(content_length, end_pos + context_chars)
            context_after = chapter.content[end_pos:context_after_end]
            
            # Văn gốc
            original_text = partial_request.selected_text
            original_word_count = len(original_text)
            
            logger.info(f"📝 Viết lại cục bộ - văn gốc: {original_word_count} từ, văn trước: {len(context_before)} từ, văn sau: {len(context_after)} từ")
            
            yield await tracker.loading("Đang xây dựng prompt...", 0.5)
            
            # Xây dựng yêu cầu số từ
            length_requirement = ""
            if partial_request.length_mode == "similar":
                min_words = int(original_word_count * 0.8)
                max_words = int(original_word_count * 1.2)
                length_requirement = f"Giữ số từ gần với văn gốc (khoảng {original_word_count} từ, cho phép dao động {min_words}-{max_words} từ)"
            elif partial_request.length_mode == "expand":
                min_words = int(original_word_count * 1.2)
                max_words = int(original_word_count * 2.0)
                length_requirement = f"Mở rộng nội dung vừa phải (mục tiêu {min_words}-{max_words} từ)"
            elif partial_request.length_mode == "condense":
                min_words = int(original_word_count * 0.5)
                max_words = int(original_word_count * 0.8)
                length_requirement = f"Cô đọng nội dung (mục tiêu {min_words}-{max_words} từ)"
            elif partial_request.length_mode == "custom" and partial_request.target_word_count:
                length_requirement = f"Số từ mục tiêu: khoảng {partial_request.target_word_count} từ (cho phép dao động ±20%)"
            else:
                length_requirement = f"Giữ số từ gần với văn gốc (khoảng {original_word_count} từ)"
            
            # Lấy template prompt
            template = await PromptService.get_template("PARTIAL_REGENERATE", user_id, db)
            if not template:
                template = PromptService.PARTIAL_REGENERATE
            
            # Xây dựng prompt
            prompt = PromptService.format_prompt(
                template,
                context_before=context_before if context_before else "(Đây là đầu chương)",
                original_word_count=original_word_count,
                selected_text=original_text,
                context_after=context_after if context_after else "(Đây là cuối chương)",
                user_instructions=partial_request.user_instructions,
                length_requirement=length_requirement,
                style_content=style_content if style_content else "Giữ phong cách kể chuyện nhất quán với văn gốc"
            )
            
            yield await tracker.preparing("Bắt đầu tạo...")
            
            # Tính max_tokens
            if partial_request.length_mode == "expand":
                target_words = int(original_word_count * 2.0)
            elif partial_request.length_mode == "custom" and partial_request.target_word_count:
                target_words = partial_request.target_word_count
            else:
                target_words = int(original_word_count * 1.5)
            
            calculated_max_tokens = max(500, min(int(target_words * 3), 8000))
            
            # Tạo streaming
            full_content = ""
            chunk_count = 0
            
            yield await tracker.generating(
                current_chars=0,
                estimated_total=target_words
            )
            
            async for chunk in user_ai_service.generate_text_stream(
                prompt=prompt,
                max_tokens=calculated_max_tokens
            ):
                full_content += chunk
                chunk_count += 1
                
                # Gửi khối nội dung
                yield await tracker.generating_chunk(chunk)
                
                # Mỗi 5 chunk gửi một cập nhật tiến độ
                if chunk_count % 5 == 0:
                    yield await tracker.generating(
                        current_chars=len(full_content),
                        estimated_total=target_words,
                        message=f'Đang viết lại... đã tạo {len(full_content)} từ'
                    )
                
                await asyncio.sleep(0)
            
            # Làm sạch output (loại bỏ tiền tố/hậu tố có thể có)
            full_content = full_content.strip()
            
            # Loại bỏ tiền tố output AI thường gặp
            prefixes_to_remove = [
                "重写后：", "重写后:", "改写后：", "改写后:",
                "以下是重写后的内容：", "以下是重写后的内容:",
                "重写内容：", "重写内容:"
            ]
            for prefix in prefixes_to_remove:
                if full_content.startswith(prefix):
                    full_content = full_content[len(prefix):].strip()
                    break
            
            # Loại bỏ dấu ngoặc kép ở đầu cuối có thể có
            if (full_content.startswith('"') and full_content.endswith('"')) or \
               (full_content.startswith("'") and full_content.endswith("'")):
                full_content = full_content[1:-1]
            if (full_content.startswith('「') and full_content.endswith('」')) or \
               (full_content.startswith('『') and full_content.endswith('』')):
                full_content = full_content[1:-1]
            
            new_word_count = len(full_content)
            
            logger.info(f"✅ Viết lại cục bộ xong: văn gốc {original_word_count} từ -> văn mới {new_word_count} từ")
            
            # Hoàn thành
            yield await tracker.complete("Viết lại xong!")
            
            # Gửi dữ liệu kết quả
            yield await tracker.result({
                'new_text': full_content,
                'word_count': new_word_count,
                'original_word_count': original_word_count,
                'start_position': partial_request.start_position,
                'end_position': partial_request.end_position
            })
            
            yield await tracker.done()
            
        except Exception as e:
            logger.error(f"❌ Viết lại cục bộ thất bại: {str(e)}", exc_info=True)
            yield await tracker.error(str(e))
    
    return create_sse_response(event_generator())


@router.post("/{chapter_id}/apply-partial-regenerate", summary="Áp dụng kết quả viết lại cục bộ")
async def apply_partial_regenerate(
    chapter_id: str,
    request: Request,
    apply_request: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Áp dụng kết quả viết lại cục bộ vào nội dung chương
    
    Body request:
    - new_text: nội dung mới sau khi viết lại
    - start_position: vị trí bắt đầu của văn gốc
    - end_position: vị trí kết thúc của văn gốc
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    # Xác minh chương tồn tại
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chương không tồn tại")
    
    # Xác minh quyền người dùng
    await verify_project_access(chapter.project_id, user_id, db)
    
    # Lấy tham số
    new_text = apply_request.get('new_text', '')
    start_position = apply_request.get('start_position', 0)
    end_position = apply_request.get('end_position', 0)
    
    if not new_text:
        raise HTTPException(status_code=400, detail="Nội dung mới không được rỗng")
    
    # Xác minh tính hợp lệ của vị trí
    content_length = len(chapter.content)
    if start_position < 0 or end_position > content_length or start_position >= end_position:
        raise HTTPException(status_code=400, detail="Tham số vị trí không hợp lệ")
    
    # Xây dựng nội dung mới
    old_word_count = chapter.word_count or 0
    new_content = chapter.content[:start_position] + new_text + chapter.content[end_position:]
    new_word_count = len(new_content)
    
    # Cập nhật chương
    chapter.content = new_content
    chapter.word_count = new_word_count
    
    # Cập nhật số từ của dự án
    project_result = await db.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    if project:
        project.current_words = project.current_words - old_word_count + new_word_count
    
    await db.commit()
    await db.refresh(chapter)
    
    logger.info(f"✅ Đã áp dụng viết lại cục bộ: chương {chapter_id}, {old_word_count} từ -> {new_word_count} từ")
    
    return {
        "success": True,
        "chapter_id": chapter_id,
        "word_count": new_word_count,
        "old_word_count": old_word_count,
        "message": "Đã áp dụng viết lại cục bộ"
    }

