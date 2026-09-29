"""API quản lý dàn ý"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, AsyncGenerator, Dict, Any
import json

from app.database import get_db
from app.api.common import verify_project_access
from app.models.outline import Outline
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.models.generation_history import GenerationHistory
from app.schemas.outline import (
    OutlineCreate,
    OutlineUpdate,
    OutlineResponse,
    OutlineListResponse,
    OutlineGenerateRequest,
    OutlineExpansionRequest,
    OutlineExpansionResponse,
    BatchOutlineExpansionRequest,
    BatchOutlineExpansionResponse,
    CreateChaptersFromPlansRequest,
    CreateChaptersFromPlansResponse
)
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.services.memory_service import memory_service
from app.services.plot_expansion_service import PlotExpansionService
from app.services.foreshadow_service import foreshadow_service
from app.services.memory_service import memory_service
from app.logger import get_logger
from app.api.settings import get_user_ai_service
from app.utils.sse_response import SSEResponse, create_sse_response, WizardProgressTracker

router = APIRouter(prefix="/outlines", tags=["Quản lý dàn ý"])
logger = get_logger(__name__)


def _build_chapters_brief(outlines: List[Outline], max_recent: int = 20) -> str:
    """Xây dựng chuỗi tổng quan chương"""
    target = outlines[-max_recent:] if len(outlines) > max_recent else outlines
    return "\n".join([f"Chương {o.order_index}: {o.title}" for o in target])


def _build_characters_info(characters: List[Character]) -> str:
    """Xây dựng chuỗi thông tin nhân vật"""
    return "\n".join([
        f"- {char.name} ({'Tổ chức' if char.is_organization else 'Nhân vật'}, {char.role_type}): "
        f"{char.personality[:100] if char.personality else 'Chưa có mô tả'}"
        for char in characters
    ])


@router.post("", response_model=OutlineResponse, summary="Tạo dàn ý")
async def create_outline(
    outline: OutlineCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tạo dàn ý chương mới (chế độ one-to-one sẽ tự động tạo chương tương ứng)"""
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(outline.project_id, user_id, db)
    
    # Tạo dàn ý
    db_outline = Outline(**outline.model_dump())
    db.add(db_outline)
    await db.flush()  # Đảm bảo dàn ý có ID
    
    # Nếu là chế độ one-to-one, tự động tạo chương tương ứng
    if project.outline_mode == 'one-to-one':
        chapter = Chapter(
            project_id=outline.project_id,
            title=db_outline.title,
            summary=db_outline.content,
            chapter_number=db_outline.order_index,
            sub_index=1,
            outline_id=db_outline.id,
            status='pending',
            content=""
        )
        db.add(chapter)
        logger.info(f"Chế độ một-một: đã tự động tạo chương tương ứng cho dàn ý tạo thủ công {db_outline.title} (số thứ tự {db_outline.order_index})")
    
    await db.commit()
    await db.refresh(db_outline)
    return db_outline


