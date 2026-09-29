"""API quản lý ký ức - cung cấp các giao diện truy vấn, phân tích ký ức"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, delete
from typing import List, Optional
from app.database import get_db
from app.models.memory import StoryMemory, PlotAnalysis
from app.models.chapter import Chapter
from app.models.project import Project
from app.services.memory_service import memory_service
from app.services.plot_analyzer import get_plot_analyzer
from app.services.foreshadow_service import foreshadow_service
from app.services.ai_service import create_user_ai_service
from app.models.settings import Settings
from app.api.settings import resolve_runtime_ai_config
from app.logger import get_logger
from app.api.common import verify_project_access
import uuid

logger = get_logger(__name__)
router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.post("/projects/{project_id}/analyze-chapter/{chapter_id}")
async def analyze_chapter(
    project_id: str,
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Phân tích chương và tạo ký ức

    Phân tích cốt truyện của chương đã chỉ định, trích xuất hook, nút thắt, điểm nút cốt truyện v.v., rồi lưu vào hệ thống ký ức
    """
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        # Lấy nội dung chương
        result = await db.execute(
            select(Chapter).where(
                and_(
                    Chapter.id == chapter_id,
                    Chapter.project_id == project_id
                )
            )
        )
        chapter = result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(status_code=404, detail="Chương không tồn tại")

        if not chapter.content:
            raise HTTPException(status_code=400, detail="Nội dung chương trống, không thể phân tích")

        # Lấy cài đặt AI của người dùng
        settings_result = await db.execute(select(Settings).where(Settings.user_id == user_id))
        settings = settings_result.scalar_one_or_none()

        if not settings:
            raise HTTPException(status_code=400, detail="Vui lòng cấu hình cài đặt AI trước")

        runtime_config = resolve_runtime_ai_config(settings.api_provider, settings.api_key, settings.api_base_url)

        # Tạo dịch vụ AI
        ai_service = create_user_ai_service(
            api_provider=runtime_config["api_provider"],
            api_key=runtime_config["api_key"],
            api_base_url=runtime_config["api_base_url"],
            model_name=settings.llm_model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens
        )

        # Lấy danh sách nút thắt đã chôn (dùng để khớp khi thu hồi)
        existing_foreshadows = await foreshadow_service.get_planted_foreshadows_for_analysis(
            db=db,
            project_id=project_id
        )
        logger.info(f"Đã lấy {len(existing_foreshadows)} nút thắt đã chôn để khớp phân tích")

        # Thực hiện phân tích cốt truyện (truyền vào danh sách nút thắt hiện có)
        analyzer = get_plot_analyzer(ai_service)
        analysis_result = await analyzer.analyze_chapter(
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            content=chapter.content,
            word_count=chapter.word_count or len(chapter.content),
            user_id=user_id,
            db=db,
            existing_foreshadows=existing_foreshadows
        )

        if not analysis_result:
            raise HTTPException(status_code=500, detail="Phân tích cốt truyện thất bại")

        # Lưu kết quả phân tích vào database
        plot_analysis = PlotAnalysis(
            id=str(uuid.uuid4()),
            project_id=project_id,
            chapter_id=chapter_id,
            plot_stage=analysis_result.get('plot_stage'),
            conflict_level=analysis_result.get('conflict', {}).get('level'),
            conflict_types=analysis_result.get('conflict', {}).get('types'),
            emotional_tone=analysis_result.get('emotional_arc', {}).get('primary_emotion'),
            emotional_intensity=analysis_result.get('emotional_arc', {}).get('intensity', 0) / 10,
            emotional_curve=analysis_result.get('emotional_arc'),
            hooks=analysis_result.get('hooks'),
            hooks_count=len(analysis_result.get('hooks', [])),
            hooks_avg_strength=sum(h.get('strength', 0) for h in analysis_result.get('hooks', [])) / max(len(analysis_result.get('hooks', [])), 1),
            foreshadows=analysis_result.get('foreshadows'),
            foreshadows_planted=sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'planted'),
            foreshadows_resolved=sum(1 for f in analysis_result.get('foreshadows', []) if f.get('type') == 'resolved'),
            plot_points=analysis_result.get('plot_points'),
            plot_points_count=len(analysis_result.get('plot_points', [])),
            character_states=analysis_result.get('character_states'),
            scenes=analysis_result.get('scenes'),
            pacing=analysis_result.get('pacing'),
            dialogue_ratio=analysis_result.get('dialogue_ratio'),
            description_ratio=analysis_result.get('description_ratio'),
            overall_quality_score=analysis_result.get('scores', {}).get('overall'),
            pacing_score=analysis_result.get('scores', {}).get('pacing'),
            engagement_score=analysis_result.get('scores', {}).get('engagement'),
            coherence_score=analysis_result.get('scores', {}).get('coherence'),
            analysis_report=analyzer.generate_analysis_summary(analysis_result),
            suggestions=analysis_result.get('suggestions'),
            word_count=chapter.word_count
        )

        # Kiểm tra đã có bản ghi phân tích chưa, nếu có thì xóa
        existing_result = await db.execute(
            select(PlotAnalysis).where(PlotAnalysis.chapter_id == chapter_id)
        )
        existing_analysis = existing_result.scalar_one_or_none()
        if existing_analysis:
            await db.delete(existing_analysis)
            await db.flush()

        db.add(plot_analysis)
        await db.commit()

        # Trích xuất đoạn ký ức từ kết quả phân tích
        memories_data = analyzer.extract_memories_from_analysis(
            analysis_result,
            chapter_id,
            chapter.chapter_number
        )

        # Trước khi phân tích lại, dọn ký ức cũ của chương (database quan hệ + vector)
        old_memories_result = await db.execute(
            select(StoryMemory).where(StoryMemory.chapter_id == chapter_id)
        )
        old_memories = old_memories_result.scalars().all()
        for old_mem in old_memories:
            await db.delete(old_mem)
        await db.flush()

        if user_id:
            try:
                await memory_service.delete_chapter_memories(
                    user_id=user_id,
                    project_id=project_id,
                    chapter_id=chapter_id
                )
            except Exception as vector_delete_error:
                logger.warning(f"Cảnh báo: dọn ký ức vector của chương thất bại (tiếp tục phân tích): {str(vector_delete_error)}")

        # Lưu ký ức vào database và vector store
        saved_count = 0
        for mem_data in memories_data:
            memory_id = str(uuid.uuid4())

            # Lưu vào database quan hệ
            memory = StoryMemory(
                id=memory_id,
                project_id=project_id,
                chapter_id=chapter_id,
                memory_type=mem_data['type'],
                title=mem_data.get('title', ''),
                content=mem_data['content'],
                story_timeline=chapter.chapter_number,
                vector_id=memory_id,
                **mem_data['metadata']
            )
            db.add(memory)

            # Lưu vào vector store
            await memory_service.add_memory(
                user_id=user_id,
                project_id=project_id,
                memory_id=memory_id,
                content=mem_data['content'],
                memory_type=mem_data['type'],
                metadata=mem_data['metadata']
            )
            saved_count += 1

        await db.commit()

        entity_changes = {
            "careers": {"updated_count": 0, "changes": []},
            "character_states": {
                "state_updated_count": 0,
                "relationship_created_count": 0,
                "relationship_updated_count": 0,
                "org_updated_count": 0,
                "changes": []
            },
            "organization_states": {"updated_count": 0, "changes": []}
        }

        # Cập nhật nghề nghiệp nhân vật / quan hệ trạng thái nhân vật / trạng thái tổ chức
        if analysis_result.get('character_states'):
            try:
                from app.services.career_update_service import CareerUpdateService
                career_update_result = await CareerUpdateService.update_careers_from_analysis(
                    db=db,
                    project_id=project_id,
                    character_states=analysis_result.get('character_states', []),
                    chapter_id=chapter_id,
                    chapter_number=chapter.chapter_number
                )
                entity_changes["careers"] = career_update_result
            except Exception as career_error:
                logger.error(f"Cảnh báo: cập nhật nghề nghiệp nhân vật thất bại (không ảnh hưởng kết quả phân tích): {str(career_error)}", exc_info=True)

            try:
                from app.services.character_state_update_service import CharacterStateUpdateService
                state_update_result = await CharacterStateUpdateService.update_from_analysis(
                    db=db,
                    project_id=project_id,
                    character_states=analysis_result.get('character_states', []),
                    chapter_id=chapter_id,
                    chapter_number=chapter.chapter_number
                )
                entity_changes["character_states"] = state_update_result
            except Exception as state_error:
                logger.error(f"Cảnh báo: cập nhật trạng thái nhân vật, quan hệ và thành viên tổ chức thất bại (không ảnh hưởng kết quả phân tích): {str(state_error)}", exc_info=True)

        if analysis_result.get('organization_states'):
            try:
                from app.services.character_state_update_service import CharacterStateUpdateService
                org_state_result = await CharacterStateUpdateService.update_organization_states(
                    db=db,
                    project_id=project_id,
                    organization_states=analysis_result.get('organization_states', []),
                    chapter_number=chapter.chapter_number
                )
                entity_changes["organization_states"] = org_state_result
            except Exception as org_state_error:
                logger.error(f"Cảnh báo: cập nhật trạng thái tổ chức thất bại (không ảnh hưởng kết quả phân tích): {str(org_state_error)}", exc_info=True)

        # [Mới] Tự động cập nhật trạng thái nút thắt
        foreshadow_stats = {"planted_count": 0, "resolved_count": 0, "created_count": 0}
        analysis_foreshadows = analysis_result.get('foreshadows', [])

        if analysis_foreshadows:
            try:
                foreshadow_stats = await foreshadow_service.auto_update_from_analysis(
                    db=db,
                    project_id=project_id,
                    chapter_id=chapter_id,
                    chapter_number=chapter.chapter_number,
                    analysis_foreshadows=analysis_foreshadows
                )
                logger.info(f"Thống kê tự động cập nhật nút thắt: chôn {foreshadow_stats['planted_count']} nút, thu hồi {foreshadow_stats['resolved_count']} nút")
            except Exception as fs_error:
                logger.error(f"Cảnh báo: tự động cập nhật nút thắt thất bại (không ảnh hưởng kết quả phân tích): {str(fs_error)}")

        logger.info(f"Phân tích chương hoàn thành: lưu {saved_count} ký ức")

        return {
            "success": True,
            "message": f"Phân tích hoàn thành, đã trích xuất {saved_count} ký ức",
            "analysis": plot_analysis.to_dict(),
            "memories_count": saved_count,
            "foreshadow_stats": foreshadow_stats,
            "entity_changes": entity_changes
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi: phân tích chương thất bại: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Phân tích thất bại: {str(e)}")


@router.get("/projects/{project_id}/memories")
async def get_project_memories(
    project_id: str,
    request: Request,
    memory_type: Optional[str] = None,
    chapter_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách ký ức của dự án"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        # Xây dựng truy vấn
        query = select(StoryMemory).where(StoryMemory.project_id == project_id)

        if memory_type:
            query = query.where(StoryMemory.memory_type == memory_type)
        if chapter_id:
            query = query.where(StoryMemory.chapter_id == chapter_id)

        query = query.order_by(desc(StoryMemory.importance_score), desc(StoryMemory.created_at)).limit(limit)

        result = await db.execute(query)
        memories = result.scalars().all()

        return {
            "success": True,
            "memories": [mem.to_dict() for mem in memories],
            "total": len(memories)
        }

    except Exception as e:
        logger.error(f"Lỗi: lấy ký ức thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/analysis/{chapter_id}")
async def get_chapter_analysis(
    project_id: str,
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy phân tích cốt truyện của chương"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        result = await db.execute(
            select(PlotAnalysis).where(
                and_(
                    PlotAnalysis.project_id == project_id,
                    PlotAnalysis.chapter_id == chapter_id
                )
            )
        )
        analysis = result.scalar_one_or_none()

        if not analysis:
            raise HTTPException(status_code=404, detail="Chương này chưa được phân tích")

        return {
            "success": True,
            "analysis": analysis.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi: lấy phân tích thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/search")
async def search_memories(
    project_id: str,
    request: Request,
    query: str,
    memory_types: Optional[List[str]] = None,
    limit: int = 10,
    min_importance: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """Tìm kiếm ngữ nghĩa ký ức của dự án"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        memories = await memory_service.search_memories(
            user_id=user_id,
            project_id=project_id,
            query=query,
            memory_types=memory_types,
            limit=limit,
            min_importance=min_importance
        )

        return {
            "success": True,
            "query": query,
            "memories": memories,
            "total": len(memories)
        }

    except Exception as e:
        logger.error(f"Lỗi: tìm kiếm ký ức thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/foreshadows")
async def get_unresolved_foreshadows(
    project_id: str,
    request: Request,
    current_chapter: int,
    db: AsyncSession = Depends(get_db)
):
    """Lấy các nút thắt chưa kết thúc"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        # Tìm kiếm từ vector store
        foreshadows = await memory_service.find_unresolved_foreshadows(
            user_id=user_id,
            project_id=project_id,
            current_chapter=current_chapter
        )

        return {
            "success": True,
            "foreshadows": foreshadows,
            "total": len(foreshadows)
        }

    except Exception as e:
        logger.error(f"Lỗi: lấy nút thắt thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/stats")
async def get_memory_stats(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy thống kê ký ức"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        stats = await memory_service.get_memory_stats(
            user_id=user_id,
            project_id=project_id
        )

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Lỗi: lấy thống kê thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/chapters/{chapter_id}/memories")
async def delete_chapter_memories(
    project_id: str,
    chapter_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa tất cả ký ức của chương"""
    try:
        user_id = getattr(request.state, 'user_id', None)

        # Xác minh quyền người dùng
        await verify_project_access(project_id, user_id, db)

        # Xóa khỏi database
        result = await db.execute(
            select(StoryMemory).where(
                and_(
                    StoryMemory.project_id == project_id,
                    StoryMemory.chapter_id == chapter_id
                )
            )
        )
        memories = result.scalars().all()

        for memory in memories:
            await db.delete(memory)

        # Xóa khỏi vector store
        await memory_service.delete_chapter_memories(
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id
        )

        await db.commit()

        return {
            "success": True,
            "message": f"Đã xóa {len(memories)} ký ức"
        }

    except Exception as e:
        logger.error(f"Lỗi: xóa ký ức thất bại: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
