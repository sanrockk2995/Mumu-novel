"""Dịch vụ nhân vật tự động - kiểm tra sau khi tạo dàn ý và tự động bổ sung nhân vật còn thiếu"""
from typing import List, Dict, Any, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.character import Character
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember, RelationshipType
from app.models.project import Project
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService
from app.logger import get_logger

logger = get_logger(__name__)


class AutoCharacterService:
    """Dịch vụ đưa nhân vật tự động vào"""
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
    
    def _build_character_summary(self, characters: List[Character]) -> str:
        """Xây dựng thông tin tóm tắt nhân vật hiện có"""
        if not characters:
            return "Tạm thời chưa có nhân vật nào"
        
        lines = []
        for char in characters:
            parts = [f"- {char.name}"]
            if char.role_type:
                role_map = {"protagonist": "nhân vật chính", "supporting": "nhân vật phụ", "antagonist": "phản diện"}
                parts.append(f"({role_map.get(char.role_type, char.role_type)})")
            if char.personality:
                parts.append(f"tính cách: {char.personality[:50]}")
            if char.background:
                parts.append(f"bối cảnh: {char.background[:50]}")
            lines.append(" ".join(parts))
        
        return "\n".join(lines)
    
    async def _generate_character_details(
        self,
        spec: Dict[str, Any],
        project: Project,
        existing_characters: List[Character],
        db: AsyncSession,
        user_id: str,
        enable_mcp: bool
    ) -> Dict[str, Any]:
        """Tạo thông tin chi tiết nhân vật"""
        
        # 🎯 Lấy danh sách nghề nghiệp của dự án
        from app.models.career import Career
        careers_result = await db.execute(
            select(Career)
            .where(Career.project_id == project.id)
            .order_by(Career.type, Career.name)
        )
        careers = careers_result.scalars().all()
        
        # Xây dựng tóm tắt thông tin nghề nghiệp (gồm thông tin giai đoạn tối đa)
        careers_info = ""
        if careers:
            main_careers = [c for c in careers if c.type == 'main']
            sub_careers = [c for c in careers if c.type == 'sub']
            
            if main_careers:
                careers_info += "\n\nDanh sách nghề chính khả dụng (vui lòng điền tên nghề và giai đoạn trong career_info):\n"
                for career in main_careers:
                    careers_info += f"- tên: {career.name}, Giai đoạn tối đa: {career.max_stage}cấp"
                    if career.description:
                        careers_info += f", mô tả: {career.description[:50]}"
                    careers_info += "\n"
            
            if sub_careers:
                careers_info += "\nDanh sách nghề phụ khả dụng (vui lòng điền tên nghề và giai đoạn trong career_info):\n"
                for career in sub_careers[:5]:
                    careers_info += f"- tên: {career.name}, Giai đoạn tối đa: {career.max_stage}cấp"
                    if career.description:
                        careers_info += f", mô tả: {career.description[:50]}"
                    careers_info += "\n"
            
            careers_info += "\n⚠️ Nhắc nhở quan trọng: khi tạo nhân vật, giai đoạn nghề nghiệp không được vượt quá giai đoạn tối đa của nghề đó!\n"
        
        # Xây dựng prompt tạo nhân vật
        template = await PromptService.get_template(
            "AUTO_CHARACTER_GENERATION",
            user_id,
            db
        )
        
        existing_chars_summary = self._build_character_summary(existing_characters)
        
        prompt = PromptService.format_prompt(
            template,
            title=project.title,
            genre=project.genre or "Chưa thiết lập",
            theme=project.theme or "Chưa thiết lập",
            time_period=project.world_time_period or "Chưa thiết lập",
            location=project.world_location or "Chưa thiết lập",
            atmosphere=project.world_atmosphere or "Chưa thiết lập",
            rules=project.world_rules or "Chưa thiết lập",
            existing_characters=existing_chars_summary + careers_info,
            plot_context="Nhân vật mới được đưa vào theo nhu cầu cốt truyện",
            character_specification=json.dumps(spec, ensure_ascii=False, indent=2),
            mcp_references=""  # MCPCông cụ đượcAIdịch vụ tự động tải
        )
        
        logger.info(f"🔧 Tạo chi tiết nhân vật: enable_mcp={enable_mcp}")
        
        # gọiAItạo
        try:
            character_data = await self.ai_service.call_with_json_retry(
                prompt=prompt,
                max_retries=2,  # Giảm số lần thử lại để tăng tốc
                auto_mcp=enable_mcp,
            )
            
            char_name = character_data.get('name', 'không rõ')
            logger.info(f"    ✅ Tạo chi tiết nhân vật thành công: {char_name}")
            logger.debug(f"       Trường dữ liệu nhân vật: {list(character_data.keys())}")
            
            # Đảm bảo các trường then chốt tồn tại
            if 'name' not in character_data or not character_data['name']:
                logger.warning(f"    ⚠️ AIDữ liệu nhân vật trả về thiếunametrường, dùng thông tin trong đặc tả")
                character_data['name'] = spec.get('name', f"Nhân vật mới{spec.get('role_description', '')[:10]}")
            
            return character_data
            
        except Exception as e:
            logger.error(f"    ❌ Tạo chi tiết nhân vật thất bại: {e}")
            raise
    
    async def _create_character_record(
        self,
        project_id: str,
        character_data: Dict[str, Any],
        db: AsyncSession
    ) -> Character:
        """Tạo bản ghi nhân vật trong cơ sở dữ liệu"""
        
        is_organization = character_data.get("is_organization", False)
        
        # Trích xuất thông tin nghề nghiệp (hỗ trợ khớp theo tên)
        career_info = character_data.get("career_info", {})
        raw_main_career_name = career_info.get("main_career_name") if career_info else None
        main_career_stage = career_info.get("main_career_stage", 1) if career_info else None
        raw_sub_careers_data = career_info.get("sub_careers", []) if career_info else []
        
        # 🔧 Khớp nghề nghiệp trong cơ sở dữ liệu theo tên nghềID
        from app.models.career import Career, CharacterCareer
        main_career_id = None
        sub_careers_data = []
        
        # Khớp tên nghề chính
        if raw_main_career_name and not is_organization:
            career_check = await db.execute(
                select(Career).where(
                    Career.name == raw_main_career_name,
                    Career.project_id == project_id,
                    Career.type == 'main'
                )
            )
            matched_career = career_check.scalar_one_or_none()
            if matched_career:
                main_career_id = matched_career.id
                # ✅ Xác thực giai đoạn không vượt quá giai đoạn tối đa
                if main_career_stage and main_career_stage > matched_career.max_stage:
                    logger.warning(f"    ⚠️ AIGiai đoạn nghề chính trả về({main_career_stage})Vượt quá giai đoạn tối đa({matched_career.max_stage}), tự động sửa thành giai đoạn tối đa")
                    main_career_stage = matched_career.max_stage
                logger.info(f"    ✅ Khớp tên nghề chính thành công: {raw_main_career_name} -> ID: {main_career_id}, giai đoạn: {main_career_stage}/{matched_career.max_stage}")
            else:
                logger.warning(f"    ⚠️ AIKhông tìm thấy tên nghề chính trả về: {raw_main_career_name}")
        
        # Khớp tên nghề phụ
        if raw_sub_careers_data and not is_organization and isinstance(raw_sub_careers_data, list):
            for sub_data in raw_sub_careers_data[:2]:
                if isinstance(sub_data, dict):
                    career_name = sub_data.get('career_name')
                    if career_name:
                        career_check = await db.execute(
                            select(Career).where(
                                Career.name == career_name,
                                Career.project_id == project_id,
                                Career.type == 'sub'
                            )
                        )
                        matched_career = career_check.scalar_one_or_none()
                        if matched_career:
                            sub_stage = sub_data.get('stage', 1)
                            # ✅ Xác thực giai đoạn không vượt quá giai đoạn tối đa
                            if sub_stage > matched_career.max_stage:
                                logger.warning(f"    ⚠️ AIGiai đoạn nghề phụ trả về({sub_stage})Vượt quá giai đoạn tối đa({matched_career.max_stage}), tự động sửa thành giai đoạn tối đa")
                                sub_stage = matched_career.max_stage
                            
                            sub_careers_data.append({
                                'career_id': matched_career.id,
                                'stage': sub_stage
                            })
                            logger.info(f"    ✅ Khớp tên nghề phụ thành công: {career_name} -> ID: {matched_career.id}, giai đoạn: {sub_stage}/{matched_career.max_stage}")
                        else:
                            logger.warning(f"    ⚠️ AIKhông tìm thấy tên nghề phụ trả về: {career_name}")
        
        # Tạo nhân vật (không ghi nữa relationships trường văn bản, quan hệ do thống nhất bởi character_relationships bảng quản lý)
        character = Character(
            project_id=project_id,
            name=character_data.get("name", "Nhân vật chưa đặt tên"),
            age=str(character_data.get("age", "")),
            gender=character_data.get("gender"),
            is_organization=is_organization,
            role_type=character_data.get("role_type", "supporting"),
            personality=character_data.get("personality", ""),
            background=character_data.get("background", ""),
            appearance=character_data.get("appearance", ""),
            organization_type=character_data.get("organization_type") if is_organization else None,
            organization_purpose=character_data.get("organization_purpose") if is_organization else None,
            traits=json.dumps(character_data.get("traits", []), ensure_ascii=False) if character_data.get("traits") else None,
            main_career_id=main_career_id,
            main_career_stage=main_career_stage if main_career_id else None,
            sub_careers=json.dumps(sub_careers_data, ensure_ascii=False) if sub_careers_data else None
        )
        
        db.add(character)
        await db.flush()
        
        # Xử lý liên kết nghề chính
        if main_career_id and not is_organization:
            char_career = CharacterCareer(
                character_id=character.id,
                career_id=main_career_id,
                career_type='main',
                current_stage=main_career_stage,
                stage_progress=0
            )
            db.add(char_career)
            logger.info(f"    ✅ Tạo liên kết nghề chính: {character.name} -> {raw_main_career_name}")
        
        # Xử lý liên kết nghề phụ
        if sub_careers_data and not is_organization:
            for sub_data in sub_careers_data:
                char_career = CharacterCareer(
                    character_id=character.id,
                    career_id=sub_data['career_id'],
                    career_type='sub',
                    current_stage=sub_data['stage'],
                    stage_progress=0
                )
                db.add(char_career)
            logger.info(f"    ✅ Tạo liên kết nghề phụ: {character.name}, số lượng: {len(sub_careers_data)}")
        
        # Nếu là tổ chức, tạoOrganizationbản ghi
        if is_organization:
            org = Organization(
                character_id=character.id,
                project_id=project_id,
                member_count=0,
                power_level=character_data.get("power_level", 50),
                location=character_data.get("location"),
                motto=character_data.get("motto"),
                color=character_data.get("color")
            )
            db.add(org)
            await db.flush()
            logger.info(f"    ✅ Tạo chi tiết tổ chức: {character.name}")
        
        return character
    
    async def _create_relationships(
        self,
        new_character: Character,
        relationship_specs: List[Dict[str, Any]],
        existing_characters: List[Character],
        project_id: str,
        db: AsyncSession
    ) -> List[CharacterRelationship]:
        """Tạo quan hệ nhân vật"""
        
        if not relationship_specs:
            return []
        
        relationships = []
        
        for rel_spec in relationship_specs:
            try:
                target_name = rel_spec.get("target_character_name")
                if not target_name:
                    continue
                
                # Tìm nhân vật mục tiêu
                target_char = next(
                    (c for c in existing_characters if c.name == target_name),
                    None
                )
                
                if not target_char:
                    logger.warning(f"    ⚠️ Nhân vật mục tiêu không tồn tại: {target_name}")
                    continue
                
                # Kiểm tra quan hệ đã tồn tại hay chưa
                existing_rel = await db.execute(
                    select(CharacterRelationship).where(
                        CharacterRelationship.project_id == project_id,
                        CharacterRelationship.character_from_id == new_character.id,
                        CharacterRelationship.character_to_id == target_char.id
                    )
                )
                if existing_rel.scalar_one_or_none():
                    logger.debug(f"    ℹ️ Quan hệ đã tồn tại: {new_character.name} -> {target_name}")
                    continue
                
                # Tạo quan hệ
                relationship = CharacterRelationship(
                    project_id=project_id,
                    character_from_id=new_character.id,
                    character_to_id=target_char.id,
                    relationship_name=rel_spec.get("relationship_type", "Quan hệ không rõ"),
                    intimacy_level=rel_spec.get("intimacy_level", 50),
                    description=rel_spec.get("description", ""),
                    status=rel_spec.get("status", "active"),
                    source="auto"  # Đánh dấu là tự động tạo
                )
                
                # Thử khớp loại quan hệ định sẵn
                rel_type_name = rel_spec.get("relationship_type")
                if rel_type_name:
                    rel_type_result = await db.execute(
                        select(RelationshipType).where(
                            RelationshipType.name == rel_type_name
                        )
                    )
                    rel_type = rel_type_result.scalar_one_or_none()
                    if rel_type:
                        relationship.relationship_type_id = rel_type.id
                
                db.add(relationship)
                relationships.append(relationship)
                
                logger.info(
                    f"    ✅ Tạo quan hệ: {new_character.name} -> {target_name} "
                    f"({rel_spec.get('relationship_type', 'không rõ')})"
                )
                
            except Exception as e:
                logger.warning(f"    ❌ Tạo quan hệ thất bại: {e}")
                continue
        
        return relationships


    async def check_and_create_missing_characters(
        self,
        project_id: str,
        outline_data_list: list,
        db: AsyncSession,
        user_id: str = None,
        enable_mcp: bool = True,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Theo dàn ýstructuretrongcharacterskiểm tra dự án có nhân vật tương ứng không,
        nếu không có thì tự động tạo thông tin nhân vật theo tóm tắt dàn ý.
        
        Args:
            project_id: dự ánID
            outline_data_list: Danh sách dữ liệu dàn ý (mỗi phần tử chứa characters, summary và các trường tương tự)
            db: cơ sở dữ liệuphiên
            user_id: người dùngID
            enable_mcp: có hay khôngbậtMCP
            progress_callback: Callback tiến độ
            
        Returns:
            {
                "created_characters": [Danh sách đối tượng nhân vật],
                "missing_names": [Danh sách tên nhân vật còn thiếu],
                "created_count": Số lượng nhân vật đã tạo
            }
        """
        logger.info(f"🔍 [Kiểm tra nhân vật] Bắt đầu kiểm tra các nhân vật được nhắc trong dàn ý có tồn tại không...")
        
        # 1. Từstructuretrích xuất tên nhân vật (tương thích định dạng cũ/mới)
        all_character_names = set()
        character_context = {}  # Ghi nhận ngữ cảnh xuất hiện của nhân vật (tóm tắt dàn ý)
        
        for outline_item in outline_data_list:
            if isinstance(outline_item, dict):
                characters = outline_item.get("characters", [])
                summary = outline_item.get("summary", "") or outline_item.get("content", "")
                title = outline_item.get("title", "")
                
                if isinstance(characters, list):
                    for char_entry in characters:
                        # Định dạng mới:{"name": "xxx", "type": "character"/"organization"}
                        if isinstance(char_entry, dict):
                            entry_type = char_entry.get("type", "character")
                            entry_name = char_entry.get("name", "")
                            # Chỉ xử lý character loại, bỏ qua organization
                            if entry_type == "organization" or not entry_name.strip():
                                continue
                            name = entry_name.strip()
                        # Định dạng cũ: chuỗi thuần
                        elif isinstance(char_entry, str) and char_entry.strip():
                            name = char_entry.strip()
                        else:
                            continue
                        
                        all_character_names.add(name)
                        # Thu thập ngữ cảnh xuất hiện của nhân vật
                        if name not in character_context:
                            character_context[name] = []
                        character_context[name].append(f"«{title}»: {summary[:200]}")
        
        if not all_character_names:
            logger.info("🔍 [Kiểm tra nhân vật] Dàn ý không nhắc tới nhân vật nào, bỏ qua kiểm tra")
            return {
                "created_characters": [],
                "missing_names": [],
                "created_count": 0
            }
        
        logger.info(f"🔍 [Kiểm tra nhân vật] Các nhân vật được nhắc trong dàn ý: {', '.join(all_character_names)}")
        
        # 2. Lấy các nhân vật hiện có của dự án
        existing_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        existing_characters = existing_result.scalars().all()
        existing_names = {char.name for char in existing_characters}
        
        # 3. Tìm các nhân vật còn thiếu
        missing_names = all_character_names - existing_names
        
        if not missing_names:
            logger.info("✅ [Kiểm tra nhân vật] Mọi nhân vật đã tồn tại, không cần tạo")
            return {
                "created_characters": [],
                "missing_names": [],
                "created_count": 0
            }
        
        logger.info(f"⚠️ phát hiện {len(missing_names)} nhân vật còn thiếu: {', '.join(missing_names)}")
        
        # 4. Lấy thông tin dự án
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            logger.error("❌ [Kiểm tra nhân vật] Dự án không tồn tại")
            return {
                "created_characters": [],
                "missing_names": list(missing_names),
                "created_count": 0
            }
        
        # 5. Tạo thông tin nhân vật cho từng nhân vật còn thiếu
        created_characters = []
        
        for idx, char_name in enumerate(missing_names):
            try:
                if progress_callback:
                    await progress_callback(
                        f"🎭 [{idx+1}/{len(missing_names)}] Tự động tạo nhân vật:{char_name}..."
                    )
                
                # Xây dựng đặc tả nhân vật (dựa trên ngữ cảnh dàn ý)
                context_summaries = character_context.get(char_name, [])
                context_text = "\n".join(context_summaries[:3])  # Tối đa3ngữ cảnh
                
                spec = {
                    "name": char_name,
                    "role_description": f"Nhân vật xuất hiện trong dàn ý, cảnh xuất hiện:\n{context_text}",
                    "suggested_role_type": "supporting",
                    "importance": "medium"
                }
                
                logger.info(f"  🤖 [{idx+1}/{len(missing_names)}] Tạo chi tiết nhân vật: {char_name}")
                
                # Tạo thông tin chi tiết nhân vật
                character_data = await self._generate_character_details(
                    spec=spec,
                    project=project,
                    existing_characters=list(existing_characters) + created_characters,
                    db=db,
                    user_id=user_id,
                    enable_mcp=enable_mcp
                )
                
                # Đảm bảo dùng tên nhân vật trong dàn ý
                character_data['name'] = char_name
                
                if progress_callback:
                    await progress_callback(
                        f"💾 [{idx+1}/{len(missing_names)}] Lưu nhân vật:{char_name}..."
                    )
                
                # Tạo bản ghi nhân vật
                character = await self._create_character_record(
                    project_id=project_id,
                    character_data=character_data,
                    db=db
                )
                
                created_characters.append(character)
                logger.info(f"  ✅ [{idx+1}/{len(missing_names)}] Tạo nhân vật thành công: {character.name}")
                
                # Thiết lập quan hệ
                relationships_data = character_data.get("relationships") or character_data.get("relationships_array", [])
                if relationships_data:
                    if progress_callback:
                        await progress_callback(
                            f"🔗 [{idx+1}/{len(missing_names)}] thiết lập {len(relationships_data)} quan hệ:{char_name}..."
                        )
                    
                    await self._create_relationships(
                        new_character=character,
                        relationship_specs=relationships_data,
                        existing_characters=list(existing_characters) + created_characters,
                        project_id=project_id,
                        db=db
                    )
                
                if progress_callback:
                    await progress_callback(
                        f"✅ [{idx+1}/{len(missing_names)}] Tạo nhân vật hoàn tất:{char_name}"
                    )
                
            except Exception as e:
                logger.error(f"  ❌ Tạo nhân vật {char_name} thất bại: {e}", exc_info=True)
                if progress_callback:
                    await progress_callback(
                        f"⚠️ [{idx+1}/{len(missing_names)}] nhân vật {char_name} tạo thất bại"
                    )
                continue
        
        # 6. flush vào cơ sở dữ liệu (để bên gọi commit)
        if created_characters:
            await db.flush()
        
        logger.info(f"🎉 [Kiểm tra nhân vật] Hoàn tất: phát hiện {len(missing_names)} nhân vật còn thiếu, tạo thành công {len(created_characters)} ")
        
        return {
            "created_characters": created_characters,
            "missing_names": list(missing_names),
            "created_count": len(created_characters)
        }


def get_auto_character_service(ai_service: AIService) -> AutoCharacterService:
    """Lấy thể hiện dịch vụ nhân vật tự động.AIService Ràng buộc cấu hình người dùng hiện tại, không thể tái dùng toàn cục."""
    return AutoCharacterService(ai_service)
