"""API quản lý tổ chức"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, AsyncGenerator
from pydantic import BaseModel, Field
import json

from app.database import get_db
from app.utils.sse_response import SSEResponse, create_sse_response, WizardProgressTracker, wrap_stream_with_heartbeat, HEARTBEAT
from app.models.relationship import Organization, OrganizationMember
from app.models.character import Character
from app.models.project import Project
from app.models.generation_history import GenerationHistory
from app.schemas.relationship import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationDetailResponse,
    OrganizationMemberCreate,
    OrganizationMemberUpdate,
    OrganizationMemberResponse,
    OrganizationMemberDetailResponse
)
from app.schemas.character import CharacterResponse
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.logger import get_logger, safe_preview
from app.api.settings import get_user_ai_service
from app.api.common import verify_project_access

router = APIRouter(prefix="/organizations", tags=["Quản lý tổ chức"])
logger = get_logger(__name__)


class OrganizationGenerateRequest(BaseModel):
    """Model yêu cầu AI tạo tổ chức"""
    project_id: str = Field(..., description="ID dự án")
    name: Optional[str] = Field(None, description="Tên tổ chức")
    organization_type: Optional[str] = Field(None, description="Loại tổ chức")
    background: Optional[str] = Field(None, description="Bối cảnh tổ chức")
    requirements: Optional[str] = Field(None, description="Yêu cầu đặc biệt")
    enable_mcp: bool = Field(True, description="Có bật tăng cường công cụ MCP (tìm kiếm tham khảo cơ cấu tổ chức) không")


@router.get("/project/{project_id}", response_model=List[OrganizationDetailResponse], summary="Lấy tất cả tổ chức của dự án")
async def get_project_organizations(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    """
    Lấy tất cả tổ chức trong dự án cùng chi tiết

    Trả về thông tin cơ bản và dữ liệu thống kê của tổ chức
    """
    result = await db.execute(
        select(Organization).where(Organization.project_id == project_id)
    )
    organizations = result.scalars().all()

    # Lấy thông tin nhân vật của mỗi tổ chức
    org_list = []
    for org in organizations:
        char_result = await db.execute(
            select(Character).where(Character.id == org.character_id)
        )
        char = char_result.scalar_one_or_none()

        if char:
            org_list.append(OrganizationDetailResponse(
                id=org.id,
                character_id=org.character_id,
                name=char.name,
                type=char.organization_type,
                purpose=char.organization_purpose,
                member_count=org.member_count,
                power_level=org.power_level,
                location=org.location,
                motto=org.motto,
                color=org.color
            ))

    logger.info(f"Lấy danh sách tổ chức của dự án {project_id}, tổng cộng {len(org_list)} tổ chức")
    return org_list


@router.get("/{org_id}", response_model=OrganizationResponse, summary="Lấy chi tiết tổ chức")
async def get_organization(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy thông tin chi tiết của tổ chức"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Tổ chức không tồn tại")

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)

    return org


@router.post("", response_model=OrganizationResponse, summary="Tạo tổ chức")
async def create_organization(
    organization: OrganizationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo tổ chức mới

    - Cần liên kết với một bản ghi nhân vật đã tồn tại (is_organization=True)
    - Có thể đặt tổ chức cha, cấp độ thế lực v.v.
    """
    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(organization.project_id, user_id, db)

    # Xác minh nhân vật tồn tại và là tổ chức
    char_result = await db.execute(
        select(Character).where(Character.id == organization.character_id)
    )
    char = char_result.scalar_one_or_none()

    if not char:
        raise HTTPException(status_code=404, detail="Nhân vật liên kết không tồn tại")
    if not char.is_organization:
        raise HTTPException(status_code=400, detail="Nhân vật liên kết không phải loại tổ chức")

    # Kiểm tra đã tồn tại chưa
    existing = await db.execute(
        select(Organization).where(Organization.character_id == organization.character_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nhân vật này đã có bản ghi chi tiết tổ chức")

    # Tạo tổ chức
    db_org = Organization(**organization.model_dump())
    db.add(db_org)
    await db.commit()
    await db.refresh(db_org)

    logger.info(f"Tạo tổ chức thành công: {db_org.id} - {char.name}")
    return db_org


@router.put("/{org_id}", response_model=OrganizationResponse, summary="Cập nhật tổ chức")
async def update_organization(
    org_id: str,
    organization: OrganizationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thuộc tính của tổ chức"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    db_org = result.scalar_one_or_none()

    if not db_org:
        raise HTTPException(status_code=404, detail="Tổ chức không tồn tại")

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_org.project_id, user_id, db)

    # Cập nhật các trường của bảng Organization
    update_data = organization.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_org, field, value)

    await db.commit()
    await db.refresh(db_org)

    logger.info(f"Cập nhật tổ chức thành công: {org_id}")
    return db_org


@router.delete("/{org_id}", summary="Xóa tổ chức")
async def delete_organization(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa tổ chức (sẽ xóa cascade tất cả quan hệ thành viên)"""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    db_org = result.scalar_one_or_none()

    if not db_org:
        raise HTTPException(status_code=404, detail="Tổ chức không tồn tại")

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_org.project_id, user_id, db)

    await db.delete(db_org)
    await db.commit()

    logger.info(f"Xóa tổ chức thành công: {org_id}")
    return {"message": "Xóa tổ chức thành công", "id": org_id}


# ============ Quản lý thành viên tổ chức ============

@router.get("/{org_id}/members", response_model=List[OrganizationMemberDetailResponse], summary="Lấy thành viên tổ chức")
async def get_organization_members(
    org_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả thành viên của tổ chức

    Sắp xếp theo cấp bậc chức vụ (rank) giảm dần
    """
    # Xác minh tổ chức tồn tại
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tổ chức không tồn tại")

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)

    # Lấy danh sách thành viên
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.rank.desc(), OrganizationMember.created_at)
    )
    members = result.scalars().all()

    # Lấy thông tin nhân vật của thành viên
    member_list = []
    for member in members:
        char_result = await db.execute(
            select(Character).where(Character.id == member.character_id)
        )
        char = char_result.scalar_one_or_none()

        if char:
            member_list.append(OrganizationMemberDetailResponse(
                id=member.id,
                character_id=member.character_id,
                character_name=char.name,
                position=member.position,
                rank=member.rank,
                loyalty=member.loyalty,
                contribution=member.contribution,
                status=member.status,
                joined_at=member.joined_at,
                left_at=member.left_at,
                notes=member.notes
            ))

    logger.info(f"Lấy danh sách thành viên của tổ chức {org_id}, tổng cộng {len(member_list)} người")
    return member_list


