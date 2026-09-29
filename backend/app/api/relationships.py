"""API quản lý quan hệ"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List, Optional

from app.database import get_db
from app.models.relationship import (
    RelationshipType,
    CharacterRelationship,
    Organization,
    OrganizationMember
)
from app.models.character import Character
from app.models.project import Project
from app.schemas.relationship import (
    RelationshipTypeResponse,
    CharacterRelationshipCreate,
    CharacterRelationshipUpdate,
    CharacterRelationshipResponse,
    RelationshipGraphData,
    RelationshipGraphNode,
    RelationshipGraphLink
)
from app.logger import get_logger
from app.api.common import verify_project_access

router = APIRouter(prefix="/relationships", tags=["Quản lý quan hệ"])
logger = get_logger(__name__)


@router.get("/types", response_model=List[RelationshipTypeResponse], summary="Lấy danh sách loại quan hệ")
async def get_relationship_types(db: AsyncSession = Depends(get_db)):
    """Lấy tất cả loại quan hệ được định nghĩa sẵn"""
    result = await db.execute(select(RelationshipType).order_by(RelationshipType.category, RelationshipType.id))
    types = result.scalars().all()
    return types


@router.get("/project/{project_id}", response_model=List[CharacterRelationshipResponse], summary="Lấy tất cả quan hệ của dự án")
async def get_project_relationships(
    project_id: str,
    request: Request,
    character_id: Optional[str] = Query(None, description="Lọc quan hệ của một nhân vật cụ thể"),
    db: AsyncSession = Depends(get_db)
):
    # Xác thực quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    """
    Lấy tất cả quan hệ nhân vật trong dự án

    - Nếu cung cấp character_id, chỉ trả về các quan hệ liên quan đến nhân vật đó (với vai trò bên khởi xướng hoặc bên nhận)
    - Nếu không, trả về tất cả quan hệ trong dự án
    """
    query = select(CharacterRelationship).where(
        CharacterRelationship.project_id == project_id
    )

    if character_id:
        query = query.where(
            or_(
                CharacterRelationship.character_from_id == character_id,
                CharacterRelationship.character_to_id == character_id
            )
        )

    query = query.order_by(CharacterRelationship.created_at.desc())
    result = await db.execute(query)
    relationships = result.scalars().all()

    logger.info(f"Lấy danh sách quan hệ của dự án {project_id}, tổng cộng {len(relationships)} quan hệ")
    return relationships


@router.get("/graph/{project_id}", response_model=RelationshipGraphData, summary="Lấy dữ liệu đồ thị quan hệ")
async def get_relationship_graph(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Xác thực quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    """
    Lấy dữ liệu đồ thị quan hệ dùng cho trực quan hóa

    Định dạng trả về:
    - nodes: danh sách nút nhân vật
    - links: danh sách cạnh quan hệ
    """
    # Lấy tất cả nhân vật (nút)
    chars_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = chars_result.scalars().all()

    nodes = [
        RelationshipGraphNode(
            id=c.id,
            name=c.name,
            type="organization" if c.is_organization else "character",
            role_type=c.role_type,
            avatar=c.avatar_url
        )
        for c in characters
    ]

    # Lấy tất cả quan hệ nhân vật (cạnh)
    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.project_id == project_id
        )
    )
    relationships = rels_result.scalars().all()

    links = [
        RelationshipGraphLink(
            source=r.character_from_id,
            target=r.character_to_id,
            relationship=r.relationship_name or "Quan hệ không xác định",
            intimacy=r.intimacy_level,
            status=r.status
        )
        for r in relationships
    ]

    # Lấy quan hệ thành viên tổ chức (tổ chức -> thành viên) và thêm vào các cạnh của đồ thị
    # source dùng ID nhân vật tương ứng của tổ chức (Organization.character_id), đảm bảo khớp với ID nút
    members_result = await db.execute(
        select(OrganizationMember, Organization).join(
            Organization,
            OrganizationMember.organization_id == Organization.id
        ).where(Organization.project_id == project_id)
    )
    org_members = members_result.all()

    member_links = [
        RelationshipGraphLink(
            source=org.character_id,
            target=member.character_id,
            relationship=f"Thành viên tổ chức·{member.position}",
            intimacy=member.loyalty,
            status=member.status
        )
        for member, org in org_members
    ]

    links.extend(member_links)

    logger.info(
        f"Lấy đồ thị quan hệ của dự án {project_id}: {len(nodes)} nút, "
        f"{len(relationships)} quan hệ nhân vật, {len(member_links)} quan hệ thành viên tổ chức"
    )
    return RelationshipGraphData(nodes=nodes, links=links)


@router.post("/", response_model=CharacterRelationshipResponse, summary="Tạo quan hệ nhân vật")
async def create_relationship(
    relationship: CharacterRelationshipCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo quan hệ nhân vật thủ công

    - Cần cung cấp ID của nhân vật A và nhân vật B
    - Có thể chỉ định loại quan hệ định nghĩa sẵn hoặc tên quan hệ tùy chỉnh
    - Có thể thiết lập các thuộc tính như độ thân thiết, trạng thái
    """
    # Xác thực quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(relationship.project_id, user_id, db)

    # Kiểm tra nhân vật có tồn tại không
    char_from = await db.execute(
        select(Character).where(Character.id == relationship.character_from_id)
    )
    char_to = await db.execute(
        select(Character).where(Character.id == relationship.character_to_id)
    )

    if not char_from.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Nhân vật A (ID: {relationship.character_from_id}) không tồn tại")
    if not char_to.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Nhân vật B (ID: {relationship.character_to_id}) không tồn tại")

    # Tạo quan hệ
    db_relationship = CharacterRelationship(
        **relationship.model_dump(),
        source="manual"
    )
    db.add(db_relationship)
    await db.commit()
    await db.refresh(db_relationship)

    logger.info(f"Tạo quan hệ thành công: {relationship.character_from_id} -> {relationship.character_to_id}")
    return db_relationship


@router.put("/{relationship_id}", response_model=CharacterRelationshipResponse, summary="Cập nhật quan hệ")
async def update_relationship(
    relationship_id: str,
    relationship: CharacterRelationshipUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thuộc tính của quan hệ nhân vật (độ thân thiết, trạng thái, v.v.)"""
    result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.id == relationship_id
        )
    )
    db_rel = result.scalar_one_or_none()

    if not db_rel:
        raise HTTPException(status_code=404, detail="Quan hệ không tồn tại")

    # Xác thực quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_rel.project_id, user_id, db)

    # Cập nhật các trường
    update_data = relationship.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rel, field, value)

    await db.commit()
    await db.refresh(db_rel)

    logger.info(f"Cập nhật quan hệ thành công: {relationship_id}")
    return db_rel


@router.delete("/{relationship_id}", summary="Xóa quan hệ")
async def delete_relationship(
    relationship_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa quan hệ nhân vật"""
    result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.id == relationship_id
        )
    )
    db_rel = result.scalar_one_or_none()

    if not db_rel:
        raise HTTPException(status_code=404, detail="Quan hệ không tồn tại")

    # Xác thực quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(db_rel.project_id, user_id, db)

    await db.delete(db_rel)
    await db.commit()

    logger.info(f"Xóa quan hệ thành công: {relationship_id}")
    return {"message": "Xóa quan hệ thành công", "id": relationship_id}
