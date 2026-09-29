"""Dịch vụ xây dựng context chương - triển khai xây dựng context thông minh theo framework RTCO"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.chapter import Chapter
from app.models.project import Project
from app.models.outline import Outline
from app.models.character import Character
from app.models.career import Career, CharacterCareer
from app.models.memory import StoryMemory, PlotAnalysis
from app.models.foreshadow import Foreshadow
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.logger import get_logger

logger = get_logger(__name__)


STATUS_LABELS = {
    "active": "đang hoạt động",
    "deceased": "tử vong",
    "missing": "mất tích",
    "retired": "rút lui",
    "destroyed": "diệt vong",
}


def _append_current_state_lines(info_lines: List[str], character: Character) -> None:
    """Tiêm trạng thái mới nhất do hệ thống phân tích duy trì vào context nhân vật."""
    status = character.status or "active"
    status_label = STATUS_LABELS.get(status, status)
    status_line = f"  Trạng thái hiện tại: {status_label}"
    if character.status_changed_chapter:
        status_line += f"(thay đổi ở chương {character.status_changed_chapter})"
    info_lines.append(status_line)

    if character.current_state:
        current_state = character.current_state[:150] if len(character.current_state) > 150 else character.current_state
        state_line = f"  Tâm lý/hoàn cảnh hiện tại: {current_state}"
        if character.state_updated_chapter:
            state_line += f"(cập nhật ở chương {character.state_updated_chapter})"
        info_lines.append(state_line)


def _stringify_list_items(value: Any, limit: int = 5) -> List[str]:
    """Nén các mục list trong field có cấu trúc thành văn bản ngắn phù hợp cho truy xuất ngữ nghĩa."""
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    result = []
    for item in items[:limit]:
        if isinstance(item, dict):
            text = item.get("name") or item.get("content") or item.get("title") or ""
        else:
            text = str(item)
        text = text.strip()
        if text:
            result.append(text)
    return result


def _format_memory_query_section(label: str, values: List[str]) -> Optional[str]:
    """Format đoạn truy xuất ký ức có cấu trúc."""
    values = [value.strip() for value in values if value and value.strip()]
    if not values:
        return None
    return f"{label}：{'；'.join(values)}"


def _select_memories_with_fallback(
    memories: List[Dict[str, Any]],
    threshold: float,
    fallback_count: int,
    log_prefix: str
) -> List[Dict[str, Any]]:
    """Lọc ký ức theo độ tương đồng; khi không có hit điểm cao thì giữ lại một ít kết quả top làm dự phòng."""
    if not memories:
        return []

    for index, mem in enumerate(memories[:5], start=1):
        logger.info(
            f"  🔎 {log_prefix}ký ức ứng viên #{index}: "
            f"similarity={mem.get('similarity', 0):.4f}, "
            f"distance={mem.get('distance', 0):.4f}, "
            f"chapter={mem.get('metadata', {}).get('chapter_number', 'không rõ')}, "
            f"content={str(mem.get('content', ''))[:60]}"
        )

    filtered = [mem for mem in memories if mem.get('similarity', 0) > threshold]
    if filtered:
        return filtered

    fallback = memories[:fallback_count]
    logger.info(
        f"  ℹ️ {log_prefix}không có ký ức nào vượt ngưỡng tương đồng {threshold:.2f},"
        f"hạ cấp giữ lại top {len(fallback)} mục"
    )
    return fallback


@dataclass
class OneToManyContext:
    """
    Cấu trúc dữ liệu context chương ở chế độ 1-N
    
    Áp dụng thiết kế phân tầng của framework RTCO:
    - P0-cốt lõi: dàn ý (gồm kế hoạch 10 chương gần nhất), điểm neo chuyển tiếp (toàn văn + tóm tắt chương trước), yêu cầu số từ
    - P1-quan trọng: nhân vật (bản đầy đủ gồm quan hệ/tổ chức/nghề), chi tiết nghề, tông cảm xúc
    - P2-tham khảo: ký ức (luôn bật, độ liên quan > 0.6), nhắc phục bút
    """
    
    # === P0-thông tin cốt lõi ===
    chapter_outline: str = ""           # Dàn ý chương này (xây từ expansion_plan)
    recent_chapters_context: Optional[str] = None  # Tóm tắt expansion_plan 10 chương gần nhất
    continuation_point: Optional[str] = None  # Điểm neo chuyển tiếp (toàn văn chương trước)
    previous_chapter_summary: Optional[str] = None  # Tóm tắt cốt truyện chương trước
    previous_chapter_events: Optional[List[str]] = None  # Sự kiện then chốt chương trước
    target_word_count: int = 3000
    min_word_count: int = 2500
    max_word_count: int = 4000
    narrative_perspective: str = "ngôi thứ ba"
    
    # === Thông tin cơ bản chương này ===
    chapter_number: int = 1
    chapter_title: str = ""
    
    # === Thông tin cơ bản project ===
    title: str = ""
    genre: str = ""
    theme: str = ""
    
    # === P1-thông tin quan trọng ===
    chapter_characters: str = ""        # Thông tin nhân vật bản đầy đủ (gồm tuổi, ngoại hình, bối cảnh, quan hệ, tổ chức)
    chapter_careers: Optional[str] = None  # Chi tiết nghề độc lập (gồm hệ thống giai đoạn đầy đủ)
    emotional_tone: str = ""
    
    # === P2-thông tin tham khảo ===
    relevant_memories: Optional[str] = None  # Luôn bật (độ liên quan > 0.6)
    foreshadow_reminders: Optional[str] = None
    
    # === Thông tin meta ===
    context_stats: Dict[str, Any] = field(default_factory=dict)
    
    def get_total_context_length(self) -> int:
        """Tính tổng độ dài context"""
        total = 0
        for field_name in ['chapter_outline', 'recent_chapters_context', 'continuation_point',
                          'chapter_characters', 'chapter_careers',
                          'relevant_memories', 'foreshadow_reminders',
                          'previous_chapter_summary']:
            value = getattr(self, field_name, None)
            if value:
                total += len(value)
        return total


@dataclass
class OneToOneContext:
    """
    Cấu trúc dữ liệu context chương ở chế độ 1-1
    
    Áp dụng thiết kế phân tầng của framework RTCO:
    - P0-cốt lõi: dàn ý trích từ outline.structure, yêu cầu số từ
    - P1-quan trọng: tóm tắt các chương gần đây, toàn văn chương trước, nhân vật lấy từ structure.characters, hệ thống nghề của chương này
    - P2-tham khảo: nhắc phục bút, ký ức liên quan (độ liên quan > 0.6)
    """
    
    # === P0-thông tin cốt lõi ===
    chapter_outline: str = ""           # Trích từ outline.structure
    target_word_count: int = 3000
    min_word_count: int = 2500
    max_word_count: int = 4000
    narrative_perspective: str = "ngôi thứ ba"
    
    # === Thông tin cơ bản chương này ===
    chapter_number: int = 1
    chapter_title: str = ""
    
    # === Thông tin cơ bản project ===
    title: str = ""
    genre: str = ""
    theme: str = ""
    
    # === P1-thông tin quan trọng ===
    recent_chapters_context: Optional[str] = None  # Tóm tắt cốt truyện N chương gần nhất
    continuation_point: Optional[str] = None  # Toàn văn chương trước
    previous_chapter_summary: Optional[str] = None  # Tóm tắt cốt truyện chương trước
    chapter_characters: str = ""        # Lấy từ structure.characters
    chapter_careers: Optional[str] = None  # Thông tin đầy đủ nghề liên quan chương này
    
    # === P2-thông tin tham khảo ===
    foreshadow_reminders: Optional[str] = None
    relevant_memories: Optional[str] = None  # Độ liên quan > 0.6
    
    # === Thông tin meta ===
    context_stats: Dict[str, Any] = field(default_factory=dict)
    
    def get_total_context_length(self) -> int:
        """Tính tổng độ dài context"""
        total = 0
        for field_name in ['chapter_outline', 'recent_chapters_context', 'continuation_point', 'previous_chapter_summary',
                          'chapter_characters', 'chapter_careers', 'foreshadow_reminders',
                          'relevant_memories']:
            value = getattr(self, field_name, None)
            if value:
                total += len(value)
        return total


# ==================== Bộ xây dựng context chế độ 1-N ====================

class OneToManyContextBuilder:
    """
    Bộ xây dựng context chế độ 1-N
    
    Chiến lược xây dựng context:
    - Dàn ý chương: expansion_plan chương này + tóm tắt expansion_plan 10 chương gần nhất
    - Điểm neo chuyển tiếp: toàn văn chương trước + tóm tắt
    - Thông tin nhân vật: bản đầy đủ (gồm tuổi, ngoại hình, bối cảnh, quan hệ, tổ chức, nghề)
    - Chi tiết nghề: field chapter_careers độc lập, gồm hệ thống giai đoạn đầy đủ
    - Ký ức liên quan: luôn bật (độ liên quan > 0.6)
    - Nhắc phục bút: luôn bật
    """
    
    # Hằng số cấu hình
    ENDING_LENGTH = None         # None nghĩa là dùng toàn văn chương trước
    MEMORY_CANDIDATE_LIMIT = 50  # Kích thước pool ứng viên truy xuất vector
    MEMORY_CONTEXT_LIMIT = 10    # Số mục ký ức tiêm vào prompt cuối cùng
    MEMORY_FALLBACK_COUNT = 5    # Số ứng viên giữ lại khi không có hit điểm cao
    MEMORY_COUNT = MEMORY_CONTEXT_LIMIT  # Tương thích thống kê/trích dẫn cũ
    MEMORY_SIMILARITY_THRESHOLD = 0.6  # Ngưỡng độ liên quan ký ức
    RECENT_CHAPTERS_COUNT = 10   # Số lượng kế hoạch chương gần đây
    
    def __init__(self, memory_service=None, foreshadow_service=None):
        """
        Khởi tạo builder
        
        Args:
            memory_service: instance dịch vụ ký ức (tùy chọn, để truy xuất ký ức liên quan)
            foreshadow_service: instance dịch vụ phục bút (tùy chọn, để lấy nhắc phục bút)
        """
        self.memory_service = memory_service
        self.foreshadow_service = foreshadow_service
    
    async def build(
        self,
        chapter: Chapter,
        project: Project,
        outline: Optional[Outline],
        user_id: str,
        db: AsyncSession,
        style_content: Optional[str] = None,
        target_word_count: int = 3000,
        temp_narrative_perspective: Optional[str] = None
    ) -> OneToManyContext:
        """
        Xây dựng context cần cho sinh chương (chế độ 1-N)
        
        Args:
            chapter: đối tượng chương
            project: đối tượng project
            outline: đối tượng dàn ý (tùy chọn)
            user_id: ID người dùng
            db: phiên làm việc cơ sở dữ liệu
            style_content: nội dung phong cách viết (tùy chọn, không dùng nữa, giữ để tương thích tham số)
            target_word_count: số từ mục tiêu
            temp_narrative_perspective: góc nhìn tự sự tạm thời (tùy chọn, ghi đè mặc định project)
        
        Returns:
            OneToManyContext: đối tượng context có cấu trúc
        """
        chapter_number = chapter.chapter_number
        logger.info(f"📝 [Chế độ 1-N] Bắt đầu xây dựng context chương: chương {chapter_number}")
        
        # Xác định góc nhìn tự sự
        narrative_perspective = (
            temp_narrative_perspective or
            project.narrative_perspective or
            "ngôi thứ ba"
        )
        
        # Khởi tạo context
        context = OneToManyContext(
            chapter_number=chapter_number,
            chapter_title=chapter.title or "",
            title=project.title or "",
            genre=project.genre or "",
            theme=project.theme or "",
            target_word_count=target_word_count,
            min_word_count=max(500, target_word_count - 500),
            max_word_count=target_word_count + 1000,
            narrative_perspective=narrative_perspective
        )
        
        # === P0-thông tin cốt lõi (luôn xây dựng) ===
        context.chapter_outline = self._build_chapter_outline_1n(chapter, outline)
        
        # === Tóm tắt expansion_plan 10 chương gần nhất ===
        if chapter_number > 1:
            context.recent_chapters_context = await self._build_recent_chapters_context(
                chapter, project.id, db
            )
            logger.info(f"  ✅ Kế hoạch chương gần đây: {len(context.recent_chapters_context or '')} ký tự")
        
        # === Điểm neo chuyển tiếp (toàn văn + tóm tắt chương trước) ===
        if chapter_number == 1:
            context.continuation_point = None
            context.previous_chapter_summary = None
            context.previous_chapter_events = None
            logger.info("  ✅ Chương 1 không cần điểm neo chuyển tiếp")
        else:
            ending_info = await self._get_last_ending_enhanced(
                chapter, db, self.ENDING_LENGTH
            )
            context.continuation_point = ending_info.get('ending_text')
            context.previous_chapter_summary = ending_info.get('summary')
            context.previous_chapter_events = ending_info.get('key_events')
            logger.info(f"  ✅ Điểm neo chuyển tiếp: {len(context.continuation_point or '')} ký tự")
        
        # === P1-thông tin quan trọng ===
        # Thông tin nhân vật (bản đầy đủ: gồm tuổi, ngoại hình, bối cảnh, quan hệ, tổ chức, nghề) + chi tiết nghề độc lập
        characters_info, careers_info = await self._build_chapter_characters_1n(
            chapter, project, outline, db
        )
        context.chapter_characters = characters_info
        context.chapter_careers = careers_info
        context.emotional_tone = self._extract_emotional_tone(chapter, outline)
        logger.info(f"  ✅ Thông tin nhân vật: {len(context.chapter_characters)} ký tự")
        logger.info(f"  ✅ Thông tin nghề: {len(context.chapter_careers or '')} ký tự")
        
        # === P2-thông tin tham khảo (luôn bật) ===
        if self.memory_service:
            context.relevant_memories = await self._get_relevant_memories_enhanced(
                user_id, project.id, chapter,
                context.chapter_outline, db
            )
            logger.info(f"  ✅ Ký ức liên quan: {len(context.relevant_memories or '')} ký tự")
        
        # === P2-nhắc phục bút ===
        if self.foreshadow_service:
            context.foreshadow_reminders = await self._get_foreshadow_reminders(
                project.id, chapter_number, db
            )
            if context.foreshadow_reminders:
                logger.info(f"  ✅ Nhắc phục bút: {len(context.foreshadow_reminders)} ký tự")
        
        # === Thông tin thống kê ===
        context.context_stats = {
            "mode": "one-to-many",
            "chapter_number": chapter_number,
            "has_continuation": context.continuation_point is not None,
            "continuation_length": len(context.continuation_point or ""),
            "characters_length": len(context.chapter_characters),
            "careers_length": len(context.chapter_careers or ""),
            "recent_context_length": len(context.recent_chapters_context or ""),
            "memories_length": len(context.relevant_memories or ""),
            "foreshadow_length": len(context.foreshadow_reminders or ""),
            "total_length": context.get_total_context_length()
        }
        
        logger.info(f"📊 [Chế độ 1-N] Xây dựng context hoàn tất: tổng độ dài {context.context_stats['total_length']} ký tự")
        
        return context
    
    def _build_chapter_outline_1n(
        self,
        chapter: Chapter,
        outline: Optional[Outline]
    ) -> str:
        """Xây dựng dàn ý chương ở chế độ 1-N"""
        # Ưu tiên dùng kế hoạch chi tiết của expansion_plan
        if chapter.expansion_plan:
            try:
                plan = json.loads(chapter.expansion_plan)
                # expansion_plan không có key plot_summary,
                outline_content = f"""Tóm tắt cốt truyện: {plan.get('plot_summary') or chapter.summary or 'không có'}"

