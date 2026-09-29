"""Dịch vụ cập nhật trạng thái nhân vật - tự động cập nhật trạng thái tâm lý, quan hệ và thành viên tổ chức dựa trên kết quả phân tích chương"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.models.character import Character
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.logger import get_logger
import uuid

logger = get_logger(__name__)

# Map từ khóa điều chỉnh độ thân mật
INTIMACY_ADJUSTMENTS = {
    # Thay đổi tích cực
    "cải thiện": +10, "thắt chặt": +15, "tin tưởng": +10, "thân thiết": +15,
    "thân thiện": +10, "công nhận": +10, "hợp tác": +5, "hòa giải": +20,
    "yêu thích": +15, "yêu": +20, "kính trọng": +10, "biết ơn": +10,
    "khá hơn": +10, "tăng cường": +10, "mật thiết": +15, "trung thành": +10,
    # Thay đổi tiêu cực
    "xấu đi": -10, "xa cách": -15, "phản bội": -30, "thù địch": -25,
    "mâu thuẫn": -10, "xung đột": -15, "nghi ngờ": -10, "mất niềm tin": -15,
    "chán ghét": -20, "thù hận": -25, "đoạn tuyệt": -30, "nghi kỵ": -10,
    "căng thẳng": -5, "đổ vỡ": -25, "trở mặt": -25, "ghen tị": -10,
    # Thay đổi đặc biệt
    "mới quen": 0, "gặp gỡ": 0, "kết minh": +10, "chia ly": -5,
}


class CharacterStateUpdateService:
    """Dịch vụ cập nhật trạng thái nhân vật - tự động cập nhật trạng thái tâm lý và quan hệ dựa trên kết quả phân tích chương"""

    @staticmethod
    async def update_from_analysis(
        db: AsyncSession,
        project_id: str,
        character_states: List[Dict[str, Any]],
        chapter_id: str,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Cập nhật trạng thái và quan hệ nhân vật dựa trên kết quả phân tích chương
        
        Args:
            db: phiên làm việc cơ sở dữ liệu
            project_id: ID project
            character_states: danh sách thay đổi trạng thái nhân vật (từ PlotAnalysis)
            chapter_id: ID chương
            chapter_number: số thứ tự chương
            
        Returns:
            Dict kết quả cập nhật
        """
        if not character_states:
            logger.info("📋 Danh sách trạng thái nhân vật trống, bỏ qua cập nhật trạng thái và quan hệ")
            return {
                "state_updated_count": 0,
                "relationship_created_count": 0,
                "relationship_updated_count": 0,
                "org_updated_count": 0,
                "changes": []
            }

        result = {
            "state_updated_count": 0,
            "relationship_created_count": 0,
            "relationship_updated_count": 0,
            "org_updated_count": 0,
            "changes": []
        }

        logger.info(f"🔍 Bắt đầu phân tích trạng thái, quan hệ nhân vật và thay đổi tổ chức của chương {chapter_number}...")

        # Tải trước mọi nhân vật của project (gồm tổ chức, index theo tên, giảm truy vấn lặp)
        all_characters_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        all_characters = all_characters_result.scalars().all()
        
        # Nhân vật không phải tổ chức index theo tên
        characters_by_name: Dict[str, Character] = {
            c.name: c for c in all_characters if not c.is_organization
        }
        
        # Tải trước thông tin tổ chức (index theo tên nhân vật tổ chức)
        orgs_result = await db.execute(
            select(Organization).where(Organization.project_id == project_id)
        )
        all_orgs = orgs_result.scalars().all()
        
        # Xây dựng map ngược character_id -> name
        char_id_to_name: Dict[str, str] = {c.id: c.name for c in all_characters}
        
        # Map tên tổ chức -> Organization
        org_by_name: Dict[str, Organization] = {}
        for org in all_orgs:
            org_char_name = char_id_to_name.get(org.character_id)
            if org_char_name:
                org_by_name[org_char_name] = org

        for char_state in character_states:
            char_name = char_state.get('character_name')
            if not char_name:
                continue

            character = characters_by_name.get(char_name)
            if not character:
                logger.warning(f"  ⚠️ Nhân vật không tồn tại: {char_name}, bỏ qua cập nhật trạng thái")
                continue

            # 0. Kiểm tra thay đổi trạng thái sống còn của nhân vật
            survival_status = char_state.get('survival_status')
            if survival_status and survival_status in ('deceased', 'missing', 'retired'):
                await CharacterStateUpdateService._update_survival_status(
                    db=db,
                    project_id=project_id,
                    character=character,
                    new_status=survival_status,
                    chapter_number=chapter_number,
                    key_event=char_state.get('key_event', ''),
                    changes=result["changes"]
                )
                result["state_updated_count"] += 1
                # Sau khi chết/mất tích không cập nhật trạng thái tâm lý nữa, chuyển thẳng sang nhân vật tiếp theo
                continue

            # 1. Cập nhật trạng thái tâm lý
            state_updated = await CharacterStateUpdateService._update_psychological_state(
                character=character,
                char_state=char_state,
                chapter_number=chapter_number,
                changes=result["changes"]
            )
            if state_updated:
                result["state_updated_count"] += 1

            # 2. Cập nhật quan hệ
            relationship_changes = char_state.get('relationship_changes', {})
            if relationship_changes and isinstance(relationship_changes, dict):
                created, updated = await CharacterStateUpdateService._update_relationships(
                    db=db,
                    project_id=project_id,
                    character=character,
                    relationship_changes=relationship_changes,
                    chapter_number=chapter_number,
                    chapter_id=chapter_id,
                    characters_by_name=characters_by_name,
                    changes=result["changes"]
                )
                result["relationship_created_count"] += created
                result["relationship_updated_count"] += updated

            # 3. Cập nhật quan hệ thành viên tổ chức
            organization_changes = char_state.get('organization_changes', [])
            if organization_changes and isinstance(organization_changes, list):
                org_updated = await CharacterStateUpdateService._update_organization_memberships(
                    db=db,
                    project_id=project_id,
                    character=character,
                    organization_changes=organization_changes,
                    chapter_number=chapter_number,
                    org_by_name=org_by_name,
                    changes=result["changes"]
                )
                result["org_updated_count"] += org_updated

        # Commit mọi thay đổi
        total_changes = (
            result["state_updated_count"] +
            result["relationship_created_count"] +
            result["relationship_updated_count"] +
            result["org_updated_count"]
        )
        if total_changes > 0:
            await db.commit()
            logger.info(
                f"✅ Cập nhật trạng thái nhân vật hoàn tất: "
                f"trạng thái tâm lý {result['state_updated_count']}, "
                f"quan hệ mới {result['relationship_created_count']}, "
                f"quan hệ cập nhật {result['relationship_updated_count']}, "
                f"biến động tổ chức {result['org_updated_count']}"
            )
        else:
            logger.info("📋 Chương này không có thay đổi trạng thái hay quan hệ nhân vật")

        return result

    @staticmethod
    async def _update_survival_status(
        db: AsyncSession,
        project_id: str,
        character: Character,
        new_status: str,
        chapter_number: int,
        key_event: str,
        changes: List[str]
    ) -> None:
        """
        Cập nhật trạng thái sống còn của nhân vật và ảnh hưởng lan truyền
        
        Khi chết/mất tích:
        - Cập nhật Character.status và status_changed_chapter
        - Cập nhật mọi quan hệ đang hoạt động thành past
        - Cập nhật mọi tư cách thành viên tổ chức thành deceased/retired
        """
        STATUS_DESC = {
            'deceased': 'tử vong',
            'missing': 'mất tích',
            'retired': 'rút lui'
        }
        
        status_desc = STATUS_DESC.get(new_status, new_status)
        
        # Ngăn chương có số nhỏ hơn ghi đè
        if (character.status_changed_chapter is not None
                and chapter_number < character.status_changed_chapter):
            logger.info(f"  ⏭️ Trạng thái {character.name} đã thay đổi ở chương {character.status_changed_chapter}, bỏ qua")
            return
        
        old_status = character.status or 'active'
        character.status = new_status
        character.status_changed_chapter = chapter_number
        character.current_state = f"{status_desc} (chương {chapter_number})"
        character.state_updated_chapter = chapter_number
        
        event_desc = f"：{key_event[:50]}" if key_event else ""
        changes.append(f"💀 {character.name} {status_desc}{event_desc}")
        logger.info(f"  💀 Trạng thái {character.name}: {old_status} → {new_status}")
        
        # Cập nhật lan truyền: mọi quan hệ đang hoạt động thành past
        rels_result = await db.execute(
            select(CharacterRelationship).where(
                and_(
                    CharacterRelationship.project_id == project_id,
                    CharacterRelationship.status == 'active',
                    or_(
                        CharacterRelationship.character_from_id == character.id,
                        CharacterRelationship.character_to_id == character.id
                    )
                )
            )
        )
        active_rels = rels_result.scalars().all()
        for rel in active_rels:
            rel.status = 'past'
            rel.ended_at = f"chương {chapter_number}"
        if active_rels:
            logger.info(f"  📋 {character.name} {status_desc}, {len(active_rels)} quan hệ đánh dấu past")
        
        # Cập nhật lan truyền: mọi tư cách thành viên tổ chức
        member_status = 'deceased' if new_status == 'deceased' else 'retired'
        members_result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.character_id == character.id,
                    OrganizationMember.status == 'active'
                )
            )
        )
        active_members = members_result.scalars().all()
        for member in active_members:
            member.status = member_status
            member.left_at = f"chương {chapter_number}"
            member.notes = (
                f"{member.notes or ''}\n[chương {chapter_number}] Nhân vật {status_desc}"
            ).strip()
        if active_members:
            logger.info(f"  📋 {character.name} {status_desc}, {len(active_members)} tư cách tổ chức đánh dấu {member_status}")

    @staticmethod
    async def _update_psychological_state(
        character: Character,
        char_state: Dict[str, Any],
        chapter_number: int,
        changes: List[str]
    ) -> bool:
        """
        Cập nhật trạng thái tâm lý nhân vật
        
        Args:
            character: đối tượng nhân vật
            char_state: dữ liệu trạng thái nhân vật
            chapter_number: số chương
            changes: danh sách nhật ký thay đổi
            
        Returns:
            Có cập nhật thực tế hay không
        """
        state_after = char_state.get('state_after')
        if not state_after:
            return False

        # Kiểm tra số chương: ngăn phân tích chương có số nhỏ hơn ghi đè trạng thái chương có số lớn hơn
        if (character.state_updated_chapter is not None
                and chapter_number < character.state_updated_chapter):
            logger.info(
                f"  ⏭️ Trạng thái tâm lý của {character.name} đã được cập nhật ở chương {character.state_updated_chapter}, "
                f"bỏ qua cập nhật của chương {chapter_number}"
            )
            return False

        old_state = character.current_state
        character.current_state = state_after
        character.state_updated_chapter = chapter_number

        state_before = char_state.get('state_before', 'không rõ')
        psychological_change = char_state.get('psychological_change', '')

        change_desc = f"👤 Trạng thái tâm lý {character.name}: {state_before} → {state_after}"
        if psychological_change:
            change_desc += f" ({psychological_change[:50]})"
        changes.append(change_desc)

        logger.info(f"  ✅ Cập nhật trạng thái tâm lý {character.name}: {state_before} → {state_after}")
        return True

    @staticmethod
    async def _update_relationships(
        db: AsyncSession,
        project_id: str,
        character: Character,
        relationship_changes: Dict[str, Any],
        chapter_number: int,
        chapter_id: str,
        characters_by_name: Dict[str, Character],
        changes: List[str]
    ) -> tuple[int, int]:
        """
        Cập nhật quan hệ nhân vật
        
        Tên quan hệ dùng trực tiếp mô tả thay đổi do AI phân tích trả về, không ép map sang kiểu định sẵn.
        relationship_type_id chỉ đặt hỗ trợ khi khớp rõ ràng được.
        
        Args:
            db: phiên làm việc cơ sở dữ liệu
            project_id: ID project
            character: nhân vật A
            relationship_changes: dict thay đổi quan hệ {"tên nhân vật": "mô tả thay đổi" hoặc {"change": ..., ...}}
            chapter_number: số chương
            chapter_id: ID chương
            characters_by_name: map tên nhân vật tới đối tượng nhân vật
            changes: danh sách nhật ký thay đổi
            
        Returns:
            (số lượng tạo mới, số lượng cập nhật)
        """
        created_count = 0
        updated_count = 0

        for target_name, change_info in relationship_changes.items():
            try:
                # Parse thông tin thay đổi (hỗ trợ hai định dạng)
                if isinstance(change_info, str):
                    change_desc = change_info
                elif isinstance(change_info, dict):
                    change_desc = change_info.get('change', str(change_info))
                else:
                    change_desc = str(change_info)

                if not change_desc:
                    continue

                # Tìm nhân vật mục tiêu
                target_character = characters_by_name.get(target_name)
                if not target_character:
                    logger.warning(f"  ⚠️ Nhân vật mục tiêu của quan hệ không tồn tại: {target_name}, bỏ qua")
                    continue

                # Tránh quan hệ với chính mình
                if character.id == target_character.id:
                    continue

                # Truy vấn xem đã tồn tại quan hệ chưa (A→B hoặc B→A)
                existing_rel_result = await db.execute(
                    select(CharacterRelationship).where(
                        and_(
                            CharacterRelationship.project_id == project_id,
                            or_(
                                and_(
                                    CharacterRelationship.character_from_id == character.id,
                                    CharacterRelationship.character_to_id == target_character.id
                                ),
                                and_(
                                    CharacterRelationship.character_from_id == target_character.id,
                                    CharacterRelationship.character_to_id == character.id
                                )
                            )
                        )
                    )
                )
                existing_rel = existing_rel_result.scalar_one_or_none()

                # Tính điều chỉnh độ thân mật
                intimacy_delta = CharacterStateUpdateService._calculate_intimacy_delta(change_desc)

                if existing_rel:
                    # Cập nhật quan hệ đã có
                    # Cập nhật tên quan hệ thành mô tả thay đổi mới nhất (lấy kết quả phân tích AI làm chuẩn)
                    existing_rel.relationship_name = change_desc
                    
                    # Thêm bản ghi thay đổi vào mô tả
                    chapter_note = f"[chương {chapter_number}] {change_desc}"
                    if existing_rel.description:
                        existing_rel.description = f"{existing_rel.description}\n{chapter_note}"
                    else:
                        existing_rel.description = chapter_note

                    # Điều chỉnh độ thân mật
                    if intimacy_delta != 0:
                        old_intimacy = existing_rel.intimacy_level or 0
                        new_intimacy = max(-100, min(100, old_intimacy + intimacy_delta))
                        existing_rel.intimacy_level = new_intimacy
                        logger.info(
                            f"  📊 Độ thân mật {character.name}↔{target_name}: "
                            f"{old_intimacy} → {new_intimacy} ({'+' if intimacy_delta > 0 else ''}{intimacy_delta})"
                        )

                    updated_count += 1
                    changes.append(
                        f"🔄 Cập nhật quan hệ {character.name}↔{target_name}: {change_desc}"
                    )
                    logger.info(f"  ✅ Cập nhật quan hệ: {character.name}↔{target_name} - {change_desc}")

                else:
                    # Tạo quan hệ mới — tên quan hệ dùng trực tiếp mô tả thay đổi của AI
                    # Đặt độ thân mật ban đầu
                    initial_intimacy = max(-100, min(100, 50 + intimacy_delta))

                    new_relationship = CharacterRelationship(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        character_from_id=character.id,
                        character_to_id=target_character.id,
                        relationship_type_id=None,  # Không ép liên kết kiểu định sẵn
                        relationship_name=change_desc,  # Dùng trực tiếp mô tả do AI phân tích trả về
                        intimacy_level=initial_intimacy,
                        status="active",
                        description=f"[chương {chapter_number}] {change_desc}",
                        source="analysis"
                    )
                    db.add(new_relationship)

                    created_count += 1
                    changes.append(
                        f"✨ Quan hệ mới {character.name}→{target_name}: {change_desc}"
                    )
                    logger.info(
                        f"  ✅ Tạo quan hệ: {character.name}→{target_name} "
                        f"({change_desc}, độ thân mật:{initial_intimacy})"
                    )

            except Exception as item_error:
                logger.error(
                    f"  ❌ Cập nhật quan hệ {character.name}→{target_name} thất bại: {str(item_error)}"
                )

        return created_count, updated_count

    @staticmethod
    async def _update_organization_memberships(
        db: AsyncSession,
        project_id: str,
        character: Character,
        organization_changes: List[Dict[str, Any]],
        chapter_number: int,
        org_by_name: Dict[str, Organization],
        changes: List[str]
    ) -> int:
        """
        Cập nhật quan hệ thành viên tổ chức của nhân vật
        
        Args:
            db: phiên làm việc cơ sở dữ liệu
            project_id: ID project
            character: đối tượng nhân vật
            organization_changes: danh sách biến động tổ chức
            chapter_number: số chương
            org_by_name: map tên tổ chức tới đối tượng Organization
            changes: danh sách nhật ký thay đổi
            
        Returns:
            Số lượng cập nhật
        """
        updated_count = 0
        
        # Map từ khóa thay đổi độ trung thành
        LOYALTY_ADJUSTMENTS = {
            "nâng cao": +10, "tăng cường": +10, "kiên định": +15, "trung thành": +15,
            "dao động": -15, "nghi ngờ": -10, "bất mãn": -10, "suy giảm": -10,
            "phản bội": -50, "phản trắc": -50, "ác cảm": -20, "thất vọng": -15,
        }
        
        for org_change in organization_changes:
            try:
                org_name = org_change.get('organization_name')
                change_type = org_change.get('change_type', '')
                new_position = org_change.get('new_position')
                loyalty_change_desc = org_change.get('loyalty_change', '')
                description = org_change.get('description', '')
                
                if not org_name:
                    continue
                
                # Tìm tổ chức
                organization = org_by_name.get(org_name)
                if not organization:
                    logger.warning(f"  ⚠️ Tổ chức không tồn tại: {org_name}, bỏ qua cập nhật biến động tổ chức")
                    continue
                
                # Tìm quan hệ thành viên đã có
                existing_member_result = await db.execute(
                    select(OrganizationMember).where(
                        and_(
                            OrganizationMember.organization_id == organization.id,
                            OrganizationMember.character_id == character.id
                        )
                    )
                )
                existing_member = existing_member_result.scalar_one_or_none()
                
                # Tính thay đổi độ trung thành
                loyalty_delta = 0
                if loyalty_change_desc:
                    for keyword, adjustment in LOYALTY_ADJUSTMENTS.items():
                        if keyword in loyalty_change_desc:
                            loyalty_delta += adjustment
                    loyalty_delta = max(-50, min(50, loyalty_delta))
                
                if change_type == 'joined':
                    # Gia nhập tổ chức
                    if existing_member:
                        # Đã tồn tại, có thể là gia nhập lại
                        if existing_member.status != 'active':
                            existing_member.status = 'active'
                            existing_member.left_at = None
                            if new_position:
                                existing_member.position = new_position
                            existing_member.notes = (
                                f"{existing_member.notes or ''}\n[chương {chapter_number}] Gia nhập lại: {description}"
                            ).strip()
                            updated_count += 1
                            changes.append(f"🏛️ {character.name} gia nhập lại {org_name}")
                            logger.info(f"  ✅ {character.name} gia nhập lại {org_name}")
                    else:
                        # Tạo quan hệ thành viên mới
                        new_member = OrganizationMember(
                            id=str(uuid.uuid4()),
                            organization_id=organization.id,
                            character_id=character.id,
                            position=new_position or 'thành viên',
                            rank=0,
                            loyalty=max(0, min(100, 50 + loyalty_delta)),
                            status='active',
                            joined_at=f"chương {chapter_number}",
                            source='analysis',
                            notes=f"[chương {chapter_number}] {description}" if description else None
                        )
                        db.add(new_member)
                        organization.member_count = (organization.member_count or 0) + 1
                        updated_count += 1
                        changes.append(f"🏛️ {character.name} gia nhập {org_name} ({new_position or 'thành viên'})")
                        logger.info(f"  ✅ {character.name} gia nhập {org_name} với vai trò {new_position or 'thành viên'}")
                
                elif change_type in ('left', 'expelled', 'betrayed'):
                    # Rời đi/bị khai trừ/phản bội
                    if existing_member and existing_member.status == 'active':
                        status_map = {
                            'left': 'retired',
                            'expelled': 'expelled',
                            'betrayed': 'expelled'
                        }
                        existing_member.status = status_map.get(change_type, 'retired')
                        existing_member.left_at = f"chương {chapter_number}"
                        if loyalty_delta != 0:
                            existing_member.loyalty = max(0, min(100, (existing_member.loyalty or 50) + loyalty_delta))
                        existing_member.notes = (
                            f"{existing_member.notes or ''}\n[chương {chapter_number}] {change_type}: {description}"
                        ).strip()
                        updated_count += 1
                        type_desc = {'left': 'rời đi', 'expelled': 'bị khai trừ', 'betrayed': 'phản bội'}
                        changes.append(f"🏛️ {character.name} {type_desc.get(change_type, change_type)} {org_name}")
                        logger.info(f"  ✅ {character.name} {type_desc.get(change_type, change_type)} {org_name}")
                
                elif change_type == 'promoted':
                    # Thăng chức
                    if existing_member:
                        old_position = existing_member.position
                        if new_position:
                            existing_member.position = new_position
                        existing_member.rank = (existing_member.rank or 0) + 1
                        if loyalty_delta != 0:
                            existing_member.loyalty = max(0, min(100, (existing_member.loyalty or 50) + loyalty_delta))
                        elif loyalty_delta == 0:
                            # Thăng chức mặc định nâng độ trung thành
                            existing_member.loyalty = max(0, min(100, (existing_member.loyalty or 50) + 5))
                        existing_member.notes = (
                            f"{existing_member.notes or ''}\n[chương {chapter_number}] Thăng chức: {old_position} → {new_position or 'chức vụ cao hơn'}: {description}"
                        ).strip()
                        updated_count += 1
                        changes.append(f"🏛️ {character.name} thăng chức ở {org_name}: {old_position} → {new_position or 'chức vụ cao hơn'}")
                        logger.info(f"  ✅ {character.name} thăng chức ở {org_name} thành {new_position or 'chức vụ cao hơn'}")
                    else:
                        logger.warning(f"  ⚠️ {character.name} không phải thành viên của {org_name}, không thể thăng chức")
                
                elif change_type == 'demoted':
                    # Giáng chức
                    if existing_member:
                        old_position = existing_member.position
                        if new_position:
                            existing_member.position = new_position
                        existing_member.rank = max(0, (existing_member.rank or 0) - 1)
                        if loyalty_delta != 0:
                            existing_member.loyalty = max(0, min(100, (existing_member.loyalty or 50) + loyalty_delta))
                        elif loyalty_delta == 0:
                            # Giáng chức mặc định giảm độ trung thành
                            existing_member.loyalty = max(0, min(100, (existing_member.loyalty or 50) - 5))
                        existing_member.notes = (
                            f"{existing_member.notes or ''}\n[chương {chapter_number}] Giáng chức: {old_position} → {new_position or 'chức vụ thấp hơn'}: {description}"
                        ).strip()
                        updated_count += 1
                        changes.append(f"🏛️ {character.name} giáng chức ở {org_name}: {old_position} → {new_position or 'chức vụ thấp hơn'}")
                        logger.info(f"  ✅ {character.name} giáng chức ở {org_name} thành {new_position or 'chức vụ thấp hơn'}")
                    else:
                        logger.warning(f"  ⚠️ {character.name} không phải thành viên của {org_name}, không thể giáng chức")
                
                else:
                    # Các loại thay đổi khác (như thay đổi độ trung thành...)
                    if existing_member and loyalty_delta != 0:
                        old_loyalty = existing_member.loyalty or 50
                        existing_member.loyalty = max(0, min(100, old_loyalty + loyalty_delta))
                        existing_member.notes = (
                            f"{existing_member.notes or ''}\n[chương {chapter_number}] {change_type}: {description}"
                        ).strip()
                        updated_count += 1
                        changes.append(
                            f"🏛️ Thay đổi độ trung thành của {character.name} ở {org_name}: "
                            f"{old_loyalty} → {existing_member.loyalty}"
                        )
                        logger.info(
                            f"  ✅ Độ trung thành của {character.name} ở {org_name}: "
                            f"{old_loyalty} → {existing_member.loyalty}"
                        )
                    
            except Exception as item_error:
                logger.error(
                    f"  ❌ Cập nhật biến động tổ chức {org_change.get('organization_name', 'không rõ')} của {character.name} thất bại: {str(item_error)}"
                )
        
        return updated_count

    @staticmethod
    async def update_organization_states(
        db: AsyncSession,
        project_id: str,
        organization_states: List[Dict[str, Any]],
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Cập nhật trạng thái bản thân tổ chức theo kết quả phân tích chương (cấp độ thế lực, cứ điểm, tôn chỉ...)
        
        Args:
            db: phiên làm việc cơ sở dữ liệu
            project_id: ID project
            organization_states: danh sách thay đổi trạng thái tổ chức (từ field cấp cao nhất của kết quả phân tích)
            chapter_number: số thứ tự chương
            
        Returns:
            Dict kết quả cập nhật
        """
        if not organization_states:
            return {"updated_count": 0, "changes": []}
        
        result = {"updated_count": 0, "changes": []}
        
        logger.info(f"🏛️ Bắt đầu cập nhật trạng thái bản thân tổ chức của chương {chapter_number}...")
        
        # Tải trước mọi nhân vật tổ chức của project
        all_chars_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == True
            )
        )
        org_chars = all_chars_result.scalars().all()
        org_char_by_name: Dict[str, Character] = {c.name: c for c in org_chars}
        
        # Tải trước chi tiết tổ chức
        char_ids = [c.id for c in org_chars]
        if not char_ids:
            logger.info("🏛️ Project không có tổ chức, bỏ qua cập nhật trạng thái tổ chức")
            return result
        
        orgs_result = await db.execute(
            select(Organization).where(Organization.character_id.in_(char_ids))
        )
        all_orgs = orgs_result.scalars().all()
        org_by_char_id: Dict[str, Organization] = {org.character_id: org for org in all_orgs}
        
        for org_state in organization_states:
            try:
                org_name = org_state.get('organization_name')
                if not org_name:
                    continue
                
                org_char = org_char_by_name.get(org_name)
                if not org_char:
                    logger.warning(f"  ⚠️ Tổ chức không tồn tại: {org_name}, bỏ qua cập nhật trạng thái")
                    continue
                
                organization = org_by_char_id.get(org_char.id)
                if not organization:
                    logger.warning(f"  ⚠️ Tổ chức {org_name} không có bản ghi chi tiết, bỏ qua cập nhật trạng thái")
                    continue
                
                updated = False
                change_parts = []
                
                # Kiểm tra tổ chức có bị diệt vong không
                is_destroyed = org_state.get('is_destroyed', False)
                if is_destroyed:
                    # Tổ chức diệt vong: xử lý lan truyền
                    org_char.status = 'destroyed'
                    org_char.status_changed_chapter = chapter_number
                    org_char.current_state = f"Diệt vong (chương {chapter_number})"
                    org_char.state_updated_chapter = chapter_number
                    organization.power_level = 0
                    
                    # Mọi thành viên đang hoạt động đánh dấu retired
                    members_result = await db.execute(
                        select(OrganizationMember).where(
                            and_(
                                OrganizationMember.organization_id == organization.id,
                                OrganizationMember.status == 'active'
                            )
                        )
                    )
                    active_members = members_result.scalars().all()
                    for member in active_members:
                        member.status = 'retired'
                        member.left_at = f"chương {chapter_number}"
                        member.notes = (
                            f"{member.notes or ''}\n[chương {chapter_number}] Tổ chức diệt vong"
                        ).strip()
                    
                    key_event = org_state.get('key_event', '')
                    event_desc = f"：{key_event[:40]}" if key_event else ""
                    result["updated_count"] += 1
                    change_summary = f"💀 {org_name} diệt vong{event_desc}, {len(active_members)} thành viên bị ảnh hưởng"
                    result["changes"].append(change_summary)
                    logger.info(f"  💀 {change_summary}")
                    continue  # Sau diệt vong không cập nhật thuộc tính khác nữa
                
                # Thay đổi cấp độ thế lực
                power_change = org_state.get('power_change', 0)
                if power_change and isinstance(power_change, (int, float)):
                    old_power = organization.power_level or 50
                    new_power = max(0, min(100, old_power + int(power_change)))
                    if new_power != old_power:
                        organization.power_level = new_power
                        change_parts.append(f"thế lực:{old_power}→{new_power}")
                        updated = True
                
                # Thay đổi cứ điểm
                new_location = org_state.get('new_location')
                if new_location and isinstance(new_location, str):
                    old_location = organization.location or 'chưa đặt'
                    organization.location = new_location
                    change_parts.append(f"cứ điểm:{old_location}→{new_location}")
                    updated = True
                
                # Thay đổi tôn chỉ/mục tiêu
                new_purpose = org_state.get('new_purpose')
                if new_purpose and isinstance(new_purpose, str):
                    old_purpose = (org_char.organization_purpose or 'chưa đặt')[:30]
                    org_char.organization_purpose = new_purpose
                    change_parts.append(f"thay đổi tôn chỉ")
                    updated = True
                
                # Mô tả trạng thái -> cập nhật vào current_state của Character
                status_desc = org_state.get('status_description')
                if status_desc and isinstance(status_desc, str):
                    org_char.current_state = status_desc
                    org_char.state_updated_chapter = chapter_number
                    if not change_parts:  # Nếu chỉ có mô tả trạng thái mà không có thay đổi khác
                        change_parts.append(f"trạng thái:{status_desc[:30]}")
                    updated = True
                
                if updated:
                    result["updated_count"] += 1
                    key_event = org_state.get('key_event', '')
                    change_summary = f"🏛️ Thay đổi trạng thái {org_name}: {', '.join(change_parts)}"
                    if key_event:
                        change_summary += f" (do:{key_event[:40]})"
                    result["changes"].append(change_summary)
                    logger.info(f"  ✅ {change_summary}")
                    
            except Exception as item_error:
                logger.error(
                    f"  ❌ Cập nhật trạng thái tổ chức {org_state.get('organization_name', 'không rõ')} thất bại: {str(item_error)}"
                )
        
        if result["updated_count"] > 0:
            await db.commit()
            logger.info(f"✅ Cập nhật trạng thái tổ chức hoàn tất: {result['updated_count']} tổ chức")
        
        return result

    @staticmethod
    def _calculate_intimacy_delta(change_desc: str) -> int:
        """
        Tính giá trị điều chỉnh độ thân mật theo mô tả thay đổi
        
        Args:
            change_desc: văn bản mô tả thay đổi quan hệ
            
        Returns:
            Giá trị điều chỉnh độ thân mật
        """
        delta = 0
        matched = False
        for keyword, adjustment in INTIMACY_ADJUSTMENTS.items():
            if keyword in change_desc:
                delta += adjustment
                matched = True

        # Giới hạn biên độ điều chỉnh mỗi lần
        if matched:
            delta = max(-30, min(30, delta))

        return delta
