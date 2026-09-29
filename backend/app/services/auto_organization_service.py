"""Dịch vụ tổ chức tự động - sau khi sinh dàn ý thì kiểm tra và tự động bổ sung tổ chức còn thiếu"""
from typing import List, Dict, Any, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.character import Character
from app.models.relationship import Organization, OrganizationMember
from app.models.project import Project
from app.services.ai_service import AIService
from app.services.prompt_service import PromptService
from app.logger import get_logger

logger = get_logger(__name__)


class AutoOrganizationService:
    """Dịch vụ giới thiệu tổ chức tự động"""
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
    
    def _build_character_summary(self, characters: List[Character]) -> str:
        """Xây dựng thông tin tóm tắt nhân vật hiện có"""
        if not characters:
            return "Chưa có nhân vật nào"
        
        lines = []
        for char in characters:
            parts = [f"- {char.name}"]
            if char.role_type:
                role_map = {"protagonist": "Nhân vật chính", "supporting": "Nhân vật phụ", "antagonist": "Phản diện"}
                parts.append(f"({role_map.get(char.role_type, char.role_type)})")
            if char.personality:
                parts.append(f"Tính cách: {char.personality[:50]}")
            lines.append(" ".join(parts))
        
        return "\n".join(lines)
    
    def _build_organization_summary(self, organizations: List[Dict[str, Any]]) -> str:
        """Xây dựng thông tin tóm tắt tổ chức hiện có"""
        if not organizations:
            return "Chưa có tổ chức nào"
        
        lines = []
        for org in organizations:
            name = org.get("name", "Không rõ") if isinstance(org, dict) else getattr(org, "name", "Không rõ")
            lines.append(f"- {name}")
        
        return "\n".join(lines)
    
    async def _generate_organization_details(
        self,
        spec: Dict[str, Any],
        project: Project,
        existing_characters: List[Character],
        existing_organizations: List[Dict[str, Any]],
        db: AsyncSession,
        user_id: str,
        enable_mcp: bool
    ) -> Dict[str, Any]:
        """Sinh thông tin chi tiết tổ chức"""
        
        # Xây dựng prompt sinh tổ chức
        template = await PromptService.get_template(
            "AUTO_ORGANIZATION_GENERATION",
            user_id,
            db
        )
        
        existing_orgs_summary = self._build_organization_summary(existing_organizations)
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
            existing_organizations=existing_orgs_summary,
            existing_characters=existing_chars_summary,
            plot_context="Tổ chức mới được giới thiệu theo nhu cầu cốt truyện",
            organization_specification=json.dumps(spec, ensure_ascii=False, indent=2),
            mcp_references="" # Tạm thời không dùng tăng cường MCP
        )
        
        # Gọi AI sinh (dùng phương thức gọi JSON thống nhất)
        try:
            # Dùng phương thức gọi JSON thống nhất (hỗ trợ tự động tải tool MCP)
            organization_data = await self.ai_service.call_with_json_retry(
                prompt=prompt,
                max_retries=3,
                auto_mcp=enable_mcp,
            )
            
            org_name = organization_data.get('name', 'Không rõ')
            logger.info(f" ✅ Sinh chi tiết tổ chức thành công: {org_name}")
            logger.debug(f" Field dữ liệu tổ chức: {list(organization_data.keys())}")
            
            # Đảm bảo field then chốt tồn tại
            if 'name' not in organization_data or not organization_data['name']:
                logger.warning(f" ⚠️ Dữ liệu tổ chức do AI trả về thiếu field name, dùng thông tin trong spec")
                organization_data['name'] = spec.get('name', f"Tổ chức mới{spec.get('organization_description', '')[:10]}")
            
            return organization_data
            
        except Exception as e:
            logger.error(f" ❌ Sinh chi tiết tổ chức thất bại: {e}")
            raise
    
    async def _create_organization_record(
        self,
        project_id: str,
        organization_data: Dict[str, Any],
        db: AsyncSession
    ) -> tuple:
        """Tạo bản ghi database tổ chức (gồm Character và Organization)"""
        
        # Tạo bản ghi Character trước (is_organization=True)
        character = Character(
            project_id=project_id,
            name=organization_data.get("name", "Tổ chức chưa đặt tên"),
            is_organization=True,
            role_type=organization_data.get("role_type", "supporting"),
            personality=organization_data.get("personality", ""), # Đặc tính tổ chức
            background=organization_data.get("background", ""), # Bối cảnh tổ chức
            appearance=organization_data.get("appearance", ""), # Biểu hiện bên ngoài
            organization_type=organization_data.get("organization_type"),
            organization_purpose=organization_data.get("organization_purpose"),
            traits=json.dumps(organization_data.get("traits", []), ensure_ascii=False) if organization_data.get("traits") else None
        )
        
        db.add(character)
        await db.flush()
        
        # Sau đó tạo bản ghi Organization
        organization = Organization(
            character_id=character.id,
            project_id=project_id,
            power_level=organization_data.get("power_level", 50),
            member_count=0,
            location=organization_data.get("location"),
            motto=organization_data.get("motto"),
            color=organization_data.get("color")
        )
        
        db.add(organization)
        await db.flush()
        
        logger.info(f" ✅ Tạo bản ghi tổ chức: {character.name}, Organization ID: {organization.id}")
        
        return character, organization
    
    async def _create_member_relationships(
        self,
        organization: Organization,
        member_specs: List[Dict[str, Any]],
        existing_characters: List[Character],
        project_id: str,
        db: AsyncSession
    ) -> List[OrganizationMember]:
        """Tạo quan hệ thành viên tổ chức"""
        
        if not member_specs:
            return []
        
        members = []
        
        for member_spec in member_specs:
            try:
                character_name = member_spec.get("character_name")
                if not character_name:
                    continue
                
                # Tìm nhân vật mục tiêu
                target_char = next(
                    (c for c in existing_characters if c.name == character_name and not c.is_organization),
                    None
                )
                
                if not target_char:
                    logger.warning(f" ⚠️ Nhân vật mục tiêu không tồn tại: {character_name}")
                    continue
                
                # Kiểm tra quan hệ thành viên đã tồn tại chưa
                existing_member = await db.execute(
                    select(OrganizationMember).where(
                        OrganizationMember.organization_id == organization.id,
                        OrganizationMember.character_id == target_char.id
                    )
                )
                if existing_member.scalar_one_or_none():
                    logger.debug(f" ℹ️ Quan hệ thành viên đã tồn tại: {character_name} -> {organization.id}")
                    continue
                
                # Tạo quan hệ thành viên
                member = OrganizationMember(
                    organization_id=organization.id,
                    character_id=target_char.id,
                    position=member_spec.get("position", "Thành viên"),
                    rank=member_spec.get("rank", 0),
                    loyalty=member_spec.get("loyalty", 50),
                    status=member_spec.get("status", "active"),
                    joined_at=member_spec.get("joined_at"),
                    source="auto" # Đánh dấu là tự động sinh
                )
                
                db.add(member)
                members.append(member)
                
                logger.info(
                    f" ✅ Tạo quan hệ thành viên: {character_name} -> {organization.id} "
                    f"({member_spec.get('position', 'Thành viên')})"
                )
                
            except Exception as e:
                logger.warning(f" ❌ Tạo quan hệ thành viên thất bại: {e}")
                continue
        
        # Cập nhật số lượng thành viên tổ chức
        if members:
            organization.member_count = (organization.member_count or 0) + len(members)
        
        return members


    async def check_and_create_missing_organizations(
        self,
        project_id: str,
        outline_data_list: list,
        db: AsyncSession,
        user_id: str = None,
        enable_mcp: bool = True,
        progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Kiểm tra project có tồn tại tổ chức tương ứng không dựa trên field characters trong structure của dàn ý (type=organization),
        nếu không tồn tại thì tự động sinh thông tin tổ chức dựa trên tóm tắt dàn ý.
        
        Args:
            project_id: ID project
            outline_data_list: danh sách dữ liệu dàn ý (mỗi phần tử gồm các field characters, summary, v.v.)
            db: session database
            user_id: ID người dùng
            enable_mcp: có bật MCP không
            progress_callback: callback tiến trình
            
        Returns:
            {
                "created_organizations": [danh sách object tổ chức],
                "missing_names": [danh sách tên tổ chức còn thiếu],
                "created_count": số lượng tổ chức đã tạo
            }
        """
        logger.info(f"🔍 【Kiểm tra tổ chức】Bắt đầu kiểm tra sự tồn tại của các tổ chức được nhắc trong dàn ý...")
        
        # 1. Trích xuất tên tổ chức từ structure của mọi dàn ý (tương thích định dạng cũ/mới)
        all_organization_names = set()
        organization_context = {} # Ghi lại context tổ chức xuất hiện (tóm tắt dàn ý)
        
        for outline_item in outline_data_list:
            if isinstance(outline_item, dict):
                characters = outline_item.get("characters", [])
                summary = outline_item.get("summary", "") or outline_item.get("content", "")
                title = outline_item.get("title", "")
                
                if isinstance(characters, list):
                    for char_entry in characters:
                        # Định dạng mới: {"name": "xxx", "type": "character"/"organization"}
                        if isinstance(char_entry, dict):
                            entry_type = char_entry.get("type", "character")
                            entry_name = char_entry.get("name", "")
                            # Chỉ xử lý loại organization
                            if entry_type != "organization" or not entry_name.strip():
                                continue
                            name = entry_name.strip()
                            all_organization_names.add(name)
                            if name not in organization_context:
                                organization_context[name] = []
                            organization_context[name].append(f"《{title}》: {summary[:200]}")
                        # Định dạng cũ: chuỗi thuần, không phân biệt được loại, bỏ qua
        
        if not all_organization_names:
            logger.info("🔍 【Kiểm tra tổ chức】Dàn ý không nhắc tới tổ chức nào, bỏ qua kiểm tra")
            return {
                "created_organizations": [],
                "missing_names": [],
                "created_count": 0
            }
        
        logger.info(f"🔍 【Kiểm tra tổ chức】Các tổ chức được nhắc trong dàn ý: {', '.join(all_organization_names)}")
        
        # 2. Lấy tổ chức hiện có của project (qua field is_organization của bảng Character)
        existing_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.is_organization == True
            )
        )
        existing_org_characters = existing_result.scalars().all()
        existing_org_names = {char.name for char in existing_org_characters}
        
        # 3. Tìm các tổ chức còn thiếu
        missing_names = all_organization_names - existing_org_names
        
        if not missing_names:
            logger.info("✅ 【Kiểm tra tổ chức】Mọi tổ chức đã tồn tại, không cần tạo")
            return {
                "created_organizations": [],
                "missing_names": [],
                "created_count": 0
            }
        
        logger.info(f"⚠️ 【Kiểm tra tổ chức】Phát hiện {len(missing_names)} tổ chức còn thiếu: {', '.join(missing_names)}")
        
        # 4. Lấy thông tin project
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            logger.error("❌ 【Kiểm tra tổ chức】Project không tồn tại")
            return {
                "created_organizations": [],
                "missing_names": list(missing_names),
                "created_count": 0
            }
        
        # 5. Lấy thông tin nhân vật và tổ chức hiện có
        all_chars_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        existing_characters = list(all_chars_result.scalars().all())
        
        existing_organizations = []
        for char in existing_org_characters:
            org_result = await db.execute(
                select(Organization).where(Organization.character_id == char.id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                existing_organizations.append({
                    "name": char.name,
                    "organization_type": char.organization_type,
                    "organization_purpose": char.organization_purpose,
                    "power_level": org.power_level,
                    "location": org.location,
                    "motto": org.motto
                })
        
        # 6. Sinh và tạo thông tin tổ chức cho từng tổ chức còn thiếu
        created_organizations = []
        
        for idx, org_name in enumerate(missing_names):
            try:
                if progress_callback:
                    await progress_callback(
                        f"🏛️ [{idx+1}/{len(missing_names)}] Tự động tạo tổ chức: {org_name}..."
                    )
                
                # Xây dựng spec tổ chức (dựa trên context dàn ý)
                context_summaries = organization_context.get(org_name, [])
                context_text = "\n".join(context_summaries[:3])
                
                spec = {
                    "name": org_name,
                    "organization_description": f"Tổ chức/thế lực xuất hiện trong dàn ý, cảnh xuất hiện:\\n{context_text}",
                    "organization_type": "Không rõ",
                    "importance": "medium"
                }
                
                logger.info(f" 🤖 [{idx+1}/{len(missing_names)}] Sinh chi tiết tổ chức: {org_name}")
                
                # Sinh thông tin chi tiết tổ chức
                organization_data = await self._generate_organization_details(
                    spec=spec,
                    project=project,
                    existing_characters=existing_characters,
                    existing_organizations=existing_organizations,
                    db=db,
                    user_id=user_id,
                    enable_mcp=enable_mcp
                )
                
                # Đảm bảo dùng tên tổ chức trong dàn ý
                organization_data['name'] = org_name
                
                if progress_callback:
                    await progress_callback(
                        f"💾 [{idx+1}/{len(missing_names)}] Lưu tổ chức: {org_name}..."
                    )
                
                # Tạo bản ghi tổ chức
                org_character, organization = await self._create_organization_record(
                    project_id=project_id,
                    organization_data=organization_data,
                    db=db
                )
                
                created_organizations.append(org_character)
                existing_characters.append(org_character)
                existing_organizations.append({
                    "name": org_character.name,
                    "organization_type": org_character.organization_type,
                    "organization_purpose": org_character.organization_purpose,
                    "power_level": organization.power_level,
                    "location": organization.location,
                    "motto": organization.motto
                })
                logger.info(f" ✅ [{idx+1}/{len(missing_names)}] Tạo tổ chức thành công: {org_character.name}")
                
                # Thiết lập quan hệ thành viên
                members_data = organization_data.get("initial_members", [])
                if members_data:
                    if progress_callback:
                        await progress_callback(
                            f"🔗 [{idx+1}/{len(missing_names)}] Thiết lập {len(members_data)} quan hệ thành viên: {org_name}..."
                        )
                    
                    await self._create_member_relationships(
                        organization=organization,
                        member_specs=members_data,
                        existing_characters=existing_characters,
                        project_id=project_id,
                        db=db
                    )
                
                if progress_callback:
                    await progress_callback(
                        f"✅ [{idx+1}/{len(missing_names)}] Tạo tổ chức hoàn tất: {org_name}"
                    )
                
            except Exception as e:
                logger.error(f" ❌ Tạo tổ chức {org_name} thất bại: {e}", exc_info=True)
                if progress_callback:
                    await progress_callback(
                        f"⚠️ [{idx+1}/{len(missing_names)}] Tổ chức {org_name} tạo thất bại"
                    )
                continue
        
        # 7. flush vào database (để phía gọi commit)
        if created_organizations:
            await db.flush()
        
        logger.info(f"🎉 【Kiểm tra tổ chức】Hoàn tất: phát hiện {len(missing_names)} tổ chức còn thiếu, tạo thành công {len(created_organizations)} tổ chức")
        
        return {
            "created_organizations": created_organizations,
            "missing_names": list(missing_names),
            "created_count": len(created_organizations)
        }


def get_auto_organization_service(ai_service: AIService) -> AutoOrganizationService:
    """Lấy instance dịch vụ tổ chức tự động. AIService gắn với cấu hình người dùng hiện tại, không thể tái dùng toàn cục."""
    return AutoOrganizationService(ai_service)