@router.get("", response_model=OutlineListResponse, summary="Lấy danh sách dàn ý")
async def get_outlines(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy mọi dàn ý của dự án chỉ định. Trường title/content là nguồn duy nhất của dữ liệu hiển thị."""
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # Lấy tổng số
    count_result = await db.execute(
        select(func.count(Outline.id)).where(Outline.project_id == project_id)
    )
    total = count_result.scalar_one()
    
    # Lấy danh sách dàn ý
    result = await db.execute(
        select(Outline)
        .where(Outline.project_id == project_id)
        .order_by(Outline.order_index)
    )
    outlines = result.scalars().all()

    # Truy vấn hàng loạt dàn ý đã triển khai chương chưa (tránh N+1 request từ frontend)
    outline_ids = [outline.id for outline in outlines]
    outline_has_chapters_map: Dict[str, bool] = {}
    if outline_ids:
        chapters_count_result = await db.execute(
            select(Chapter.outline_id, func.count(Chapter.id))
            .where(Chapter.outline_id.in_(outline_ids))
            .group_by(Chapter.outline_id)
        )
        outline_has_chapters_map = {
            str(outline_id): count > 0
            for outline_id, count in chapters_count_result.all()
            if outline_id
        }

    for outline in outlines:
        # Gắn động trạng thái đã có chương triển khai để frontend dùng trực tiếp
        setattr(outline, "has_chapters", outline_has_chapters_map.get(outline.id, False))

    return OutlineListResponse(total=total, items=outlines)


@router.get("/project/{project_id}", response_model=OutlineListResponse, summary="Lấy mọi dàn ý của dự án")
async def get_project_outlines(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy mọi dàn ý của dự án chỉ định (phiên bản tham số đường dẫn, tương thích API cũ)"""
    return await get_outlines(project_id, request, db)


@router.get("/{outline_id}", response_model=OutlineResponse, summary="Lấy chi tiết dàn ý")
async def get_outline(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết dàn ý theo ID"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    return outline


@router.put("/{outline_id}", response_model=OutlineResponse, summary="Cập nhật dàn ý")
async def update_outline(
    outline_id: str,
    outline_update: OutlineUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thông tin dàn ý và đồng bộ trường structure cùng chương liên quan"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(outline.project_id, user_id, db)
    
    # Cập nhật trường
    update_data = outline_update.model_dump(exclude_unset=True)
    if "content" in update_data and update_data["content"] is None:
        update_data["content"] = ""
    
    # 🔧 Xử lý đặc biệt: nếu truyền trực tiếp trường structure thì ưu tiên dùng nó
    if 'structure' in update_data:
        # Dùng trực tiếp structure do frontend truyền (frontend đã xử lý xong JSON đầy đủ)
        outline.structure = update_data['structure']
        logger.info(f"Cập nhật trực tiếp trường structure của dàn ý {outline_id}")
        # Xóa structure khỏi update_data để tránh xử lý trùng lặp sau này
        structure_updated = True
        del update_data['structure']
    else:
        structure_updated = False
    
    # Cập nhật các trường còn lại
    for field, value in update_data.items():
        setattr(outline, field, value)
    
    # Nếu không cập nhật trực tiếp structure nhưng sửa content hoặc title thì đồng bộ trường structure
    if not structure_updated and ('content' in update_data or 'title' in update_data):
        try:
            # Thử phân tích structure hiện có
            if outline.structure:
                structure_data = json.loads(outline.structure)
            else:
                structure_data = {}
            
            # Cập nhật trường tương ứng trong structure
            if 'title' in update_data:
                structure_data['title'] = outline.title
            if 'content' in update_data:
                structure_data['summary'] = outline.content
                structure_data['content'] = outline.content
            
            # Lưu structure đã cập nhật
            outline.structure = json.dumps(structure_data, ensure_ascii=False)
            logger.info(f"Đồng bộ trường structure của dàn ý {outline_id}")
        except json.JSONDecodeError:
            logger.warning(f"Trường structure của dàn ý {outline_id} sai định dạng, bỏ qua cập nhật")
    
    # 🔧 Chế độ truyền thống (one-to-one): đồng bộ tiêu đề chương liên quan
    if 'title' in update_data and project.outline_mode == 'one-to-one':
        try:
            # Tìm chương tương ứng (khớp chapter_number với order_index)
            chapter_result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == outline.project_id,
                    Chapter.chapter_number == outline.order_index
                )
            )
            chapter = chapter_result.scalar_one_or_none()
            
            if chapter:
                # Đồng bộ tiêu đề chương
                chapter.title = outline.title

                logger.info(f"Chế độ một-một: đồng bộ tiêu đề chương {chapter.id} thành '{outline.title}'")
            else:
                logger.debug(f"Chế độ một-một: không tìm thấy chương tương ứng (chapter_number={outline.order_index})")
        except Exception as e:
            logger.error(f"Đồng bộ tiêu đề chương thất bại: {str(e)}")
            # Không chặn luồng cập nhật dàn ý, chỉ ghi log lỗi
    
    await db.commit()
    await db.refresh(outline)
    return outline


@router.delete("/{outline_id}", summary="Xóa dàn ý")
async def delete_outline(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa dàn ý, đồng thời xóa mọi chương tương ứng và dữ liệu manh mối ẩn liên quan"""
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(outline.project_id, user_id, db)
    
    project_id = outline.project_id
    deleted_order = outline.order_index
    
    # Lấy các chương cần xóa và tính tổng số từ
    deleted_word_count = 0
    deleted_foreshadow_count = 0
    if project.outline_mode == 'one-to-one':
        # Chế độ one-to-one: lấy chương tương ứng qua chapter_number
        chapters_result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == outline.order_index
            )
        )
        chapters_to_delete = chapters_result.scalars().all()
        deleted_word_count = sum(ch.word_count or 0 for ch in chapters_to_delete)
        
        # 🔮 Dọn dữ liệu manh mối ẩn và ký ức vector liên quan đến chương
        for chapter in chapters_to_delete:
            try:
                # Dọn dữ liệu ký ức trong cơ sở dữ liệu vector
                await memory_service.delete_chapter_memories(
                    user_id=user_id,
                    project_id=project_id,
                    chapter_id=chapter.id
                )
                logger.info(f"✅ Đã dọn dữ liệu ký ức vector của chương {chapter.id[:8]}")
            except Exception as e:
                logger.warning(f"⚠️ Dọn ký ức vector của chương {chapter.id[:8]} thất bại: {str(e)}")
            
            try:
                # Dọn dữ liệu manh mối ẩn (manh mối ẩn từ nguồn phân tích)
                foreshadow_result = await foreshadow_service.delete_chapter_foreshadows(
                    db=db,
                    project_id=project_id,
                    chapter_id=chapter.id,
                    only_analysis_source=True
                )
                deleted_foreshadow_count += foreshadow_result.get('deleted_count', 0)
                if foreshadow_result.get('deleted_count', 0) > 0:
                    logger.info(f"🔮 Đã dọn {foreshadow_result['deleted_count']} dữ liệu manh mối ẩn của chương {chapter.id[:8]}")
            except Exception as e:
                logger.warning(f"⚠️ Dọn dữ liệu manh mối ẩn của chương {chapter.id[:8]} thất bại: {str(e)}")
        
        # Xóa chương
        delete_result = await db.execute(
            delete(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == outline.order_index
            )
        )
        deleted_chapters_count = delete_result.rowcount
        logger.info(f"Chế độ một-một: xóa dàn ý {outline_id} (số thứ tự {outline.order_index}), đồng thời xóa chương {outline.order_index} ({deleted_chapters_count} chương, {deleted_word_count} từ, {deleted_foreshadow_count} manh mối ẩn)")
    else:
        # Chế độ one-to-many: lấy chương liên quan qua outline_id
        chapters_result = await db.execute(
            select(Chapter).where(Chapter.outline_id == outline_id)
        )
        chapters_to_delete = chapters_result.scalars().all()
        deleted_word_count = sum(ch.word_count or 0 for ch in chapters_to_delete)
        
        # 🔮 Dọn dữ liệu manh mối ẩn và ký ức vector liên quan đến chương
        for chapter in chapters_to_delete:
            try:
                # Dọn dữ liệu ký ức trong cơ sở dữ liệu vector
                await memory_service.delete_chapter_memories(
                    user_id=user_id,
                    project_id=project_id,
                    chapter_id=chapter.id
                )
                logger.info(f"✅ Đã dọn dữ liệu ký ức vector của chương {chapter.id[:8]}")
            except Exception as e:
                logger.warning(f"⚠️ Dọn ký ức vector của chương {chapter.id[:8]} thất bại: {str(e)}")
            
            try:
                # Dọn dữ liệu manh mối ẩn (manh mối ẩn từ nguồn phân tích)
                foreshadow_result = await foreshadow_service.delete_chapter_foreshadows(
                    db=db,
                    project_id=project_id,
                    chapter_id=chapter.id,
                    only_analysis_source=True
                )
                deleted_foreshadow_count += foreshadow_result.get('deleted_count', 0)
                if foreshadow_result.get('deleted_count', 0) > 0:
                    logger.info(f"🔮 Đã dọn {foreshadow_result['deleted_count']} dữ liệu manh mối ẩn của chương {chapter.id[:8]}")
            except Exception as e:
                logger.warning(f"⚠️ Dọn dữ liệu manh mối ẩn của chương {chapter.id[:8]} thất bại: {str(e)}")
        
        # Xóa chương
        delete_result = await db.execute(
            delete(Chapter).where(Chapter.outline_id == outline_id)
        )
        deleted_chapters_count = delete_result.rowcount
        logger.info(f"Chế độ một-nhiều: xóa dàn ý {outline_id}, đồng thời xóa {deleted_chapters_count} chương liên quan ({deleted_word_count} từ, {deleted_foreshadow_count} manh mối ẩn)")
    
    # Cập nhật số từ của dự án
    if deleted_word_count > 0:
        project.current_words = max(0, project.current_words - deleted_word_count)
        logger.info(f"Cập nhật số từ dự án: giảm {deleted_word_count} từ")
    
    # Xóa dàn ý
    await db.delete(outline)
    
    # Sắp xếp lại các dàn ý phía sau (số thứ tự -1)
    result = await db.execute(
        select(Outline).where(
            Outline.project_id == project_id,
            Outline.order_index > deleted_order
        )
    )
    subsequent_outlines = result.scalars().all()
    
    for o in subsequent_outlines:
        o.order_index -= 1
    
    # Nếu là chế độ one-to-one, còn cần sắp xếp lại chapter_number của các chương phía sau
    if project.outline_mode == 'one-to-one':
        chapters_result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number > deleted_order
            ).order_by(Chapter.chapter_number)
        )
        subsequent_chapters = chapters_result.scalars().all()
        
        for ch in subsequent_chapters:
            ch.chapter_number -= 1
        
        logger.info(f"Chế độ một-một: đã sắp xếp lại {len(subsequent_chapters)} chương phía sau")
    
    await db.commit()
    
    return {
        "message": "Xóa dàn ý thành công",
        "deleted_chapters": deleted_chapters_count,
        "deleted_foreshadows": deleted_foreshadow_count
    }




async def _build_outline_continue_context(
    project: Project,
    latest_outlines: List[Outline],
    characters: List[Character],
    chapter_count: int,
    plot_stage: str,
    story_direction: str,
    requirements: str,
    db: AsyncSession
) -> dict:
    """
    Xây dựng ngữ cảnh viết tiếp dàn ý (bản rút gọn)
    
    Gồm:
    1. Thông tin cơ bản dự án: title, theme, genre, world_time_period, world_location,
       world_atmosphere, world_rules, narrative_perspective
    2. structure đầy đủ của 10 chương gần nhất (phân tích JSON thành văn bản)
    3. Toàn bộ thông tin của mọi nhân vật
    4. Đầu vào của người dùng: chapter_count, plot_stage, story_direction, requirements
    
    Args:
        project: đối tượng dự án
        latest_outlines: danh sách mọi dàn ý đã có
        characters: danh sách mọi nhân vật
        chapter_count: số chương cần tạo
        plot_stage: giai đoạn cốt truyện
        story_direction: hướng phát triển câu chuyện
        requirements: yêu cầu khác
        
    Returns:
        dict chứa thông tin ngữ cảnh
    """
    context = {
        'project_info': '',
        'recent_outlines': '',
        'characters_info': '',
        'user_input': '',
        'stats': {
            'total_outlines': len(latest_outlines),
            'recent_outlines_count': 0,
            'characters_count': len(characters)
        }
    }
    
    try:
        # 1. Thông tin cơ bản dự án
        project_info_parts = [
            f"【Thông tin cơ bản dự án】",
            f"Tiêu đề: {project.title}",
            f"Chủ đề: {project.theme or 'Chưa đặt'}",
            f"Thể loại: {project.genre or 'Chưa đặt'}",
            f"Bối cảnh thời đại: {project.world_time_period or 'Chưa đặt'}",
            f"Địa điểm: {project.world_location or 'Chưa đặt'}",
            f"Tông không khí: {project.world_atmosphere or 'Chưa đặt'}",
            f"Quy tắc thế giới: {project.world_rules or 'Chưa đặt'}",
            f"Góc nhìn kể chuyện: {project.narrative_perspective or 'Ngôi thứ ba'}"
        ]
        context['project_info'] = "\n".join(project_info_parts)
        
        # 2. structure đầy đủ của 10 chương gần nhất (phân tích JSON thành văn bản)
        recent_count = min(10, len(latest_outlines))
        if recent_count > 0:
            recent_outlines = latest_outlines[-recent_count:]
            context['stats']['recent_outlines_count'] = recent_count
            
            outline_texts = []
            outline_texts.append(f"【Chi tiết {recent_count} dàn ý gần nhất】")
            
            for outline in recent_outlines:
                outline_text = f"\nChương {outline.order_index}: {outline.title}"
                
                # Thử phân tích trường structure
                if outline.structure:
                    try:
                        structure_data = json.loads(outline.structure)
                        
                        # Trích các trường (dùng tên trường lưu trữ thực tế)
                        if structure_data.get('summary'):

                            outline_text += f"\n Tóm tắt: {structure_data['summary']}"
                        
                        # key_points tương ứng Sự kiện chính
                        if structure_data.get('key_points'):
                            events = structure_data['key_points']
                            if isinstance(events, list):
                                outline_text += f"\n Sự kiện chính: {', '.join(events)}"
                            else:
                                outline_text += f"\n Sự kiện chính: {events}"
                        
                        # characters tương ứng Nhân vật/ tổ chức trọng điểm (tương thích định dạng mới và cũ)
                        if structure_data.get('characters'):
                            chars = structure_data['characters']
                            if isinstance(chars, list):
                                # Định dạng mới: [{"name": "xxx", "type": "character"/"organization"}]
                                # Định dạng cũ: ["Tên nhân vật 1", "Tên nhân vật 2"]
                                char_names = []
                                org_names = []
                                for c in chars:
                                    if isinstance(c, dict):
                                        name = c.get('name', '')
                                        if c.get('type') == 'organization':
                                            org_names.append(name)
                                        else:
                                            char_names.append(name)
                                    elif isinstance(c, str):
                                        char_names.append(c)
                                if char_names:
                                    outline_text += f"\n Nhân vật trọng điểm: {', '.join(char_names)}"
                                if org_names:
                                    outline_text += f"\n Tổ chức liên quan: {', '.join(org_names)}"
                            else:
                                outline_text += f"\n Nhân vật trọng điểm: {chars}"
                        
                        # emotion tương ứng Tông cảm xúc
                        if structure_data.get('emotion'):
                            outline_text += f"\n Tông cảm xúc: {structure_data['emotion']}"
                        
                        # goal tương ứng Mục tiêu kể chuyện
                        if structure_data.get('goal'):
                            outline_text += f"\n Mục tiêu kể chuyện: {structure_data['goal']}"
                        
                        # scenes thông tin bối cảnh (hiển thị tùy chọn)
                        if structure_data.get('scenes'):
                            scenes = structure_data['scenes']
                            if isinstance(scenes, list) and scenes:
                                outline_text += f"\n Bối cảnh: {', '.join(scenes)}"
                            
                    except json.JSONDecodeError:
                        # Nếu phân tích thất bại, dùng trường content
                        outline_text += f"\n Nội dung: {outline.content}"
                else:
                    # Không có structure, dùng content
                    outline_text += f"\n Nội dung: {outline.content}"
                
                outline_texts.append(outline_text)
            
            context['recent_outlines'] = "\n".join(outline_texts)
            logger.info(f" ✅ Dàn ý gần nhất: {recent_count} chương")
        
        # 3. Toàn bộ thông tin của mọi nhân vật (kèm thông tin nghề nghiệp)
        if characters:
            from app.models.career import Career, CharacterCareer
            
            char_texts = []
            char_texts.append("【Thông tin nhân vật】")
            
            for char in characters:
                char_text = f"\n{char.name}（{'Tổ chức' if char.is_organization else 'Nhân vật'}，{char.role_type}）"
                
                if char.personality:
                    char_text += f"\n Tính cách: {char.personality}"
                
                if char.background:
                    char_text += f"\n Câu chuyện nền: {char.background}"
                
                if char.appearance:
                    char_text += f"\n Mô tả ngoại hình: {char.appearance}"
                
                if char.traits:
                    char_text += f"\n Nhãn đặc trưng: {char.traits}"
                
                # Truy vấn quan hệ từ bảng character_relationships
                from sqlalchemy import or_
                rels_result = await db.execute(
                    select(CharacterRelationship).where(
                        CharacterRelationship.project_id == project.id,
                        or_(
                            CharacterRelationship.character_from_id == char.id,
                            CharacterRelationship.character_to_id == char.id
                        )
                    )
                )
                rels = rels_result.scalars().all()
                if rels:
                    # Thu thập tên các nhân vật liên quan
                    related_ids = set()
                    for r in rels:
                        related_ids.add(r.character_from_id)
                        related_ids.add(r.character_to_id)
                    related_ids.discard(char.id)
                    if related_ids:
                        names_result = await db.execute(
                            select(Character.id, Character.name).where(Character.id.in_(related_ids))
                        )
                        name_map = {row.id: row.name for row in names_result}
                        rel_parts = []
                        for r in rels:
                            if r.character_from_id == char.id:
                                target_name = name_map.get(r.character_to_id, "Không xác định")
                            else:
                                target_name = name_map.get(r.character_from_id, "Không xác định")
                            rel_name = r.relationship_name or "liên quan"
                            rel_parts.append(f"Với {target_name}: {rel_name}")
                        char_text += f"\n Mạng lưới quan hệ: {'；'.join(rel_parts)}"
                
                # Trường riêng của tổ chức
                if char.is_organization:
                    if char.organization_type:
                        char_text += f"\n Loại tổ chức: {char.organization_type}"
                    if char.organization_purpose:
                        char_text += f"\n Tôn chỉ tổ chức: {char.organization_purpose}"
                    # Truy vấn động thành viên tổ chức từ bảng OrganizationMember
                    org_result = await db.execute(
                        select(Organization).where(Organization.character_id == char.id)
                    )
                    org = org_result.scalar_one_or_none()
                    if org:
                        members_result = await db.execute(
                            select(OrganizationMember, Character.name).join(
                                Character, OrganizationMember.character_id == Character.id
                            ).where(OrganizationMember.organization_id == org.id)
                        )
                        members = members_result.all()
                        if members:
                            member_parts = [f"{name}（{m.position}）" for m, name in members]
                            char_text += f"\n Thành viên tổ chức: {'、'.join(member_parts)}"
                
                # Truy vấn thông tin nghề nghiệp của nhân vật
                if not char.is_organization:
                    try:
                        career_result = await db.execute(
                            select(Career, CharacterCareer)
                            .join(CharacterCareer, Career.id == CharacterCareer.career_id)
                            .where(CharacterCareer.character_id == char.id)
                        )
                        career_data = career_result.first()
                        
                        if career_data:
                            career, char_career = career_data
                            char_text += f"\n Nghề nghiệp: {career.name}"
                            if char_career.current_stage:
                                char_text += f"（cấp {char_career.current_stage}）"
                            if char_career.career_type:
                                char_text += f"\n Loại nghề nghiệp: {char_career.career_type}"
                    except Exception as e:
                        logger.warning(f"Truy vấn thông tin nghề nghiệp của nhân vật {char.name} thất bại: {str(e)}")
                
                char_texts.append(char_text)
            
            context['characters_info'] = "\n".join(char_texts)
            logger.info(f" ✅ Thông tin nhân vật: {len(characters)} nhân vật")
        else:
            context['characters_info'] = "【Thông tin nhân vật】\\nChưa có thông tin nhân vật"
        
        # 4. Đầu vào của người dùng
        user_input_parts = [
            "【Đầu vào người dùng】",
            f"Số chương cần tạo: {chapter_count} chương",
            f"Giai đoạn cốt truyện: {plot_stage}",
            f"Hướng phát triển câu chuyện: {story_direction}",
        ]
        if requirements:
            user_input_parts.append(f"Yêu cầu khác: {requirements}")
        
        context['user_input'] = "\n".join(user_input_parts)
        
        # Tính tổng độ dài
        total_length = sum([
            len(context['project_info']),
            len(context['recent_outlines']),
            len(context['characters_info']),
            len(context['user_input'])
        ])
        context['stats']['total_length'] = total_length
        logger.info(f"📊 Tổng độ dài ngữ cảnh viết tiếp dàn ý: {total_length} ký tự")
        
    except Exception as e:
        logger.error(f"❌ Xây dựng ngữ cảnh viết tiếp dàn ý thất bại: {str(e)}", exc_info=True)
    
    return context


async def _check_and_create_missing_characters_from_outlines(
    outline_data: list,
    project_id: str,
    db: AsyncSession,
    user_ai_service: AIService,
    user_id: str = None,
    enable_mcp: bool = True,
    tracker = None
) -> dict:
    """
    Sau khi tạo/viết tiếp dàn ý, kiểm tra characters trong structure có nhân vật tương ứng không,
    nhân vật thiếu sẽ tự động được tạo thông tin dựa trên tóm tắt dàn ý.
    
    Args:
        outline_data: danh sách dữ liệu dàn ý (dữ liệu gốc sau khi phân tích JSON, gồm các trường characters, summary, v.v.)
        project_id: ID dự án
        db: session cơ sở dữ liệu
        user_ai_service: instance dịch vụ AI
        user_id: ID người dùng
        enable_mcp: có bật MCP không
        tracker: tùy chọn, WizardProgressTracker để gửi tiến trình
        
    Returns:
        {"created_count": int, "created_characters": list}
    """
    try:
        from app.services.auto_character_service import get_auto_character_service
        
        auto_char_service = get_auto_character_service(user_ai_service)
        
        # Định nghĩa callback tiến trình
        async def progress_cb(message: str):
            if tracker:
                # Lưu ý: ở đây không thể yield trực tiếp, cần xử lý bằng cách khác
                logger.info(f" 📌 {message}")
        
        result = await auto_char_service.check_and_create_missing_characters(
            project_id=project_id,
            outline_data_list=outline_data,
            db=db,
            user_id=user_id,
            enable_mcp=enable_mcp,
            progress_callback=progress_cb
        )
        
        if result["created_count"] > 0:
            logger.info(
                f"🎭 【Kiểm tra nhân vật hoàn tất】Đã tự động tạo {result['created_count']} nhân vật còn thiếu: "
                f"{', '.join(c.name for c in result['created_characters'])}"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"⚠️ 【Kiểm tra nhân vật】thất bại (không ảnh hưởng luồng chính): {e}", exc_info=True)
        return {"created_count": 0, "created_characters": []}


async def _check_and_create_missing_organizations_from_outlines(
    outline_data: list,
    project_id: str,
    db: AsyncSession,
    user_ai_service: AIService,
    user_id: str = None,
    enable_mcp: bool = True,
    tracker = None
) -> dict:
    """
    Sau khi tạo/viết tiếp dàn ý, kiểm tra characters (type=organization) trong structure có tổ chức tương ứng không,
    tổ chức thiếu sẽ tự động được tạo thông tin dựa trên tóm tắt dàn ý.
    
    Args:
        outline_data: danh sách dữ liệu dàn ý (dữ liệu gốc sau khi phân tích JSON, gồm các trường characters, summary, v.v.)
        project_id: ID dự án
        db: session cơ sở dữ liệu
        user_ai_service: instance dịch vụ AI
        user_id: ID người dùng
        enable_mcp: có bật MCP không
        tracker: tùy chọn, WizardProgressTracker để gửi tiến trình
        
    Returns:
        {"created_count": int, "created_organizations": list}
    """
    try:
        from app.services.auto_organization_service import get_auto_organization_service
        
        auto_org_service = get_auto_organization_service(user_ai_service)
        
        # Định nghĩa callback tiến trình
        async def progress_cb(message: str):
            if tracker:
                logger.info(f" 📌 {message}")
        
        result = await auto_org_service.check_and_create_missing_organizations(
            project_id=project_id,
            outline_data_list=outline_data,
            db=db,
            user_id=user_id,
            enable_mcp=enable_mcp,
            progress_callback=progress_cb
        )
        
        if result["created_count"] > 0:
            logger.info(
                f"🏛️ 【Kiểm tra tổ chức hoàn tất】Đã tự động tạo {result['created_count']} tổ chức còn thiếu: "
                f"{', '.join(c.name for c in result['created_organizations'])}"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"⚠️ 【Kiểm tra tổ chức】thất bại (không ảnh hưởng luồng chính): {e}", exc_info=True)
        return {"created_count": 0, "created_organizations": []}


class JSONParseError(Exception):
    """Ngoại lệ phân tích JSON thất bại, dùng để kích hoạt thử lại"""
    def __init__(self, message: str, original_content: str = ""):
        super().__init__(message)
        self.original_content = original_content


def _normalize_character_entries(raw_characters: Any) -> list:
    """Chuẩn hóa trường characters của dàn ý, tương thích định dạng chuỗi cũ."""
    if not isinstance(raw_characters, list):
        return []

    normalized = []
    seen = set()
    # Từ khóa heuristic nhận diện tên tổ chức (logic, giữ nguyên)
    org_keywords = ("宗", "门", "派", "阁", "会", "帮", "盟", "国", "军", "司", "院", "族", "府", "殿", "教", "堂", "队", "集团", "组织", "势力")

    for item in raw_characters:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            item_type = str(item.get("type") or "character").strip().lower()
        else:
            name = str(item or "").strip()
            item_type = "organization" if any(keyword in name for keyword in org_keywords) else "character"

        if not name:
            continue
        if item_type not in {"character", "organization"}:
            item_type = "character"

        key = (name, item_type)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"name": name, "type": item_type})

    return normalized


def _normalize_outline_data(outline_data: list, expected_count: int, start_index: int) -> list:
    """Kiểm tra và chuẩn hóa dữ liệu dàn ý do AI trả về."""
    if not isinstance(outline_data, list):
        raise JSONParseError("Dữ liệu dàn ý phải là mảng", json.dumps(outline_data, ensure_ascii=False, default=str))

    if expected_count is not None and len(outline_data)!= expected_count:
        raise JSONParseError(f"Số lượng dàn ý không khớp: kỳ vọng {expected_count} chương, thực tế {len(outline_data)} chương", json.dumps(outline_data, ensure_ascii=False, default=str))

    normalized = []
    for idx, chapter_data in enumerate(outline_data):
        if not isinstance(chapter_data, dict):
            raise JSONParseError(f"Mục thứ {idx + 1} không phải object hợp lệ", json.dumps(outline_data, ensure_ascii=False, default=str))

        chapter_number = start_index + idx
        title = str(chapter_data.get("title") or f"Chương {chapter_number}").strip()
        summary = str(chapter_data.get("summary") or chapter_data.get("content") or "").strip()
        if not summary:
            raise JSONParseError(f"Chương {chapter_number} thiếu summary/content", json.dumps(chapter_data, ensure_ascii=False, default=str))

        scenes = chapter_data.get("scenes")
        if not isinstance(scenes, list):
            scenes = []
        key_points = chapter_data.get("key_points")
        if not isinstance(key_points, list):
            key_points = []

        normalized_chapter = dict(chapter_data)
        normalized_chapter["chapter_number"] = chapter_number
        normalized_chapter["title"] = title
        normalized_chapter["summary"] = summary
        normalized_chapter["scenes"] = [str(scene).strip() for scene in scenes if str(scene).strip()]
        normalized_chapter["characters"] = _normalize_character_entries(chapter_data.get("characters", []))
        normalized_chapter["key_points"] = [str(point).strip() for point in key_points if str(point).strip()]
        normalized_chapter["emotion"] = str(chapter_data.get("emotion") or chapter_data.get("emotional_tone") or "Chưa đặt").strip()
        normalized_chapter["goal"] = str(chapter_data.get("goal") or chapter_data.get("narrative_goal") or "Chưa đặt").strip()
        normalized.append(normalized_chapter)

    return normalized


def _parse_ai_response(ai_response: str, raise_on_error: bool = False) -> list:
    """
    Phân tích response của AI thành danh sách dữ liệu chương (dùng phương thức làm sạch JSON thống nhất)
    
    Args:
        ai_response: văn bản gốc do AI trả về
        raise_on_error: nếu True, khi phân tích thất bại sẽ ném ngoại lệ thay vì trả dữ liệu dự phòng
        
    Returns:
        danh sách dữ liệu chương đã phân tích
        
    Raises:
        JSONParseError: ném ra khi raise_on_error=True và phân tích thất bại
    """
    try:
        # Dùng phương thức làm sạch JSON thống nhất (import từ AIService)
        from app.services.ai_service import AIService
        ai_service_temp = AIService()
        cleaned_text = ai_service_temp._clean_json_response(ai_response)
        
        outline_data = loads_json(cleaned_text)
        
        # Đảm bảo định dạng list
        if not isinstance(outline_data, list):
            # Nếu là object, thử trích trường chapters
            if isinstance(outline_data, dict):
                outline_data = outline_data.get("chapters", [outline_data])
            else:
                outline_data = [outline_data]
        
        # Kiểm tra kết quả phân tích có hợp lệ không (ít nhất một chương hợp lệ)
        valid_chapters = [
            ch for ch in outline_data
            if isinstance(ch, dict) and (ch.get("title") or ch.get("summary") or ch.get("content"))
        ]
        
        if not valid_chapters:
            error_msg = "Kết quả phân tích không hợp lệ: không tìm thấy dữ liệu chương hợp lệ"
            logger.error(f"❌ {error_msg}")
            if raise_on_error:
                raise JSONParseError(error_msg, ai_response)
            return [{
                "title": "Dàn ý do AI tạo",
                "content": ai_response[:1000],
                "summary": ai_response[:1000]
            }]
        
        logger.info(f"✅ Phân tích thành công {len(valid_chapters)} dữ liệu chương")
        return valid_chapters
        
    except json.JSONDecodeError as e:
        error_msg = f"Phân tích JSON thất bại: {e}"
        logger.error(f"❌ Phân tích response AI thất bại: {e}")
        
        if raise_on_error:
            raise JSONParseError(error_msg, ai_response)
        
        # Trả về một chương chứa nội dung gốc
        return [{
            "title": "Dàn ý do AI tạo",
            "content": ai_response[:1000],
            "summary": ai_response[:1000]
        }]
    except JSONParseError:
        # Ném lại JSONParseError
        raise
    except Exception as e:
        error_msg = f"Ngoại lệ khi phân tích: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        if raise_on_error:
            raise JSONParseError(error_msg, ai_response)
        
        return [{
            "title": "Dàn ý phân tích ngoại lệ",
            "content": "Lỗi hệ thống",
            "summary": "Lỗi hệ thống"
        }]


async def _save_outlines(
    project_id: str,
    outline_data: list,
    db: AsyncSession,
    start_index: int = 1
) -> List[Outline]:
    """
    Lưu dàn ý vào cơ sở dữ liệu (bản sửa: trích title và content từ structure để lưu)
    
    Nếu dự án ở chế độ one-to-one, đồng thời tự động tạo các chương tương ứng
    """
    # Lấy thông tin dự án để xác định outline_mode
    project_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = project_result.scalar_one_or_none()
    
    outlines = []
    outline_data = _normalize_outline_data(outline_data, expected_count=len(outline_data), start_index=start_index)
    
    for idx, chapter_data in enumerate(outline_data):
        order_idx = chapter_data.get("chapter_number", start_index + idx)
        
        # 🔧 Sửa: trích title và summary/content từ structure để lưu vào cơ sở dữ liệu
        chapter_title = chapter_data.get("title", f"Chương {order_idx}")
        chapter_content = chapter_data.get("summary") or chapter_data.get("content") or ""
        
        outline = Outline(
            project_id=project_id,
            title=chapter_title, # Trích title từ JSON
            content=chapter_content, # Trích summary hoặc content từ JSON
            structure=json.dumps(chapter_data, ensure_ascii=False),
            order_index=order_idx
        )

        db.add(outline)
        outlines.append(outline)
    
    # Nếu là chế độ one-to-one, tự động tạo chương
    if project and project.outline_mode == 'one-to-one':
        await db.flush() # Đảm bảo dàn ý có ID
        
        for outline in outlines:
            await db.refresh(outline)
            
            # 🔧 Trích title và summary từ structure để tạo chương
            try:
                structure_data = json.loads(outline.structure) if outline.structure else {}
                chapter_title = structure_data.get("title", f"Chương {outline.order_index}")
                chapter_summary = structure_data.get("summary") or structure_data.get("content", "")
            except json.JSONDecodeError:
                logger.warning(f"Phân tích structure của dàn ý {outline.id} thất bại, dùng giá trị mặc định")
                chapter_title = f"Chương {outline.order_index}"
                chapter_summary = ""
            
            # Tạo chương tương ứng cho mỗi dàn ý
            chapter = Chapter(
                project_id=project_id,
                title=chapter_title,
                summary=chapter_summary,
                chapter_number=outline.order_index,
                sub_index=1,
                outline_id=outline.id,
                status='pending',
                content=""
            )
            db.add(chapter)
        
        logger.info(f"Chế độ một-một: đã tự động tạo chương tương ứng cho {len(outlines)} dàn ý")
    
    return outlines


async def new_outline_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo SSE tạo mới hoàn toàn dàn ý (bản tăng cường MCP)"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Dàn ý")
    
    try:
        yield await tracker.start()
        
        project_id = data.get("project_id")
        # Đảm bảo chapter_count là số nguyên (frontend có thể gửi chuỗi)
        chapter_count = int(data.get("chapter_count", 10))
        enable_mcp = data.get("enable_mcp", True)
        
        # Kiểm tra dự án
        yield await tracker.loading("Đang tải thông tin dự án...", 0.3)
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            yield await tracker.error("Dự án không tồn tại", 404)
            return
        
        yield await tracker.loading(f"Đang chuẩn bị tạo dàn ý {chapter_count} chương...", 0.6)
        
        # Lấy thông tin nhân vật
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = characters_result.scalars().all()
        characters_info = _build_characters_info(characters)
        
        # Thiết lập thông tin người dùng để bật MCP
        user_id_for_mcp = data.get("user_id")
        if user_id_for_mcp:
            user_ai_service.user_id = user_id_for_mcp
            user_ai_service.db_session = db
        
        # Dùng mẫu prompt
        yield await tracker.preparing("Đang chuẩn bị prompt AI...")
        template = await PromptService.get_template("OUTLINE_CREATE", user_id_for_mcp, db)
        prompt = PromptService.format_prompt(
            template,
            title=project.title,
            theme=data.get("theme") or project.theme or "Chưa đặt",
            genre=data.get("genre") or project.genre or "Chung",
            chapter_count=chapter_count,
            narrative_perspective=data.get("narrative_perspective") or "Ngôi thứ ba",
            time_period=project.world_time_period or "Chưa đặt",
            location=project.world_location or "Chưa đặt",
            atmosphere=project.world_atmosphere or "Chưa đặt",
            rules=project.world_rules or "Chưa đặt",
            characters_info=characters_info or "Chưa có thông tin nhân vật",
            requirements=data.get("requirements") or "",
            mcp_references=""
        )
        logger.debug(f"Hoàn tất prompt tạo dàn ý: prompt_length={len(prompt)}")
        # Thêm log debug
        model_param = data.get("model")
        provider_param = data.get("provider")
        logger.info(f"=== Tham số gọi AI tạo dàn ý ===")
        logger.info(f" tham số provider: {provider_param}")
        logger.info(f" tham số model: {model_param}")
        
        # ✅ Tạo streaming (kèm đếm số từ và tiến trình)
        estimated_total = chapter_count * 1000
        accumulated_text = ""
        chunk_count = 0
        
        yield await tracker.generating(current_chars=0, estimated_total=estimated_total)
        
        async for chunk in user_ai_service.generate_text_stream(
            prompt=prompt,
            provider=provider_param,
            model=model_param,
            auto_mcp=enable_mcp
        ):
            chunk_count += 1
            accumulated_text += chunk
            
            # Gửi khối nội dung
            yield await tracker.generating_chunk(chunk)
            
            # Cập nhật tiến trình định kỳ
            if chunk_count % 10 == 0:
                yield await tracker.generating(
                    current_chars=len(accumulated_text),
                    estimated_total=estimated_total
                )
            
            # Mỗi 20 khối gửi một heartbeat
            if chunk_count % 20 == 0:
                yield await tracker.heartbeat()
        
        yield await tracker.parsing("Đang phân tích dữ liệu dàn ý...")
        
        ai_content = accumulated_text
        ai_response = {"content": ai_content}
        
        # Phân tích response (có cơ chế thử lại)
        max_retries = 2
        retry_count = 0
        outline_data = None
        
        while retry_count <= max_retries:
            try:
                # Dùng raise_on_error=True, khi phân tích thất bại sẽ ném ngoại lệ
                outline_data = _normalize_outline_data(
                    _parse_ai_response(ai_content, raise_on_error=True),
                    expected_count=chapter_count,
                    start_index=1
                )
                break # Phân tích thành công, thoát vòng lặp
                
            except JSONParseError as e:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"❌ Phân tích dàn ý thất bại, đã đạt số lần thử tối đa ({max_retries})")
                    raise e
                
                logger.warning(f"⚠️ Phân tích JSON thất bại (lần {retry_count}), đang thử lại...")
                yield await tracker.retry(retry_count, max_retries, "Phân tích JSON thất bại")
                
                # Khi thử lại thì đặt lại tiến trình tạo
                tracker.reset_generating_progress()
                
                # Gọi lại AI để tạo
                accumulated_text = ""
                chunk_count = 0
                
                # Thêm nhấn mạnh định dạng vào prompt
                retry_prompt = prompt + "\\n\\n【Nhắc nhở quan trọng】Hãy đảm bảo trả về mảng JSON đầy đủ, không cắt ngắn. Mỗi object chương phải có đầy đủ các trường title, summary."
                
                async for chunk in user_ai_service.generate_text_stream(
                    prompt=retry_prompt,
                    provider=provider_param,
                    model=model_param,
                    auto_mcp=enable_mcp
                ):
                    chunk_count += 1
                    accumulated_text += chunk
                    
                    # Gửi khối nội dung
                    yield await tracker.generating_chunk(chunk)
                    
                    # Mỗi 20 khối gửi một heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()
                
                ai_content = accumulated_text
                ai_response = {"content": ai_content}
                logger.info(f"🔄 Hoàn tất tạo thử lại, tích lũy {len(ai_content)} ký tự")
        
        # Chế độ tạo mới hoàn toàn: xóa dàn ý cũ và mọi chương, manh mối ẩn, dữ liệu phân tích liên quan
        yield await tracker.saving("Đang dọn dữ liệu cũ (dàn ý, chương, manh mối ẩn, phân tích)...", 0.2)
        logger.info(f"🧹 Tạo mới hoàn toàn: bắt đầu dọn mọi dữ liệu cũ của dự án {project_id} (outline_mode: {project.outline_mode})")
        
        from sqlalchemy import delete as sql_delete
        
        # 1. Lấy trước ID mọi chương cũ (để dọn sau này)
        old_chapters_result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id)
        )
        old_chapters = old_chapters_result.scalars().all()
        old_chapter_ids = [ch.id for ch in old_chapters]
        deleted_word_count = sum(ch.word_count or 0 for ch in old_chapters)
        
        # 2. Dọn dữ liệu manh mối ẩn (xóa manh mối ẩn phân tích, đặt lại manh mối ẩn thủ công)
        try:
            foreshadow_result = await foreshadow_service.clear_project_foreshadows_for_reset(db, project_id)
            logger.info(f"✅ Dọn manh mối ẩn: xóa {foreshadow_result['deleted_count']} manh mối ẩn phân tích, đặt lại {foreshadow_result['reset_count']} manh mối ẩn thủ công")
        except Exception as e:
            logger.error(f"❌ Dọn dữ liệu manh mối ẩn thất bại: {str(e)}")
            # Tiếp tục luồng, nhưng ghi log lỗi
        
        # 3. Dọn dữ liệu phân tích chương (PlotAnalysis)
        try:
            # Dù có CASCADE xóa, xóa tường minh dễ kiểm soát hơn
            from app.models.memory import PlotAnalysis
            delete_analysis_result = await db.execute(
                sql_delete(PlotAnalysis).where(PlotAnalysis.project_id == project_id)
            )
            deleted_analysis_count = delete_analysis_result.rowcount
            logger.info(f"✅ Dọn phân tích chương: xóa {deleted_analysis_count} bản ghi phân tích")
        except Exception as e:
            logger.error(f"❌ Dọn dữ liệu phân tích chương thất bại: {str(e)}")
        
        # 4. Dọn dữ liệu ký ức vector (StoryMemory)
        try:
            from app.models.memory import StoryMemory
            delete_memory_result = await db.execute(
                sql_delete(StoryMemory).where(StoryMemory.project_id == project_id)
            )
            deleted_memory_count = delete_memory_result.rowcount
            if deleted_memory_count > 0:
                logger.info(f"✅ Dọn ký ức vector: xóa {deleted_memory_count} dữ liệu ký ức")
        except Exception as e:
            logger.error(f"❌ Dọn dữ liệu ký ức vector thất bại: {str(e)}")
        
        # 5. Xóa ký ức trong cơ sở dữ liệu vector (nếu có chương)
        if old_chapter_ids:
            try:
                user_id_for_memory = data.get("user_id")
                if user_id_for_memory:
                    for chapter_id in old_chapter_ids:
                        try:
                            await memory_service.delete_chapter_memories(

                                user_id=user_id_for_memory,
                                project_id=project_id,
                                chapter_id=chapter_id
                            )
                        except Exception as mem_err:
                            logger.debug(f"Dọn ký ức vector của chương {chapter_id[:8]} thất bại: {str(mem_err)}")
                    logger.info(f"✅ Dọn cơ sở dữ liệu vector: đã dọn ký ức vector của {len(old_chapter_ids)} chương")
            except Exception as e:
                logger.warning(f"⚠️ Dọn cơ sở dữ liệu vector thất bại (không ảnh hưởng luồng chính): {str(e)}")
        
        # 6. Xóa mọi chương cũ
        delete_chapters_result = await db.execute(
            sql_delete(Chapter).where(Chapter.project_id == project_id)
        )
        deleted_chapters_count = delete_chapters_result.rowcount
        logger.info(f"✅ Dọn chương: xóa {deleted_chapters_count} chương ({deleted_word_count} từ)")
        
        # Cập nhật số từ dự án
        if deleted_word_count > 0:
            project.current_words = max(0, project.current_words - deleted_word_count)
            logger.info(f"Cập nhật số từ dự án: giảm {deleted_word_count} từ")
        
        # Xóa tiếp mọi dàn ý cũ
        delete_outlines_result = await db.execute(
            sql_delete(Outline).where(Outline.project_id == project_id)
        )
        deleted_outlines_count = delete_outlines_result.rowcount
        logger.info(f"✅ Tạo mới hoàn toàn: đã xóa {deleted_outlines_count} dàn ý cũ")
        
        # Lưu dàn ý mới
        yield await tracker.saving("Đang lưu dàn ý vào cơ sở dữ liệu...", 0.6)
        outlines = await _save_outlines(
            project_id, outline_data, db, start_index=1
        )
        
        # 🎭 Kiểm tra nhân vật: kiểm tra characters trong structure của dàn ý có nhân vật tương ứng không
        yield await tracker.saving("🎭 Đang kiểm tra thông tin nhân vật...", 0.7)
        try:
            char_check_result = await _check_and_create_missing_characters_from_outlines(
                outline_data=outline_data,
                project_id=project_id,
                db=db,
                user_ai_service=user_ai_service,
                user_id=data.get("user_id"),
                enable_mcp=data.get("enable_mcp", True),
                tracker=tracker
            )
            if char_check_result["created_count"] > 0:
                created_names = [c.name for c in char_check_result["created_characters"]]
                yield await tracker.saving(
                    f"🎭 Đã tự động tạo {char_check_result['created_count']} nhân vật: {', '.join(created_names)}",
                    0.8
                )
        except Exception as e:
            logger.error(f"⚠️ Kiểm tra nhân vật thất bại (không ảnh hưởng luồng chính): {e}")
        
        # 🏛️ Kiểm tra tổ chức: kiểm tra characters (type=organization) trong structure của dàn ý có tổ chức tương ứng không
        yield await tracker.saving("🏛️ Đang kiểm tra thông tin tổ chức...", 0.75)
        try:
            org_check_result = await _check_and_create_missing_organizations_from_outlines(
                outline_data=outline_data,
                project_id=project_id,
                db=db,
                user_ai_service=user_ai_service,
                user_id=data.get("user_id"),
                enable_mcp=data.get("enable_mcp", True),
                tracker=tracker
            )
            if org_check_result["created_count"] > 0:
                created_names = [c.name for c in org_check_result["created_organizations"]]
                yield await tracker.saving(
                    f"🏛️ Đã tự động tạo {org_check_result['created_count']} tổ chức: {', '.join(created_names)}",
                    0.85
                )
        except Exception as e:
            logger.error(f"⚠️ Kiểm tra tổ chức thất bại (không ảnh hưởng luồng chính): {e}")
        
        # Ghi lịch sử
        history = GenerationHistory(
            project_id=project_id,
            prompt=prompt,
            generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
            model=data.get("model") or "default"
        )
        db.add(history)
        
        await db.commit()
        db_committed = True
        
        for outline in outlines:
            await db.refresh(outline)
        
        logger.info(f"Hoàn tất tạo mới hoàn toàn - {len(outlines)} chương")
        
        yield await tracker.complete()
        
        # Gửi kết quả cuối
        yield await tracker.result({
            "message": f"Tạo thành công dàn ý {len(outlines)} chương",
            "total_chapters": len(outlines),
            "outlines": [
                {
                    "id": outline.id,
                    "project_id": outline.project_id,
                    "title": outline.title,
                    "content": outline.content,
                    "order_index": outline.order_index,
                    "structure": outline.structure,
                    "created_at": outline.created_at.isoformat() if outline.created_at else None,
                    "updated_at": outline.updated_at.isoformat() if outline.updated_at else None
                } for outline in outlines
            ]
        })
        
        yield await tracker.done()
        
    except GeneratorExit:
        logger.warning("Trình tạo dàn ý bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo dàn ý (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo dàn ý thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo dàn ý (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")


async def continue_outline_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService,
    user_id: str = "system"
) -> AsyncGenerator[str, None]:
    """Trình tạo SSE viết tiếp dàn ý - tạo theo lô, đẩy tiến trình (bản tăng cường ký ức + MCP)"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Viết tiếp dàn ý")
    
    try:
        # === Giai đoạn khởi tạo ===
        yield await tracker.start("Bắt đầu viết tiếp dàn ý...")
        
        project_id = data.get("project_id")
        # Đảm bảo chapter_count là số nguyên (frontend có thể gửi chuỗi)
        total_chapters_to_generate = int(data.get("chapter_count", 5))
        
        # Kiểm tra dự án
        yield await tracker.loading("Đang tải thông tin dự án...", 0.2)
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            yield await tracker.error("Dự án không tồn tại", 404)
            return
        
        # Lấy dàn ý hiện có
        yield await tracker.loading("Đang phân tích dàn ý đã có...", 0.5)
        existing_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        existing_outlines = existing_result.scalars().all()
        
        if not existing_outlines:
            yield await tracker.error("Chế độ viết tiếp cần có dàn ý sẵn, dự án hiện chưa có dàn ý", 400)
            return
        
        current_chapter_count = len(existing_outlines)
        last_chapter_number = existing_outlines[-1].order_index
        
        yield await tracker.loading(
            f"Hiện đã có {str(current_chapter_count)} chương, sẽ viết tiếp {str(total_chapters_to_generate)} chương",
            0.8
        )
        
        # Lấy thông tin nhân vật
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = characters_result.scalars().all()
        characters_info = _build_characters_info(characters)

        # Cấu hình chia lô
        batch_size = 5
        total_batches = (total_chapters_to_generate + batch_size - 1) // batch_size
        
        # Hướng dẫn giai đoạn cốt truyện
        stage_instructions = {
            "development": "Tiếp tục triển khai cốt truyện, làm sâu sắc quan hệ nhân vật, thúc đẩy xung đột chính",
            "climax": "Bước vào cao trào câu chuyện, mâu thuẫn gay gắt, xung đột then chốt bùng nổ",
            "ending": "Giải quyết xung đột chính, thu hồi manh mối ẩn, đưa ra kết thúc"
        }
        stage_instruction = stage_instructions.get(data.get("plot_stage", "development"), "")
        
        # === Giai đoạn tạo theo lô ===
        all_new_outlines = []
        current_start_chapter = last_chapter_number + 1
        
        for batch_num in range(total_batches):
            # Tính số chương của lô hiện tại
            remaining_chapters = int(total_chapters_to_generate) - len(all_new_outlines)
            current_batch_size = min(batch_size, remaining_chapters)
            
            # Ước tính tiến trình cho mỗi lô
            estimated_chars_per_batch = current_batch_size * 1000
            
            # Đặt lại tiến trình tạo để mỗi lô tính độc lập
            tracker.reset_generating_progress()
            
            yield await tracker.generating(
                current_chars=0,
                estimated_total=estimated_chars_per_batch,
                message=f"📝 Lô {str(batch_num + 1)}/{str(total_batches)}: đang tạo chương {str(current_start_chapter)}-{str(current_start_chapter + current_batch_size - 1)}"
            )
            
            # Lấy danh sách dàn ý mới nhất (gồm các lô đã tạo trước)
            latest_result = await db.execute(
                select(Outline)
                .where(Outline.project_id == project_id)
                .order_by(Outline.order_index)
            )
            latest_outlines = latest_result.scalars().all()
            
            # 🚀 Dùng cách xây dựng ngữ cảnh rút gọn mới
            context = await _build_outline_continue_context(
                project=project,
                latest_outlines=latest_outlines,
                characters=characters,
                chapter_count=current_batch_size,
                plot_stage=data.get("plot_stage", "development"),
                story_direction=data.get("story_direction", "Tiếp nối tự nhiên"),
                requirements=data.get("requirements", ""),
                db=db
            )
            
            # Thống kê log
            stats = context['stats']
            logger.info(f"📊 Ngữ cảnh dàn ý lô {batch_num + 1}: tổng dàn ý {stats['total_outlines']}, "
                       f"{stats['recent_outlines_count']} chương gần nhất, "
                       f"{stats['characters_count']} nhân vật, "
                       f"độ dài {stats['total_length']} ký tự")
            
            # Thiết lập thông tin người dùng để bật MCP
            if user_id:
                user_ai_service.user_id = user_id
                user_ai_service.db_session = db

            yield await tracker.generating(
                current_chars=0,
                estimated_total=estimated_chars_per_batch,
                message=f"🤖 Đang gọi AI tạo lô {str(batch_num + 1)}..."
            )
            
            # Lấy thông tin nhắc manh mối ẩn (dùng cho viết tiếp dàn ý)
            foreshadow_reminders_text = "Chưa có manh mối ẩn cần chú ý"
            try:
                foreshadow_context = await foreshadow_service.build_chapter_context(
                    db=db,
                    project_id=project_id,
                    chapter_number=current_start_chapter,
                    include_pending=False,
                    include_overdue=True,
                    lookahead=10
                )
                if foreshadow_context and foreshadow_context.get("context_text"):
                    foreshadow_reminders_text = foreshadow_context["context_text"]
                    logger.info(f"✅ Viết tiếp dàn ý lấy được nhắc manh mối ẩn: {len(foreshadow_reminders_text)} ký tự")
                    # Thêm thông tin thống kê manh mối ẩn
                    foreshadow_stats = await foreshadow_service.get_stats(db, project_id)
                    if foreshadow_stats:
                        planted = foreshadow_stats.get('planted', 0)
                        resolved = foreshadow_stats.get('resolved', 0)
                        partial = foreshadow_stats.get('partially_resolved', 0)
                        pending = foreshadow_stats.get('pending', 0)
                        foreshadow_reminders_text += f"\\n【📊 Thống kê manh mối ẩn】Đã gieo: {planted} Đã thu hồi: {resolved} Thu hồi một phần: {partial} Chờ gieo: {pending}"
            except Exception as e:
                logger.warning(f"⚠️ Lấy nhắc manh mối ẩn viết tiếp dàn ý thất bại: {str(e)}")

            # Dùng mẫu prompt viết tiếp chuẩn (bản rút gọn)
            template = await PromptService.get_template("OUTLINE_CONTINUE", user_id, db)
            prompt = PromptService.format_prompt(
                template,
                # Thông tin cơ bản
                title=project.title,
                theme=project.theme or "Chưa đặt",
                genre=project.genre or "Chung",
                narrative_perspective=project.narrative_perspective or "Ngôi thứ ba",
                time_period=project.world_time_period or "Chưa đặt",
                location=project.world_location or "Chưa đặt",
                atmosphere=project.world_atmosphere or "Chưa đặt",
                rules=project.world_rules or "Chưa đặt",
                # Thông tin ngữ cảnh
                recent_outlines=context['recent_outlines'],
                characters_info=context['characters_info'],
                # Nhắc manh mối ẩn
                foreshadow_reminders=foreshadow_reminders_text,
                # Tham số viết tiếp
                chapter_count=current_batch_size,
                start_chapter=current_start_chapter,
                end_chapter=current_start_chapter + current_batch_size - 1,
                current_chapter_count=len(latest_outlines),
                plot_stage_instruction=stage_instruction,
                story_direction=data.get("story_direction", "Tiếp nối tự nhiên"),
                requirements=data.get("requirements", ""),
                mcp_references=""
            )
            logger.debug(f"Hoàn tất prompt viết tiếp: batch={batch_num + 1}, prompt_length={len(prompt)}")
            # Gọi AI tạo lô hiện tại
            model_param = data.get("model")
            provider_param = data.get("provider")
            logger.info(f"=== Tham số gọi AI lô viết tiếp {batch_num + 1} ===")
            logger.info(f" tham số provider: {provider_param}")
            logger.info(f" tham số model: {model_param}")
            
            # Tạo streaming và tích lũy văn bản
            accumulated_text = ""
            chunk_count = 0
            
            async for chunk in user_ai_service.generate_text_stream(
                prompt=prompt,
                provider=provider_param,
                model=model_param,
                auto_mcp=data.get("enable_mcp", True)
            ):
                chunk_count += 1
                accumulated_text += chunk
                
                # Gửi khối nội dung
                yield await tracker.generating_chunk(chunk)
                
                # Cập nhật tiến trình định kỳ
                if chunk_count % 10 == 0:
                    yield await tracker.generating(
                        current_chars=len(accumulated_text),
                        estimated_total=estimated_chars_per_batch,
                        message=f"📝 Lô {str(batch_num + 1)}/{str(total_batches)} đang tạo"
                    )
                
                # Mỗi 20 khối gửi một heartbeat
                if chunk_count % 20 == 0:
                    yield await tracker.heartbeat()
            
            yield await tracker.parsing(f"✅ Lô {str(batch_num + 1)} AI tạo xong, đang phân tích...")
            
            # Trích nội dung
            ai_content = accumulated_text
            ai_response = {"content": ai_content}
            
            # Phân tích response (có cơ chế thử lại)
            max_retries = 2
            retry_count = 0
            outline_data = None
            
            while retry_count <= max_retries:
                try:
                    # Dùng raise_on_error=True, khi phân tích thất bại sẽ ném ngoại lệ
                    outline_data = _normalize_outline_data(
                        _parse_ai_response(ai_content, raise_on_error=True),
                        expected_count=current_batch_size,
                        start_index=current_start_chapter
                    )
                    break # Phân tích thành công, thoát vòng lặp
                    
                except JSONParseError as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"❌ Lô {batch_num + 1} phân tích thất bại, đã đạt số lần thử tối đa ({max_retries})")
                        raise e
                    
                    logger.warning(f"⚠️ Lô {batch_num + 1} phân tích JSON thất bại (lần {retry_count}), đang thử lại...")
                    yield await tracker.retry(retry_count, max_retries, f"Lô {str(batch_num + 1)} phân tích thất bại")
                    
                    # Khi thử lại thì đặt lại tiến trình tạo
                    tracker.reset_generating_progress()
                    
                    # Gọi lại AI để tạo
                    accumulated_text = ""
                    chunk_count = 0
                    
                    # Thêm nhấn mạnh định dạng vào prompt
                    retry_prompt = prompt + "\\n\\n【Nhắc nhở quan trọng】Hãy đảm bảo trả về mảng JSON đầy đủ, không cắt ngắn. Mỗi object chương phải có đầy đủ các trường title, summary."
                    
                    async for chunk in user_ai_service.generate_text_stream(
                        prompt=retry_prompt,
                        provider=provider_param,
                        model=model_param,
                        auto_mcp=data.get("enable_mcp", True)
                    ):
                        chunk_count += 1
                        accumulated_text += chunk
                        
                        # Gửi khối nội dung
                        yield await tracker.generating_chunk(chunk)
                        
                        # Mỗi 20 khối gửi một heartbeat
                        if chunk_count % 20 == 0:
                            yield await tracker.heartbeat()
                    
                    ai_content = accumulated_text
                    ai_response = {"content": ai_content}
                    logger.info(f"🔄 Lô {batch_num + 1} tạo thử lại xong, tích lũy {len(ai_content)} ký tự")
            
            # Lưu dàn ý của lô hiện tại
            batch_outlines = await _save_outlines(
                project_id, outline_data, db, start_index=current_start_chapter
            )
            
            # 🎭 Kiểm tra nhân vật: kiểm tra characters trong structure của dàn ý lô này có nhân vật tương ứng không
            try:
                char_check_result = await _check_and_create_missing_characters_from_outlines(
                    outline_data=outline_data,
                    project_id=project_id,
                    db=db,
                    user_ai_service=user_ai_service,
                    user_id=user_id,
                    enable_mcp=data.get("enable_mcp", True),
                    tracker=tracker
                )
                if char_check_result["created_count"] > 0:
                    created_names = [c.name for c in char_check_result["created_characters"]]
                    yield await tracker.saving(
                        f"🎭 Lô {str(batch_num + 1)}: đã tự động tạo {char_check_result['created_count']} nhân vật: {', '.join(created_names)}",
                        (batch_num + 1) / total_batches * 0.5
                    )
                    # Cập nhật danh sách nhân vật (để các lô sau dùng)
                    characters.extend(char_check_result["created_characters"])
                    characters_info = _build_characters_info(characters)
            except Exception as e:
                logger.error(f"⚠️ Lô {batch_num + 1} kiểm tra nhân vật thất bại (không ảnh hưởng luồng chính): {e}")
            
            # 🏛️ Kiểm tra tổ chức: kiểm tra characters (type=organization) trong structure của dàn ý lô này có tổ chức tương ứng không
            try:
                org_check_result = await _check_and_create_missing_organizations_from_outlines(
                    outline_data=outline_data,
                    project_id=project_id,
                    db=db,
                    user_ai_service=user_ai_service,
                    user_id=user_id,
                    enable_mcp=data.get("enable_mcp", True),
                    tracker=tracker
                )
                if org_check_result["created_count"] > 0:
                    created_names = [c.name for c in org_check_result["created_organizations"]]
                    yield await tracker.saving(
                        f"🏛️ Lô {str(batch_num + 1)}: đã tự động tạo {org_check_result['created_count']} tổ chức: {', '.join(created_names)}",
                        (batch_num + 1) / total_batches * 0.55
                    )
                    # Cập nhật danh sách nhân vật (tổ chức cũng là Character, để các lô sau dùng)
                    characters.extend(org_check_result["created_organizations"])
                    characters_info = _build_characters_info(characters)
            except Exception as e:
                logger.error(f"⚠️ Lô {batch_num + 1} kiểm tra tổ chức thất bại (không ảnh hưởng luồng chính): {e}")
            
            # Ghi lịch sử
            history = GenerationHistory(
                project_id=project_id,
                prompt=f"[Lô viết tiếp {batch_num + 1}/{total_batches}] {str(prompt)[:500]}",
                generated_content=json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else ai_response,
                model=data.get("model") or "default"
            )
            db.add(history)
            
            # Commit lô hiện tại
            await db.commit()
            
            for outline in batch_outlines:
                await db.refresh(outline)
            
            all_new_outlines.extend(batch_outlines)
            current_start_chapter += current_batch_size
            
            yield await tracker.saving(
                f"💾 Lô {str(batch_num + 1)} lưu thành công! Lô này tạo {str(len(batch_outlines))} chương, tích lũy thêm {str(len(all_new_outlines))} chương",
                (batch_num + 1) / total_batches
            )
            
            logger.info(f"Lô {str(batch_num + 1)} tạo xong, lô này tạo {str(len(batch_outlines))} chương")
        
        db_committed = True
        
        # Trả về mọi dàn ý (gồm cũ và mới)
        final_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        all_outlines = final_result.scalars().all()
        
        yield await tracker.complete()
        
        # Gửi kết quả cuối
        yield await tracker.result({
            "message": f"Viết tiếp hoàn tất! Tổng {str(total_batches)} lô, thêm {str(len(all_new_outlines))} chương, tổng cộng {str(len(all_outlines))} chương",
            "total_batches": total_batches,
            "new_chapters": len(all_new_outlines),
            "total_chapters": len(all_outlines),

            "outlines": [
                {
                    "id": outline.id,
                    "project_id": outline.project_id,
                    "title": outline.title,
                    "content": outline.content,
                    "order_index": outline.order_index,
                    "structure": outline.structure,
                    "created_at": outline.created_at.isoformat() if outline.created_at else None,
                    "updated_at": outline.updated_at.isoformat() if outline.updated_at else None
                } for outline in all_outlines
            ]
        })
        
        yield await tracker.done()
        
    except GeneratorExit:
        logger.warning("Trình tạo viết tiếp dàn ý bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch viết tiếp dàn ý (GeneratorExit)")
    except Exception as e:
        logger.error(f"Viết tiếp dàn ý thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch viết tiếp dàn ý (ngoại lệ)")
        yield await tracker.error(f"Viết tiếp thất bại: {str(e)}")