@router.post("/{org_id}/members", response_model=OrganizationMemberResponse, summary="Thêm thành viên tổ chức")
async def add_organization_member(
    org_id: str,
    member: OrganizationMemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Thêm nhân vật vào tổ chức

    - Một nhân vật trong cùng tổ chức chỉ có thể giữ một chức vụ
    - Tự động cập nhật số lượng thành viên của tổ chức
    """
    # Xác minh tổ chức tồn tại
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tổ chức không tồn tại")

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)

    # Xác minh nhân vật tồn tại
    char_result = await db.execute(
        select(Character).where(Character.id == member.character_id)
    )
    char = char_result.scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")
    if char.is_organization:
        raise HTTPException(status_code=400, detail="Không thể thêm tổ chức làm thành viên")

    # Kiểm tra đã tồn tại chưa
    existing = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.character_id == member.character_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nhân vật này đã ở trong tổ chức")

    # Tạo quan hệ thành viên
    db_member = OrganizationMember(
        organization_id=org_id,
        **member.model_dump(),
        source="manual"
    )
    db.add(db_member)

    # Cập nhật số lượng thành viên của tổ chức
    org.member_count += 1

    await db.commit()
    await db.refresh(db_member)

    logger.info(f"Thêm thành viên thành công: {char.name} gia nhập tổ chức {org_id}")
    return db_member


@router.put("/members/{member_id}", response_model=OrganizationMemberResponse, summary="Cập nhật thông tin thành viên")
async def update_organization_member(
    member_id: str,
    member: OrganizationMemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật chức vụ, độ trung thành v.v. của thành viên tổ chức"""
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.id == member_id)
    )
    db_member = result.scalar_one_or_none()

    if not db_member:
        raise HTTPException(status_code=404, detail="Bản ghi thành viên không tồn tại")

    # Xác minh quyền người dùng thông qua tổ chức của thành viên
    org_result = await db.execute(
        select(Organization).where(Organization.id == db_member.organization_id)
    )
    org = org_result.scalar_one()
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)

    # Cập nhật các trường
    update_data = member.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_member, field, value)

    await db.commit()
    await db.refresh(db_member)

    logger.info(f"Cập nhật thông tin thành viên thành công: {member_id}")
    return db_member


