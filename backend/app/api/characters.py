"""API quản lý nhân vật"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json
from typing import AsyncGenerator

from app.database import get_db
from app.utils.sse_response import SSEResponse, create_sse_response, WizardProgressTracker, wrap_stream_with_heartbeat, HEARTBEAT
from app.models.character import Character
from app.models.project import Project
from app.models.generation_history import GenerationHistory
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember, RelationshipType
from app.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterListResponse,
    CharacterGenerateRequest
)
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.services.import_export_service import ImportExportService
from app.schemas.import_export import CharactersExportRequest, CharactersImportResult
from app.logger import get_logger, safe_preview
from app.api.settings import get_user_ai_service
from app.api.common import verify_project_access

router = APIRouter(prefix="/characters", tags=["Quản lý nhân vật"])
logger = get_logger(__name__)


async def _build_relationships_summary(character_id: str, project_id: str, db: AsyncSession) -> str:
    """Xây dựng văn bản tóm tắt quan hệ nhân vật từ bảng character_relationships"""
    from sqlalchemy import or_

    # Truy vấn mọi quan hệ mà nhân vật này tham gia
    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.project_id == project_id,
            or_(
                CharacterRelationship.character_from_id == character_id,
                CharacterRelationship.character_to_id == character_id
            )
        )
    )
    rels = rels_result.scalars().all()

    if not rels:
        return ""

    # Thu thập mọi ID nhân vật liên quan
    related_ids = set()
    for r in rels:
        related_ids.add(r.character_from_id)
        related_ids.add(r.character_to_id)
    related_ids.discard(character_id)

    if not related_ids:
        return ""

    # Truy vấn tên nhân vật hàng loạt
    chars_result = await db.execute(
        select(Character.id, Character.name).where(Character.id.in_(related_ids))
    )
    name_map = {row.id: row.name for row in chars_result}

    # Xây dựng tóm tắt
    parts = []
    for r in rels:
        if r.character_from_id == character_id:
            target_name = name_map.get(r.character_to_id, "Không xác định")
            rel_name = r.relationship_name or "Liên quan"
        else:
            target_name = name_map.get(r.character_from_id, "Không xác định")
            rel_name = r.relationship_name or "Liên quan"
        parts.append(f"Với {target_name}: {rel_name}")

    return "; ".join(parts)


async def _build_org_members_summary(character_id: str, db: AsyncSession) -> str:
    """Xây dựng chuỗi JSON thành viên tổ chức từ bảng organization_members (giữ khớp với schema)"""
    # Tìm bản ghi Organization tương ứng của nhân vật này trước
    org_result = await db.execute(
        select(Organization).where(Organization.character_id == character_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        return ""

    # Truy vấn mọi thành viên của tổ chức (sắp xếp theo cấp bậc giảm dần, đảm bảo thứ tự hiển thị ổn định)
    members_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.rank.desc(), OrganizationMember.created_at)
    )
    members = members_result.scalars().all()
    if not members:
        return ""

    # Truy vấn tên nhân vật thành viên hàng loạt
    member_char_ids = [m.character_id for m in members]
    chars_result = await db.execute(
        select(Character.id, Character.name).where(Character.id.in_(member_char_ids))
    )
    name_map = {row.id: row.name for row in chars_result}

    # Trả về mảng chuỗi JSON, tránh lỗi JSON.parse ở frontend
    member_items = []
    for m in members:
        name = name_map.get(m.character_id, "Không xác định")
        position = m.position or "Thành viên"
        member_items.append(f"{name} ({position})")

    return json.dumps(member_items, ensure_ascii=False)


@router.get("", response_model=CharacterListResponse, summary="Lấy danh sách nhân vật")
async def get_characters(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy mọi nhân vật của dự án được chỉ định (phiên bản tham số query)"""
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    # Lấy tổng số
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    total = count_result.scalar_one()

    # Lấy danh sách nhân vật
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.created_at.desc())
    )
    characters = result.scalars().all()

    # Điền tóm tắt quan hệ, các trường phụ tổ chức, thông tin nghề nghiệp cho nhân vật
    enriched_characters = []
    for char in characters:
        # Tạo động tóm tắt quan hệ từ bảng character_relationships
        rel_summary = await _build_relationships_summary(char.id, project_id, db)

        char_dict = {
            "id": char.id,
            "project_id": char.project_id,
            "name": char.name,
            "age": char.age,
            "gender": char.gender,
            "is_organization": char.is_organization,
            "role_type": char.role_type,
            "personality": char.personality,
            "background": char.background,
            "appearance": char.appearance,
            "relationships": rel_summary,
            "organization_type": char.organization_type,
            "organization_purpose": char.organization_purpose,
            "organization_members": await _build_org_members_summary(char.id, db) if char.is_organization else "",
            "traits": char.traits,
            "avatar_url": char.avatar_url,
            "created_at": char.created_at,
            "updated_at": char.updated_at,
            "power_level": None,
            "location": None,
            "motto": None,
            "color": None,
            "main_career_id": char.main_career_id,
            "main_career_stage": char.main_career_stage,
            "sub_careers": json.loads(char.sub_careers) if char.sub_careers else None
        }

        if char.is_organization:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                char_dict.update({
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto,
                    "color": org.color
                })

        enriched_characters.append(char_dict)

    return CharacterListResponse(total=total, items=enriched_characters)