Sự kiện then chốt:
{chr(10).join(f'- {event}' for event in plan.get('key_events', []))}

Tiêu điểm nhân vật: {', '.join(plan.get('character_focus', []))}
Tông cảm xúc: {plan.get('emotional_tone', 'chưa đặt')}
Mục tiêu tự sự: {plan.get('narrative_goal', 'chưa đặt')}
Loại xung đột: {plan.get('conflict_type', 'chưa đặt')}"""
                return outline_content
            except json.JSONDecodeError:
                pass
        
        # Fallback về nội dung dàn ý
        return outline.content if outline else chapter.summary or 'chưa có dàn ý'
    
    async def _build_chapter_characters_1n(
        self,
        chapter: Chapter,
        project: Project,
        outline: Optional[Outline],
        db: AsyncSession
    ) -> tuple[str, Optional[str]]:
        """Xây dựng thông tin nhân vật ở chế độ 1-N (bản đầy đủ: gồm tuổi, ngoại hình, bối cảnh, quan hệ, tổ chức, nghề) + chi tiết nghề độc lập"""
        from sqlalchemy import or_
        
        # Lấy mọi nhân vật
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        all_characters = characters_result.scalars().all()
        
        if not all_characters:
            return "Chưa có thông tin nhân vật", None
        
        # Xây dựng map tên nhân vật toàn cục (để truy vấn quan hệ)
        all_char_map = {c.id: c.name for c in all_characters}
        
        # Trích tiêu điểm nhân vật từ expansion_plan
        filter_character_names = None
        if chapter.expansion_plan:
            try:
                plan = json.loads(chapter.expansion_plan)
                filter_character_names = plan.get('character_focus', [])
            except json.JSONDecodeError:
                pass
        
        # Lọc nhân vật
        characters = all_characters
        if filter_character_names:
            characters = [c for c in all_characters if c.name in filter_character_names]
        
        if not characters:
            return "Chưa có nhân vật liên quan", None
        
        # Giới hạn tối đa 10 nhân vật
        characters = characters[:10]
        character_ids = [c.id for c in characters]
        
        # === Truy vấn hàng loạt dữ liệu quan hệ ===
        rels_result = await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.project_id == project.id,
                or_(
                    CharacterRelationship.character_from_id.in_(character_ids),
                    CharacterRelationship.character_to_id.in_(character_ids)
                )
            )
        )
        all_rels = rels_result.scalars().all()
        
        # Nhóm quan hệ theo ID nhân vật
        char_rels_map: Dict[str, List] = {cid: [] for cid in character_ids}
        for r in all_rels:
            if r.character_from_id in char_rels_map:
                char_rels_map[r.character_from_id].append(r)
            if r.character_to_id in char_rels_map:
                char_rels_map[r.character_to_id].append(r)
        
        # === Truy vấn hàng loạt dữ liệu thành viên tổ chức ===
        non_org_ids = [c.id for c in characters if not c.is_organization]
        org_memberships_map: Dict[str, List] = {cid: [] for cid in non_org_ids}
        
        if non_org_ids:
            member_result = await db.execute(
                select(OrganizationMember, Character.name).join(
                    Organization, OrganizationMember.organization_id == Organization.id
                ).join(
                    Character, Organization.character_id == Character.id
                ).where(OrganizationMember.character_id.in_(non_org_ids))
            )
            for m, org_name in member_result.all():
                if m.character_id in org_memberships_map:
                    org_memberships_map[m.character_id].append((m, org_name))
        
        # === Truy vấn hàng loạt dữ liệu liên kết nghề (CharacterCareer) ===
        char_career_result = await db.execute(
            select(CharacterCareer).where(CharacterCareer.character_id.in_(character_ids))
        )
        all_char_careers = char_career_result.scalars().all()
        
        # Thu thập mọi ID nghề
        career_ids = set()
        for cc in all_char_careers:
            career_ids.add(cc.career_id)
        # Cũng thêm main_career_id
        for c in characters:
            if not c.is_organization and c.main_career_id:
                career_ids.add(c.main_career_id)
        
        careers_map: Dict[str, Career] = {}
        if career_ids:
            careers_result = await db.execute(
                select(Career).where(Career.id.in_(list(career_ids)))
            )
            careers_map = {c.id: c for c in careers_result.scalars().all()}
        
        # Xây dựng map từ ID nhân vật tới liên kết nghề
        char_career_relations: Dict[str, Dict[str, List]] = {}
        for cc in all_char_careers:
            if cc.character_id not in char_career_relations:
                char_career_relations[cc.character_id] = {'main': [], 'sub': []}
            if cc.career_type == 'main':
                char_career_relations[cc.character_id]['main'].append(cc)
            else:
                char_career_relations[cc.character_id]['sub'].append(cc)
        
        # === Truy vấn danh sách thành viên của nhân vật tổ chức ===
        org_chars = [c for c in characters if c.is_organization]
        org_members_map: Dict[str, List] = {}
        
        if org_chars:
            org_char_ids = [c.id for c in org_chars]
            orgs_result = await db.execute(
                select(Organization).where(Organization.character_id.in_(org_char_ids))
            )
            orgs = orgs_result.scalars().all()
            
            if orgs:
                org_id_to_char_id = {o.id: o.character_id for o in orgs}
                org_ids = [o.id for o in orgs]
                
                members_result = await db.execute(
                    select(OrganizationMember, Character.name).join(
                        Character, OrganizationMember.character_id == Character.id
                    ).where(OrganizationMember.organization_id.in_(org_ids))
                )
                for m, member_name in members_result.all():
                    char_id = org_id_to_char_id.get(m.organization_id)
                    if char_id:
                        if char_id not in org_members_map:
                            org_members_map[char_id] = []
                        org_members_map[char_id].append((m, member_name))
        
        # === Xây dựng thông tin nhân vật bản đầy đủ ===
        characters_info_parts = []
        for c in characters:
            entity_type = 'tổ chức' if c.is_organization else 'nhân vật'
            role_type_map = {
                'protagonist': 'nhân vật chính',
                'antagonist': 'phản diện',
                'supporting': 'vai phụ'
            }
            role_type = role_type_map.get(c.role_type, c.role_type or 'vai phụ')
            
            info_lines = [f"【{c.name}】({entity_type}, {role_type})"]
            
            # Thuộc tính chi tiết
            if c.age:
                info_lines.append(f"  Tuổi: {c.age}")
            if c.gender:
                info_lines.append(f"  Giới tính: {c.gender}")
            if c.appearance:
                appearance_preview = c.appearance[:100] if len(c.appearance) > 100 else c.appearance
                info_lines.append(f"  Ngoại hình: {appearance_preview}")
            if c.personality:
                personality_preview = c.personality[:100] if len(c.personality) > 100 else c.personality
                info_lines.append(f"  Tính cách: {personality_preview}")
            if c.background:
                background_preview = c.background[:150] if len(c.background) > 150 else c.background
                info_lines.append(f"  Bối cảnh: {background_preview}")
            _append_current_state_lines(info_lines, c)
            
            # Thông tin nghề
            if c.id in char_career_relations:
                career_rel = char_career_relations[c.id]
                if career_rel['main']:
                    for cc in career_rel['main']:
                        career = careers_map.get(cc.career_id)
                        if career:
                            try:
                                stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                                stage_name = f'giai đoạn {cc.current_stage}'
                                for stage in (stages or []):
                                    if stage.get('level') == cc.current_stage:
                                        stage_name = stage.get('name', stage_name)
                                        break
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                stage_name = f'giai đoạn {cc.current_stage}'
                            info_lines.append(f"  Nghề chính: {career.name} ({cc.current_stage}/{career.max_stage} giai đoạn - {stage_name})")
                if career_rel['sub']:
                    for cc in career_rel['sub']:
                        career = careers_map.get(cc.career_id)
                        if career:
                            try:
                                stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                                stage_name = f'giai đoạn {cc.current_stage}'
                                for stage in (stages or []):
                                    if stage.get('level') == cc.current_stage:
                                        stage_name = stage.get('name', stage_name)
                                        break
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                stage_name = f'giai đoạn {cc.current_stage}'
                            info_lines.append(f"  Nghề phụ: {career.name} ({cc.current_stage}/{career.max_stage} giai đoạn - {stage_name})")
            elif not c.is_organization and c.main_career_id:
                career = careers_map.get(c.main_career_id)
                if career:
                    stage = c.main_career_stage or 1
                    info_lines.append(f"  Nghề chính: {career.name} (giai đoạn {stage})")
            
            # Quan hệ nhân vật
            if not c.is_organization and c.id in char_rels_map:
                rels = char_rels_map[c.id]
                if rels:
                    rel_parts = []
                    for r in rels:
                        if r.character_from_id == c.id:
                            target_name = all_char_map.get(r.character_to_id, "không rõ")
                        else:
                            target_name = all_char_map.get(r.character_from_id, "không rõ")
                        rel_name = r.relationship_name or "liên quan"
                        rel_parts.append(f"Với {target_name}: {rel_name}")
                    info_lines.append(f"  Mạng quan hệ: {';'.join(rel_parts)}")
            
            # Trực thuộc tổ chức
            if not c.is_organization and c.id in org_memberships_map:
                memberships = org_memberships_map[c.id]
                if memberships:
                    org_parts = [f"{org_name}（{m.position}）" for m, org_name in memberships[:2]]
                    info_lines.append(f"  Trực thuộc tổ chức: {'、'.join(org_parts)}")
            
            # Thông tin đặc thù tổ chức
            if c.is_organization:
                if c.organization_type:
                    info_lines.append(f"  Loại tổ chức: {c.organization_type}")
                if c.organization_purpose:
                    info_lines.append(f"  Mục đích tổ chức: {c.organization_purpose[:100]}")
                if c.id in org_members_map:
                    members = org_members_map[c.id]
                    if members:
                        member_parts = [f"{name}（{m.position}）" for m, name in members[:5]]
                        info_lines.append(f"  Thành viên tổ chức: {'、'.join(member_parts)}")
            
            characters_info_parts.append("\n".join(info_lines))
        
        characters_result_str = "\n\n".join(characters_info_parts)
        logger.info(f"  ✅ [Bản đầy đủ 1-N] Đã xây dựng thông tin {len(characters_info_parts)} nhân vật, tổng độ dài: {len(characters_result_str)} ký tự")
        
        # === Xây dựng chi tiết nghề độc lập ===
        careers_info_parts = []
        if careers_map:
            for career_id, career in careers_map.items():
                career_lines = [f"{career.name} (nghề {career.type})"]
                if career.description:
                    career_lines.append(f"  Mô tả: {career.description}")
                if career.category:
                    career_lines.append(f"  Phân loại: {career.category}")
                try:
                    stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                    if stages:
                        career_lines.append(f"  Hệ thống giai đoạn: (tổng {career.max_stage} giai đoạn)")
                        for stage in stages:
                            level = stage.get('level', '?')
                            name = stage.get('name', 'chưa đặt tên')
                            desc = stage.get('description', '')
                            career_lines.append(f"    Giai đoạn {level}-{name}: {desc}")
                except (json.JSONDecodeError, AttributeError, TypeError):
                    career_lines.append(f"  Hệ thống giai đoạn: tổng {career.max_stage} giai đoạn")
                if career.special_abilities:
                    career_lines.append(f"  Năng lực đặc biệt: {career.special_abilities}")
                careers_info_parts.append("\n".join(career_lines))
        
        careers_result_str = None
        if careers_info_parts:
            careers_result_str = "\n\n".join(careers_info_parts)
            logger.info(f"  ✅ [Bản đầy đủ 1-N] Đã xây dựng chi tiết {len(careers_map)} nghề, tổng độ dài: {len(careers_result_str)} ký tự")
        
        return characters_result_str, careers_result_str
    
    async def _build_recent_chapters_context(
        self,
        chapter: Chapter,
        project_id: str,
        db: AsyncSession
    ) -> Optional[str]:
        """Xây dựng tóm tắt expansion_plan 10 chương gần nhất"""
        try:
            result = await db.execute(
                select(Chapter.id, Chapter.chapter_number, Chapter.title, Chapter.expansion_plan, Chapter.summary)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < chapter.chapter_number)
                .order_by(Chapter.chapter_number.desc())
                .limit(self.RECENT_CHAPTERS_COUNT)
            )
            recent_chapters = result.all()
            
            if not recent_chapters:
                return None
            
            # Sắp xếp tăng dần theo số chương
            recent_chapters = sorted(recent_chapters, key=lambda x: x[1])

            chapter_ids = [row[0] for row in recent_chapters]
            summary_map: Dict[str, str] = {}
            analysis_map: Dict[str, Any] = {}
            if chapter_ids:
                summary_result = await db.execute(
                    select(StoryMemory.chapter_id, StoryMemory.content)
                    .where(StoryMemory.chapter_id.in_(chapter_ids))
                    .where(StoryMemory.memory_type == 'chapter_summary')
                )
                summary_map = {chapter_id: content for chapter_id, content in summary_result.all()}

                analysis_result = await db.execute(
                    select(PlotAnalysis.chapter_id, PlotAnalysis.plot_points, PlotAnalysis.character_states)
                    .where(PlotAnalysis.chapter_id.in_(chapter_ids))
                )
                analysis_map = {
                    chapter_id: {"plot_points": plot_points or [], "character_states": character_states or []}
                    for chapter_id, plot_points, character_states in analysis_result.all()
                }
            
            lines = ["【Kế hoạch chương gần đây】"]
            for ch_id, ch_num, ch_title, expansion_plan, summary in recent_chapters:
                real_summary = summary_map.get(ch_id)
                analysis = analysis_map.get(ch_id)
                if real_summary:
                    line = f"Chương {ch_num}《{ch_title}》: {real_summary[:180]}"
                    if analysis and analysis.get("plot_points"):
                        points = []
                        for point in analysis["plot_points"][:3]:
                            if isinstance(point, dict):
                                points.append(str(point.get("content") or ""))
                            else:
                                points.append(str(point))
                        points = [p for p in points if p]
                        if points:
                            line += f"(điểm cốt truyện thực: {';'.join(points)})"
                    lines.append(line)
                elif expansion_plan:
                    try:
                        plan = json.loads(expansion_plan)
                        plot_summary = plan.get('plot_summary', '')
                        key_events = plan.get('key_events', [])
                        events_str = '；'.join(key_events[:3]) if key_events else ''
                        line = f"Chương {ch_num}《{ch_title}》: {plot_summary}"
                        if events_str:
                            line += f"(sự kiện then chốt: {events_str})"
                        lines.append(line)
                    except json.JSONDecodeError:
                        if summary:
                            lines.append(f"Chương {ch_num}《{ch_title}》: {summary[:100]}")
                elif summary:
                    lines.append(f"Chương {ch_num}《{ch_title}》: {summary[:100]}")
            
            if len(lines) <= 1:
                return None
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"❌ Xây dựng context chương gần đây thất bại: {str(e)}")
            return None
    
    async def _get_relevant_memories_enhanced(
        self,
        user_id: str,
        project_id: str,
        chapter: Chapter,
        chapter_outline: str,
        db: AsyncSession
    ) -> Optional[str]:
        """Lấy ký ức liên quan (ưu tiên dùng nhân vật, sự kiện, mục tiêu và xung đột trong expansion_plan 1-N)."""
        if not self.memory_service:
            return None
        
        try:
            chapter_number = chapter.chapter_number
            query_text = self._build_memory_query_from_expansion_plan(chapter, chapter_outline)
            logger.info(f"  🔍 [1-N] Truy vấn ký ức có cấu trúc: {query_text[:180]}...")
            
            relevant_memories = await self.memory_service.search_memories(
                user_id=user_id,
                project_id=project_id,
                query=query_text,
                limit=self.MEMORY_CANDIDATE_LIMIT,
                min_importance=0.0,
                chapter_range=(1, max(0, chapter_number - 1))
            )
            
            filtered_memories = _select_memories_with_fallback(
                memories=relevant_memories,
                threshold=self.MEMORY_SIMILARITY_THRESHOLD,
                fallback_count=self.MEMORY_FALLBACK_COUNT,
                log_prefix="[1-N] "
            )
            
            if not filtered_memories:
                return None
            
            memory_lines = ["【Ký ức liên quan】"]
            for mem in filtered_memories[:self.MEMORY_CONTEXT_LIMIT]:
                similarity = mem.get('similarity', 0)
                content = mem.get('content', '')[:100]
                memory_lines.append(f"- (độ liên quan: {similarity:.2f}) {content}")
            
            return "\n".join(memory_lines) if len(memory_lines) > 1 else None
            
        except Exception as e:
            logger.error(f"❌ Lấy ký ức liên quan thất bại: {str(e)}")
            return None
    
    def _build_memory_query_from_expansion_plan(
        self,
        chapter: Chapter,
        chapter_outline: str
    ) -> str:
        """Xây dựng query truy xuất ký ức tín hiệu cao từ kế hoạch mở rộng chương 1-N."""
        sections = []
        if chapter.expansion_plan:
            try:
                plan = json.loads(chapter.expansion_plan)
                sections.extend(filter(None, [
                    _format_memory_query_section("nhân vật", _stringify_list_items(plan.get("character_focus"), limit=8)),
                    _format_memory_query_section("sự kiện then chốt", _stringify_list_items(plan.get("key_events"), limit=6)),
                    _format_memory_query_section("mục tiêu tự sự", _stringify_list_items(plan.get("narrative_goal"), limit=1)),
                    _format_memory_query_section("xung đột", _stringify_list_items(plan.get("conflict_type"), limit=1)),
                    _format_memory_query_section("cảm xúc", _stringify_list_items(plan.get("emotional_tone"), limit=1)),
                ]))
            except json.JSONDecodeError:
                logger.warning(f"  ⚠️ [1-N] Phân tích expansion_plan thất bại, dùng dàn ý chương dự phòng: chapter={chapter.id}")

        if sections:
            return "\n".join(sections)[:800]

        return chapter_outline[:500].replace('\n', ' ')
    
    async def _get_last_ending_enhanced(
        self,
        chapter: Chapter,
        db: AsyncSession,
        max_length: Optional[int]
    ) -> Dict[str, Any]:
        """Lấy điểm neo chuyển tiếp bản tăng cường (gồm toàn văn, tóm tắt và sự kiện then chốt chương trước)"""
        result_info = {
            'ending_text': None,
            'summary': None,
            'key_events': []
        }
        
        if chapter.chapter_number <= 1:
            return result_info
        
        # Truy vấn chương trước: không giả định số thứ tự liên tục, lấy chương có chapter_number < chương hiện tại lớn nhất
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == chapter.project_id)
            .where(Chapter.chapter_number < chapter.chapter_number)
            .order_by(Chapter.chapter_number.desc())
            .limit(1)
        )
        prev_chapter = result.scalar_one_or_none()
        
        if not prev_chapter:
            return result_info
        
        # 1. Trích toàn văn chương trước; max_length chỉ làm dự phòng tương thích
        if prev_chapter.content:
            content = prev_chapter.content.strip()
            if max_length is None or len(content) <= max_length:
                result_info['ending_text'] = content
            else:
                result_info['ending_text'] = content[-max_length:]
        
        # 2. Lấy tóm tắt chương trước
        summary_result = await db.execute(
            select(StoryMemory.content)
            .where(StoryMemory.project_id == chapter.project_id)
            .where(StoryMemory.chapter_id == prev_chapter.id)
            .where(StoryMemory.memory_type == 'chapter_summary')
            .limit(1)
        )
        summary_mem = summary_result.scalar_one_or_none()
        
        if summary_mem:
            result_info['summary'] = summary_mem[:300]
        elif prev_chapter.summary:
            result_info['summary'] = prev_chapter.summary[:300]
        elif prev_chapter.expansion_plan:
            try:
                plan = json.loads(prev_chapter.expansion_plan)
                result_info['summary'] = plan.get('plot_summary', '')[:300]
            except json.JSONDecodeError:
                pass
        
        # 3. Trích sự kiện then chốt chương trước
        if prev_chapter.expansion_plan:
            try:
                plan = json.loads(prev_chapter.expansion_plan)
                key_events = plan.get('key_events', [])
                if key_events:
                    result_info['key_events'] = key_events[:5]
            except json.JSONDecodeError:
                pass
        
        return result_info
    
    def _extract_emotional_tone(
        self,
        chapter: Chapter,
        outline: Optional[Outline]
    ) -> str:
        """Trích tông cảm xúc chương này"""
        if chapter.expansion_plan:
            try:
                plan = json.loads(chapter.expansion_plan)
                tone = plan.get('emotional_tone')
                if tone:
                    return tone
            except json.JSONDecodeError:
                pass
        
        if outline and outline.structure:
            try:
                structure = json.loads(outline.structure)
                tone = structure.get('emotion') or structure.get('emotional_tone')
                if tone:
                    return tone
            except json.JSONDecodeError:
                pass
        
        return "chưa đặt"
    
    def _summarize_style(self, style_content: str) -> str:
        """Nén mô tả phong cách thành điểm then chốt"""
        if not style_content:
            return ""
        
        if len(style_content) <= self.STYLE_MAX_LENGTH:
            return style_content
        
        return style_content[:self.STYLE_MAX_LENGTH] + "..."
    
    async def _get_relevant_memories(
        self,
        user_id: str,
        project_id: str,
        chapter_number: int,
        chapter_outline: str,
        limit: int = 3
    ) -> Optional[str]:
        """
        Lấy ký ức liên quan nhất tới chương này
        
        Chú ý: thông tin liên quan phục bút do _get_foreshadow_reminders() cung cấp thống nhất qua foreshadow_service,
        phương thức này chỉ phụ trách lấy ký ức truyện, không lấy thông tin phục bút từ memory_service cũ nữa.
        """
        if not self.memory_service:
            return None
        
        try:
            relevant = await self.memory_service.search_memories(
                user_id=user_id,
                project_id=project_id,
                query=chapter_outline,
                limit=limit,
                min_importance=self.MEMORY_IMPORTANCE_THRESHOLD
            )
            
            return self._format_memories(relevant, max_length=500)
            
        except Exception as e:
            logger.error(f"❌ Lấy ký ức liên quan thất bại: {str(e)}")
            return None
    
    def _format_memories(
        self,
        relevant: List[Dict[str, Any]],
        max_length: int = 500
    ) -> str:
        """Format ký ức thành văn bản gọn (ký ức thuần, không gồm phục bút)"""
        if not relevant:
            return None
        
        lines = ["【Ký ức liên quan】"]
        current_length = 0
        
        for mem in relevant:
            content = mem.get('content', '')[:80]
            text = f"- {content}"
            if current_length + len(text) > max_length:
                break
            lines.append(text)
            current_length += len(text)
        
        return "\n".join(lines) if len(lines) > 1 else None
    
    async def _get_foreshadow_reminders(
        self,
        project_id: str,
        chapter_number: int,
        db: AsyncSession
    ) -> Optional[str]:
        """
        Lấy thông tin nhắc phục bút (bản tăng cường)
        
        Chiến lược:
        1. Phục bút phải thu hồi trong chương này (target_resolve_chapter_number == chapter_number)
        2. Phục bút quá hạn chưa thu hồi (target_resolve_chapter_number < chapter_number)
        3. Phục bút sắp đến hạn (target_resolve_chapter_number trong 3 chương tới)
        """
        if not self.foreshadow_service:
            return None
        
        try:
            lines = []
            
            # 1. Phục bút phải thu hồi trong chương này
            must_resolve = await self.foreshadow_service.get_must_resolve_foreshadows(
                db=db,
                project_id=project_id,
                chapter_number=chapter_number
            )
            
            if must_resolve:
                lines.append("【🎯 Phục bút phải thu hồi trong chương này】")
                for f in must_resolve:
                    lines.append(f"- {f.title}")
                    lines.append(f"  Chương gieo: chương {f.plant_chapter_number}")
                    lines.append(f"  Nội dung phục bút: {f.content[:100]}{'...' if len(f.content) > 100 else ''}")
                    if f.resolution_notes:
                        lines.append(f"  Gợi ý thu hồi: {f.resolution_notes}")
                    lines.append("")
            
            # 2. Phục bút quá hạn chưa thu hồi
            overdue = await self.foreshadow_service.get_overdue_foreshadows(
                db=db,
                project_id=project_id,
                current_chapter=chapter_number
            )
            
            if overdue:
                lines.append("【⚠️ Phục bút quá hạn thu hồi】")
                for f in overdue[:3]:  # Hiển thị tối đa 3
                    overdue_chapters = chapter_number - (f.target_resolve_chapter_number or 0)
                    lines.append(f"- {f.title} [đã quá hạn {overdue_chapters} chương]")
                    lines.append(f"  Chương gieo: chương {f.plant_chapter_number}, kế hoạch gốc thu hồi ở chương {f.target_resolve_chapter_number}")
                    lines.append(f"  Nội dung phục bút: {f.content[:80]}...")
                    lines.append("")
            
            # 3. Phục bút sắp đến hạn (trong 3 chương tới)
            upcoming = await self.foreshadow_service.get_pending_resolve_foreshadows(
                db=db,
                project_id=project_id,
                current_chapter=chapter_number,
                lookahead=3
            )
            
            # Lọc: chỉ giữ chương tương lai, loại chương này và quá hạn
            upcoming_filtered = [f for f in upcoming
                               if (f.target_resolve_chapter_number or 0) > chapter_number]
            
            if upcoming_filtered:
                lines.append("【📋 Phục bút sắp đến hạn (chỉ tham khảo)】")
                for f in upcoming_filtered[:3]:  # Hiển thị tối đa 3
                    remaining = (f.target_resolve_chapter_number or 0) - chapter_number
                    lines.append(f"- {f.title} (kế hoạch thu hồi ở chương {f.target_resolve_chapter_number}, còn {remaining} chương)")
                lines.append("")
            
            return "\n".join(lines) if lines else None
            
        except Exception as e:
            logger.error(f"❌ Lấy nhắc phục bút thất bại: {str(e)}")
            return None
    
    async def _build_story_skeleton(
        self,
        project_id: str,
        chapter_number: int,
        db: AsyncSession
    ) -> Optional[str]:
        """Xây dựng khung truyện (lấy mẫu mỗi N chương)"""
        try:
            result = await db.execute(
                select(Chapter.id, Chapter.chapter_number, Chapter.title)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < chapter_number)
                .where(Chapter.content != None)
                .where(Chapter.content != "")
                .order_by(Chapter.chapter_number)
            )
            chapters = result.all()
            
            if not chapters:
                return None
            
            skeleton_lines = ["【Khung truyện】"]
            for i, (ch_id, ch_num, ch_title) in enumerate(chapters):
                if i % self.SKELETON_SAMPLE_INTERVAL == 0:
                    summary_result = await db.execute(
                        select(StoryMemory.content)
                        .where(StoryMemory.project_id == project_id)
                        .where(StoryMemory.chapter_id == ch_id)
                        .where(StoryMemory.memory_type == 'chapter_summary')
                        .limit(1)
                    )
                    summary = summary_result.scalar_one_or_none()
                    
                    if summary:
                        skeleton_lines.append(f"Chương {ch_num}《{ch_title}》: {summary[:100]}")
                    else:
                        skeleton_lines.append(f"Chương {ch_num}《{ch_title}》")
            
            if len(skeleton_lines) <= 1:
                return None
            
            return "\n".join(skeleton_lines)
            
        except Exception as e:
            logger.error(f"❌ Xây dựng khung truyện thất bại: {str(e)}")
            return None


# ==================== Bộ xây dựng context chế độ 1-1 ====================

class OneToOneContextBuilder:
    """
    Bộ xây dựng context chế độ 1-1
    
    Chiến lược xây dựng context:
    Thông tin cốt lõi P0:
    1. Trích từ JSON của outline.structure: summary, scenes, key_points, emotion, goal
    2. target_word_count
    
    Thông tin quan trọng P1:
    1. Tóm tắt cốt truyện N chương gần nhất làm tham khảo tính liên tục
    2. Toàn văn chương trước làm tham khảo
    3. Lấy thông tin nhân vật theo characters trong structure (gồm nghề)
    
    Thông tin tham khảo P2:
    1. Nhắc phục bút
    2. Truy xuất ký ức liên quan theo tên nhân vật (độ liên quan > 0.6)
    """
    
    RECENT_CHAPTERS_COUNT = 10   # Số lượng tóm tắt chương gần đây
    MEMORY_CANDIDATE_LIMIT = 50  # Kích thước pool ứng viên truy xuất vector
    MEMORY_CONTEXT_LIMIT = 10    # Số mục ký ức tiêm vào prompt cuối cùng
    MEMORY_FALLBACK_COUNT = 5    # Số ứng viên giữ lại khi không có hit điểm cao

    def __init__(self, memory_service=None, foreshadow_service=None):
        """
        Khởi tạo builder
        
        Args:
            memory_service: instance dịch vụ ký ức (tùy chọn)
            foreshadow_service: instance dịch vụ phục bút (tùy chọn)
        """
        self.memory_service = memory_service
        self.foreshadow_service = foreshadow_service
    
    async def build(
        self,
        chapter: Chapter,
        project: Project,
        outline: Optional[Outline],
        user_id: str,
        db: AsyncSession,
        target_word_count: int = 3000
    ) -> OneToOneContext:
        """
        Xây dựng context chế độ 1-1
        
        Args:
            chapter: đối tượng chương
            project: đối tượng project
            outline: đối tượng dàn ý
            user_id: ID người dùng
            db: phiên làm việc cơ sở dữ liệu
            target_word_count: số từ mục tiêu
            
        Returns:
            OneToOneContext: đối tượng context
        """
        chapter_number = chapter.chapter_number
        logger.info(f"📝 [Chế độ 1-1] Bắt đầu xây dựng context: chương {chapter_number}")
        
        # Khởi tạo context
        context = OneToOneContext(
            chapter_number=chapter_number,
            chapter_title=chapter.title or "",
            title=project.title or "",
            genre=project.genre or "",
            theme=project.theme or "",
            target_word_count=target_word_count,
            min_word_count=max(500, target_word_count - 500),
            max_word_count=target_word_count + 1000,
            narrative_perspective=project.narrative_perspective or "ngôi thứ ba"
        )
        
        # === P0-thông tin cốt lõi ===
        context.chapter_outline = self._build_outline_from_structure(outline, chapter)
        logger.info(f"  ✅ P0-thông tin dàn ý: {len(context.chapter_outline)} ký tự")
        
        # === P1-thông tin quan trọng ===
        # 0. Cửa sổ tóm tắt cốt truyện N chương gần nhất
        if chapter_number > 1:
            context.recent_chapters_context = await self._build_recent_chapters_context(
                chapter, project.id, db
            )
            logger.info(f"  ✅ P1-tóm tắt chương gần đây: {len(context.recent_chapters_context or '')} ký tự")

        # 1. Lấy toàn văn và tóm tắt chương trước
        if chapter_number > 1:
            # Tìm chương trước: không giả định số thứ tự liên tục, lấy chương có chapter_number < chương hiện tại lớn nhất
            prev_chapter_result = await db.execute(
                select(Chapter)
                .where(Chapter.project_id == chapter.project_id)
                .where(Chapter.chapter_number < chapter_number)
                .order_by(Chapter.chapter_number.desc())
                .limit(1)
            )
            prev_chapter = prev_chapter_result.scalar_one_or_none()
            
            if prev_chapter and prev_chapter.content:
                content = prev_chapter.content.strip()
                context.continuation_point = content
                logger.info(f"  ✅ P1-toàn văn chương trước: {len(context.continuation_point)} ký tự")
                
                # Lấy tóm tắt chương trước (ưu tiên từ hệ thống ký ức, sau đó dùng tóm tắt chương)
                summary_result = await db.execute(
                    select(StoryMemory.content)
                    .where(StoryMemory.project_id == chapter.project_id)
                    .where(StoryMemory.chapter_id == prev_chapter.id)
                    .where(StoryMemory.memory_type == 'chapter_summary')
                    .limit(1)
                )
                summary_mem = summary_result.scalar_one_or_none()
                
                if summary_mem:
                    context.previous_chapter_summary = summary_mem[:300]
                    logger.info(f"  ✅ P1-tóm tắt chương trước (ký ức): {len(context.previous_chapter_summary)} ký tự")
                elif prev_chapter.summary:
                    context.previous_chapter_summary = prev_chapter.summary[:300]
                    logger.info(f"  ✅ P1-tóm tắt chương trước (chương): {len(context.previous_chapter_summary)} ký tự")
                else:
                    context.previous_chapter_summary = None
                    logger.info(f"  ⚠️ P1-tóm tắt chương trước: không có")
            else:
                context.continuation_point = None
                context.previous_chapter_summary = None
                logger.info(f"  ⚠️ P1-nội dung chương trước: không có")
        else:
            context.continuation_point = None
            context.previous_chapter_summary = None
            logger.info(f"  ✅ P1-chương 1 không cần nội dung chương trước")
        
        # 2. Lấy thông tin nhân vật theo characters trong structure (gồm nghề)
        character_names = []
        if outline and outline.structure:
            try:
                structure = json.loads(outline.structure)
                raw_characters = structure.get('characters', [])
                # characters có thể là list chuỗi hoặc list dict, trích thống nhất thành list chuỗi tên
                character_names = [
                    c['name'] if isinstance(c, dict) else c
                    for c in raw_characters
                ]
                logger.info(f"  📋 Trích nhân vật từ structure: {character_names}")
            except json.JSONDecodeError:
                pass
        
        if character_names:
            # Lấy thông tin cơ bản nhân vật
            characters_result = await db.execute(
                select(Character)
                .where(Character.project_id == project.id)
                .where(Character.name.in_(character_names))
            )
            characters = characters_result.scalars().all()
            
            if characters:
                # Xây dựng context nhân vật gồm thông tin nghề và chi tiết nghề
                characters_info, careers_info = await self._build_characters_and_careers(
                    db=db,
                    project_id=project.id,
                    characters=characters,
                    filter_character_names=character_names
                )
                context.chapter_characters = characters_info
                context.chapter_careers = careers_info
                logger.info(f"  ✅ P1-thông tin nhân vật: {len(context.chapter_characters)} ký tự")
                logger.info(f"  ✅ P1-thông tin nghề: {len(context.chapter_careers or '')} ký tự")
            else:
                context.chapter_characters = "Chưa có thông tin nhân vật"
                context.chapter_careers = None
                logger.info(f"  ⚠️ P1-thông tin nhân vật: lọc xong không có nhân vật khớp")
        else:
            context.chapter_characters = "Chưa có thông tin nhân vật"
            context.chapter_careers = None
            logger.info(f"  ⚠️ P1-thông tin nhân vật: không có")
        
        # === P2-thông tin tham khảo ===
        # 1. Nhắc phục bút
        if self.foreshadow_service:
            context.foreshadow_reminders = await self._get_foreshadow_reminders(
                project.id, chapter_number, db
            )
            if context.foreshadow_reminders:
                logger.info(f"  ✅ P2-nhắc phục bút: {len(context.foreshadow_reminders)} ký tự")
            else:
                logger.info(f"  ⚠️ P2-nhắc phục bút: không có")
        
        # 2. Truy xuất ký ức liên quan theo nội dung dàn ý (độ liên quan > 0.4)
        if self.memory_service and context.chapter_outline:
            try:
                query_text = self._build_memory_query_from_outline_structure(outline, context.chapter_outline)
                logger.info(f"  🔍 [1-1] Truy vấn ký ức có cấu trúc: {query_text[:180]}...")
                
                relevant_memories = await self.memory_service.search_memories(
                    user_id=user_id,
                    project_id=project.id,
                    query=query_text,
                    limit=self.MEMORY_CANDIDATE_LIMIT,
                    min_importance=0.0,
                    chapter_range=(1, max(0, chapter_number - 1))
                )
                
                filtered_memories = _select_memories_with_fallback(
                    memories=relevant_memories,
                    threshold=0.6,
                    fallback_count=self.MEMORY_FALLBACK_COUNT,
                    log_prefix="[1-1] "
                )
                
                if filtered_memories:
                    memory_lines = ["【Ký ức liên quan】"]
                    for mem in filtered_memories[:self.MEMORY_CONTEXT_LIMIT]:
                        similarity = mem.get('similarity', 0)
                        content = mem.get('content', '')[:100]
                        memory_lines.append(f"- (độ liên quan: {similarity:.2f}) {content}")
                    
                    context.relevant_memories = "\n".join(memory_lines)
                    logger.info(f"  ✅ P2-ký ức liên quan: {len(filtered_memories)} mục (độ liên quan > 0.6, tìm được {len(relevant_memories)} mục)")
                else:
                    context.relevant_memories = None
                    logger.info(f"  ⚠️ P2-ký ức liên quan: không có ký ức đạt điều kiện (tìm được {len(relevant_memories)} mục)")
                    
            except Exception as e:
                logger.error(f"  ❌ Truy xuất ký ức liên quan thất bại: {str(e)}")
                context.relevant_memories = None
        else:
            context.relevant_memories = None
            logger.info(f"  ⚠️ P2-ký ức liên quan: không có nội dung dàn ý hoặc dịch vụ ký ức không khả dụng")
        
        # === Thông tin thống kê ===
        context.context_stats = {
            "mode": "one-to-one",
            "chapter_number": chapter_number,
            "has_previous_content": context.continuation_point is not None,
            "recent_context_length": len(context.recent_chapters_context or ""),
            "previous_content_length": len(context.continuation_point or ""),
            "previous_summary_length": len(context.previous_chapter_summary or ""),
            "outline_length": len(context.chapter_outline),
            "characters_length": len(context.chapter_characters),
            "careers_length": len(context.chapter_careers or ""),
            "foreshadow_length": len(context.foreshadow_reminders or ""),
            "memories_length": len(context.relevant_memories or ""),
            "total_length": context.get_total_context_length()
        }
        
        logger.info(f"📊 [Chế độ 1-1] Xây dựng context hoàn tất: tổng độ dài {context.context_stats['total_length']} ký tự")
        
        return context
    
    async def _build_recent_chapters_context(
        self,
        chapter: Chapter,
        project_id: str,
        db: AsyncSession
    ) -> Optional[str]:
        """Xây dựng cửa sổ tóm tắt cốt truyện N chương gần nhất (chế độ 1-1)."""
        try:
            result = await db.execute(
                select(Chapter.id, Chapter.chapter_number, Chapter.title, Chapter.summary)
                .where(Chapter.project_id == project_id)
                .where(Chapter.chapter_number < chapter.chapter_number)
                .order_by(Chapter.chapter_number.desc())
                .limit(self.RECENT_CHAPTERS_COUNT)
            )
            recent_chapters = result.all()

            if not recent_chapters:
                return None

            recent_chapters = sorted(recent_chapters, key=lambda x: x[1])
            chapter_ids = [row[0] for row in recent_chapters]
            summary_map: Dict[str, str] = {}
            analysis_map: Dict[str, Any] = {}

            if chapter_ids:
                summary_result = await db.execute(
                    select(StoryMemory.chapter_id, StoryMemory.content)
                    .where(StoryMemory.chapter_id.in_(chapter_ids))
                    .where(StoryMemory.memory_type == 'chapter_summary')
                )
                summary_map = {chapter_id: content for chapter_id, content in summary_result.all()}

                analysis_result = await db.execute(
                    select(PlotAnalysis.chapter_id, PlotAnalysis.plot_points)
                    .where(PlotAnalysis.chapter_id.in_(chapter_ids))
                )
                analysis_map = {
                    chapter_id: plot_points or []
                    for chapter_id, plot_points in analysis_result.all()
                }

            lines = [f"【Tóm tắt cốt truyện {len(recent_chapters)} chương gần nhất】"]
            for ch_id, ch_num, ch_title, summary in recent_chapters:
                real_summary = summary_map.get(ch_id) or summary
                if real_summary:
                    line = f"Chương {ch_num}《{ch_title}》: {real_summary[:180]}"
                else:
                    line = f"Chương {ch_num}《{ch_title}》"

                plot_points = analysis_map.get(ch_id) or []
                points = []
                for point in plot_points[:3]:
                    if isinstance(point, dict):
                        points.append(str(point.get("content") or ""))
                    else:
                        points.append(str(point))
                points = [p for p in points if p]
                if points:
                    line += f"(điểm cốt truyện then chốt: {';'.join(points)})"
                lines.append(line)

            return "\n".join(lines) if len(lines) > 1 else None
        except Exception as e:
            logger.error(f"❌ Xây dựng context chương gần đây 1-1 thất bại: {str(e)}")
            return None
    
    def _build_memory_query_from_outline_structure(
        self,
        outline: Optional[Outline],
        chapter_outline: str
    ) -> str:
        """Xây dựng query truy xuất ký ức tín hiệu cao từ structure dàn ý 1-1."""
        sections = []
        if outline and outline.structure:
            try:
                structure = json.loads(outline.structure)
                raw_characters = structure.get("characters", [])
                character_names = []
                organization_names = []
                for item in raw_characters:
                    if isinstance(item, dict):
                        name = str(item.get("name") or "").strip()
                        if not name:
                            continue
                        if item.get("type") == "organization":
                            organization_names.append(name)
                        else:
                            character_names.append(name)
                    elif isinstance(item, str) and item.strip():
                        character_names.append(item.strip())

                sections.extend(filter(None, [
                    _format_memory_query_section("nhân vật", character_names[:8]),
                    _format_memory_query_section("tổ chức", organization_names[:5]),
                    _format_memory_query_section("sự kiện then chốt", _stringify_list_items(structure.get("key_points"), limit=6)),
                    _format_memory_query_section("mục tiêu tự sự", _stringify_list_items(structure.get("goal"), limit=1)),
                    _format_memory_query_section("bối cảnh", _stringify_list_items(structure.get("scenes"), limit=2)),
                    _format_memory_query_section("cảm xúc", _stringify_list_items(structure.get("emotion"), limit=1)),
                ]))

                if not sections and structure.get("summary"):
                    sections.append(f"Tóm tắt: {str(structure['summary'])[:200]}")
            except json.JSONDecodeError:
                logger.warning(f"  ⚠️ [1-1] Phân tích outline.structure thất bại, dùng dàn ý chương dự phòng: outline={outline.id}")

        if sections:
            return "\n".join(sections)[:900]

        return chapter_outline[:500].replace('\n', ' ')
    
    def _build_outline_from_structure(
        self,
        outline: Optional[Outline],
        chapter: Chapter
    ) -> str:
        """Trích thông tin dàn ý từ outline.structure (chuyên cho chế độ 1-1)"""
        if outline and outline.structure:
            try:
                structure = json.loads(outline.structure)
                
                outline_parts = []
                
                if structure.get('summary'):
                    outline_parts.append(f"【Tóm tắt chương】\n{structure['summary']}")
                
                if structure.get('scenes'):
                    scenes_text = "\n".join([f"- {scene}" for scene in structure['scenes']])
                    outline_parts.append(f"【Thiết lập bối cảnh】\n{scenes_text}")
                
                if structure.get('key_points'):
                    points_text = "\n".join([f"- {point}" for point in structure['key_points']])
                    outline_parts.append(f"【Điểm cốt truyện】\n{points_text}")
                
                if structure.get('emotion'):
                    outline_parts.append(f"【Tông cảm xúc】\n{structure['emotion']}")
                
                if structure.get('goal'):
                    outline_parts.append(f"【Mục tiêu tự sự】\n{structure['goal']}")
                
                return "\n\n".join(outline_parts)
                
            except json.JSONDecodeError as e:
                logger.error(f"  ❌ Phân tích outline.structure thất bại: {e}")
                return outline.content if outline else "chưa có dàn ý"
        else:
            return outline.content if outline else "chưa có dàn ý"
    
    async def _build_characters_and_careers(
        self,
        db: AsyncSession,
        project_id: str,
        characters: list,
        filter_character_names: Optional[list] = None
    ) -> tuple[str, Optional[str]]:
        """
        Xây dựng thông tin nhân vật và thông tin nghề (chuyên cho chế độ 1-1)
        Lấy dữ liệu đầy đủ của nhân vật, và truy vấn liên kết dữ liệu đầy đủ của từng nghề
        Trả về riêng thông tin nhân vật và thông tin nghề
        
        Args:
            db: phiên làm việc cơ sở dữ liệu
            project_id: ID project
            characters: danh sách nhân vật
            filter_character_names: danh sách tên nhân vật cần lọc
            
        Returns:
            tuple: (chuỗi thông tin nhân vật, chuỗi thông tin nghề)
        """
        if not characters:
            return 'Chưa có thông tin nhân vật', None
        
        # Nếu đã cung cấp danh sách lọc, chỉ giữ nhân vật khớp
        if filter_character_names:
            filtered_characters = [c for c in characters if c.name in filter_character_names]
            if not filtered_characters:
                logger.warning(f"Lọc xong không có nhân vật khớp, dùng toàn bộ nhân vật. Danh sách lọc: {filter_character_names}")
                filtered_characters = characters
            else:
                logger.info(f"Theo danh sách lọc giữ lại {len(filtered_characters)}/{len(characters)} nhân vật: {[c.name for c in filtered_characters]}")
            characters = filtered_characters
        
        # Lấy danh sách ID nhân vật
        character_ids = [c.id for c in characters]
        if not character_ids:
            return 'Chưa có thông tin nhân vật', None
        
        # Truy vấn lại dữ liệu đầy đủ của nhân vật (đảm bảo lấy mọi field)
        full_characters_result = await db.execute(
            select(Character).where(Character.id.in_(character_ids))
        )
        full_characters = {c.id: c for c in full_characters_result.scalars().all()}
        
        # Lấy dữ liệu liên kết nghề của mọi nhân vật
        character_careers_result = await db.execute(
            select(CharacterCareer).where(CharacterCareer.character_id.in_(character_ids))
        )
        character_careers = character_careers_result.scalars().all()
        
        # Thu thập mọi ID nghề cần truy vấn
        career_ids = set()
        for cc in character_careers:
            career_ids.add(cc.career_id)
        
        # Truy vấn dữ liệu đầy đủ của mọi nghề liên quan
        careers_map = {}
        if career_ids:
            careers_result = await db.execute(
                select(Career).where(Career.id.in_(list(career_ids)))
            )
            careers_map = {c.id: c for c in careers_result.scalars().all()}
            logger.info(f"  📋 Truy vấn được dữ liệu đầy đủ của {len(careers_map)} nghề")
        
        # Xây dựng map từ ID nhân vật tới dữ liệu liên kết nghề
        char_career_relations = {}
        for cc in character_careers:
            if cc.character_id not in char_career_relations:
                char_career_relations[cc.character_id] = {'main': [], 'sub': []}
            
            # Lưu đối tượng CharacterCareer đầy đủ
            if cc.career_type == 'main':
                char_career_relations[cc.character_id]['main'].append(cc)
            else:
                char_career_relations[cc.character_id]['sub'].append(cc)
        
        # Xây dựng chuỗi thông tin nhân vật
        characters_info_parts = []
        for char_id in character_ids[:10]:  # Giới hạn tối đa 10 nhân vật
            c = full_characters.get(char_id)
            if not c:
                continue
            
            # === Thông tin cơ bản nhân vật ===
            entity_type = 'tổ chức' if c.is_organization else 'nhân vật'
            role_type_map = {
                'protagonist': 'nhân vật chính',
                'antagonist': 'phản diện',
                'supporting': 'vai phụ'
            }
            role_type = role_type_map.get(c.role_type, c.role_type or 'vai phụ')
            
            # Xây dựng dòng thông tin cơ bản
            info_lines = [f"【{c.name}】({entity_type}, {role_type})"]
            
            # === Thuộc tính chi tiết nhân vật ===
            if c.age:
                info_lines.append(f"  Tuổi: {c.age}")
            if c.gender:
                info_lines.append(f"  Giới tính: {c.gender}")
            if c.appearance:
                appearance_preview = c.appearance[:100] if len(c.appearance) > 100 else c.appearance
                info_lines.append(f"  Ngoại hình: {appearance_preview}")
            if c.personality:
                personality_preview = c.personality[:100] if len(c.personality) > 100 else c.personality
                info_lines.append(f"  Tính cách: {personality_preview}")
            if c.background:
                background_preview = c.background[:150] if len(c.background) > 150 else c.background
                info_lines.append(f"  Bối cảnh: {background_preview}")
            
            # === Thông tin nghề (dữ liệu đầy đủ) ===
            if char_id in char_career_relations:
                career_relations = char_career_relations[char_id]
                
                # Nghề chính
                if career_relations['main']:
                    for cc in career_relations['main']:
                        career = careers_map.get(cc.career_id)
                        if career:
                            # Phân tích thông tin giai đoạn đầy đủ của nghề
                            try:
                                stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                                current_stage_info = None
                                for stage in stages:
                                    if stage.get('level') == cc.current_stage:
                                        current_stage_info = stage
                                        break
                                
                                stage_name = current_stage_info.get('name', f'giai đoạn {cc.current_stage}') if current_stage_info else f'giai đoạn {cc.current_stage}'
                            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                                logger.warning(f"Phân tích thông tin giai đoạn nghề thất bại: {e}")
                                stage_name = f'giai đoạn {cc.current_stage}'
                                stage_desc = ''
                            
                            # Xây dựng thông tin nghề chính (chỉ hiển thị tham chiếu, chi tiết ở phần "nghề chương này" bên dưới)
                            info_lines.append(f"  Nghề chính: {career.name} ({cc.current_stage}/{career.max_stage} giai đoạn - {stage_name})")
                
                # Nghề phụ
                if career_relations['sub']:
                    info_lines.append(f"  Nghề phụ:")
                    for cc in career_relations['sub']:
                        career = careers_map.get(cc.career_id)
                        if career:
                            # Phân tích thông tin giai đoạn nghề phụ
                            try:
                                stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                                current_stage_info = None
                                for stage in stages:
                                    if stage.get('level') == cc.current_stage:
                                        current_stage_info = stage
                                        break
                                stage_name = current_stage_info.get('name', f'giai đoạn {cc.current_stage}') if current_stage_info else f'giai đoạn {cc.current_stage}'
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                stage_name = f'giai đoạn {cc.current_stage}'
                            
                            # Nghề phụ cũng chỉ hiển thị tham chiếu
                            info_lines.append(f"    - {career.name} ({cc.current_stage}/{career.max_stage} giai đoạn - {stage_name})")
            
            # === Thông tin quan hệ nhân vật ===
            if not c.is_organization:
                from sqlalchemy import or_
                rels_result = await db.execute(
                    select(CharacterRelationship).where(
                        CharacterRelationship.project_id == project_id,
                        or_(
                            CharacterRelationship.character_from_id == c.id,
                            CharacterRelationship.character_to_id == c.id
                        )
                    )
                )
                rels = rels_result.scalars().all()
                if rels:
                    related_ids = set()
                    for r in rels:
                        related_ids.add(r.character_from_id)
                        related_ids.add(r.character_to_id)
                    related_ids.discard(c.id)
                    if related_ids:
                        names_result = await db.execute(
                            select(Character.id, Character.name).where(Character.id.in_(related_ids))
                        )
                        name_map = {row.id: row.name for row in names_result}
                        rel_parts = []
                        for r in rels:
                            if r.character_from_id == c.id:
                                target_name = name_map.get(r.character_to_id, "không rõ")
                            else:
                                target_name = name_map.get(r.character_from_id, "không rõ")
                            rel_name = r.relationship_name or "liên quan"
                            rel_parts.append(f"Với {target_name}: {rel_name}")
                        info_lines.append(f"  Mạng quan hệ: {';'.join(rel_parts)}")
            
            # === Thông tin đặc thù tổ chức ===
            if c.is_organization:
                if c.organization_type:
                    info_lines.append(f"  Loại tổ chức: {c.organization_type}")
                if c.organization_purpose:
                    info_lines.append(f"  Mục đích tổ chức: {c.organization_purpose[:100]}")
                # Truy vấn động thành viên tổ chức từ bảng OrganizationMember
                org_result = await db.execute(
                    select(Organization).where(Organization.character_id == c.id)
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
                        info_lines.append(f"  Thành viên tổ chức: {'、'.join(member_parts)[:100]}")
            
            # Kết hợp thông tin đầy đủ
            full_info = "\n".join(info_lines)
            characters_info_parts.append(full_info)
        
        characters_result = "\n\n".join(characters_info_parts)
        logger.info(f"  ✅ Đã xây dựng thông tin đầy đủ của {len(characters_info_parts)} nhân vật, tổng độ dài: {len(characters_result)} ký tự")
        
        # === Xây dựng phần thông tin nghề ===
        careers_info_parts = []
        if careers_map:
            for career_id, career in careers_map.items():
                career_lines = [f"{career.name} (nghề {career.type})"]
                
                # Mô tả nghề
                if career.description:
                    career_lines.append(f"  Mô tả: {career.description}")
                
                # Phân loại nghề
                if career.category:
                    career_lines.append(f"  Phân loại: {career.category}")
                
                # Hệ thống giai đoạn
                try:
                    stages = json.loads(career.stages) if isinstance(career.stages, str) else career.stages
                    if stages:
                        career_lines.append(f"  Hệ thống giai đoạn: (tổng {career.max_stage} giai đoạn)")
                        for stage in stages:  # Hiển thị mọi giai đoạn
                            level = stage.get('level', '?')
                            name = stage.get('name', 'chưa đặt tên')
                            desc = stage.get('description', '')
                            career_lines.append(f"    Giai đoạn {level}-{name}: {desc}")
                except (json.JSONDecodeError, AttributeError, TypeError) as e:
                    logger.warning(f"Phân tích giai đoạn nghề thất bại: {e}")
                    career_lines.append(f"  Hệ thống giai đoạn: tổng {career.max_stage} giai đoạn")
                
                # Yêu cầu nghề
                if career.requirements:
                    career_lines.append(f"  Yêu cầu nghề: {career.requirements}")
                
                # Năng lực đặc biệt
                if career.special_abilities:
                    career_lines.append(f"  Năng lực đặc biệt: {career.special_abilities}")
                
                # Quy tắc thế giới quan
                if career.worldview_rules:
                    career_lines.append(f"  Quy tắc thế giới quan: {career.worldview_rules}")
                
                # Cộng thuộc tính
                if career.attribute_bonuses:
                    try:
                        bonuses = json.loads(career.attribute_bonuses) if isinstance(career.attribute_bonuses, str) else career.attribute_bonuses
                        if bonuses:
                            bonus_str = ", ".join([f"{k}:{v}" for k, v in bonuses.items()])
                            career_lines.append(f"  Cộng thuộc tính: {bonus_str}")
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        pass
                
                careers_info_parts.append("\n".join(career_lines))
        
        careers_result = None
        if careers_info_parts:  # Có dữ liệu nghề thì trả về
            careers_result = "\n\n".join(careers_info_parts)
            logger.info(f"  ✅ Đã xây dựng thông tin đầy đủ của {len(careers_map)} nghề, tổng độ dài: {len(careers_result)} ký tự")
        else:
            logger.info(f"  ⚠️ Chương này không có nghề liên quan")
        
        return characters_result, careers_result
    
    async def _get_foreshadow_reminders(
        self,
        project_id: str,
        chapter_number: int,
        db: AsyncSession
    ) -> Optional[str]:
        """
        Lấy thông tin nhắc phục bút (bản tăng cường)
        
        Chiến lược:
        1. Phục bút phải thu hồi trong chương này (target_resolve_chapter_number == chapter_number)
        2. Phục bút quá hạn chưa thu hồi (target_resolve_chapter_number < chapter_number)
        3. Phục bút sắp đến hạn (target_resolve_chapter_number trong 3 chương tới)
        """
        if not self.foreshadow_service:
            return None
        
        try:
            lines = []
            
            # 1. Phục bút phải thu hồi trong chương này
            must_resolve = await self.foreshadow_service.get_must_resolve_foreshadows(
                db=db,
                project_id=project_id,
                chapter_number=chapter_number
            )
            
            if must_resolve:
                lines.append("【🎯 Phục bút phải thu hồi trong chương này】")
                for f in must_resolve:
                    lines.append(f"- {f.title}")
                    lines.append(f"  Chương gieo: chương {f.plant_chapter_number}")
                    lines.append(f"  Nội dung phục bút: {f.content[:100]}{'...' if len(f.content) > 100 else ''}")
                    if f.resolution_notes:
                        lines.append(f"  Gợi ý thu hồi: {f.resolution_notes}")
                    lines.append("")
            
            # 2. Phục bút quá hạn chưa thu hồi
            overdue = await self.foreshadow_service.get_overdue_foreshadows(
                db=db,
                project_id=project_id,
                current_chapter=chapter_number
            )
            
            if overdue:
                lines.append("【⚠️ Phục bút quá hạn thu hồi】")
                for f in overdue[:3]:  # Hiển thị tối đa 3
                    overdue_chapters = chapter_number - (f.target_resolve_chapter_number or 0)
                    lines.append(f"- {f.title} [đã quá hạn {overdue_chapters} chương]")
                    lines.append(f"  Chương gieo: chương {f.plant_chapter_number}, kế hoạch gốc thu hồi ở chương {f.target_resolve_chapter_number}")
                    lines.append(f"  Nội dung phục bút: {f.content[:80]}...")
                    lines.append("")
            
            # 3. Phục bút sắp đến hạn (trong 3 chương tới)
            upcoming = await self.foreshadow_service.get_pending_resolve_foreshadows(
                db=db,
                project_id=project_id,
                current_chapter=chapter_number,
                lookahead=3
            )
            
            # Lọc: chỉ giữ chương tương lai, loại chương này và quá hạn
            upcoming_filtered = [f for f in upcoming
                               if (f.target_resolve_chapter_number or 0) > chapter_number]
            
            if upcoming_filtered:
                lines.append("【📋 Phục bút sắp đến hạn (chỉ tham khảo)】")
                for f in upcoming_filtered[:3]:  # Hiển thị tối đa 3
                    remaining = (f.target_resolve_chapter_number or 0) - chapter_number
                    lines.append(f"- {f.title} (kế hoạch thu hồi ở chương {f.target_resolve_chapter_number}, còn {remaining} chương)")
                lines.append("")
            
            return "\n".join(lines) if lines else None
            
        except Exception as e:
            logger.error(f"❌ Lấy nhắc phục bút thất bại: {str(e)}")
            return None

