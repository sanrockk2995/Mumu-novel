"""Hàm hỗ trợ tính nhất quán dữ liệu"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Tuple, List
from app.models.character import Character
from app.models.relationship import Organization, OrganizationMember, CharacterRelationship
from app.logger import get_logger

logger = get_logger(__name__)


async def ensure_organization_record(
    character: Character,
    db: AsyncSession,
    power_level: int = 50,
    location: Optional[str] = None,
    motto: Optional[str] = None
) -> Optional[Organization]:
    """
    Đảm bảo nhân vật tổ chức có bản ghi Organization tương ứng

    Args:
        character: đối tượng Character (phải có is_organization=True)
        db: session database
        power_level: cấp độ thế lực (mặc định 50)
        location: nơi đặt
        motto: tôn chỉ/khẩu hiệu

    Returns:
        Đối tượng Organization, trả về None nếu character không phải tổ chức
    """
    if not character.is_organization:
        logger.debug(f"Nhân vật {character.name} không phải tổ chức, bỏ qua tạo bản ghi Organization")
        return None

    # Kiểm tra đã tồn tại chưa
    result = await db.execute(
        select(Organization).where(Organization.character_id == character.id)
    )
    org = result.scalar_one_or_none()

    if not org:
        # Tạo bản ghi Organization mới
        org = Organization(
            character_id=character.id,
            project_id=character.project_id,
            member_count=0,
            power_level=power_level,
            location=location,
            motto=motto
        )
        db.add(org)
        await db.flush()
        await db.refresh(org)
        logger.info(f"✅ Tự động tạo chi tiết tổ chức: {character.name} (Org ID: {org.id})")
    else:
        logger.debug(f"Chi tiết tổ chức đã tồn tại: {character.name} (Org ID: {org.id})")

    return org


async def sync_organization_member_count(
    organization: Organization,
    db: AsyncSession
) -> int:
    """
    Đồng bộ số lượng thành viên của tổ chức, tính từ bản ghi thành viên thực tế

    Args:
        organization: đối tượng Organization
        db: session database

    Returns:
        Số lượng thành viên thực tế
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.status == "active"
        )
    )
    members = result.scalars().all()
    actual_count = len(members)

    if organization.member_count != actual_count:
        logger.warning(
            f"Tổ chức {organization.id} số lượng thành viên không nhất quán: "
            f"giá trị ghi={organization.member_count}, giá trị thực={actual_count}, đã sửa"
        )
        organization.member_count = actual_count
        await db.flush()

    return actual_count


async def fix_missing_organization_records(
    project_id: str,
    db: AsyncSession
) -> Tuple[int, int]:
    """
    Sửa các bản ghi Organization còn thiếu trong dự án

    Tạo bản ghi cho mọi Character có is_organization=True nhưng chưa có bản ghi Organization

    Args:
        project_id: ID dự án
        db: session database

    Returns:
        (số lượng đã sửa, tổng số đã kiểm tra)
    """
    # Tìm mọi nhân vật tổ chức
    result = await db.execute(
        select(Character).where(
            Character.project_id == project_id,
            Character.is_organization == True
        )
    )
    org_characters = result.scalars().all()

    fixed_count = 0
    for char in org_characters:
        org = await ensure_organization_record(char, db)
        if org and org.id:  # Chỉ đếm cái mới tạo
            # Kiểm tra có phải mới tạo không (qua truy vấn lịch sử)
            result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            if result.scalar_one_or_none():
                fixed_count += 1

    await db.commit()

    logger.info(f"📊 Thống kê sửa - đã kiểm tra {len(org_characters)} tổ chức, đã sửa {fixed_count} bản ghi Organization còn thiếu")
    return fixed_count, len(org_characters)


async def fix_organization_member_counts(
    project_id: str,
    db: AsyncSession
) -> Tuple[int, int]:
    """
    Sửa số lượng thành viên của mọi tổ chức trong dự án

    Args:
        project_id: ID dự án
        db: session database

    Returns:
        (số lượng đã sửa, tổng số đã kiểm tra)
    """
    # Tìm mọi tổ chức
    result = await db.execute(
        select(Organization).where(Organization.project_id == project_id)
    )
    organizations = result.scalars().all()

    fixed_count = 0
    for org in organizations:
        old_count = org.member_count
        actual_count = await sync_organization_member_count(org, db)
        if old_count != actual_count:
            fixed_count += 1

    await db.commit()

    logger.info(f"📊 Thống kê sửa - đã kiểm tra {len(organizations)} tổ chức, đã sửa {fixed_count} lỗi đếm")
    return fixed_count, len(organizations)