@router.get("/project/{project_id}", response_model=CharacterListResponse, summary="Lấy mọi nhân vật của dự án")
async def get_project_characters(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy mọi nhân vật của dự án được chỉ định (phiên bản tham số đường dẫn)"""
    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    # Lấy tổng số
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    total = count_result.scalar_one()

    # Lấy danh sách nhân vật
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.created_at.desc())
    )
    characters = result.scalars().all()

    # Điền tóm tắt quan hệ, các trường phụ tổ chức, thông tin nghề nghiệp cho nhân vật
    enriched_characters = []
    for char in characters:
        # Tạo động tóm tắt quan hệ từ bảng character_relationships
        rel_summary = await _build_relationships_summary(char.id, project_id, db)

        char_dict = {
            "id": char.id,
            "project_id": char.project_id,
            "name": char.name,
            "age": char.age,
            "gender": char.gender,
            "is_organization": char.is_organization,
            "role_type": char.role_type,
            "personality": char.personality,
            "background": char.background,
            "appearance": char.appearance,
            "relationships": rel_summary,
            "organization_type": char.organization_type,
            "organization_purpose": char.organization_purpose,
            "organization_members": await _build_org_members_summary(char.id, db) if char.is_organization else "",
            "traits": char.traits,
            "avatar_url": char.avatar_url,
            "created_at": char.created_at,
            "updated_at": char.updated_at,
            "power_level": None,
            "location": None,
            "motto": None,
            "color": None,
            "main_career_id": char.main_career_id,
            "main_career_stage": char.main_career_stage,
            "sub_careers": json.loads(char.sub_careers) if char.sub_careers else None
        }

        if char.is_organization:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                char_dict.update({
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto,
                    "color": org.color
                })

        enriched_characters.append(char_dict)

    return CharacterListResponse(total=total, items=enriched_characters)


@router.get("/{character_id}", response_model=CharacterResponse, summary="Lấy chi tiết nhân vật")
async def get_character(
    character_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết nhân vật theo ID"""
    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Tạo động tóm tắt quan hệ từ bảng character_relationships
    rel_summary = await _build_relationships_summary(character.id, character.project_id, db)

    char_dict = {
        "id": character.id,
        "project_id": character.project_id,
        "name": character.name,
        "age": character.age,
        "gender": character.gender,
        "is_organization": character.is_organization,
        "role_type": character.role_type,
        "personality": character.personality,
        "background": character.background,
        "appearance": character.appearance,
        "relationships": rel_summary,
        "organization_type": character.organization_type,
        "organization_purpose": character.organization_purpose,
        "organization_members": await _build_org_members_summary(character.id, db) if character.is_organization else "",
        "traits": character.traits,
        "avatar_url": character.avatar_url,
        "created_at": character.created_at,
        "updated_at": character.updated_at,
        "power_level": None,
        "location": None,
        "motto": None,
        "color": None,
        "main_career_id": character.main_career_id,
        "main_career_stage": character.main_career_stage,
        "sub_careers": json.loads(character.sub_careers) if character.sub_careers else None
    }

    if character.is_organization:
        org_result = await db.execute(
            select(Organization).where(Organization.character_id == character.id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            char_dict.update({
                "power_level": org.power_level,
                "location": org.location,
                "motto": org.motto,
                "color": org.color
            })

    return char_dict


@router.put("/{character_id}", response_model=CharacterResponse, summary="Cập nhật nhân vật")
async def update_character(
    character_id: str,
    character_update: CharacterUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thông tin nhân vật"""
    from app.models.career import CharacterCareer, Career

    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Cập nhật các trường
    update_data = character_update.model_dump(exclude_unset=True)

    # Nếu là tổ chức, cần đồng bộ cập nhật các trường của bảng Organization
    org_fields = {}
    if character.is_organization:
        # Trích xuất các trường cần đồng bộ sang bảng Organization
        if 'power_level' in update_data:
            org_fields['power_level'] = update_data.pop('power_level')
        if 'location' in update_data:
            org_fields['location'] = update_data.pop('location')
        if 'motto' in update_data:
            org_fields['motto'] = update_data.pop('motto')
        if 'color' in update_data:
            org_fields['color'] = update_data.pop('color')

    # Xử lý cập nhật nghề chính và nghề phụ
    main_career_id = update_data.pop('main_career_id', None)
    main_career_stage = update_data.pop('main_career_stage', None)
    sub_careers_json = update_data.pop('sub_careers', None)

    if main_career_id is not None:
        # Kiểm tra nghề nghiệp tồn tại
        if main_career_id:  # Không rỗng
            career_result = await db.execute(
                select(Career).where(
                    Career.id == main_career_id,
                    Career.project_id == character.project_id,
                    Career.type == 'main'
                )
            )
            career = career_result.scalar_one_or_none()

            if not career:
                raise HTTPException(status_code=400, detail="Nghề chính không tồn tại hoặc loại không đúng")

            # Kiểm tra tính hợp lệ của cấp
            if main_career_stage and main_career_stage > career.max_stage:
                raise HTTPException(status_code=400, detail=f"Cấp vượt quá phạm vi, cấp tối đa của nghề nghiệp này là {career.max_stage}")

            # Cập nhật hoặc tạo liên kết CharacterCareer
            char_career_result = await db.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == character_id,
                    CharacterCareer.career_type == 'main'
                )
            )
            char_career = char_career_result.scalar_one_or_none()

            if char_career:
                # Cập nhật liên kết hiện có
                char_career.career_id = main_career_id
                if main_career_stage:
                    char_career.current_stage = main_career_stage
                logger.info(f"Cập nhật liên kết nghề chính: {character.name} -> {career.name}")
            else:
                # Tạo liên kết mới
                char_career = CharacterCareer(
                    character_id=character_id,
                    career_id=main_career_id,
                    career_type='main',
                    current_stage=main_career_stage or 1,
                    stage_progress=0
                )
                db.add(char_career)
                logger.info(f"Tạo liên kết nghề chính: {character.name} -> {career.name}")

            # Cập nhật các trường dư thừa của bảng Character
            character.main_career_id = main_career_id
            character.main_career_stage = main_career_stage or char_career.current_stage
        else:
            # Xóa nghề chính
            char_career_result = await db.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == character_id,
                    CharacterCareer.career_type == 'main'
                )
            )
            char_career = char_career_result.scalar_one_or_none()
            if char_career:
                await db.delete(char_career)
                logger.info(f"Gỡ liên kết nghề chính: {character.name}")

            character.main_career_id = None
            character.main_career_stage = None
    elif main_career_stage is not None and character.main_career_id:
        # Chỉ cập nhật cấp
        char_career_result = await db.execute(
            select(CharacterCareer).where(
                CharacterCareer.character_id == character_id,
                CharacterCareer.career_type == 'main'
            )
        )
        char_career = char_career_result.scalar_one_or_none()
        if char_career:
            char_career.current_stage = main_career_stage
            character.main_career_stage = main_career_stage
            logger.info(f"Cập nhật cấp nghề chính: {character.name} -> cấp {main_career_stage}")

    # Xử lý cập nhật nghề phụ
    if sub_careers_json is not None:
        # Phân tích JSON nghề phụ
        try:
            sub_careers_data = json.loads(sub_careers_json) if isinstance(sub_careers_json, str) else sub_careers_json
        except Exception:
            sub_careers_data = []

        # Xóa mọi liên kết nghề phụ hiện có
        existing_subs = await db.execute(
            select(CharacterCareer).where(
                CharacterCareer.character_id == character_id,
                CharacterCareer.career_type == 'sub'
            )
        )
        for sub_career in existing_subs.scalars():
            await db.delete(sub_career)

        # Tạo các liên kết nghề phụ mới
        for sub_data in sub_careers_data[:2]:  # Tối đa 2 nghề phụ
            career_id = sub_data.get('career_id')
            if not career_id:
                continue

            # Kiểm tra nghề phụ tồn tại
            career_result = await db.execute(
                select(Career).where(
                    Career.id == career_id,
                    Career.project_id == character.project_id,
                    Career.type == 'sub'
                )
            )
            career = career_result.scalar_one_or_none()

            if career:
                # Tạo liên kết nghề phụ
                char_career = CharacterCareer(
                    character_id=character_id,
                    career_id=career_id,
                    career_type='sub',
                    current_stage=sub_data.get('stage', 1),
                    stage_progress=0
                )
                db.add(char_career)
                logger.info(f"Thêm liên kết nghề phụ: {character.name} -> {career.name}")

        # Cập nhật trường dư thừa sub_careers của bảng Character
        character.sub_careers = sub_careers_json if isinstance(sub_careers_json, str) else json.dumps(sub_careers_data, ensure_ascii=False)
        logger.info(f"Cập nhật thông tin nghề phụ: {character.name}")

    # Cập nhật các trường bảng Character (loại trừ relationships và organization_members, các trường này giờ do bảng cấu trúc điều khiển)
    update_data.pop('relationships', None)
    update_data.pop('organization_members', None)
    for field, value in update_data.items():
        setattr(character, field, value)

    # Nếu là tổ chức và có trường cần đồng bộ, cập nhật bảng Organization
    if character.is_organization and org_fields:
        org_result = await db.execute(
            select(Organization).where(Organization.character_id == character_id)
        )
        org = org_result.scalar_one_or_none()

        if org:
            for field, value in org_fields.items():
                setattr(org, field, value)
            logger.info(f"Đồng bộ cập nhật chi tiết tổ chức: {character.name}")
        else:
            # Nếu bản ghi Organization chưa tồn tại, tự động tạo
            org = Organization(
                character_id=character_id,
                project_id=character.project_id,
                member_count=0,
                **org_fields
            )
            db.add(org)
            logger.info(f"Tự động tạo chi tiết tổ chức: {character.name}")

    await db.commit()
    await db.refresh(character)

    logger.info(f"Cập nhật nhân vật/tổ chức thành công: {character.name} (ID: {character_id})")

    # Xây dựng response, tạo động relationships từ bảng quan hệ
    rel_summary = await _build_relationships_summary(character_id, character.project_id, db)
    response_data = {
        "id": character.id,
        "project_id": character.project_id,
        "name": character.name,
        "age": character.age,
        "gender": character.gender,
        "is_organization": character.is_organization,
        "role_type": character.role_type,
        "personality": character.personality,
        "background": character.background,
        "appearance": character.appearance,
        "relationships": rel_summary,
        "organization_type": character.organization_type,
        "organization_purpose": character.organization_purpose,
        "organization_members": await _build_org_members_summary(character.id, db) if character.is_organization else "",
        "traits": character.traits,
        "avatar_url": character.avatar_url,
        "created_at": character.created_at,
        "updated_at": character.updated_at,
        "main_career_id": character.main_career_id,
        "main_career_stage": character.main_career_stage,
        "sub_careers": json.loads(character.sub_careers) if character.sub_careers else None,
        "power_level": None,
        "location": None,
        "motto": None,
        "color": None
    }

    # Nếu là tổ chức, thêm các trường phụ tổ chức
    if character.is_organization:
        org_result = await db.execute(
            select(Organization).where(Organization.character_id == character_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            response_data.update({
                "power_level": org.power_level,
                "location": org.location,
                "motto": org.motto,
                "color": org.color
            })

    return response_data


@router.delete("/{character_id}", summary="Xóa nhân vật")
async def delete_character(
    character_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa nhân vật"""
    from app.models.career import CharacterCareer

    result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Dọn dẹp liên kết nhân vật - nghề nghiệp
    career_relations_result = await db.execute(
        select(CharacterCareer).where(CharacterCareer.character_id == character_id)
    )
    career_relations = career_relations_result.scalars().all()

    for relation in career_relations:
        await db.delete(relation)
        logger.info(f"Xóa liên kết nghề nghiệp nhân vật: character_id={character_id}, career_id={relation.career_id}, type={relation.career_type}")

    # Xóa nhân vật
    await db.delete(character)
    await db.commit()

    logger.info(f"Xóa nhân vật thành công: {character.name} (ID: {character_id}), đã dọn {len(career_relations)} liên kết nghề nghiệp")

    return {"message": "Xóa nhân vật thành công"}


@router.post("", response_model=CharacterResponse, summary="Tạo nhân vật thủ công")
async def create_character(
    character_data: CharacterCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo nhân vật hoặc tổ chức thủ công

    - Có thể tạo nhân vật thường (is_organization=False)
    - Cũng có thể tạo tổ chức (is_organization=True)
    - Nếu tạo tổ chức và có các trường phụ tổ chức, sẽ tự động tạo bản ghi chi tiết Organization
    - Hỗ trợ đặt nghề chính và nghề phụ
    """
    from app.models.career import CharacterCareer, Career

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character_data.project_id, user_id, db)

    try:
        # Tạo nhân vật (không ghi trường văn bản relationships nữa, quan hệ do bảng character_relationships quản lý thống nhất)
        character = Character(
            project_id=character_data.project_id,
            name=character_data.name,
            age=character_data.age,
            gender=character_data.gender,
            is_organization=character_data.is_organization,
            role_type=character_data.role_type or "supporting",
            personality=character_data.personality,
            background=character_data.background,
            appearance=character_data.appearance,
            organization_type=character_data.organization_type,
            organization_purpose=character_data.organization_purpose,
            traits=character_data.traits,
            avatar_url=character_data.avatar_url,
            main_career_id=character_data.main_career_id,
            main_career_stage=character_data.main_career_stage,
            sub_careers=character_data.sub_careers
        )
        db.add(character)
        await db.flush()  # Lấy character.id

        logger.info(f"✅ Tạo nhân vật thủ công thành công: {character.name} (ID: {character.id}, có phải tổ chức: {character.is_organization})")

        # Xử lý liên kết nghề chính
        if character_data.main_career_id and not character.is_organization:
            # Kiểm tra nghề nghiệp tồn tại
            career_result = await db.execute(
                select(Career).where(
                    Career.id == character_data.main_career_id,
                    Career.project_id == character_data.project_id,
                    Career.type == 'main'
                )
            )
            career = career_result.scalar_one_or_none()

            if career:
                # Tạo liên kết nghề chính
                char_career = CharacterCareer(
                    character_id=character.id,
                    career_id=character_data.main_career_id,
                    career_type='main',
                    current_stage=character_data.main_career_stage or 1,
                    stage_progress=0
                )
                db.add(char_career)
                logger.info(f"✅ Tạo liên kết nghề chính: {character.name} -> {career.name}")
            else:
                logger.warning(f"⚠️ ID nghề chính không tồn tại hoặc loại không đúng: {character_data.main_career_id}")

        # Xử lý liên kết nghề phụ
        if character_data.sub_careers and not character.is_organization:
            try:
                sub_careers_data = json.loads(character_data.sub_careers) if isinstance(character_data.sub_careers, str) else character_data.sub_careers

                for sub_data in sub_careers_data[:2]:  # Tối đa 2 nghề phụ
                    career_id = sub_data.get('career_id')
                    if not career_id:
                        continue

                    # Kiểm tra nghề phụ tồn tại
                    career_result = await db.execute(
                        select(Career).where(
                            Career.id == career_id,
                            Career.project_id == character_data.project_id,
                            Career.type == 'sub'
                        )
                    )
                    career = career_result.scalar_one_or_none()

                    if career:
                        # Tạo liên kết nghề phụ
                        char_career = CharacterCareer(
                            character_id=character.id,
                            career_id=career_id,
                            career_type='sub',
                            current_stage=sub_data.get('stage', 1),
                            stage_progress=0
                        )
                        db.add(char_career)
                        logger.info(f"✅ Tạo liên kết nghề phụ: {character.name} -> {career.name}")
                    else:
                        logger.warning(f"⚠️ ID nghề phụ không tồn tại hoặc loại không đúng: {career_id}")
            except Exception as e:
                logger.warning(f"⚠️ Phân tích dữ liệu nghề phụ thất bại: {e}")

        # Nếu là tổ chức và có các trường phụ tổ chức, tự động tạo bản ghi chi tiết Organization
        if character.is_organization and (
            character_data.power_level is not None or
            character_data.location or
            character_data.motto or
            character_data.color
        ):
            organization = Organization(
                character_id=character.id,
                project_id=character_data.project_id,
                member_count=0,
                power_level=character_data.power_level or 50,
                location=character_data.location,
                motto=character_data.motto,
                color=character_data.color
            )
            db.add(organization)
            await db.flush()
            logger.info(f"✅ Tự động tạo chi tiết tổ chức: {character.name} (Org ID: {organization.id})")

        await db.commit()
        await db.refresh(character)

        logger.info(f"🎉 Tạo nhân vật/tổ chức thủ công thành công: {character.name}")

        # Xây dựng response (relationships tạo động từ bảng quan hệ)
        char_dict = {
            "id": character.id,
            "project_id": character.project_id,
            "name": character.name,
            "age": character.age,
            "gender": character.gender,
            "is_organization": character.is_organization,
            "role_type": character.role_type,
            "personality": character.personality,
            "background": character.background,
            "appearance": character.appearance,
            "relationships": "",
            "organization_type": character.organization_type,
            "organization_purpose": character.organization_purpose,
            "organization_members": await _build_org_members_summary(character.id, db) if character.is_organization else "",
            "traits": character.traits,
            "avatar_url": character.avatar_url,
            "created_at": character.created_at,
            "updated_at": character.updated_at,
            "power_level": None,
            "location": None,
            "motto": None,
            "color": None,
            "main_career_id": character.main_career_id,
            "main_career_stage": character.main_career_stage,
            "sub_careers": json.loads(character.sub_careers) if character.sub_careers else None
        }

        if character.is_organization:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == character.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                char_dict.update({
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto,
                    "color": org.color
                })

        return char_dict

    except Exception as e:
        logger.error(f"Tạo nhân vật thủ công thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tạo nhân vật thất bại: {str(e)}")


@router.post("/generate-stream", summary="AI tạo nhân vật (streaming)")
async def generate_character_stream(
    request: CharacterGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng AI tạo thẻ nhân vật (hỗ trợ hiển thị tiến trình streaming SSE)

    Trả về thông tin tiến trình theo thời gian thực qua Server-Sent Events
    """
    async def generate() -> AsyncGenerator[str, None]:
        tracker = WizardProgressTracker("Nhân vật")
        try:
            # Kiểm tra quyền người dùng và dự án có tồn tại không
            user_id = getattr(http_request.state, 'user_id', None)
            project = await verify_project_access(request.project_id, user_id, db)

            yield await tracker.start()

            # Lấy danh sách nhân vật hiện có
            yield await tracker.loading("Đang lấy ngữ cảnh dự án...", 0.3)

            existing_chars_result = await db.execute(
                select(Character)
                .where(Character.project_id == request.project_id)
                .order_by(Character.created_at.desc())
            )
            existing_characters = existing_chars_result.scalars().all()

            # Xây dựng tóm tắt thông tin nhân vật hiện có
            existing_chars_info = ""
            character_list = []
            organization_list = []

            if existing_characters:
                for c in existing_characters[:10]:
                    if c.is_organization:
                        organization_list.append(f"- {c.name} [{c.organization_type or 'Tổ chức'}]")
                    else:
                        character_list.append(f"- {c.name} ({c.role_type or 'Không xác định'})")

                if character_list:
                    existing_chars_info += "\nNhân vật hiện có:\n" + "\n".join(character_list)
                if organization_list:
                    existing_chars_info += "\n\nTổ chức hiện có:\n" + "\n".join(organization_list)

            # 🎯 Lấy danh sách nghề nghiệp của dự án
            from app.models.career import Career
            careers_result = await db.execute(
                select(Career)
                .where(Career.project_id == request.project_id)
                .order_by(Career.type, Career.name)
            )
            careers = careers_result.scalars().all()

            # Xây dựng tóm tắt thông tin nghề nghiệp
            careers_info = ""
            if careers:
                main_careers = [c for c in careers if c.type == 'main']
                sub_careers = [c for c in careers if c.type == 'sub']

                if main_careers:
                    careers_info += "\n\nDanh sách nghề chính khả dụng (hãy điền tên nghề nghiệp vào career_info, hệ thống sẽ tự khớp ID):\n"
                    for career in main_careers:
                        # Phân tích thông tin cấp
                        import json as json_lib
                        try:
                            stages = json_lib.loads(career.stages) if career.stages else []
                            stage_names = [s.get('name', f'Cấp {s.get("level")}') for s in stages[:3]]  # Chỉ hiển thị 3 cấp đầu
                            stage_info = " → ".join(stage_names)
                            if len(stages) > 3:
                                stage_info += " → ..."
                        except Exception:
                            stage_info = f"Tổng {career.max_stage} cấp"

                        careers_info += f"- Tên: {career.name}"
                        if career.description:
                            careers_info += f", Mô tả: {career.description[:50]}"
                        careers_info += f", Cấp: {stage_info}\n"

                if sub_careers:
                    careers_info += "\nDanh sách nghề phụ khả dụng (hãy điền tên nghề nghiệp vào career_info, hệ thống sẽ tự khớp ID):\n"
                    for career in sub_careers[:5]:  # Hiển thị tối đa 5 nghề phụ
                        careers_info += f"- Tên: {career.name}"
                        if career.description:
                            careers_info += f", Mô tả: {career.description[:50]}"
                        careers_info += "\n"
            else:
                careers_info = "\n\n⚠️ Dự án tạm thời chưa có thiết lập nghề nghiệp"

            # Xây dựng ngữ cảnh dự án
            project_context = f"""
Thông tin dự án:
- Tên sách: {project.title}
- Chủ đề: {project.theme or 'Chưa đặt'}
- Thể loại: {project.genre or 'Chưa đặt'}
- Bối cảnh thời gian: {project.world_time_period or 'Chưa đặt'}
- Vị trí địa lý: {project.world_location or 'Chưa đặt'}
- Tông màu không khí: {project.world_atmosphere or 'Chưa đặt'}
- Quy tắc thế giới: {project.world_rules or 'Chưa đặt'}
{existing_chars_info}
{careers_info}
"""

            user_input = f"""
Yêu cầu của người dùng:
- Tên nhân vật: {request.name or 'Hãy để AI tạo'}
- Định vị nhân vật: {request.role_type or 'supporting'}
- Thiết lập bối cảnh: {request.background or 'Không yêu cầu đặc biệt'}
- Yêu cầu khác: {request.requirements or 'Không'}
"""

            yield await tracker.loading("Hoàn tất chuẩn bị ngữ cảnh dự án", 0.7)
            yield await tracker.preparing("Đang xây dựng prompt AI...")

            # Lấy mẫu prompt tùy chỉnh
            template = await PromptService.get_template("SINGLE_CHARACTER_GENERATION", user_id, db)
            # Định dạng prompt
            prompt = PromptService.format_prompt(
                template,
                project_context=project_context,
                user_input=user_input
            )

            yield await tracker.generating(0, max(3000, len(prompt) * 8), "Đang gọi dịch vụ AI tạo nhân vật...")
            logger.info(f"🎯 Bắt đầu tạo nhân vật cho dự án {request.project_id} (streaming SSE)")

            try:
                # Dùng trực tiếp streaming của AIService
                ai_response = ""
                chunk_count = 0
                estimated_total = max(3000, len(prompt) * 8)

                logger.info(f"🎯 Bắt đầu tạo nhân vật (chế độ streaming)...")
                yield await tracker.generating(0, estimated_total, "Bắt đầu tạo nhân vật...")

                async for chunk in wrap_stream_with_heartbeat(
                    user_ai_service.generate_text_stream(
                        prompt=prompt,
                        tool_choice="required",
                    ),
                    heartbeat_interval=15.0
                ):
                    # Sentinel heartbeat: gửi heartbeat giữ kết nối, không trộn vào response AI
                    if chunk is HEARTBEAT:
                        yield await tracker.heartbeat()
                        continue

                    # chunk giờ có thể là dict hoặc str, trích xuất trường content
                    if isinstance(chunk, dict):
                        content = chunk.get("content", "")
                    else:
                        content = chunk

                    if content:
                        ai_response += content

                        # Gửi khối nội dung
                        yield await SSEResponse.send_chunk(content)

                        # Cập nhật tiến trình định kỳ (mỗi ~500 ký tự cập nhật một lần, tránh quá thường xuyên)
                        current_len = len(ai_response)
                        if current_len >= chunk_count * 500:
                            chunk_count += 1
                            yield await tracker.generating(current_len, estimated_total)

                        # Heartbeat
                        if chunk_count % 20 == 0:
                            yield await tracker.heartbeat()

            except Exception as ai_error:
                logger.error(f"❌ Lỗi gọi dịch vụ AI: {str(ai_error)}")
                yield await tracker.error(f"Gọi dịch vụ AI thất bại: {str(ai_error)}")
                return

            if not ai_response or not ai_response.strip():
                logger.error(
                    "❌ Dịch vụ AI trả về response rỗng: chưa nhận được chính văn. Nếu dùng mô hình suy luận, nội dung suy nghĩ sẽ không được ghi vào JSON nhân vật, hãy kiểm tra mô hình có xuất JSON cuối cùng không."
                )
                yield await tracker.error("Dịch vụ AI trả về response rỗng")
                return

            yield await tracker.parsing("Đang phân tích response AI...", 0.5)

            # ✅ Dùng phương thức làm sạch JSON thống nhất
            try:
                cleaned_response = user_ai_service._clean_json_response(ai_response)
                character_data = loads_json(cleaned_response)
                logger.info(f"✅ Phân tích JSON nhân vật thành công")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Phân tích JSON nhân vật thất bại: {e}")
                logger.debug(f"   Xem trước response gốc: {safe_preview(ai_response, 200)}")
                yield await tracker.error(f"Nội dung AI trả về không phân tích được thành JSON: {str(e)}")
                return

            yield await tracker.saving("Đang tạo bản ghi nhân vật...", 0.3)

            # Chuyển đổi traits
            traits_json = json.dumps(character_data.get("traits", []), ensure_ascii=False) if character_data.get("traits") else None
            is_organization = character_data.get("is_organization", False)

            # Trích xuất thông tin nghề nghiệp (hỗ trợ khớp theo tên)
            career_info = character_data.get("career_info", {})
            raw_main_career_name = career_info.get("main_career_name") if career_info else None
            main_career_stage = career_info.get("main_career_stage", 1) if career_info else None
            raw_sub_careers_data = career_info.get("sub_careers", []) if career_info else []

            # Log debug: xuất thông tin nghề nghiệp
            logger.info(f"🔍 Trích xuất thông tin nghề nghiệp - career_info: {career_info}")
            logger.info(f"🔍 raw_main_career_name: {raw_main_career_name}, main_career_stage: {main_career_stage}")
            logger.info(f"🔍 kiểu raw_sub_careers_data: {type(raw_sub_careers_data)}, nội dung: {raw_sub_careers_data}")

            # 🔧 Khớp ID nghề nghiệp trong cơ sở dữ liệu theo tên nghề nghiệp
            from app.models.career import Career
            main_career_id = None
            sub_careers_data = []

            # Khớp tên nghề chính
            if raw_main_career_name and not is_organization:
                career_check = await db.execute(
                    select(Career).where(
                        Career.name == raw_main_career_name,
                        Career.project_id == request.project_id,
                        Career.type == 'main'
                    )
                )
                matched_career = career_check.scalar_one_or_none()
                if matched_career:
                    main_career_id = matched_career.id
                    logger.info(f"✅ Khớp tên nghề chính thành công: {raw_main_career_name} -> ID: {main_career_id}")
                else:
                    logger.warning(f"⚠️ Không tìm thấy tên nghề chính do AI trả về: {raw_main_career_name}")

            # Khớp tên nghề phụ
            if raw_sub_careers_data and not is_organization and isinstance(raw_sub_careers_data, list):
                for sub_data in raw_sub_careers_data[:2]:
                    if isinstance(sub_data, dict):
                        career_name = sub_data.get('career_name')
                        if career_name:
                            career_check = await db.execute(
                                select(Career).where(
                                    Career.name == career_name,
                                    Career.project_id == request.project_id,
                                    Career.type == 'sub'
                                )
                            )
                            matched_career = career_check.scalar_one_or_none()
                            if matched_career:
                                # Chuyển thành định dạng có ID
                                sub_careers_data.append({
                                    'career_id': matched_career.id,
                                    'stage': sub_data.get('stage', 1)
                                })
                                logger.info(f"✅ Khớp tên nghề phụ thành công: {career_name} -> ID: {matched_career.id}")
                            else:
                                logger.warning(f"⚠️ Không tìm thấy tên nghề phụ do AI trả về: {career_name}")

            # Tạo nhân vật (không ghi trường văn bản relationships nữa, quan hệ do bảng character_relationships quản lý thống nhất)
            character = Character(
                project_id=request.project_id,
                name=character_data.get("name", request.name or "Nhân vật chưa đặt tên"),
                age=str(character_data.get("age", "")),
                gender=character_data.get("gender"),
                is_organization=is_organization,
                role_type=request.role_type or "supporting",
                personality=character_data.get("personality", ""),
                background=character_data.get("background", ""),
                appearance=character_data.get("appearance", ""),
                organization_type=character_data.get("organization_type") if is_organization else None,
                organization_purpose=character_data.get("organization_purpose") if is_organization else None,
                traits=traits_json,
                main_career_id=main_career_id,
                main_career_stage=main_career_stage if main_career_id else None,
                sub_careers=json.dumps(sub_careers_data, ensure_ascii=False) if sub_careers_data else None
            )
            db.add(character)
            await db.flush()

            logger.info(f"✅ Tạo nhân vật thành công: {character.name} (ID: {character.id})")

            # Xử lý liên kết nghề chính
            if main_career_id and not is_organization:
                from app.models.career import CharacterCareer, Career

                career_result = await db.execute(
                    select(Career).where(
                        Career.id == main_career_id,
                        Career.project_id == request.project_id,
                        Career.type == 'main'
                    )
                )
                career = career_result.scalar_one_or_none()

                if career:
                    char_career = CharacterCareer(
                        character_id=character.id,
                        career_id=main_career_id,
                        career_type='main',
                        current_stage=main_career_stage,
                        stage_progress=0
                    )
                    db.add(char_career)
                    logger.info(f"✅ AI tạo nhân vật - tạo liên kết nghề chính: {character.name} -> {career.name}")
                else:
                    logger.warning(f"⚠️ ID nghề chính do AI trả về không tồn tại: {main_career_id}")

            # Xử lý liên kết nghề phụ
            if sub_careers_data and not is_organization:
                from app.models.career import CharacterCareer, Career

                logger.info(f"🔍 Bắt đầu xử lý liên kết nghề phụ, dữ liệu: {sub_careers_data}")

                # Đảm bảo sub_careers_data là list
                if not isinstance(sub_careers_data, list):
                    logger.warning(f"⚠️ sub_careers_data không phải kiểu list: {type(sub_careers_data)}")
                    sub_careers_data = []

                for idx, sub_data in enumerate(sub_careers_data[:2]):  # Tối đa 2 nghề phụ
                    logger.info(f"🔍 Đang xử lý nghề phụ thứ {idx+1}, dữ liệu: {sub_data}, kiểu: {type(sub_data)}")

                    # Tương thích các định dạng dữ liệu khác nhau
                    if isinstance(sub_data, dict):
                        career_id = sub_data.get('career_id')
                        stage = sub_data.get('stage', 1)
                    else:
                        logger.warning(f"⚠️ Định dạng dữ liệu nghề phụ sai, phải là dict: {sub_data}")
                        continue

                    if not career_id:
                        logger.warning(f"⚠️ Dữ liệu nghề phụ thiếu trường career_id")
                        continue

                    logger.info(f"🔍 Truy vấn nghề phụ: career_id={career_id}, project_id={request.project_id}")

                    career_result = await db.execute(
                        select(Career).where(
                            Career.id == career_id,
                            Career.project_id == request.project_id,
                            Career.type == 'sub'
                        )
                    )
                    career = career_result.scalar_one_or_none()

                    if career:
                        char_career = CharacterCareer(
                            character_id=character.id,
                            career_id=career_id,
                            career_type='sub',
                            current_stage=stage,
                            stage_progress=0
                        )
                        db.add(char_career)
                        logger.info(f"✅ AI tạo nhân vật - tạo liên kết nghề phụ: {character.name} -> {career.name} (cấp {stage})")
                    else:
                        logger.warning(f"⚠️ ID nghề phụ do AI trả về không tồn tại: {career_id} (project ID: {request.project_id})")

            # Nếu là tổ chức, tạo chi tiết Organization
            if is_organization:
                yield await tracker.saving("Đang tạo chi tiết tổ chức...", 0.6)

                org_check = await db.execute(
                    select(Organization).where(Organization.character_id == character.id)
                )
                existing_org = org_check.scalar_one_or_none()

                if not existing_org:
                    organization = Organization(
                        character_id=character.id,
                        project_id=request.project_id,
                        member_count=0,
                        power_level=character_data.get("power_level", 50),
                        location=character_data.get("location"),
                        motto=character_data.get("motto"),
                        color=character_data.get("color")
                    )
                    db.add(organization)
                    await db.flush()

            # Xử lý dữ liệu quan hệ cấu trúc (chỉ với nhân vật không phải tổ chức)
            if not is_organization:
                relationships_data = character_data.get("relationships", [])
                if relationships_data and isinstance(relationships_data, list):
                    logger.info(f"📊 Bắt đầu xử lý {len(relationships_data)} dữ liệu quan hệ")
                    created_rels = 0

                    for rel in relationships_data:
                        try:
                            target_name = rel.get("target_character_name")
                            if not target_name:
                                logger.debug(f"  ⚠️  Quan hệ thiếu target_character_name, bỏ qua")
                                continue

                            target_result = await db.execute(
                                select(Character).where(
                                    Character.project_id == request.project_id,
                                    Character.name == target_name
                                )
                            )
                            target_char = target_result.scalar_one_or_none()

                            if target_char:
                                # Kiểm tra đã tồn tại quan hệ giống nhau chưa
                                existing_rel = await db.execute(
                                    select(CharacterRelationship).where(
                                        CharacterRelationship.project_id == request.project_id,
                                        CharacterRelationship.character_from_id == character.id,
                                        CharacterRelationship.character_to_id == target_char.id
                                    )
                                )
                                if existing_rel.scalar_one_or_none():
                                    logger.debug(f"  ℹ️  Quan hệ đã tồn tại: {character.name} -> {target_name}")
                                    continue

                                relationship = CharacterRelationship(
                                    project_id=request.project_id,
                                    character_from_id=character.id,
                                    character_to_id=target_char.id,
                                    relationship_name=rel.get("relationship_type", "Quan hệ không xác định"),
                                    intimacy_level=rel.get("intimacy_level", 50),
                                    description=rel.get("description", ""),
                                    started_at=rel.get("started_at"),
                                    source="ai"
                                )

                                # Khớp loại quan hệ định nghĩa sẵn
                                rel_type_result = await db.execute(
                                    select(RelationshipType).where(
                                        RelationshipType.name == rel.get("relationship_type")
                                    )
                                )
                                rel_type = rel_type_result.scalar_one_or_none()
                                if rel_type:
                                    relationship.relationship_type_id = rel_type.id

                                db.add(relationship)
                                created_rels += 1
                                logger.info(f"  ✅ Tạo quan hệ: {character.name} -> {target_name} ({rel.get('relationship_type')})")
                            else:
                                logger.warning(f"  ⚠️  Nhân vật mục tiêu không tồn tại: {target_name}")

                        except Exception as rel_error:
                            logger.warning(f"  ❌ Tạo quan hệ thất bại: {str(rel_error)}")
                            continue

                    logger.info(f"✅ Tạo thành công {created_rels} bản ghi quan hệ")

            # Xử lý quan hệ thành viên tổ chức (chỉ với nhân vật không phải tổ chức)
            if not is_organization:
                org_memberships = character_data.get("organization_memberships", [])
                if org_memberships and isinstance(org_memberships, list):
                    logger.info(f"🏢 Bắt đầu xử lý {len(org_memberships)} quan hệ thành viên tổ chức")
                    created_members = 0

                    for membership in org_memberships:
                        try:
                            org_name = membership.get("organization_name")
                            if not org_name:
                                logger.debug(f"  ⚠️  Quan hệ thành viên tổ chức thiếu organization_name, bỏ qua")
                                continue

                            org_char_result = await db.execute(
                                select(Character).where(
                                    Character.project_id == request.project_id,
                                    Character.name == org_name,
                                    Character.is_organization == True
                                )
                            )
                            org_char = org_char_result.scalar_one_or_none()

                            if org_char:
                                # Lấy hoặc tạo bản ghi Organization
                                org_result = await db.execute(
                                    select(Organization).where(Organization.character_id == org_char.id)
                                )
                                org = org_result.scalar_one_or_none()

                                if not org:
                                    # Nếu Character tổ chức tồn tại nhưng Organization chưa tồn tại, tự động tạo
                                    org = Organization(
                                        character_id=org_char.id,
                                        project_id=request.project_id,
                                        member_count=0
                                    )
                                    db.add(org)
                                    await db.flush()
                                    logger.info(f"  ℹ️  Tự động tạo chi tiết tổ chức còn thiếu: {org_name}")

                                # Kiểm tra đã tồn tại quan hệ thành viên chưa
                                existing_member = await db.execute(
                                    select(OrganizationMember).where(
                                        OrganizationMember.organization_id == org.id,
                                        OrganizationMember.character_id == character.id
                                    )
                                )
                                if existing_member.scalar_one_or_none():
                                    logger.debug(f"  ℹ️  Quan hệ thành viên đã tồn tại: {character.name} -> {org_name}")
                                    continue

                                # Tạo quan hệ thành viên
                                member = OrganizationMember(
                                    organization_id=org.id,
                                    character_id=character.id,
                                    position=membership.get("position", "Thành viên"),
                                    rank=membership.get("rank", 0),
                                    loyalty=membership.get("loyalty", 50),
                                    joined_at=membership.get("joined_at"),
                                    status=membership.get("status", "active"),
                                    source="ai"
                                )
                                db.add(member)

                                # Cập nhật số lượng thành viên tổ chức
                                org.member_count += 1

                                created_members += 1
                                logger.info(f"  ✅ Thêm thành viên: {character.name} -> {org_name} ({membership.get('position')})")
                            else:
                                logger.warning(f"  ⚠️  Tổ chức không tồn tại: {org_name}")

                        except Exception as org_error:
                            logger.warning(f"  ❌ Thêm thành viên tổ chức thất bại: {str(org_error)}")
                            continue

                    logger.info(f"✅ Tạo thành công {created_members} bản ghi thành viên tổ chức")

            yield await tracker.saving("Đang lưu lịch sử tạo...", 0.9)

            # Ghi lịch sử tạo
            history = GenerationHistory(
                project_id=request.project_id,
                prompt=prompt,
                generated_content=ai_response,
                model=user_ai_service.default_model
            )
            db.add(history)

            await db.commit()
            await db.refresh(character)

            logger.info(f"🎉 Tạo nhân vật thành công: {character.name}")

            yield await tracker.complete("Hoàn tất tạo nhân vật!")

            # Gửi dữ liệu kết quả
            yield await tracker.result({
                "character": {
                    "id": character.id,
                    "name": character.name,
                    "role_type": character.role_type,
                    "is_organization": character.is_organization
                }
            })

            yield await tracker.done()

        except HTTPException as he:
            logger.error(f"Ngoại lệ HTTP: {he.detail}")
            yield await tracker.error(he.detail, he.status_code)
        except Exception as e:
            logger.error(f"Tạo nhân vật thất bại: {str(e)}")
            yield await tracker.error(f"Tạo nhân vật thất bại: {str(e)}")

    return create_sse_response(generate())


@router.post("/export", summary="Xuất hàng loạt nhân vật/tổ chức")
async def export_characters(
    export_request: CharactersExportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Xuất hàng loạt nhân vật/tổ chức thành định dạng JSON

    - Hỗ trợ xuất một hoặc nhiều nhân vật/tổ chức
    - Gồm mọi thông tin của nhân vật (thông tin cơ bản, nghề nghiệp, chi tiết tổ chức, v.v.)
    - Trả về file JSON để tải xuống
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    if not export_request.character_ids:
        raise HTTPException(status_code=400, detail="Hãy chọn ít nhất một nhân vật/tổ chức")

    try:
        # Kiểm tra quyền của mọi nhân vật
        for char_id in export_request.character_ids:
            result = await db.execute(
                select(Character).where(Character.id == char_id)
            )
            character = result.scalar_one_or_none()

            if not character:
                raise HTTPException(status_code=404, detail=f"Nhân vật không tồn tại: {char_id}")

            # Kiểm tra quyền dự án
            await verify_project_access(character.project_id, user_id, db)

        # Thực hiện xuất
        export_data = await ImportExportService.export_characters(
            character_ids=export_request.character_ids,
            db=db
        )

        # Tạo tên file
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        count = len(export_request.character_ids)
        filename = f"characters_export_{count}_{timestamp}.json"

        logger.info(f"Người dùng {user_id} đã xuất {count} nhân vật/tổ chức")

        # Trả về file JSON
        return JSONResponse(
            content=export_data,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json; charset=utf-8"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xuất nhân vật/tổ chức thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Xuất thất bại: {str(e)}")


@router.post("/import", response_model=CharactersImportResult, summary="Nhập nhân vật/tổ chức")
async def import_characters(
    project_id: str,
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Nhập nhân vật/tổ chức từ file JSON

    - Hỗ trợ nhập file JSON nhân vật/tổ chức đã xuất trước đó
    - Tự động xử lý tên trùng lặp (bỏ qua)
    - Kiểm tra tính hợp lệ của ID nghề nghiệp
    - Tự động tạo bản ghi chi tiết tổ chức
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Kiểm tra quyền dự án
    await verify_project_access(project_id, user_id, db)

    # Kiểm tra loại file
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng JSON")

    try:
        # Đọc nội dung file
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        # Thực hiện nhập
        result = await ImportExportService.import_characters(
            data=data,
            project_id=project_id,
            user_id=user_id,
            db=db
        )

        logger.info(f"Người dùng {user_id} nhập nhân vật/tổ chức vào dự án {project_id}: {result['message']}")

        return result

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Lỗi định dạng JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Nhập nhân vật/tổ chức thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Nhập thất bại: {str(e)}")


@router.post("/validate-import", summary="Kiểm tra file nhập")
async def validate_import(
    file: UploadFile = File(...),
    request: Request = None
):
    """
    Kiểm tra định dạng và nội dung file nhập nhân vật/tổ chức

    - Kiểm tra định dạng file
    - Kiểm tra tương thích phiên bản
    - Thống kê lượng dữ liệu
    - Trả về kết quả kiểm tra và thông tin cảnh báo
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Kiểm tra loại file
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng JSON")

    try:
        # Đọc nội dung file
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        # Kiểm tra dữ liệu
        validation_result = ImportExportService.validate_characters_import(data)

        logger.info(f"Người dùng {user_id} kiểm tra file nhập: {file.filename}")

        return validation_result

    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "version": "",
            "statistics": {"characters": 0, "organizations": 0},
            "errors": [f"Lỗi định dạng JSON: {str(e)}"],
            "warnings": []
        }
    except Exception as e:
        logger.error(f"Kiểm tra file nhập thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kiểm tra thất bại: {str(e)}")