@router.post("/generate", summary="AI tạo/viết tiếp dàn ý (tác vụ nền)")
async def generate_outline_task(
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng tác vụ nền để tạo hoặc viết tiếp dàn ý tiểu thuyết (không sợ mất kết nối, tắt trình duyệt vẫn chạy tiếp)
    
    Trả về task_id, frontend dùng GET /api/tasks/{task_id} để thăm dò tiến trình
    
    Các chế độ hỗ trợ:
    - auto/new/continue (giống generate-stream)
    """
    from app.services.background_task_service import background_task_service, TaskProgressTracker
    from app.database import get_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as NewAsyncSession

    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(data.get("project_id"), user_id, db)

    # Xác định chế độ
    mode = data.get("mode", "auto")
    existing_result = await db.execute(
        select(Outline)
        .where(Outline.project_id == data.get("project_id"))
        .order_by(Outline.order_index)
    )
    existing_outlines = existing_result.scalars().all()

    if mode == "auto":
        mode = "continue" if existing_outlines else "new"

    data["user_id"] = user_id
    data["mode"] = mode

    if mode == "continue" and not existing_outlines:
        raise HTTPException(status_code=400, detail="Chế độ viết tiếp cần có dàn ý sẵn")

    # Tạo tác vụ nền
    task_type = "outline_new" if mode == "new" else "outline_continue"
    task = await background_task_service.create_task(
        user_id=user_id,
        project_id=data.get("project_id"),
        task_type=task_type,
        task_input=data,
        db=db
    )

    # Hàm chạy nền
    async def _run_outline_generation(task_id: str, user_id: str):
        engine = await get_engine(user_id)
        AsyncSessionLocal = async_sessionmaker(engine, class_=NewAsyncSession, expire_on_commit=False)
        
        async with AsyncSessionLocal() as bg_db:
            tracker = TaskProgressTracker(task_id, user_id, "Dàn ý")
            try:
                await tracker.start()
                
                # Lấy dịch vụ AI (cần tạo instance mới trong nền)
                from app.api.settings import get_user_ai_service_from_db
                bg_ai_service = await get_user_ai_service_from_db(user_id, bg_db)
                
                if mode == "new":
                    await _run_new_outline_bg(data, bg_db, bg_ai_service, tracker)
                else:
                    await _run_continue_outline_bg(data, bg_db, bg_ai_service, tracker, user_id)
                    
            except Exception as e:
                logger.error(f"❌ Tạo dàn ý nền thất bại: {e}", exc_info=True)
                await tracker.error(str(e))

    await background_task_service.spawn_background_task(
        task.id, user_id, _run_outline_generation
    )

    return {
        "task_id": task.id,
        "task_type": task_type,
        "status": "pending",
        "message": "Đã tạo tác vụ, hãy dùng GET /api/tasks/{task_id} để tra tiến trình"
    }


async def _run_new_outline_bg(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService,
    tracker
):
    """Chạy nền tạo mới hoàn toàn dàn ý"""
    from app.database import get_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as BgAsyncSession

    project_id = data.get("project_id")
    chapter_count = int(data.get("chapter_count", 10))
    user_id_for_mcp = data.get("user_id")

    await tracker.loading("Đang tải thông tin dự án...", 0.3)
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await tracker.error("Dự án không tồn tại")
        return

    await tracker.loading(f"Đang chuẩn bị tạo dàn ý {chapter_count} chương...", 0.6)
    characters_result = await db.execute(select(Character).where(Character.project_id == project_id))
    characters = characters_result.scalars().all()
    characters_info = _build_characters_info(characters)

    if user_id_for_mcp:
        user_ai_service.user_id = user_id_for_mcp
        user_ai_service.db_session = db

    await tracker.preparing("Đang chuẩn bị prompt AI...")
    template = await PromptService.get_template("OUTLINE_CREATE", user_id_for_mcp, db)
    prompt = PromptService.format_prompt(
        template,
        title=project.title,
        theme=data.get("theme") or project.theme or "Chưa đặt",
        genre=data.get("genre") or project.genre or "Chung",
        chapter_count=chapter_count,
        narrative_perspective=data.get("narrative_perspective") or "Ngôi thứ ba",
        time_period=project.world_time_period or "Chưa đặt",
        location=project.world_location or "Chưa đặt",
        atmosphere=project.world_atmosphere or "Chưa đặt",
        rules=project.world_rules or "Chưa đặt",
        characters_info=characters_info or "Chưa có thông tin nhân vật",
        requirements=data.get("requirements") or "",
        mcp_references=""
    )

    model_param = data.get("model")
    provider_param = data.get("provider")

    estimated_total = chapter_count * 1000
    accumulated_text = ""
    chunk_count = 0

    await tracker.generating(current_chars=0, estimated_total=estimated_total)

    async for chunk in user_ai_service.generate_text_stream(
        prompt=prompt, provider=provider_param, model=model_param, auto_mcp=data.get("enable_mcp", True)
    ):
        chunk_count += 1
        accumulated_text += chunk
        if chunk_count % 10 == 0:
            if await tracker.check_cancelled():
                await tracker.error("Tác vụ đã bị hủy")
                return
            await tracker.generating(
                current_chars=len(accumulated_text),
                estimated_total=estimated_total
            )

    await tracker.parsing("Đang phân tích dữ liệu dàn ý...")
    ai_content = accumulated_text

    # Phân tích response (có thử lại)
    max_retries = 2
    retry_count = 0
    outline_data = None

    while retry_count <= max_retries:
        try:
            outline_data = _normalize_outline_data(
                _parse_ai_response(ai_content, raise_on_error=True),
                expected_count=chapter_count,
                start_index=1
            )
            break
        except JSONParseError:
            retry_count += 1
            if retry_count > max_retries:
                raise
            await tracker.retry(retry_count, max_retries, "Phân tích JSON thất bại")
            tracker.reset_generating_progress()
            accumulated_text = ""
            retry_prompt = prompt + "\\n\\n【Nhắc nhở quan trọng】Hãy đảm bảo trả về mảng JSON đầy đủ."
            async for chunk in user_ai_service.generate_text_stream(
                prompt=retry_prompt, provider=provider_param, model=model_param, auto_mcp=data.get("enable_mcp", True)
            ):
                accumulated_text += chunk
            ai_content = accumulated_text

    await tracker.saving("Đang dọn dữ liệu cũ...", 0.2)
    from sqlalchemy import delete as sql_delete
    from app.models.memory import PlotAnalysis, StoryMemory

    old_chapters_result = await db.execute(select(Chapter).where(Chapter.project_id == project_id))
    old_chapters = old_chapters_result.scalars().all()
    old_chapter_ids = [ch.id for ch in old_chapters]
    deleted_word_count = sum(ch.word_count or 0 for ch in old_chapters)

    for ch in old_chapters:
        try:
            await memory_service.delete_chapter_memories(
                user_id=user_id_for_mcp, project_id=project_id, chapter_id=ch.id
            )
        except Exception as mem_err:
            logger.debug(f"Dọn ký ức vector của chương {ch.id[:8]} thất bại: {mem_err}")

    try:
        await foreshadow_service.clear_project_foreshadows_for_reset(db, project_id)
    except Exception as fs_err:
        logger.warning(f"⚠️ Dọn manh mối ẩn thất bại (tiếp tục tái tạo dàn ý): {fs_err}")

    await db.execute(sql_delete(PlotAnalysis).where(PlotAnalysis.project_id == project_id))
    await db.execute(sql_delete(StoryMemory).where(StoryMemory.project_id == project_id))
    await db.execute(sql_delete(Chapter).where(Chapter.project_id == project_id))
    await db.execute(sql_delete(Outline).where(Outline.project_id == project_id))
    if deleted_word_count > 0:
        project.current_words = max(0, (project.current_words or 0) - deleted_word_count)
    logger.info(f"✅ Dọn dữ liệu cũ xong: xóa {len(old_chapter_ids)} chương cũ")

    await tracker.saving("Đang lưu dàn ý mới vào cơ sở dữ liệu...", 0.6)
    outlines = await _save_outlines(project_id, outline_data, db, start_index=1)
    logger.info(f"✅ Đã lưu dàn ý mới: {len(outlines)} chương")

    # Kiểm tra nhân vật

    await tracker.saving("🎭 Đang kiểm tra thông tin nhân vật...", 0.7)
    try:
        await _check_and_create_missing_characters_from_outlines(
            outline_data=outline_data, project_id=project_id, db=db,
            user_ai_service=user_ai_service, user_id=data.get("user_id"),
            enable_mcp=data.get("enable_mcp", True), tracker=tracker
        )
    except Exception:
        pass

    # Kiểm tra tổ chức
    try:
        await _check_and_create_missing_organizations_from_outlines(
            outline_data=outline_data, project_id=project_id, db=db,
            user_ai_service=user_ai_service, user_id=data.get("user_id"),
            enable_mcp=data.get("enable_mcp", True), tracker=tracker
        )
    except Exception:
        pass

    # Lưu kết quả vào bản ghi tác vụ
    result_data = {
        "message": f"Tạo thành công dàn ý {len(outlines)} chương",
        "total_chapters": len(outlines),
        "outline_ids": [o.id for o in outlines]
    }

    # Cập nhật kết quả tác vụ
    from app.models.background_task import BackgroundTask
    task_result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == tracker.task_id))
    bg_task = task_result.scalar_one_or_none()
    if bg_task:
        bg_task.task_result = result_data
        await db.commit()

    await tracker.complete(f"Tạo thành công dàn ý {len(outlines)} chương")
    logger.info(f"✅ Tạo dàn ý nền hoàn tất: {len(outlines)} chương")


async def _run_continue_outline_bg(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService,
    tracker,
    user_id: str
):
    """Chạy nền viết tiếp dàn ý"""
    project_id = data.get("project_id")
    total_chapters = int(data.get("chapter_count", 5))

    await tracker.loading("Đang tải thông tin dự án...", 0.2)
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        await tracker.error("Dự án không tồn tại")
        return

    existing_result = await db.execute(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.order_index)
    )
    existing_outlines = existing_result.scalars().all()
    if not existing_outlines:
        await tracker.error("Chế độ viết tiếp cần có dàn ý sẵn")
        return

    last_chapter_number = existing_outlines[-1].order_index

    characters_result = await db.execute(select(Character).where(Character.project_id == project_id))
    characters = characters_result.scalars().all()

    batch_size = 5
    total_batches = (total_chapters + batch_size - 1) // batch_size
    all_new_outlines = []
    current_start_chapter = last_chapter_number + 1

    stage_instructions = {
        "development": "Tiếp tục triển khai cốt truyện, làm sâu sắc quan hệ nhân vật",
        "climax": "Bước vào cao trào câu chuyện, mâu thuẫn gay gắt",
        "ending": "Giải quyết xung đột chính, đưa ra kết thúc"
    }
    stage_instruction = stage_instructions.get(data.get("plot_stage", "development"), "")

    for batch_num in range(total_batches):
        if await tracker.check_cancelled():
            await tracker.error("Tác vụ đã bị hủy")
            return

        remaining = total_chapters - len(all_new_outlines)
        current_batch_size = min(batch_size, remaining)
        tracker.reset_generating_progress()

        await tracker.generating(
            message=f"📝 Lô {batch_num + 1}/{total_batches}: đang tạo chương {current_start_chapter}-{current_start_chapter + current_batch_size - 1}"
        )

        latest_result = await db.execute(
            select(Outline).where(Outline.project_id == project_id).order_by(Outline.order_index)
        )
        latest_outlines = latest_result.scalars().all()

        context = await _build_outline_continue_context(
            project=project, latest_outlines=latest_outlines, characters=characters,
            chapter_count=current_batch_size,
            plot_stage=data.get("plot_stage", "development"),
            story_direction=data.get("story_direction", "Tiếp nối tự nhiên"),
            requirements=data.get("requirements", ""), db=db
        )

        user_ai_service.user_id = user_id
        user_ai_service.db_session = db

        # Lấy nhắc manh mối ẩn
        foreshadow_reminders_text = "Chưa có manh mối ẩn cần chú ý"
        try:
            foreshadow_context = await foreshadow_service.build_chapter_context(
                db=db, project_id=project_id, chapter_number=current_start_chapter,
                include_pending=False, include_overdue=True, lookahead=10
            )
            if foreshadow_context and foreshadow_context.get("context_text"):
                foreshadow_reminders_text = foreshadow_context["context_text"]
        except Exception:
            pass

        template = await PromptService.get_template("OUTLINE_CONTINUE", user_id, db)
        prompt = PromptService.format_prompt(
            template,
            title=project.title, theme=project.theme or "Chưa đặt",
            genre=project.genre or "Chung",
            narrative_perspective=project.narrative_perspective or "Ngôi thứ ba",
            time_period=project.world_time_period or "Chưa đặt",
            location=project.world_location or "Chưa đặt",
            atmosphere=project.world_atmosphere or "Chưa đặt",
            rules=project.world_rules or "Chưa đặt",
            recent_outlines=context['recent_outlines'],
            characters_info=context['characters_info'],
            foreshadow_reminders=foreshadow_reminders_text,
            chapter_count=current_batch_size,
            start_chapter=current_start_chapter,
            end_chapter=current_start_chapter + current_batch_size - 1,
            current_chapter_count=len(latest_outlines),
            plot_stage_instruction=stage_instruction,
            story_direction=data.get("story_direction", "Tiếp nối tự nhiên"),
            requirements=data.get("requirements", ""),
            mcp_references=""
        )

        accumulated_text = ""
        chunk_count = 0
        estimated_chars = current_batch_size * 1000

        async for chunk in user_ai_service.generate_text_stream(
            prompt=prompt,
            provider=data.get("provider"),
            model=data.get("model"),
            auto_mcp=data.get("enable_mcp", True)
        ):
            chunk_count += 1
            accumulated_text += chunk
            if chunk_count % 10 == 0:
                await tracker.generating(
                    current_chars=len(accumulated_text), estimated_total=estimated_chars,
                    message=f"📝 Lô {batch_num + 1}/{total_batches} đang tạo..."
                )

        await tracker.parsing(f"Đang phân tích dữ liệu lô {batch_num + 1}...")

        # Phân tích
        max_retries = 2
        retry_count = 0
        outline_data = None
        while retry_count <= max_retries:
            try:
                outline_data = _normalize_outline_data(
                    _parse_ai_response(accumulated_text, raise_on_error=True),
                    expected_count=current_batch_size,
                    start_index=current_start_chapter
                )
                break
            except JSONParseError:
                retry_count += 1
                if retry_count > max_retries:
                    raise
                await tracker.retry(retry_count, max_retries, "Phân tích JSON thất bại")
                tracker.reset_generating_progress()
                accumulated_text = ""
                retry_prompt = prompt + "\\n\\n【Nhắc nhở quan trọng】Hãy đảm bảo trả về mảng JSON đầy đủ."
                async for chunk in user_ai_service.generate_text_stream(
                    prompt=retry_prompt,
                    provider=data.get("provider"),
                    model=data.get("model"),
                    auto_mcp=data.get("enable_mcp", True)
                ):
                    accumulated_text += chunk

        # Lưu lô hiện tại
        await tracker.saving(f"Đang lưu dàn ý lô {batch_num + 1}...", 0.5)
        batch_outlines = await _save_outlines(
            project_id, outline_data, db, start_index=current_start_chapter
        )
        await db.commit()
        all_new_outlines.extend(batch_outlines)
        current_start_chapter += current_batch_size

        # Kiểm tra nhân vật/tổ chức và làm mới ngữ cảnh lô tiếp theo
        try:
            char_check_result = await _check_and_create_missing_characters_from_outlines(
                outline_data=outline_data, project_id=project_id, db=db,
                user_ai_service=user_ai_service, user_id=user_id,
                enable_mcp=data.get("enable_mcp", True), tracker=tracker
            )
            org_check_result = await _check_and_create_missing_organizations_from_outlines(
                outline_data=outline_data, project_id=project_id, db=db,
                user_ai_service=user_ai_service, user_id=user_id,
                enable_mcp=data.get("enable_mcp", True), tracker=tracker
            )
            if char_check_result.get("created_count", 0) or org_check_result.get("created_count", 0):
                characters_result = await db.execute(select(Character).where(Character.project_id == project_id))
                characters = characters_result.scalars().all()
            await db.commit()
        except Exception:
            logger.warning("Kiểm tra nhân vật/tổ chức viết tiếp dàn ý nền thất bại", exc_info=True)

    # Lưu kết quả
    result_data = {
        "message": f"Viết tiếp thành công dàn ý {len(all_new_outlines)} chương",
        "total_chapters": len(all_new_outlines),
        "outline_ids": [o.id for o in all_new_outlines]
    }
    from app.models.background_task import BackgroundTask
    task_result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == tracker.task_id))
    bg_task = task_result.scalar_one_or_none()
    if bg_task:
        bg_task.task_result = result_data
        await db.commit()

    await tracker.complete(f"Viết tiếp thành công dàn ý {len(all_new_outlines)} chương")
    logger.info(f"✅ Viết tiếp dàn ý nền hoàn tất: {len(all_new_outlines)} chương")


@router.post("/generate-stream", summary="AI tạo/viết tiếp dàn ý (streaming SSE)")
async def generate_outline_stream(
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE streaming tạo hoặc viết tiếp dàn ý tiểu thuyết, đẩy tiến trình theo lô theo thời gian thực
    
    Các chế độ hỗ trợ:
    - auto: tự động phán đoán (không có dàn ý → tạo mới, có dàn ý → viết tiếp)
    - new: tạo mới hoàn toàn
    - continue: chế độ viết tiếp
    
    Ví dụ request body:
    {
        "project_id": "ID dự án",
        "chapter_count": 5, // số chương
        "mode": "auto", // auto/new/continue
        "theme": "chủ đề câu chuyện", // chế độ new bắt buộc
        "story_direction": "hướng phát triển câu chuyện", // chế độ continue tùy chọn
        "plot_stage": "development", // chế độ continue: development/climax/ending
        "narrative_perspective": "Ngôi thứ ba",
        "requirements": "yêu cầu khác",
        "provider": "openai", // tùy chọn
        "model": "gpt-4" // tùy chọn
    }
    """

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(data.get("project_id"), user_id, db)
    
    # Xác định chế độ
    mode = data.get("mode", "auto")
    
    # Lấy dàn ý hiện có
    existing_result = await db.execute(
        select(Outline)
        .where(Outline.project_id == data.get("project_id"))
        .order_by(Outline.order_index)
    )
    existing_outlines = existing_result.scalars().all()
    
    # Tự động phán đoán chế độ
    if mode == "auto":
        mode = "continue" if existing_outlines else "new"
        logger.info(f"Tự động phán đoán chế độ: {'viết tiếp' if existing_outlines else 'tạo mới'}")
    
    # Lấy ID người dùng
    user_id = getattr(request.state, "user_id", "system")
    data["user_id"] = user_id
    # Chọn trình tạo theo chế độ
    if mode == "new":
        return create_sse_response(new_outline_generator(data, db, user_ai_service))
    elif mode == "continue":
        if not existing_outlines:
            raise HTTPException(
                status_code=400,
                detail="Chế độ viết tiếp cần có dàn ý sẵn, dự án hiện chưa có dàn ý"
            )
        return create_sse_response(continue_outline_generator(data, db, user_ai_service, user_id))
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Chế độ không hỗ trợ: {mode}"
        )