async def validate_relationships(
    project_id: str,
    db: AsyncSession
) -> List[dict]:
    """
    Kiểm tra tính toàn vẹn dữ liệu quan hệ trong dự án

    Kiểm tra character_from_id và character_to_id trong mọi quan hệ có trỏ tới nhân vật tồn tại không

    Args:
        project_id: ID dự án
        db: session database

    Returns:
        Danh sách vấn đề, mỗi vấn đề gồm {issue_type, relationship_id, details}
    """
    issues = []

    # Lấy mọi quan hệ
    result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.project_id == project_id)
    )
    relationships = result.scalars().all()

    for rel in relationships:
        # Kiểm tra nhân vật from
        from_char = await db.execute(
            select(Character).where(Character.id == rel.character_from_id)
        )
        if not from_char.scalar_one_or_none():
            issues.append({
                "issue_type": "missing_from_character",
                "relationship_id": rel.id,
                "details": f"Quan hệ {rel.id} có nhân vật nguồn {rel.character_from_id} không tồn tại"
            })

        # Kiểm tra nhân vật to
        to_char = await db.execute(
            select(Character).where(Character.id == rel.character_to_id)
        )
        if not to_char.scalar_one_or_none():
            issues.append({
                "issue_type": "missing_to_character",
                "relationship_id": rel.id,
                "details": f"Quan hệ {rel.id} có nhân vật đích {rel.character_to_id} không tồn tại"
            })

    if issues:
        logger.warning(f"⚠️  Phát hiện {len(issues)} vấn đề dữ liệu quan hệ")
        for issue in issues:
            logger.warning(f"  - {issue['details']}")
    else:
        logger.info(f"✅ Mọi {len(relationships)} dữ liệu quan hệ đều đầy đủ")

    return issues


async def validate_organization_members(
    project_id: str,
    db: AsyncSession
) -> List[dict]:
    """
    Kiểm tra tính toàn vẹn dữ liệu thành viên tổ chức trong dự án

    Kiểm tra organization_id và character_id trong mọi quan hệ thành viên có hợp lệ không

    Args:
        project_id: ID dự án
        db: session database

    Returns:
        Danh sách vấn đề
    """
    issues = []

    # Lấy mọi quan hệ thành viên
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id.in_(
                select(Organization.id).where(Organization.project_id == project_id)
            )
        )
    )
    members = result.scalars().all()

    for member in members:
        # Kiểm tra tổ chức
        org = await db.execute(
            select(Organization).where(Organization.id == member.organization_id)
        )
        if not org.scalar_one_or_none():
            issues.append({
                "issue_type": "missing_organization",
                "member_id": member.id,
                "details": f"Thành viên {member.id} có tổ chức {member.organization_id} không tồn tại"
            })

        # Kiểm tra nhân vật
        char = await db.execute(
            select(Character).where(Character.id == member.character_id)
        )
        if not char.scalar_one_or_none():
            issues.append({
                "issue_type": "missing_character",
                "member_id": member.id,
                "details": f"Thành viên {member.id} có nhân vật {member.character_id} không tồn tại"
            })

    if issues:
        logger.warning(f"⚠️  Phát hiện {len(issues)} vấn đề dữ liệu thành viên tổ chức")
        for issue in issues:
            logger.warning(f"  - {issue['details']}")
    else:
        logger.info(f"✅ Mọi {len(members)} dữ liệu thành viên tổ chức đều đầy đủ")

    return issues


async def run_full_data_consistency_check(
    project_id: str,
    db: AsyncSession,
    auto_fix: bool = True
) -> dict:
    """
    Chạy kiểm tra và sửa tính nhất quán dữ liệu đầy đủ cho dự án

    Args:
        project_id: ID dự án
        db: session database
        auto_fix: có tự động sửa vấn đề không (mặc định True)

    Returns:
        Dict báo cáo kiểm tra
    """
    logger.info(f"🔍 Bắt đầu kiểm tra tính nhất quán dữ liệu - dự án {project_id}")

    report = {
        "project_id": project_id,
        "checks": {}
    }

    # 1. Kiểm tra và sửa bản ghi Organization còn thiếu
    if auto_fix:
        fixed, total = await fix_missing_organization_records(project_id, db)
        report["checks"]["organization_records"] = {
            "checked": total,
            "fixed": fixed,
            "status": "ok" if fixed == 0 else "fixed"
        }

    # 2. Kiểm tra và sửa số lượng thành viên
    if auto_fix:
        fixed, total = await fix_organization_member_counts(project_id, db)
        report["checks"]["member_counts"] = {
            "checked": total,
            "fixed": fixed,
            "status": "ok" if fixed == 0 else "fixed"
        }

    # 3. Kiểm tra dữ liệu quan hệ
    rel_issues = await validate_relationships(project_id, db)
    report["checks"]["relationships"] = {
        "issues_found": len(rel_issues),
        "issues": rel_issues,
        "status": "ok" if len(rel_issues) == 0 else "warning"
    }

    # 4. Kiểm tra dữ liệu thành viên tổ chức
    member_issues = await validate_organization_members(project_id, db)
    report["checks"]["organization_members"] = {
        "issues_found": len(member_issues),
        "issues": member_issues,
        "status": "ok" if len(member_issues) == 0 else "warning"
    }

    logger.info(f"✅ Kiểm tra tính nhất quán dữ liệu hoàn tất")
    return report
