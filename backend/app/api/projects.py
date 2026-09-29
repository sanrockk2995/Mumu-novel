"""API quản lý dự án"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List
import json
from urllib.parse import quote
from app.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.models.outline import Outline
from app.models.chapter import Chapter
from app.models.generation_history import GenerationHistory
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.models.memory import StoryMemory, PlotAnalysis
from app.models.foreshadow import Foreshadow
from app.models.career import Career, CharacterCareer
from app.models.analysis_task import AnalysisTask
from app.models.batch_generation_task import BatchGenerationTask
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse
)
from app.schemas.import_export import (
    ExportOptions,
    ImportValidationResult,
    ImportResult
)
from app.services.import_export_service import ImportExportService
from app.services.memory_service import memory_service
from app.logger import get_logger
from app.utils.data_consistency import (
    run_full_data_consistency_check,
    fix_missing_organization_records,
    fix_organization_member_counts
)

logger = get_logger(__name__)
router = APIRouter(prefix="/projects", tags=["Quản lý dự án"])


@router.post("", response_model=ProjectResponse, summary="Tạo dự án")
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố tạo dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Tạo dự án mới: {project.title}, user_id={user_id}")

        # Khi tạo dự án tự động gán user_id
        project_data = project.model_dump()
        project_data['user_id'] = user_id
        db_project = Project(**project_data)

        db.add(db_project)
        await db.commit()
        await db.refresh(db_project)
        logger.info(f"Tạo dự án thành công: project_id={db_project.id}, user_id={user_id}")

        return db_project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tạo dự án thất bại: {str(e)}", exc_info=True)
        raise


@router.get("", response_model=ProjectListResponse, summary="Lấy danh sách dự án")
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """Lấy danh sách dự án của người dùng hiện tại"""
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố lấy danh sách dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.debug(f"Lấy danh sách dự án: user_id={user_id}, skip={skip}, limit={limit}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        count_result = await db.execute(
            select(func.count(Project.id)).where(Project.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        projects = result.scalars().all()
        logger.info(f"Lấy danh sách dự án thành công: user_id={user_id}, tổng {total} dự án")

        return ProjectListResponse(total=total, items=projects)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lấy danh sách dự án thất bại: {str(e)}", exc_info=True)
        raise


@router.get("/{project_id}", response_model=ProjectResponse, summary="Lấy chi tiết dự án")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố lấy chi tiết dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.debug(f"Lấy chi tiết dự án: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        logger.info(f"Lấy chi tiết dự án thành công: {project.title}")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lấy chi tiết dự án thất bại: {str(e)}", exc_info=True)
        raise


@router.put("/{project_id}", response_model=ProjectResponse, summary="Cập nhật dự án")
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố cập nhật dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Cập nhật dự án: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        update_data = project_update.model_dump(exclude_unset=True)
        logger.debug(f"Các trường cập nhật: {list(update_data.keys())}")
        for field, value in update_data.items():
            setattr(project, field, value)

        await db.commit()
        await db.refresh(project)
        logger.info(f"Cập nhật dự án thành công: {project.title}")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cập nhật dự án thất bại: {str(e)}", exc_info=True)
        raise


@router.delete("/{project_id}", summary="Xóa dự án")
async def delete_project(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố xóa dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Xóa dự án: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        project_title = project.title

        # Xóa ký ức trong cơ sở dữ liệu vector (user_id đã lấy ở trên)
        if user_id:
            try:
                await memory_service.delete_project_memories(user_id, project_id)
                logger.info(f"✅ Dọn dẹp cơ sở dữ liệu vector thành công")
            except Exception as e:
                logger.warning(f"⚠️ Dọn dẹp cơ sở dữ liệu vector thất bại (tiếp tục xóa dữ liệu khác): {str(e)}")
        else:
            logger.warning(f"⚠️ Không tìm thấy ID người dùng, bỏ qua dọn dẹp cơ sở dữ liệu vector")

        # === Xóa tất cả dữ liệu liên quan (SQLite mặc định không bật ràng buộc khóa ngoại, cần xóa tường minh) ===

        # 1. Xóa quan hệ nhân vật
        relationships_result = await db.execute(
            delete(CharacterRelationship).where(CharacterRelationship.project_id == project_id)
        )
        logger.debug(f"Số quan hệ nhân vật đã xóa: {relationships_result.rowcount}")

        # 2. Xóa thành viên tổ chức và tổ chức
        orgs_result = await db.execute(
            select(Organization).where(Organization.project_id == project_id)
        )
        orgs = orgs_result.scalars().all()
        org_member_count = 0
        for org in orgs:
            members_result = await db.execute(
                delete(OrganizationMember).where(OrganizationMember.organization_id == org.id)
            )
            org_member_count += members_result.rowcount
        logger.debug(f"Số thành viên tổ chức đã xóa: {org_member_count}")

        organizations_result = await db.execute(
            delete(Organization).where(Organization.project_id == project_id)
        )
        logger.debug(f"Số tổ chức đã xóa: {organizations_result.rowcount}")

        # 3. Xóa lịch sử tạo
        history_result = await db.execute(
            delete(GenerationHistory).where(GenerationHistory.project_id == project_id)
        )
        logger.debug(f"Số lịch sử tạo đã xóa: {history_result.rowcount}")

        # 4. Xóa tác vụ phân tích
        analysis_tasks_result = await db.execute(
            delete(AnalysisTask).where(AnalysisTask.project_id == project_id)
        )
        logger.debug(f"Số tác vụ phân tích đã xóa: {analysis_tasks_result.rowcount}")

        # 5. Xóa tác vụ tạo hàng loạt
        batch_tasks_result = await db.execute(
            delete(BatchGenerationTask).where(BatchGenerationTask.project_id == project_id)
        )
        logger.debug(f"Số tác vụ tạo hàng loạt đã xóa: {batch_tasks_result.rowcount}")

        # 6. Xóa liên kết nghề nghiệp nhân vật (lấy danh sách ID nhân vật trước)
        characters_query = await db.execute(
            select(Character.id).where(Character.project_id == project_id)
        )
        character_ids = [row[0] for row in characters_query.fetchall()]

        if character_ids:
            character_careers_result = await db.execute(
                delete(CharacterCareer).where(CharacterCareer.character_id.in_(character_ids))
            )
            logger.debug(f"Số liên kết nghề nghiệp nhân vật đã xóa: {character_careers_result.rowcount}")

        # 7. Xóa hệ thống nghề nghiệp
        careers_result = await db.execute(
            delete(Career).where(Career.project_id == project_id)
        )
        logger.debug(f"Số hệ thống nghề nghiệp đã xóa: {careers_result.rowcount}")

        # 8. Xóa ký ức truyện
        story_memories_result = await db.execute(
            delete(StoryMemory).where(StoryMemory.project_id == project_id)
        )
        logger.debug(f"Số ký ức truyện đã xóa: {story_memories_result.rowcount}")

        # 9. Xóa chương (sẽ cascade xóa PlotAnalysis)
        chapters_result = await db.execute(
            delete(Chapter).where(Chapter.project_id == project_id)
        )
        logger.debug(f"Số chương đã xóa: {chapters_result.rowcount}")

        # 10. Xóa dàn ý
        outlines_result = await db.execute(
            delete(Outline).where(Outline.project_id == project_id)
        )
        logger.debug(f"Số dàn ý đã xóa: {outlines_result.rowcount}")

        # 11. Xóa nhân vật
        characters_result = await db.execute(
            delete(Character).where(Character.project_id == project_id)
        )
        logger.debug(f"Số nhân vật đã xóa: {characters_result.rowcount}")

        # 12. Xóa manh mối ẩn
        foreshadows_result = await db.execute(
            delete(Foreshadow).where(Foreshadow.project_id == project_id)
        )
        logger.debug(f"Số manh mối ẩn đã xóa: {foreshadows_result.rowcount}")

        # Cuối cùng xóa chính dự án
        await db.delete(project)
        await db.commit()

        logger.info(f"Xóa dự án thành công: {project_title}")
        return {"message": "Xóa dự án và tất cả dữ liệu liên quan (gồm cơ sở dữ liệu vector) thành công"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xóa dự án thất bại: {str(e)}", exc_info=True)
        raise


@router.get("/{project_id}/export", summary="Xuất các chương của dự án thành TXT")
async def export_project_chapters(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Xuất nội dung tất cả các chương của dự án thành file văn bản TXT
    Sắp xếp theo thứ tự chương, dùng định dạng chương thuần túy để tiện nhập tách sách lại
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố xuất dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu xuất dự án: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        chapters_result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()

        if not chapters:
            logger.warning(f"Dự án không có chương: {project_id}")
            raise HTTPException(status_code=404, detail="Dự án không có chương nào")

        txt_content = []

        for idx, chapter in enumerate(chapters):
            chapter_title = (chapter.title or "").strip() or f"Chương chưa đặt tên {chapter.chapter_number}"
            raw_content = (chapter.content or "").strip()
            if raw_content:
                formatted_lines = []
                for line in raw_content.splitlines():
                    stripped_line = line.strip()
                    if stripped_line:
                        formatted_lines.append(f"　　{stripped_line}")
                    else:
                        formatted_lines.append("")
                chapter_content = "\n".join(formatted_lines)
            else:
                chapter_content = "　　（Chương này tạm thời chưa có nội dung）"

            # Dùng định dạng tiêu đề chương mà tách sách có thể nhận diện ổn định: 第X章 标题
            # (Giữ nguyên định dạng tiếng Trung để bộ tách sách nhận diện được khi nhập lại)
            txt_content.append(f"第{chapter.chapter_number}章 {chapter_title}")
            txt_content.append(chapter_content)

            # Giữa các chương chỉ giữ một dòng trống, tránh đường phân cách trang trí làm nhiễu nhận diện tách sách
            if idx < len(chapters) - 1:
                txt_content.append("")

        final_content = "\n".join(txt_content)

        safe_title = "".join(c for c in (project.title or "Dự án chưa đặt tên") if c.isalnum() or c in (' ', '-', '_', '，', '。', '、'))
        filename = f"{safe_title}.txt"

        from urllib.parse import quote
        encoded_filename = quote(filename)

        logger.info(f"Xuất thành công: {filename}, tổng {len(chapters)} chương, {len(final_content)} ký tự")

        return Response(
            content=final_content.encode('utf-8'),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xuất dự án thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Xuất thất bại: {str(e)}")


@router.post("/{project_id}/check-consistency", summary="Kiểm tra tính nhất quán dữ liệu")
async def check_project_consistency(
    project_id: str,
    request: Request,
    auto_fix: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Kiểm tra và sửa các vấn đề nhất quán dữ liệu của dự án

    Args:
        project_id: ID dự án
        auto_fix: có tự động sửa vấn đề không (mặc định True)

    Trả về báo cáo kiểm tra, gồm:
    - organization_records: kiểm tra và sửa các bản ghi Organization còn thiếu
    - member_counts: kiểm tra và sửa số lượng thành viên tổ chức
    - relationships: xác thực tính toàn vẹn dữ liệu quan hệ
    - organization_members: xác thực tính toàn vẹn dữ liệu thành viên tổ chức
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố kiểm tra tính nhất quán dữ liệu")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu kiểm tra tính nhất quán dữ liệu: project_id={project_id}, user_id={user_id}, auto_fix={auto_fix}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        report = await run_full_data_consistency_check(project_id, db, auto_fix)

        logger.info(f"Hoàn tất kiểm tra tính nhất quán dữ liệu: {project_id}")
        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kiểm tra tính nhất quán dữ liệu thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Kiểm tra thất bại: {str(e)}")


@router.post("/{project_id}/fix-organizations", summary="Sửa bản ghi tổ chức")
async def fix_project_organizations(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Sửa các bản ghi Organization còn thiếu trong dự án

    Tạo bản ghi cho mọi Character có is_organization=True nhưng chưa có bản ghi Organization
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố sửa bản ghi tổ chức")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu sửa bản ghi tổ chức: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        fixed_count, total_count = await fix_missing_organization_records(project_id, db)

        logger.info(f"Hoàn tất sửa bản ghi tổ chức: {project_id}, đã sửa {fixed_count}/{total_count}")
        return {
            "message": "Hoàn tất sửa bản ghi tổ chức",
            "fixed": fixed_count,
            "total": total_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sửa bản ghi tổ chức thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sửa thất bại: {str(e)}")


@router.post("/{project_id}/fix-member-counts", summary="Sửa số lượng thành viên")
async def fix_project_member_counts(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Sửa số lượng thành viên của mọi tổ chức trong dự án

    Tính lại member_count của từng tổ chức từ các bản ghi thành viên thực tế
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố sửa số lượng thành viên")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu sửa số lượng thành viên: project_id={project_id}, user_id={user_id}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        fixed_count, total_count = await fix_organization_member_counts(project_id, db)

        logger.info(f"Hoàn tất sửa số lượng thành viên: {project_id}, đã sửa {fixed_count}/{total_count}")
        return {
            "message": "Hoàn tất sửa số lượng thành viên",
            "fixed": fixed_count,
            "total": total_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sửa số lượng thành viên thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sửa thất bại: {str(e)}")


@router.post("/{project_id}/export-data", summary="Xuất dữ liệu dự án thành JSON")
async def export_project_data(
    project_id: str,
    request: Request,
    options: ExportOptions,
    db: AsyncSession = Depends(get_db)
):
    """
    Xuất toàn bộ dữ liệu dự án thành định dạng JSON

    Args:
        project_id: ID dự án
        options: tùy chọn xuất
            - include_generation_history: có gồm lịch sử tạo không
            - include_writing_styles: có gồm phong cách viết không
            - include_careers: có gồm hệ thống nghề nghiệp không
            - include_memories: có gồm ký ức truyện không
            - include_plot_analysis: có gồm phân tích cốt truyện không

    Returns:
        Tải xuống file JSON
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố xuất dữ liệu dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu xuất dữ liệu dự án: project_id={project_id}, user_id={user_id}, options={options.model_dump()}")

        # Chỉ truy vấn dự án của người dùng hiện tại
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.warning(f"Dự án không tồn tại hoặc không có quyền truy cập: project_id={project_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Dự án không tồn tại")

        # Xuất dữ liệu (dùng mọi tùy chọn)
        export_data = await ImportExportService.export_project(
            project_id=project_id,
            db=db,
            include_generation_history=options.include_generation_history,
            include_writing_styles=options.include_writing_styles,
            include_careers=options.include_careers,
            include_memories=options.include_memories,
            include_plot_analysis=options.include_plot_analysis
        )

        # Chuyển thành JSON
        json_content = export_data.model_dump_json(indent=2, exclude_none=True, by_alias=True)

        # Tạo tên file
        safe_title = "".join(c for c in project.title if c.isalnum() or c in (' ', '-', '_'))
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"project_{safe_title}_{date_str}.json"
        encoded_filename = quote(filename)

        logger.info(f"Xuất dữ liệu dự án thành công: {filename}")

        return Response(
            content=json_content.encode('utf-8'),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "application/json; charset=utf-8"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xuất dữ liệu dự án thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Xuất thất bại: {str(e)}")


@router.post("/validate-import", response_model=ImportValidationResult, summary="Kiểm tra file nhập")
async def validate_import_file(
    file: UploadFile = File(...)
):
    """
    Kiểm tra định dạng và nội dung file nhập

    Args:
        file: file JSON được tải lên

    Returns:
        Kết quả kiểm tra
    """
    try:
        logger.info(f"Kiểm tra file nhập: {file.filename}")

        # Kiểm tra loại file
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng JSON")

        # Đọc nội dung file
        content = await file.read()

        # Kiểm tra kích thước file (giới hạn 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail="Kích thước file vượt quá giới hạn 50MB")

        # Phân tích JSON
        try:
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Định dạng JSON không hợp lệ: {str(e)}")

        # Kiểm tra dữ liệu
        validation_result = ImportExportService.validate_import_data(data)

        logger.info(f"Hoàn tất kiểm tra file: valid={validation_result.valid}")
        return validation_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Kiểm tra file nhập thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Kiểm tra thất bại: {str(e)}")


@router.post("/import", response_model=ImportResult, summary="Nhập dự án")
async def import_project(
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Nhập dữ liệu dự án (tạo dự án mới)

    Args:
        file: file JSON được tải lên

    Returns:
        Kết quả nhập
    """
    try:
        # Lấy ID người dùng từ middleware xác thực
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.warning("Người dùng chưa đăng nhập cố nhập dự án")
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")

        logger.info(f"Bắt đầu nhập dự án: {file.filename}, user_id={user_id}")

        # Kiểm tra loại file
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng JSON")

        # Đọc nội dung file
        content = await file.read()

        # Kiểm tra kích thước file
        max_size = 50 * 1024 * 1024  # 50MB
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail="Kích thước file vượt quá giới hạn 50MB")

        # Phân tích JSON
        try:
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Định dạng JSON không hợp lệ: {str(e)}")

        # Nhập dữ liệu (truyền user_id)
        import_result = await ImportExportService.import_project(data, db, user_id)

        if import_result.success:
            logger.info(f"Nhập dự án thành công: {import_result.project_id}")
        else:
            logger.warning(f"Nhập dự án thất bại: {import_result.message}")

        return import_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nhập dự án thất bại: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Nhập thất bại: {str(e)}")