async def expand_outline_generator(
    outline_id: str,
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo SSE triển khai một dàn ý - đẩy tiến trình theo thời gian thực (hỗ trợ tạo theo lô)"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Triển khai dàn ý")
    
    try:
        yield await tracker.start()
        
        target_chapter_count = int(data.get("target_chapter_count", 3))
        expansion_strategy = data.get("expansion_strategy", "balanced")
        enable_scene_analysis = data.get("enable_scene_analysis", True)
        auto_create_chapters = data.get("auto_create_chapters", False)
        batch_size = int(data.get("batch_size", 5))  # Hỗ trợ tùy chỉnh kích thước lô
        
        # Lấy dàn ý
        yield await tracker.loading("Đang tải thông tin dàn ý...", 0.3)
        result = await db.execute(
            select(Outline).where(Outline.id == outline_id)
        )
        outline = result.scalar_one_or_none()
        
        if not outline:
            yield await tracker.error("Dàn ý không tồn tại", 404)
            return
        
        # Lấy thông tin dự án
        yield await tracker.loading("Đang tải thông tin dự án...", 0.7)
        project_result = await db.execute(
            select(Project).where(Project.id == outline.project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            yield await tracker.error("Dự án không tồn tại", 404)
            return
        
        yield await tracker.preparing(
            f"Đang chuẩn bị triển khai《{outline.title}》thành {target_chapter_count} chương..."
        )
        
        # Tạo instance dịch vụ triển khai
        expansion_service = PlotExpansionService(user_ai_service)
        
        # Phân tích dàn ý và tạo quy hoạch chương (hỗ trợ chia lô)
        if target_chapter_count > batch_size:
            yield await tracker.generating(
                current_chars=0,
                estimated_total=target_chapter_count * 500,
                message=f"🤖 AI tạo quy hoạch chương theo lô (mỗi lô {batch_size} chương)..."
            )
        else:
            yield await tracker.generating(
                current_chars=0,
                estimated_total=target_chapter_count * 500,
                message="🤖 AI phân tích dàn ý, tạo quy hoạch chương..."
            )
        
        chapter_plans = await expansion_service.analyze_outline_for_chapters(
            outline=outline,
            project=project,
            db=db,
            target_chapter_count=target_chapter_count,
            expansion_strategy=expansion_strategy,
            enable_scene_analysis=enable_scene_analysis,
            provider=data.get("provider"),
            model=data.get("model"),
            batch_size=batch_size,
            progress_callback=None  # Trong SSE tạm thời không hỗ trợ callback lồng nhau
        )
        
        if not chapter_plans:
            yield await tracker.error("AI phân tích thất bại, không tạo được quy hoạch chương", 500)
            return
        
        yield await tracker.parsing(
            f"✅ Tạo quy hoạch xong! Tổng {len(chapter_plans)} chương"
        )
        
        # Quyết định có tạo bản ghi chương không dựa vào cấu hình
        created_chapters = None
        if auto_create_chapters:
            yield await tracker.saving("💾 Đang tạo bản ghi chương...", 0.3)
            
            created_chapters = await expansion_service.create_chapters_from_plans(
                outline_id=outline_id,
                chapter_plans=chapter_plans,
                project_id=outline.project_id,
                db=db,
                start_chapter_number=None  # Tự động tính số thứ tự chương
            )
            
            await db.commit()
            db_committed = True
            
            # Làm mới dữ liệu chương
            for chapter in created_chapters:
                await db.refresh(chapter)
            
            yield await tracker.saving(
                f"✅ Tạo thành công {len(created_chapters)} bản ghi chương",
                0.8
            )
        
        yield await tracker.complete()
        
        # Xây dựng dữ liệu response
        result_data = {
            "outline_id": outline_id,
            "outline_title": outline.title,
            "target_chapter_count": target_chapter_count,
            "actual_chapter_count": len(chapter_plans),
            "expansion_strategy": expansion_strategy,
            "chapter_plans": chapter_plans,
            "created_chapters": [
                {
                    "id": ch.id,
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "summary": ch.summary,
                    "outline_id": ch.outline_id,
                    "sub_index": ch.sub_index,
                    "status": ch.status
                }
                for ch in created_chapters
            ] if created_chapters else None
        }
        
        yield await tracker.result(result_data)
        yield await tracker.done()
        
    except GeneratorExit:
        logger.warning("Trình tạo triển khai dàn ý bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch triển khai dàn ý (GeneratorExit)")
    except Exception as e:
        logger.error(f"Triển khai dàn ý thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch triển khai dàn ý (ngoại lệ)")
        yield await tracker.error(f"Triển khai thất bại: {str(e)}")


async def _save_background_task_result(db: AsyncSession, task_id: str, result_data: Dict[str, Any]) -> None:
    """Lưu kết quả tác vụ nền vào background_tasks.task_result."""
    from app.models.background_task import BackgroundTask

    task_result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task:
        task.task_result = result_data
        await db.commit()


async def _run_outline_expansion_background(
    task_id: str,
    user_id: str,
    outline_id: str,
    data: Dict[str, Any]
):
    """Chạy nền triển khai một dàn ý và có thể tạo chương trực tiếp."""
    from app.database import get_engine
    from app.api.settings import get_user_ai_service_from_db
    from app.services.background_task_service import TaskProgressTracker
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as BgAsyncSession

    engine = await get_engine(user_id)
    AsyncSessionLocal = async_sessionmaker(engine, class_=BgAsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as bg_db:
        tracker = TaskProgressTracker(task_id, user_id, "Triển khai dàn ý")
        try:
            await tracker.start("Bắt đầu tác vụ triển khai dàn ý...")

            target_chapter_count = int(data.get("target_chapter_count", 3))
            expansion_strategy = data.get("expansion_strategy", "balanced")
            enable_scene_analysis = data.get("enable_scene_analysis", True)
            auto_create_chapters = data.get("auto_create_chapters", True)
            batch_size = int(data.get("batch_size", 5))

            await tracker.loading("Đang tải thông tin dàn ý...", 0.3)
            outline_result = await bg_db.execute(select(Outline).where(Outline.id == outline_id))
            outline = outline_result.scalar_one_or_none()
            if not outline:
                raise ValueError("Dàn ý không tồn tại")

            await tracker.loading("Đang tải thông tin dự án...", 0.7)
            project_result = await bg_db.execute(select(Project).where(Project.id == outline.project_id))
            project = project_result.scalar_one_or_none()
            if not project:
                raise ValueError("Dự án không tồn tại")

            if await tracker.check_cancelled():
                return

            await tracker.preparing(f"Đang chuẩn bị triển khai《{outline.title}》thành {target_chapter_count} chương...")

            bg_ai_service = await get_user_ai_service_from_db(user_id, bg_db)
            expansion_service = PlotExpansionService(bg_ai_service)

            await tracker.generating(
                current_chars=0,
                estimated_total=target_chapter_count * 500,
                message=f"AI phân tích dàn ý《{outline.title}》, tạo quy hoạch chương..."
            )


            chapter_plans = await expansion_service.analyze_outline_for_chapters(
                outline=outline,
                project=project,
                db=bg_db,
                target_chapter_count=target_chapter_count,
                expansion_strategy=expansion_strategy,
                enable_scene_analysis=enable_scene_analysis,
                provider=data.get("provider"),
                model=data.get("model"),
                batch_size=batch_size,
                progress_callback=None
            )

            if await tracker.check_cancelled():
                return
            if not chapter_plans:
                raise ValueError("AI phân tích thất bại, không tạo được quy hoạch chương")

            await tracker.parsing(f"Tạo quy hoạch xong, tổng {len(chapter_plans)} chương")

            created_chapters = None
            if auto_create_chapters:
                await tracker.saving("Đang tạo bản ghi chương...", 0.3)
                created_chapters = await expansion_service.create_chapters_from_plans(
                    outline_id=outline_id,
                    chapter_plans=chapter_plans,
                    project_id=outline.project_id,
                    db=bg_db,
                    start_chapter_number=None
                )
                await tracker.saving(f"Tạo thành công {len(created_chapters)} bản ghi chương", 0.8)

            result_data = {
                "outline_id": outline_id,
                "outline_title": outline.title,
                "target_chapter_count": target_chapter_count,
                "actual_chapter_count": len(chapter_plans),
                "expansion_strategy": expansion_strategy,
                "chapter_plans": chapter_plans,
                "created_chapters": [
                    {
                        "id": ch.id,
                        "chapter_number": ch.chapter_number,
                        "title": ch.title,
                        "summary": ch.summary,
                        "outline_id": ch.outline_id,
                        "sub_index": ch.sub_index,
                        "status": ch.status
                    }
                    for ch in created_chapters
                ] if created_chapters else None
            }
            await _save_background_task_result(bg_db, task_id, result_data)
            await tracker.complete(f"《{outline.title}》triển khai xong")
        except Exception as e:
            logger.error(f"Triển khai dàn ý nền thất bại: {str(e)}", exc_info=True)
            try:
                if bg_db.in_transaction():
                    await bg_db.rollback()
            except Exception:
                pass
            await tracker.error(str(e))


async def _run_batch_outline_expansion_background(
    task_id: str,
    user_id: str,
    data: Dict[str, Any]
):
    """Chạy nền triển khai hàng loạt dàn ý và có thể tạo chương trực tiếp."""
    from app.database import get_engine
    from app.api.settings import get_user_ai_service_from_db
    from app.services.background_task_service import TaskProgressTracker
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as BgAsyncSession

    engine = await get_engine(user_id)
    AsyncSessionLocal = async_sessionmaker(engine, class_=BgAsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as bg_db:
        tracker = TaskProgressTracker(task_id, user_id, "Triển khai hàng loạt dàn ý")
        try:
            await tracker.start("Bắt đầu tác vụ triển khai hàng loạt dàn ý...")

            project_id = data.get("project_id")
            chapters_per_outline = int(data.get("chapters_per_outline", 3))
            expansion_strategy = data.get("expansion_strategy", "balanced")
            auto_create_chapters = data.get("auto_create_chapters", True)
            outline_ids = data.get("outline_ids")

            await tracker.loading("Đang tải thông tin dự án...", 0.4)
            project_result = await bg_db.execute(select(Project).where(Project.id == project_id))
            project = project_result.scalar_one_or_none()
            if not project:
                raise ValueError("Dự án không tồn tại")

            await tracker.loading("Đang lấy danh sách dàn ý...", 0.8)
            if outline_ids:
                outlines_result = await bg_db.execute(
                    select(Outline)
                    .where(Outline.project_id == project_id, Outline.id.in_(outline_ids))
                    .order_by(Outline.order_index)
                )
            else:
                outlines_result = await bg_db.execute(
                    select(Outline)
                    .where(Outline.project_id == project_id)
                    .order_by(Outline.order_index)
                )
            outlines = outlines_result.scalars().all()
            if not outlines:
                raise ValueError("Không tìm thấy dàn ý cần triển khai")

            total_outlines = len(outlines)
            await tracker.preparing(f"Tìm thấy {total_outlines} dàn ý, đang chuẩn bị triển khai hàng loạt...")

            bg_ai_service = await get_user_ai_service_from_db(user_id, bg_db)
            expansion_service = PlotExpansionService(bg_ai_service)

            expansion_results = []
            skipped_outlines = []
            total_chapters_created = 0

            for idx, outline in enumerate(outlines):
                if await tracker.check_cancelled():
                    return

                await tracker.generating(
                    current_chars=idx * chapters_per_outline * 500,
                    estimated_total=total_outlines * chapters_per_outline * 500,
                    message=f"Đang xử lý dàn ý {idx + 1}/{total_outlines}: 《{outline.title}》"
                )

                existing_chapters_result = await bg_db.execute(
                    select(Chapter).where(Chapter.outline_id == outline.id).limit(1)
                )
                existing_chapter = existing_chapters_result.scalar_one_or_none()
                if existing_chapter:
                    skipped_outlines.append({
                        "outline_id": outline.id,
                        "outline_title": outline.title,
                        "reason": "Đã triển khai"
                    })
                    await tracker.warning(f"《{outline.title}》đã triển khai, đã bỏ qua")
                    continue

                chapter_plans = await expansion_service.analyze_outline_for_chapters(
                    outline=outline,
                    project=project,
                    db=bg_db,
                    target_chapter_count=chapters_per_outline,
                    expansion_strategy=expansion_strategy,
                    enable_scene_analysis=data.get("enable_scene_analysis", True),
                    provider=data.get("provider"),
                    model=data.get("model")
                )

                created_chapters = None
                if auto_create_chapters:
                    created_chapters = await expansion_service.create_chapters_from_plans(
                        outline_id=outline.id,
                        chapter_plans=chapter_plans,
                        project_id=outline.project_id,
                        db=bg_db,
                        start_chapter_number=None
                    )
                    total_chapters_created += len(created_chapters)

                expansion_results.append({
                    "outline_id": outline.id,
                    "outline_title": outline.title,
                    "target_chapter_count": chapters_per_outline,
                    "actual_chapter_count": len(chapter_plans),
                    "expansion_strategy": expansion_strategy,
                    "chapter_plans": chapter_plans,
                    "created_chapters": [
                        {
                            "id": ch.id,
                            "chapter_number": ch.chapter_number,
                            "title": ch.title,
                            "summary": ch.summary,
                            "outline_id": ch.outline_id,
                            "sub_index": ch.sub_index,
                            "status": ch.status
                        }
                        for ch in created_chapters
                    ] if created_chapters else None
                })

                await tracker.generating(
                    current_chars=(idx + 1) * chapters_per_outline * 500,
                    estimated_total=total_outlines * chapters_per_outline * 500,
                    message=f"《{outline.title}》triển khai xong ({len(chapter_plans)} chương)"
                )

            await tracker.parsing("Đang tổng hợp kết quả triển khai hàng loạt...")
            result_data = {
                "project_id": project_id,
                "total_outlines_expanded": len(expansion_results),
                "total_chapters_created": total_chapters_created,
                "skipped_count": len(skipped_outlines),
                "skipped_outlines": skipped_outlines,
                "expansion_results": expansion_results
            }
            await _save_background_task_result(bg_db, task_id, result_data)
            await tracker.complete(f"Triển khai hàng loạt xong, đã tạo {total_chapters_created} chương")
        except Exception as e:
            logger.error(f"Triển khai hàng loạt dàn ý nền thất bại: {str(e)}", exc_info=True)
            try:
                if bg_db.in_transaction():
                    await bg_db.rollback()
            except Exception:
                pass
            await tracker.error(str(e))


@router.post("/{outline_id}/create-single-chapter", summary="Tạo một chương theo một-một (chế độ truyền thống)")
async def create_single_chapter_from_outline(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Chế độ truyền thống: một dàn ý tương ứng tạo một chương
    
    Trường hợp áp dụng:
    - outline_mode của dự án là 'one-to-one'
    - Lấy trực tiếp nội dung dàn ý làm tóm tắt chương
    - Không gọi AI, không triển khai
    
    Luồng:
    1. Kiểm tra chế độ dự án là one-to-one
    2. Kiểm tra dàn ý đã tạo chương chưa
    3. Tạo bản ghi chương (outline_id=NULL, chapter_number=outline.order_index)
    
    Trả về: thông tin chương đã tạo
    """
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    
    # Lấy dàn ý
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền dự án và lấy thông tin dự án

    project = await verify_project_access(outline.project_id, user_id, db)
    
    # Kiểm tra chế độ dự án
    if project.outline_mode != 'one-to-one':
        raise HTTPException(
            status_code=400,
            detail=f"Dự án hiện đang ở chế độ {project.outline_mode}, không hỗ trợ tạo một-một. Vui lòng dùng chức năng triển khai."
        )
    
    # Kiểm tra chương của dàn ý đã tồn tại chưa
    existing_chapter_result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == outline.project_id,
            Chapter.chapter_number == outline.order_index,
            Chapter.sub_index == 1
        )
    )
    existing_chapter = existing_chapter_result.scalar_one_or_none()
    
    if existing_chapter:
        raise HTTPException(
            status_code=400,
            detail=f"Chương {outline.order_index} đã tồn tại, không thể tạo trùng"
        )
    
    try:
        # Tạo chương (outline_id=NULL nghĩa là chế độ một-một)
        new_chapter = Chapter(
            project_id=outline.project_id,
            title=outline.title,
            summary=outline.content,  # Dùng nội dung dàn ý làm tóm tắt
            chapter_number=outline.order_index,
            sub_index=1,  # Chế độ một-một cố định là 1
            outline_id=None,  # Chế độ truyền thống không liên kết outline_id
            status='pending'
        )
        
        db.add(new_chapter)
        await db.commit()
        await db.refresh(new_chapter)
        
        logger.info(f"Chế độ một-một: tạo chương {new_chapter.chapter_number} cho dàn ý {outline.title}")
        
        return {
            "message": "Tạo chương thành công",
            "chapter": {
                "id": new_chapter.id,
                "project_id": new_chapter.project_id,
                "title": new_chapter.title,
                "summary": new_chapter.summary,
                "chapter_number": new_chapter.chapter_number,
                "sub_index": new_chapter.sub_index,
                "outline_id": new_chapter.outline_id,
                "status": new_chapter.status,
                "created_at": new_chapter.created_at.isoformat() if new_chapter.created_at else None
            }
        }
        
    except Exception as e:
        logger.error(f"Tạo chương một-một thất bại: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Tạo chương thất bại: {str(e)}")


@router.post("/{outline_id}/expand-background", summary="Nền triển khai một dàn ý thành nhiều chương")
async def expand_outline_to_chapters_background(
    outline_id: str,
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tạo tác vụ nền triển khai một dàn ý, sau khi xong có thể xem kết quả ở bảng tác vụ nền góc dưới bên phải."""
    result = await db.execute(select(Outline).where(Outline.id == outline_id))
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")

    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)

    from app.services.background_task_service import background_task_service

    task_input = dict(data or {})
    task_input["outline_id"] = outline_id
    task_input.setdefault("auto_create_chapters", True)

    task = await background_task_service.create_task(
        user_id=user_id,
        project_id=outline.project_id,
        task_type="outline_expand",
        task_input=task_input,
        db=db
    )

    await background_task_service.spawn_background_task(
        task.id, user_id, _run_outline_expansion_background, outline_id, task_input
    )

    return {
        "task_id": task.id,
        "task_type": "outline_expand",
        "status": "pending",
        "message": "Đã tạo tác vụ triển khai dàn ý, vui lòng xem tiến trình ở bảng tác vụ nền"
    }


@router.post("/{outline_id}/expand-stream", summary="Triển khai một dàn ý thành nhiều chương (streaming SSE)")
async def expand_outline_to_chapters_stream(
    outline_id: str,
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE streaming triển khai một dàn ý, đẩy tiến trình theo thời gian thực
    
    Ví dụ request body:
    {
        "target_chapter_count": 3,  // số chương mục tiêu
        "expansion_strategy": "balanced",  // balanced/climax/detail
        "auto_create_chapters": false,  // có tự động tạo chương không
        "enable_scene_analysis": true,  // có bật phân tích cảnh không
        "provider": "openai",  // tùy chọn
        "model": "gpt-4"  // tùy chọn
    }
    
    Các giai đoạn tiến trình:
    - 5% - Bắt đầu triển khai
    - 10% - Tải thông tin dàn ý
    - 15% - Tải thông tin dự án
    - 20% - Chuẩn bị tham số triển khai
    - 30% - AI phân tích dàn ý (tốn thời gian)
    - 70% - Tạo quy hoạch xong
    - 80% - Tạo bản ghi chương (nếu auto_create_chapters=True)
    - 90% - Tạo xong
    - 95% - Tổng hợp dữ liệu kết quả
    - 100% - Hoàn tất
    """
    # Lấy dàn ý và kiểm tra quyền
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    return create_sse_response(expand_outline_generator(outline_id, data, db, user_ai_service))


@router.get("/{outline_id}/chapters", summary="Lấy các chương liên kết với dàn ý")
async def get_outline_chapters(
    outline_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy danh sách chương đã triển khai từ dàn ý chỉ định
    
    Dùng để kiểm tra dàn ý đã triển khai chưa, nếu có thì trả về thông tin chương
    """
    # Lấy dàn ý
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(outline.project_id, user_id, db)
    
    # Truy vấn các chương liên kết với dàn ý
    chapters_result = await db.execute(
        select(Chapter)
        .where(Chapter.outline_id == outline_id)
        .order_by(Chapter.sub_index)
    )
    chapters = chapters_result.scalars().all()
    
    # Nếu có chương, phân tích quy hoạch triển khai
    expansion_plans = []
    if chapters:
        for chapter in chapters:
            plan_data = None
            if chapter.expansion_plan:
                try:
                    plan_data = json.loads(chapter.expansion_plan)
                except json.JSONDecodeError:
                    logger.warning(f"Chương {chapter.id} phân tích expansion_plan thất bại")
                    plan_data = None
            
            expansion_plans.append({
                "sub_index": chapter.sub_index,
                "title": chapter.title,
                "plot_summary": chapter.summary or "",
                "key_events": plan_data.get("key_events", []) if plan_data else [],
                "character_focus": plan_data.get("character_focus", []) if plan_data else [],
                "emotional_tone": plan_data.get("emotional_tone", "") if plan_data else "",
                "narrative_goal": plan_data.get("narrative_goal", "") if plan_data else "",
                "conflict_type": plan_data.get("conflict_type", "") if plan_data else "",
                "estimated_words": plan_data.get("estimated_words", 0) if plan_data else 0,
                "scenes": plan_data.get("scenes") if plan_data else None
            })
    
    return {
        "has_chapters": len(chapters) > 0,
        "outline_id": outline_id,
        "outline_title": outline.title,
        "chapter_count": len(chapters),
        "chapters": [
            {
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "summary": ch.summary,
                "sub_index": ch.sub_index,
                "status": ch.status,
                "word_count": ch.word_count
            }
            for ch in chapters
        ],
        "expansion_plans": expansion_plans if expansion_plans else None
    }


async def batch_expand_outlines_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo SSE triển khai hàng loạt dàn ý - đẩy tiến trình theo thời gian thực"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Triển khai hàng loạt dàn ý")
    
    try:
        yield await tracker.start()
        
        project_id = data.get("project_id")
        chapters_per_outline = int(data.get("chapters_per_outline", 3))
        expansion_strategy = data.get("expansion_strategy", "balanced")
        auto_create_chapters = data.get("auto_create_chapters", False)

        outline_ids = data.get("outline_ids")
        
        # Lấy thông tin dự án
        yield await tracker.loading("Đang tải thông tin dự án...", 0.5)
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            yield await tracker.error("Dự án không tồn tại", 404)
            return
        
        # Lấy danh sách dàn ý cần triển khai
        yield await tracker.loading("Đang lấy danh sách dàn ý...", 0.8)
        if outline_ids:
            outlines_result = await db.execute(
                select(Outline)
                .where(
                    Outline.project_id == project_id,
                    Outline.id.in_(outline_ids)
                )
                .order_by(Outline.order_index)
            )
        else:
            outlines_result = await db.execute(
                select(Outline)
                .where(Outline.project_id == project_id)
                .order_by(Outline.order_index)
            )
        
        outlines = outlines_result.scalars().all()
        
        if not outlines:
            yield await tracker.error("Không tìm thấy dàn ý cần triển khai", 404)
            return
        
        total_outlines = len(outlines)
        yield await tracker.preparing(
            f"Tìm thấy {total_outlines} dàn ý, bắt đầu triển khai hàng loạt..."
        )
        
        # Tạo instance dịch vụ triển khai
        expansion_service = PlotExpansionService(user_ai_service)
        
        expansion_results = []
        total_chapters_created = 0
        skipped_outlines = []
        
        for idx, outline in enumerate(outlines):
            try:
                # Tính tiến trình con hiện tại (0.0-1.0) cho giai đoạn generating
                sub_progress = idx / max(total_outlines, 1)
                
                yield await tracker.generating(
                    current_chars=idx * chapters_per_outline * 500,
                    estimated_total=total_outlines * chapters_per_outline * 500,
                    message=f"📝 Đang xử lý dàn ý {idx + 1}/{total_outlines}: {outline.title}"
                )
                
                # Kiểm tra dàn ý đã triển khai chưa
                existing_chapters_result = await db.execute(
                    select(Chapter)
                    .where(Chapter.outline_id == outline.id)
                    .limit(1)
                )
                existing_chapter = existing_chapters_result.scalar_one_or_none()
                
                if existing_chapter:
                    logger.info(f"Dàn ý {outline.title} (ID: {outline.id}) đã triển khai, bỏ qua")
                    skipped_outlines.append({
                        "outline_id": outline.id,
                        "outline_title": outline.title,
                        "reason": "Đã triển khai"
                    })
                    yield await tracker.generating(
                        current_chars=(idx + 1) * chapters_per_outline * 500,
                        estimated_total=total_outlines * chapters_per_outline * 500,
                        message=f"⏭️ {outline.title} đã triển khai, bỏ qua"
                    )
                    continue
                
                # Phân tích dàn ý tạo quy hoạch chương
                yield await tracker.generating(
                    current_chars=idx * chapters_per_outline * 500,
                    estimated_total=total_outlines * chapters_per_outline * 500,
                    message=f"🤖 AI phân tích dàn ý: {outline.title}"
                )
                
                chapter_plans = await expansion_service.analyze_outline_for_chapters(
                    outline=outline,
                    project=project,
                    db=db,
                    target_chapter_count=chapters_per_outline,
                    expansion_strategy=expansion_strategy,
                    enable_scene_analysis=data.get("enable_scene_analysis", True),
                    provider=data.get("provider"),
                    model=data.get("model")
                )
                
                yield await tracker.generating(
                    current_chars=(idx + 0.5) * chapters_per_outline * 500,
                    estimated_total=total_outlines * chapters_per_outline * 500,
                    message=f"✅ {outline.title} tạo quy hoạch xong ({len(chapter_plans)} chương)"
                )
                
                created_chapters = None
                if auto_create_chapters:
                    # Tạo bản ghi chương
                    chapters = await expansion_service.create_chapters_from_plans(
                        outline_id=outline.id,
                        chapter_plans=chapter_plans,
                        project_id=outline.project_id,
                        db=db,
                        start_chapter_number=None  # Tự động tính số thứ tự chương
                    )
                    created_chapters = [
                        {
                            "id": ch.id,
                            "chapter_number": ch.chapter_number,
                            "title": ch.title,
                            "summary": ch.summary,
                            "outline_id": ch.outline_id,
                            "sub_index": ch.sub_index,
                            "status": ch.status
                        }
                        for ch in chapters
                    ]
                    total_chapters_created += len(chapters)
                    
                    yield await tracker.generating(
                        current_chars=(idx + 1) * chapters_per_outline * 500,
                        estimated_total=total_outlines * chapters_per_outline * 500,
                        message=f"💾 {outline.title} tạo chương xong ({len(chapters)} chương)"
                    )
                
                expansion_results.append({
                    "outline_id": outline.id,
                    "outline_title": outline.title,
                    "target_chapter_count": chapters_per_outline,
                    "actual_chapter_count": len(chapter_plans),
                    "expansion_strategy": expansion_strategy,
                    "chapter_plans": chapter_plans,
                    "created_chapters": created_chapters
                })
                
                logger.info(f"Dàn ý {outline.title} triển khai xong, tạo {len(chapter_plans)} quy hoạch chương")
                
            except Exception as e:
                logger.error(f"Triển khai dàn ý {outline.id} thất bại: {str(e)}", exc_info=True)
                yield await tracker.warning(
                    f"❌ {outline.title} triển khai thất bại: {str(e)}"
                )
                expansion_results.append({
                    "outline_id": outline.id,
                    "outline_title": outline.title,
                    "target_chapter_count": chapters_per_outline,
                    "actual_chapter_count": 0,
                    "expansion_strategy": expansion_strategy,
                    "chapter_plans": [],
                    "created_chapters": None,
                    "error": str(e)
                })
        
        yield await tracker.parsing("Đang tổng hợp dữ liệu kết quả...")
        
        db_committed = True
        
        logger.info(f"Triển khai hàng loạt xong: {len(expansion_results)} dàn ý, bỏ qua {len(skipped_outlines)}, tổng tạo {total_chapters_created} chương")
        
        yield await tracker.complete()
        
        # Gửi kết quả cuối
        result_data = {
            "project_id": project_id,
            "total_outlines_expanded": len(expansion_results),
            "total_chapters_created": total_chapters_created,
            "skipped_count": len(skipped_outlines),
            "skipped_outlines": skipped_outlines,
            "expansion_results": [
                {
                    "outline_id": result["outline_id"],
                    "outline_title": result["outline_title"],
                    "target_chapter_count": result["target_chapter_count"],
                    "actual_chapter_count": result["actual_chapter_count"],
                    "expansion_strategy": result["expansion_strategy"],
                    "chapter_plans": result["chapter_plans"],
                    "created_chapters": result.get("created_chapters")
                }
                for result in expansion_results
            ]
        }
        
        yield await tracker.result(result_data)
        yield await tracker.done()
        
    except GeneratorExit:
        logger.warning("Trình tạo triển khai hàng loạt bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch triển khai hàng loạt (GeneratorExit)")
    except Exception as e:
        logger.error(f"Triển khai hàng loạt thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch triển khai hàng loạt (ngoại lệ)")
        yield await SSEResponse.send_error(f"Triển khai hàng loạt thất bại: {str(e)}")


@router.post("/batch-expand-background", summary="Nền triển khai hàng loạt dàn ý thành nhiều chương")
async def batch_expand_outlines_background(
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tạo tác vụ nền triển khai hàng loạt dàn ý, sau khi xong có thể xem kết quả ở bảng tác vụ nền góc dưới bên phải."""
    user_id = getattr(request.state, 'user_id', None)
    project = await verify_project_access(data.get("project_id"), user_id, db)

    from app.services.background_task_service import background_task_service

    task_input = dict(data or {})
    task_input.setdefault("auto_create_chapters", True)

    task = await background_task_service.create_task(
        user_id=user_id,
        project_id=project.id,
        task_type="outline_batch_expand",
        task_input=task_input,
        db=db
    )

    await background_task_service.spawn_background_task(
        task.id, user_id, _run_batch_outline_expansion_background, task_input
    )

    return {
        "task_id": task.id,
        "task_type": "outline_batch_expand",
        "status": "pending",
        "message": "Đã tạo tác vụ triển khai hàng loạt dàn ý, vui lòng xem tiến trình ở bảng tác vụ nền"
    }


@router.post("/batch-expand-stream", summary="Triển khai hàng loạt dàn ý thành nhiều chương (streaming SSE)")
async def batch_expand_outlines_stream(
    data: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):

    """
    Dùng SSE streaming triển khai hàng loạt dàn ý, đẩy tiến trình xử lý từng dàn ý theo thời gian thực
    
    Ví dụ request body:
    {
        "project_id": "ID dự án",
        "outline_ids": ["ID dàn ý 1", "ID dàn ý 2"],  // tùy chọn, không truyền thì triển khai tất cả dàn ý
        "chapters_per_outline": 3,  // mỗi dàn ý triển khai thành mấy chương
        "expansion_strategy": "balanced",  // balanced/climax/detail
        "auto_create_chapters": false,  // có tự động tạo chương không
        "enable_scene_analysis": true,  // có bật phân tích cảnh không
        "provider": "openai",  // tùy chọn
        "model": "gpt-4"  // tùy chọn
    }
    """
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(data.get("project_id"), user_id, db)
    
    return create_sse_response(batch_expand_outlines_generator(data, db, user_ai_service))


@router.post("/{outline_id}/create-chapters-from-plans", response_model=CreateChaptersFromPlansResponse, summary="Tạo chương từ quy hoạch có sẵn")
async def create_chapters_from_existing_plans(
    outline_id: str,
    plans_request: CreateChaptersFromPlansRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Tạo trực tiếp bản ghi chương từ quy hoạch chương đã có trong cache frontend, tránh gọi lại AI
    
    Kịch bản sử dụng:
    1. Người dùng lần đầu gọi /outlines/{outline_id}/expand?auto_create_chapters=false để lấy bản xem trước quy hoạch
    2. Frontend hiển thị quy hoạch cho người dùng xác nhận
    3. Người dùng xác nhận xong, frontend gọi endpoint này, truyền dữ liệu quy hoạch đã cache để tạo chương trực tiếp
    
    Ưu điểm:
    - Tránh gọi AI trùng lặp, tiết kiệm token và thời gian
    - Đảm bảo bản xem trước người dùng thấy hoàn toàn khớp với chương thực tế được tạo
    - Nâng cao trải nghiệm người dùng
    
    Tham số:
    - outline_id: ID dàn ý cần triển khai
    - plans_request: chứa danh sách quy hoạch chương do AI tạo trước đó
    
    Trả về:
    - Danh sách chương đã tạo và thông tin thống kê
    """
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    
    # Lấy dàn ý
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Dàn ý không tồn tại")
    
    # Kiểm tra quyền dự án
    await verify_project_access(outline.project_id, user_id, db)
    
    try:
        # Kiểm tra dữ liệu quy hoạch
        if not plans_request.chapter_plans:
            raise HTTPException(status_code=400, detail="Danh sách quy hoạch chương không được để trống")
        
        logger.info(f"Tạo {len(plans_request.chapter_plans)} chương cho dàn ý {outline_id} từ quy hoạch có sẵn")
        
        # Tạo instance dịch vụ triển khai
        expansion_service = PlotExpansionService(user_ai_service)
        
        # Chuyển model Pydantic thành danh sách dict
        chapter_plans_dict = [plan.model_dump() for plan in plans_request.chapter_plans]
        
        # Dùng trực tiếp quy hoạch được truyền để tạo bản ghi chương (không gọi AI)
        created_chapters = await expansion_service.create_chapters_from_plans(
            outline_id=outline_id,
            chapter_plans=chapter_plans_dict,
            project_id=outline.project_id,
            db=db,
            start_chapter_number=None  # Tự động tính số thứ tự chương
        )
        
        await db.commit()
        
        # Làm mới dữ liệu chương
        for chapter in created_chapters:
            await db.refresh(chapter)
        
        logger.info(f"Tạo thành công {len(created_chapters)} bản ghi chương từ quy hoạch có sẵn")
        
        # Xây dựng response
        return CreateChaptersFromPlansResponse(
            outline_id=outline_id,
            outline_title=outline.title,
            chapters_created=len(created_chapters),
            created_chapters=[
                {
                    "id": ch.id,
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "summary": ch.summary,
                    "outline_id": ch.outline_id,
                    "sub_index": ch.sub_index,
                    "status": ch.status
                }
                for ch in created_chapters
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tạo chương từ quy hoạch có sẵn thất bại: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Tạo chương thất bại: {str(e)}")