@router.delete("/members/{member_id}", summary="Xóa thành viên khỏi tổ chức")
async def remove_organization_member(
    member_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa thành viên khỏi tổ chức

    Tự động cập nhật số lượng thành viên của tổ chức
    """
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.id == member_id)
    )
    db_member = result.scalar_one_or_none()

    if not db_member:
        raise HTTPException(status_code=404, detail="Bản ghi thành viên không tồn tại")

    # Cập nhật số lượng thành viên của tổ chức
    org_result = await db.execute(
        select(Organization).where(Organization.id == db_member.organization_id)
    )
    org = org_result.scalar_one()

    # Xác minh quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(org.project_id, user_id, db)
    org.member_count = max(0, org.member_count - 1)

    await db.delete(db_member)
    await db.commit()

    logger.info(f"Xóa thành viên thành công: {member_id}")
    return {"message": "Xóa thành viên thành công", "id": member_id}

@router.post("/generate-stream", summary="AI tạo tổ chức (stream)")
async def generate_organization_stream(
    gen_request: OrganizationGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng AI tạo thiết lập tổ chức (hỗ trợ hiển thị tiến độ stream SSE)

    Trả về thông tin tiến độ thời gian thực qua Server-Sent Events
    """
    async def generate() -> AsyncGenerator[str, None]:
        tracker = WizardProgressTracker("Tổ chức")
        try:
            # Xác minh quyền người dùng và dự án tồn tại
            user_id = getattr(http_request.state, 'user_id', None)
            project = await verify_project_access(gen_request.project_id, user_id, db)

            yield await tracker.start()

            # Lấy danh sách nhân vật và tổ chức đã tồn tại
            yield await tracker.loading("Đang lấy ngữ cảnh dự án...", 0.3)

            existing_chars_result = await db.execute(
                select(Character)
                .where(Character.project_id == gen_request.project_id)
                .order_by(Character.created_at.desc())
            )
            existing_characters = existing_chars_result.scalars().all()

            # Xây dựng tóm tắt thông tin nhân vật và tổ chức hiện có
            existing_info = ""
            character_list = []
            organization_list = []

            if existing_characters:
                for c in existing_characters[:10]:
                    if c.is_organization:
                        organization_list.append(f"- {c.name} [{c.organization_type or 'Tổ chức'}]")
                    else:
                        character_list.append(f"- {c.name} ({c.role_type or 'Chưa rõ'})")

                if character_list:
                    existing_info += "\nNhân vật hiện có:\n" + "\n".join(character_list)
                if organization_list:
                    existing_info += "\n\nTổ chức hiện có:\n" + "\n".join(organization_list)

            # Xây dựng ngữ cảnh dự án
            project_context = f"""
Thông tin dự án:
- Tên sách: {project.title}
- Chủ đề: {project.theme or 'Chưa đặt'}
- Thể loại: {project.genre or 'Chưa đặt'}
- Bối cảnh thời gian: {project.world_time_period or 'Chưa đặt'}
- Vị trí địa lý: {project.world_location or 'Chưa đặt'}
- Tông không khí: {project.world_atmosphere or 'Chưa đặt'}
- Quy tắc thế giới: {project.world_rules or 'Chưa đặt'}
{existing_info}
"""

            user_input = f"""
Yêu cầu của người dùng:
- Tên tổ chức: {gen_request.name or 'Để AI tạo'}
- Loại tổ chức: {gen_request.organization_type or 'Để AI quyết định theo thế giới quan'}
- Bối cảnh: {gen_request.background or 'Không yêu cầu đặc biệt'}
- Yêu cầu khác: {gen_request.requirements or 'Không có'}
"""

            yield await tracker.loading("Chuẩn bị ngữ cảnh dự án hoàn tất", 0.7)
            yield await tracker.preparing("Đang xây dựng prompt AI...")

            # Lấy template prompt tùy chỉnh
            template = await PromptService.get_template("SINGLE_ORGANIZATION_GENERATION", user_id, db)
            # Định dạng prompt
            prompt = PromptService.format_prompt(
                template,
                project_context=project_context,
                user_input=user_input
            )

            yield await tracker.generating(0, max(3000, len(prompt) * 8), "Đang gọi dịch vụ AI tạo tổ chức...")
            logger.info(f"Bắt đầu tạo tổ chức cho dự án {gen_request.project_id} (stream SSE)")

            try:
                # Dùng tạo stream thay cho không stream
                ai_content = ""
                chunk_count = 0
                estimated_total = max(3000, len(prompt) * 8)

                async for chunk in wrap_stream_with_heartbeat(
                    user_ai_service.generate_text_stream(prompt=prompt),
                    heartbeat_interval=15.0
                ):
                    # Sentinel heartbeat: gửi heartbeat giữ kết nối, không trộn vào phản hồi AI
                    if chunk is HEARTBEAT:
                        yield await tracker.heartbeat()
                        continue

                    chunk_count += 1
                    ai_content += chunk

                    # Gửi khối nội dung
                    yield await SSEResponse.send_chunk(chunk)

                    # Cập nhật số chữ định kỳ (tránh quá thường xuyên)
                    if chunk_count % 5 == 0:
                        yield await tracker.generating(len(ai_content), estimated_total)

                    # Heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()

            except Exception as ai_error:
                logger.error(f"Ngoại lệ khi gọi dịch vụ AI: {str(ai_error)}")
                yield await tracker.error(f"Gọi dịch vụ AI thất bại: {str(ai_error)}")
                return

            if not ai_content or not ai_content.strip():
                yield await tracker.error("Dịch vụ AI trả về phản hồi trống")
                return

            yield await tracker.parsing("Đang phân tích phản hồi AI...", 0.5)

            # Dùng phương pháp làm sạch JSON thống nhất
            try:
                cleaned_response = user_ai_service._clean_json_response(ai_content)
                organization_data = loads_json(cleaned_response)
                logger.info(f"Phân tích JSON tổ chức thành công")
            except json.JSONDecodeError as e:
                logger.error(f"Phân tích JSON tổ chức thất bại: {e}")
                logger.debug(f"   Xem trước phản hồi gốc: {safe_preview(ai_content, 200)}")
                yield await tracker.error(f"Nội dung AI trả về không thể phân tích thành JSON: {str(e)}")
                return

            yield await tracker.saving("Đang tạo bản ghi tổ chức...", 0.3)

            # Tạo bản ghi nhân vật (tổ chức cũng là một loại nhân vật)
            character = Character(
                project_id=gen_request.project_id,
                name=organization_data.get("name", gen_request.name or "Tổ chức chưa đặt tên"),
                is_organization=True,
                role_type="supporting",
                personality=organization_data.get("personality", ""),
                background=organization_data.get("background", ""),
                appearance=organization_data.get("appearance", ""),
                organization_type=organization_data.get("organization_type"),
                organization_purpose=organization_data.get("organization_purpose"),
                traits=json.dumps(
                    organization_data.get("traits", []),
                    ensure_ascii=False
                )
            )
            db.add(character)
            await db.flush()

            logger.info(f"Tạo nhân vật tổ chức thành công: {character.name} (ID: {character.id})")

            yield await tracker.saving("Đang tạo chi tiết tổ chức...", 0.6)

            # Tự động tạo bản ghi chi tiết Organization
            organization = Organization(
                character_id=character.id,
                project_id=gen_request.project_id,
                member_count=0,
                power_level=organization_data.get("power_level", 50),
                location=organization_data.get("location"),
                motto=organization_data.get("motto"),
                color=organization_data.get("color")
            )
            db.add(organization)
            await db.flush()

            logger.info(f"Tạo chi tiết tổ chức thành công: {character.name} (Org ID: {organization.id})")

            yield await tracker.saving("Đang lưu lịch sử tạo...", 0.9)

            # Ghi lịch sử tạo
            history = GenerationHistory(
                project_id=gen_request.project_id,
                prompt=prompt,
                generated_content=ai_content,
                model=user_ai_service.default_model
            )
            db.add(history)

            await db.commit()
            await db.refresh(character)

            logger.info(f"Tạo tổ chức thành công: {character.name}")

            yield await tracker.complete("Tạo tổ chức hoàn tất!")

            # Gửi dữ liệu kết quả
            yield await tracker.result({
                "character": {
                    "id": character.id,
                    "name": character.name,
                    "organization_type": character.organization_type,
                    "is_organization": character.is_organization
                }
            })

            yield await tracker.done()

        except HTTPException as he:
            logger.error(f"Ngoại lệ HTTP: {he.detail}")
            yield await tracker.error(he.detail, he.status_code)
        except Exception as e:
            logger.error(f"Tạo tổ chức thất bại: {str(e)}")
            yield await tracker.error(f"Tạo tổ chức thất bại: {str(e)}")

    return create_sse_response(generate())
