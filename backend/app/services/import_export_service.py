"""Dịch vụ import/export"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.outline import Outline
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember
from app.models.writing_style import WritingStyle
from app.models.generation_history import GenerationHistory
from app.models.career import Career, CharacterCareer
from app.models.memory import StoryMemory, PlotAnalysis
from app.models.analysis_task import AnalysisTask
from app.models.project_default_style import ProjectDefaultStyle
from app.schemas.import_export import (
    ProjectExportData,
    ChapterExportData,
    CharacterExportData,
    OutlineExportData,
    RelationshipExportData,
    OrganizationExportData,
    OrganizationMemberExportData,
    WritingStyleExportData,
    GenerationHistoryExportData,
    CareerExportData,
    CharacterCareerExportData,
    StoryMemoryExportData,
    PlotAnalysisExportData,
    ProjectDefaultStyleExportData,
    ImportValidationResult,
    ImportResult
)
from app.logger import get_logger

logger = get_logger(__name__)


class ImportExportService:
    """Class dịch vụ import/export"""
    
    SUPPORTED_VERSIONS = ["1.0.0", "1.1.0"]  # Danh sách phiên bản được hỗ trợ
    CURRENT_VERSION = "1.1.0"  # Phiên bản export hiện tại
    
    @staticmethod
    async def export_project(
        project_id: str,
        db: AsyncSession,
        include_generation_history: bool = False,
        include_writing_styles: bool = True,
        include_careers: bool = True,
        include_memories: bool = False,
        include_plot_analysis: bool = False
    ) -> ProjectExportData:
        """
        Export dữ liệu đầy đủ của project
        
        Args:
            project_id: ID project
            db: phiên làm việc cơ sở dữ liệu
            include_generation_history: có gồm lịch sử sinh không
            include_writing_styles: có gồm phong cách viết không
            include_careers: có gồm hệ thống nghề không
            include_memories: có gồm ký ức truyện không
            include_plot_analysis: có gồm phân tích cốt truyện không
            
        Returns:
            ProjectExportData: dữ liệu project được export
        """
        logger.info(f"Bắt đầu export project: {project_id}")
        
        # Lấy thông tin cơ bản project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project không tồn tại: {project_id}")
        
        # Thông tin cơ bản project
        project_data = {
            "title": project.title,
            "description": project.description,
            "theme": project.theme,
            "genre": project.genre,
            "target_words": project.target_words,
            "current_words": project.current_words,
            "status": project.status,
            "world_time_period": project.world_time_period,
            "world_location": project.world_location,
            "world_atmosphere": project.world_atmosphere,
            "world_rules": project.world_rules,
            "chapter_count": project.chapter_count,
            "narrative_perspective": project.narrative_perspective,
            "character_count": project.character_count,
            "outline_mode": project.outline_mode,
            "user_id": project.user_id,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
        
        # Export chương
        chapters = await ImportExportService._export_chapters(project_id, db)
        logger.info(f"Số chương export: {len(chapters)}")
        
        # Export nhân vật
        characters = await ImportExportService._export_characters(project_id, db)
        logger.info(f"Số nhân vật export: {len(characters)}")
        
        # Export dàn ý
        outlines = await ImportExportService._export_outlines(project_id, db)
        logger.info(f"Số dàn ý export: {len(outlines)}")
        
        # Export quan hệ
        relationships = await ImportExportService._export_relationships(project_id, db)
        logger.info(f"Số quan hệ export: {len(relationships)}")
        
        # Export chi tiết tổ chức
        organizations = await ImportExportService._export_organizations(project_id, db)
        logger.info(f"Số tổ chức export: {len(organizations)}")
        
        # Export thành viên tổ chức
        org_members = await ImportExportService._export_organization_members(project_id, db)
        logger.info(f"Số thành viên tổ chức export: {len(org_members)}")
        
        # Export phong cách viết (tùy chọn)
        writing_styles = []
        if include_writing_styles:
            writing_styles = await ImportExportService._export_writing_styles(project_id, db)
            logger.info(f"Số phong cách viết export: {len(writing_styles)}")
        
        # Export lịch sử sinh (tùy chọn)
        generation_history = []
        if include_generation_history:
            generation_history = await ImportExportService._export_generation_history(project_id, db)
            logger.info(f"Số lịch sử sinh export: {len(generation_history)}")
        
        # Export hệ thống nghề (tùy chọn)
        careers = []
        character_careers = []
        if include_careers:
            careers = await ImportExportService._export_careers(project_id, db)
            logger.info(f"Số nghề export: {len(careers)}")
            character_careers = await ImportExportService._export_character_careers(project_id, db)
            logger.info(f"Số liên kết nghề-nhân vật export: {len(character_careers)}")
        
        # Export ký ức truyện (tùy chọn)
        story_memories = []
        if include_memories:
            story_memories = await ImportExportService._export_story_memories(project_id, db)
            logger.info(f"Số ký ức truyện export: {len(story_memories)}")
        
        # Export phân tích cốt truyện (tùy chọn)
        plot_analysis = []
        if include_plot_analysis:
            plot_analysis = await ImportExportService._export_plot_analysis(project_id, db)
            logger.info(f"Số phân tích cốt truyện export: {len(plot_analysis)}")
        
        # Export phong cách mặc định của project
        project_default_style = await ImportExportService._export_project_default_style(project_id, db)
        if project_default_style:
            logger.info(f"Export phong cách mặc định của project: {project_default_style.style_name}")
        
        export_data = ProjectExportData(
            version=ImportExportService.CURRENT_VERSION,
            export_time=datetime.utcnow().isoformat(),
            project=project_data,
            chapters=chapters,
            characters=characters,
            outlines=outlines,
            relationships=relationships,
            organizations=organizations,
            organization_members=org_members,
            writing_styles=writing_styles,
            generation_history=generation_history,
            careers=careers,
            character_careers=character_careers,
            story_memories=story_memories,
            plot_analysis=plot_analysis,
            project_default_style=project_default_style
        )
        
        logger.info(f"Export project hoàn tất: {project_id}")
        return export_data
    
    @staticmethod
    async def _export_chapters(project_id: str, db: AsyncSession) -> List[ChapterExportData]:
        """Export chương"""
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        
        # Xây dựng map từ ID dàn ý tới tiêu đề
        outline_mapping = {}
        if chapters:
            outline_ids = [ch.outline_id for ch in chapters if ch.outline_id]
            if outline_ids:
                outline_result = await db.execute(
                    select(Outline).where(Outline.id.in_(outline_ids))
                )
                outlines = outline_result.scalars().all()
                outline_mapping = {ol.id: ol.title for ol in outlines}
        
        exported_chapters = []
        for ch in chapters:
            # Phân tích expansion_plan JSON
            expansion_plan = None
            if ch.expansion_plan:
                try:
                    expansion_plan = json.loads(ch.expansion_plan) if isinstance(ch.expansion_plan, str) else ch.expansion_plan
                except Exception:
                    expansion_plan = None
            
            exported_chapters.append(ChapterExportData(
                title=ch.title,
                content=ch.content,
                summary=ch.summary,
                chapter_number=ch.chapter_number,
                word_count=ch.word_count or 0,
                status=ch.status,
                created_at=ch.created_at.isoformat() if ch.created_at else None,
                outline_title=outline_mapping.get(ch.outline_id) if ch.outline_id else None,
                sub_index=ch.sub_index,
                expansion_plan=expansion_plan
            ))
        
        return exported_chapters
    
    @staticmethod
    async def _export_characters(project_id: str, db: AsyncSession) -> List[CharacterExportData]:
        """Export nhân vật"""
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = result.scalars().all()
        
        exported = []
        for char in characters:
            # Phân tích traits JSON
            traits = None
            if char.traits:
                try:
                    traits = json.loads(char.traits) if isinstance(char.traits, str) else char.traits
                except Exception:
                    traits = None
            
            exported.append(CharacterExportData(
                name=char.name,
                age=char.age,
                gender=char.gender,
                is_organization=char.is_organization or False,
                role_type=char.role_type,
                personality=char.personality,
                background=char.background,
                appearance=char.appearance,
                traits=traits,
                organization_type=char.organization_type,
                organization_purpose=char.organization_purpose,
                created_at=char.created_at.isoformat() if char.created_at else None
            ))
        
        return exported
    
    @staticmethod
    async def _export_outlines(project_id: str, db: AsyncSession) -> List[OutlineExportData]:
        """Export dàn ý"""
        result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        outlines = result.scalars().all()
        
        return [
            OutlineExportData(
                title=ol.title,
                content=ol.content,
                structure=ol.structure,
                order_index=ol.order_index,
                created_at=ol.created_at.isoformat() if ol.created_at else None
            )
            for ol in outlines
        ]
    
    @staticmethod
    async def _export_relationships(project_id: str, db: AsyncSession) -> List[RelationshipExportData]:
        """Export quan hệ"""
        result = await db.execute(
            select(CharacterRelationship, Character)
            .join(Character, CharacterRelationship.character_from_id == Character.id)
            .where(CharacterRelationship.project_id == project_id)
        )
        relationships = result.all()
        
        exported = []
        for rel, char_from in relationships:
            # Lấy tên nhân vật đích
            target_result = await db.execute(
                select(Character).where(Character.id == rel.character_to_id)
            )
            char_to = target_result.scalar_one_or_none()
            
            if char_to:
                exported.append(RelationshipExportData(
                    source_name=char_from.name,
                    target_name=char_to.name,
                    relationship_name=rel.relationship_name,
                    intimacy_level=rel.intimacy_level or 50,
                    status=rel.status or "active",
                    description=rel.description,
                    started_at=rel.started_at
                ))
        
        return exported
    
    @staticmethod
    async def _export_organizations(project_id: str, db: AsyncSession) -> List[OrganizationExportData]:
        """Export chi tiết tổ chức"""
        result = await db.execute(
            select(Organization, Character)
            .join(Character, Organization.character_id == Character.id)
            .where(Organization.project_id == project_id)
        )
        organizations = result.all()
        
        exported = []
        for org, char in organizations:
            # Lấy tên tổ chức cha
            parent_name = None
            if org.parent_org_id:
                parent_result = await db.execute(
                    select(Organization, Character)
                    .join(Character, Organization.character_id == Character.id)
                    .where(Organization.id == org.parent_org_id)
                )
                parent_data = parent_result.first()
                if parent_data:
                    parent_name = parent_data[1].name
            
            exported.append(OrganizationExportData(
                character_name=char.name,
                parent_org_name=parent_name,
                power_level=org.power_level or 50,
                member_count=org.member_count or 0,
                location=org.location,
                motto=org.motto,
                color=org.color
            ))
        
        return exported
    
    @staticmethod
    async def _export_organization_members(project_id: str, db: AsyncSession) -> List[OrganizationMemberExportData]:
        """Export thành viên tổ chức"""
        result = await db.execute(
            select(OrganizationMember, Organization, Character)
            .join(Organization, OrganizationMember.organization_id == Organization.id)
            .join(Character, Organization.character_id == Character.id)
            .where(Organization.project_id == project_id)
        )
        members = result.all()
        
        exported = []
        for member, org, org_char in members:
            # Lấy tên nhân vật thành viên
            char_result = await db.execute(
                select(Character).where(Character.id == member.character_id)
            )
            member_char = char_result.scalar_one_or_none()
            
            if member_char:
                exported.append(OrganizationMemberExportData(
                    organization_name=org_char.name,
                    character_name=member_char.name,
                    position=member.position,
                    rank=member.rank or 0,
                    status=member.status or "active",
                    joined_at=member.joined_at,
                    loyalty=member.loyalty or 50,
                    contribution=member.contribution or 0,
                    notes=member.notes
                ))
        
        return exported
    
    @staticmethod
    async def _export_writing_styles(project_id: str, db: AsyncSession) -> List[WritingStyleExportData]:
        """Export phong cách viết (phong cách người dùng tự định nghĩa)"""
        # Lấy người dùng sở hữu project
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            return []
        
        # Export phong cách tùy chỉnh của người dùng này (không gồm preset toàn cục)
        result = await db.execute(
            select(WritingStyle)
            .where(WritingStyle.user_id == project.user_id)
            .order_by(WritingStyle.order_index)
        )
        styles = result.scalars().all()
        
        return [
            WritingStyleExportData(
                name=style.name,
                style_type=style.style_type,
                preset_id=style.preset_id,
                description=style.description,
                prompt_content=style.prompt_content,
                order_index=style.order_index or 0
            )
            for style in styles
        ]
    
    @staticmethod
    async def _export_generation_history(project_id: str, db: AsyncSession) -> List[GenerationHistoryExportData]:
        """Export lịch sử sinh"""
        result = await db.execute(
            select(GenerationHistory, Chapter)
            .outerjoin(Chapter, GenerationHistory.chapter_id == Chapter.id)
            .where(GenerationHistory.project_id == project_id)
            .order_by(GenerationHistory.created_at.desc())
            .limit(100)  # Giới hạn export tối đa 100 bản ghi lịch sử
        )
        histories = result.all()
        
        return [
            GenerationHistoryExportData(
                chapter_title=chapter.title if chapter else None,
                prompt=history.prompt,
                generated_content=history.generated_content,
                model=history.model,
                tokens_used=history.tokens_used,
                generation_time=history.generation_time,
                created_at=history.created_at.isoformat() if history.created_at else None
            )
            for history, chapter in histories
        ]
    
    @staticmethod
    async def _export_careers(project_id: str, db: AsyncSession) -> List[CareerExportData]:
        """Export hệ thống nghề"""
        result = await db.execute(
            select(Career)
            .where(Career.project_id == project_id)
            .order_by(Career.type, Career.created_at)
        )
        careers = result.scalars().all()
        
        return [
            CareerExportData(
                name=career.name,
                type=career.type,
                description=career.description,
                category=career.category,
                stages=career.stages,
                max_stage=career.max_stage or 10,
                requirements=career.requirements,
                special_abilities=career.special_abilities,
                worldview_rules=career.worldview_rules,
                attribute_bonuses=career.attribute_bonuses,
                source=career.source or "ai",
                created_at=career.created_at.isoformat() if career.created_at else None
            )
            for career in careers
        ]
    
    @staticmethod
    async def _export_character_careers(project_id: str, db: AsyncSession) -> List[CharacterCareerExportData]:
        """Export liên kết nghề-nhân vật"""
        # Truy vấn mọi liên kết nghề-nhân vật thuộc project này
        result = await db.execute(
            select(CharacterCareer, Character, Career)
            .join(Character, CharacterCareer.character_id == Character.id)
            .join(Career, CharacterCareer.career_id == Career.id)
            .where(Character.project_id == project_id)
        )
        character_careers = result.all()
        
        return [
            CharacterCareerExportData(
                character_name=char.name,
                career_name=career.name,
                career_type=cc.career_type,
                current_stage=cc.current_stage or 1,
                stage_progress=cc.stage_progress or 0,
                started_at=cc.started_at,
                reached_current_stage_at=cc.reached_current_stage_at,
                notes=cc.notes
            )
            for cc, char, career in character_careers
        ]
    
    @staticmethod
    async def _export_story_memories(project_id: str, db: AsyncSession) -> List[StoryMemoryExportData]:
        """Export ký ức truyện"""
        # Xây dựng map từ ID chương tới tiêu đề
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id)
        )
        chapters = chapter_result.scalars().all()
        chapter_mapping = {ch.id: ch.title for ch in chapters}
        
        # Xây dựng map từ ID nhân vật tới tên
        char_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = char_result.scalars().all()
        char_mapping = {char.id: char.name for char in characters}
        
        result = await db.execute(
            select(StoryMemory)
            .where(StoryMemory.project_id == project_id)
            .order_by(StoryMemory.story_timeline, StoryMemory.chapter_position)
        )
        memories = result.scalars().all()
        
        exported = []
        for mem in memories:
            # Chuyển list ID nhân vật thành list tên
            related_char_names = None
            if mem.related_characters:
                related_char_names = [
                    char_mapping.get(char_id, char_id)
                    for char_id in mem.related_characters
                ]
            
            exported.append(StoryMemoryExportData(
                chapter_title=chapter_mapping.get(mem.chapter_id) if mem.chapter_id else None,
                memory_type=mem.memory_type,
                title=mem.title,
                content=mem.content,
                full_context=mem.full_context,
                related_characters=related_char_names,
                related_locations=mem.related_locations,
                tags=mem.tags,
                importance_score=mem.importance_score or 0.5,
                story_timeline=mem.story_timeline,
                chapter_position=mem.chapter_position or 0,
                text_length=mem.text_length or 0,
                is_foreshadow=mem.is_foreshadow or 0,
                foreshadow_strength=mem.foreshadow_strength,
                created_at=mem.created_at.isoformat() if mem.created_at else None
            ))
        
        return exported
    
    @staticmethod
    async def _export_plot_analysis(project_id: str, db: AsyncSession) -> List[PlotAnalysisExportData]:
        """Export phân tích cốt truyện"""
        # Xây dựng map từ ID chương tới tiêu đề
        chapter_result = await db.execute(
            select(Chapter).where(Chapter.project_id == project_id)
        )
        chapters = chapter_result.scalars().all()
        chapter_mapping = {ch.id: ch.title for ch in chapters}
        
        result = await db.execute(
            select(PlotAnalysis)
            .where(PlotAnalysis.project_id == project_id)
        )
        analyses = result.scalars().all()
        
        exported = []
        for analysis in analyses:
            chapter_title = chapter_mapping.get(analysis.chapter_id)
            if not chapter_title:
                continue  # Bỏ qua phân tích không có chương liên kết
            
            exported.append(PlotAnalysisExportData(
                chapter_title=chapter_title,
                plot_stage=analysis.plot_stage,
                conflict_level=analysis.conflict_level,
                conflict_types=analysis.conflict_types,
                emotional_tone=analysis.emotional_tone,
                emotional_intensity=analysis.emotional_intensity,
                emotional_curve=analysis.emotional_curve,
                hooks=analysis.hooks,
                hooks_count=analysis.hooks_count or 0,
                hooks_avg_strength=analysis.hooks_avg_strength,
                foreshadows=analysis.foreshadows,
                foreshadows_planted=analysis.foreshadows_planted or 0,
                foreshadows_resolved=analysis.foreshadows_resolved or 0,
                plot_points=analysis.plot_points,
                plot_points_count=analysis.plot_points_count or 0,
                character_states=analysis.character_states,
                scenes=analysis.scenes,
                pacing=analysis.pacing,
                overall_quality_score=analysis.overall_quality_score,
                pacing_score=analysis.pacing_score,
                engagement_score=analysis.engagement_score,
                coherence_score=analysis.coherence_score,
                analysis_report=analysis.analysis_report,
                suggestions=analysis.suggestions,
                word_count=analysis.word_count,
                dialogue_ratio=analysis.dialogue_ratio,
                description_ratio=analysis.description_ratio,
                created_at=analysis.created_at.isoformat() if analysis.created_at else None
            ))
        
        return exported
    
    @staticmethod
    async def _export_project_default_style(project_id: str, db: AsyncSession) -> Optional[ProjectDefaultStyleExportData]:
        """Export phong cách mặc định của project"""
        result = await db.execute(
            select(ProjectDefaultStyle, WritingStyle)
            .join(WritingStyle, ProjectDefaultStyle.style_id == WritingStyle.id)
            .where(ProjectDefaultStyle.project_id == project_id)
        )
        row = result.first()
        
        if row:
            _, style = row
            return ProjectDefaultStyleExportData(style_name=style.name)
        
        return None
    
    @staticmethod
    def validate_import_data(data: Dict) -> ImportValidationResult:
        """
        Xác thực dữ liệu import
        
        Args:
            data: dữ liệu JSON import
            
        Returns:
            ImportValidationResult: kết quả xác thực
        """
        errors = []
        warnings = []
        statistics = {}
        
        # Kiểm tra phiên bản
        version = data.get("version", "")
        if not version:
            errors.append("Thiếu thông tin phiên bản")
        elif version not in ImportExportService.SUPPORTED_VERSIONS:
            warnings.append(f"Phiên bản không khớp: phiên bản file import là {version}, phiên bản hỗ trợ hiện tại là {', '.join(ImportExportService.SUPPORTED_VERSIONS)}")
        
        # Kiểm tra field bắt buộc
        if "project" not in data:
            errors.append("Thiếu thông tin project")
        else:
            project = data["project"]
            if not project.get("title"):
                errors.append("Tiêu đề project không được để trống")
        
        # Thống kê dữ liệu (gồm field mới thêm)
        statistics = {
            "chapters": len(data.get("chapters", [])),
            "characters": len(data.get("characters", [])),
            "outlines": len(data.get("outlines", [])),
            "relationships": len(data.get("relationships", [])),
            "organizations": len(data.get("organizations", [])),
            "organization_members": len(data.get("organization_members", [])),
            "writing_styles": len(data.get("writing_styles", [])),
            "generation_history": len(data.get("generation_history", [])),
            "careers": len(data.get("careers", [])),
            "character_careers": len(data.get("character_careers", [])),
            "story_memories": len(data.get("story_memories", [])),
            "plot_analysis": len(data.get("plot_analysis", [])),
            "has_default_style": data.get("project_default_style") is not None
        }
        
        # Kiểm tra tính đầy đủ dữ liệu
        if statistics["chapters"] == 0:
            warnings.append("Project không có dữ liệu chương")
        
        if statistics["characters"] == 0:
            warnings.append("Project không có dữ liệu nhân vật")
        
        project_name = data.get("project", {}).get("title", "project không rõ")
        
        return ImportValidationResult(
            valid=len(errors) == 0,
            version=version,
            project_name=project_name,
            statistics=statistics,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    async def import_project(
        data: Dict,
        db: AsyncSession,
        user_id: str
    ) -> ImportResult:
        """
        Import dữ liệu project (tạo project mới)
        
        Args:
            data: dữ liệu JSON import
            db: phiên làm việc cơ sở dữ liệu
            user_id: ID người dùng đích (chủ sở hữu project sau import)
            
        Returns:
            ImportResult: kết quả import
        """
        warnings = []
        statistics = {}
        
        try:
            # Xác thực dữ liệu
            validation = ImportExportService.validate_import_data(data)
            if not validation.valid:
                return ImportResult(
                    success=False,
                    message=f"Xác thực dữ liệu thất bại: {', '.join(validation.errors)}",
                    statistics={},
                    warnings=validation.warnings
                )
            
            warnings.extend(validation.warnings)
            
            logger.info(f"Bắt đầu import project: {validation.project_name}")
            
            # Tạo project
            project_data = data["project"]
            new_project = Project(
                user_id=user_id,  # Đặt thành ID người dùng hiện tại
                title=project_data.get("title"),
                description=project_data.get("description"),
                theme=project_data.get("theme"),
                genre=project_data.get("genre"),
                target_words=project_data.get("target_words"),
                status=project_data.get("status", "planning"),
                world_time_period=project_data.get("world_time_period"),
                world_location=project_data.get("world_location"),
                world_atmosphere=project_data.get("world_atmosphere"),
                world_rules=project_data.get("world_rules"),
                chapter_count=project_data.get("chapter_count"),
                narrative_perspective=project_data.get("narrative_perspective"),
                character_count=project_data.get("character_count"),
                outline_mode=project_data.get("outline_mode", "one-to-many"),  # ✅ Import chế độ dàn ý, mặc định một-nhiều
                current_words=project_data.get("current_words", 0),  # Giữ số từ của project gốc
                wizard_step=4,  # Project import được đặt trạng thái hoàn thành wizard
                wizard_status="completed"  # Đánh dấu wizard đã hoàn thành
            )
            db.add(new_project)
            await db.flush()  # Lấy project_id
            
            logger.info(f"Tạo project thành công: {new_project.id}")
            
            # Import nhân vật (gồm tổ chức) - cần import nhân vật trước vì dàn ý có thể cần thông tin nhân vật
            char_mapping = await ImportExportService._import_characters(
                new_project.id, data.get("characters", []), db
            )
            statistics["characters"] = len(char_mapping)
            logger.info(f"Số nhân vật import: {len(char_mapping)}")
            
            # Import dàn ý - cần import trước chương để thiết lập liên kết
            outline_mapping = await ImportExportService._import_outlines(
                new_project.id, data.get("outlines", []), db
            )
            statistics["outlines"] = len(outline_mapping)
            logger.info(f"Số dàn ý import: {len(outline_mapping)}")
            
            # Import chương - dùng map dàn ý để tái tạo quan hệ liên kết
            chapters_count = await ImportExportService._import_chapters(
                new_project.id, data.get("chapters", []), outline_mapping, db
            )
            statistics["chapters"] = chapters_count
            logger.info(f"Số chương import: {chapters_count}")
            
            # Import quan hệ
            relationships_count = await ImportExportService._import_relationships(
                new_project.id, data.get("relationships", []), char_mapping, db
            )
            statistics["relationships"] = relationships_count
            logger.info(f"Số quan hệ import: {relationships_count}")
            
            # Import chi tiết tổ chức
            org_mapping = await ImportExportService._import_organizations(
                new_project.id, data.get("organizations", []), char_mapping, db
            )
            statistics["organizations"] = len(org_mapping)
            logger.info(f"Số tổ chức import: {len(org_mapping)}")
            
            # Import thành viên tổ chức
            org_members_count = await ImportExportService._import_organization_members(
                data.get("organization_members", []), char_mapping, org_mapping, db
            )
            statistics["organization_members"] = org_members_count
            logger.info(f"Số thành viên tổ chức import: {org_members_count}")
            
            # Import phong cách viết
            styles_count = await ImportExportService._import_writing_styles(
                new_project.id, data.get("writing_styles", []), db
            )
            statistics["writing_styles"] = styles_count
            logger.info(f"Số phong cách viết import: {styles_count}")
            
            # Import hệ thống nghề
            career_mapping = await ImportExportService._import_careers(
                new_project.id, data.get("careers", []), db
            )
            statistics["careers"] = len(career_mapping)
            logger.info(f"Số nghề import: {len(career_mapping)}")
            
            # Import liên kết nghề-nhân vật
            char_careers_count = await ImportExportService._import_character_careers(
                data.get("character_careers", []), char_mapping, career_mapping, db
            )
            statistics["character_careers"] = char_careers_count
            logger.info(f"Số liên kết nghề-nhân vật import: {char_careers_count}")
            
            # Import ký ức truyện
            # Cần xây dựng trước map từ tiêu đề chương tới ID (dùng tổ hợp số chương + tiêu đề để đảm bảo duy nhất)
            chapter_title_to_id = {}
            chapter_result = await db.execute(
                select(Chapter).where(Chapter.project_id == new_project.id)
            )
            imported_chapters = chapter_result.scalars().all()
            for ch in imported_chapters:
                # Dùng tiêu đề làm key, nếu trùng tiêu đề thì lấy mục đầu tiên (theo thứ tự đã import)
                if ch.title and ch.title not in chapter_title_to_id:
                    chapter_title_to_id[ch.title] = ch.id
            
            memories_count = await ImportExportService._import_story_memories(
                new_project.id, data.get("story_memories", []), chapter_title_to_id, char_mapping, db
            )
            statistics["story_memories"] = memories_count
            logger.info(f"Số ký ức truyện import: {memories_count}")
            
            # Import phân tích cốt truyện (truyền user_id để tạo bản ghi nhiệm vụ phân tích)
            plot_analysis_count = await ImportExportService._import_plot_analysis(
                new_project.id, data.get("plot_analysis", []), chapter_title_to_id, db, user_id
            )
            statistics["plot_analysis"] = plot_analysis_count
            logger.info(f"Số phân tích cốt truyện import: {plot_analysis_count}")
            
            # Import phong cách mặc định của project
            default_style_imported = await ImportExportService._import_project_default_style(
                new_project.id, data.get("project_default_style"), db
            )
            statistics["project_default_style"] = 1 if default_style_imported else 0
            if default_style_imported:
                logger.info("Import phong cách mặc định của project thành công")
            
            # Commit transaction
            await db.commit()
            
            logger.info(f"Import project hoàn tất: {new_project.id}")
            
            return ImportResult(
                success=True,
                project_id=new_project.id,
                message="Import project thành công",
                statistics=statistics,
                warnings=warnings
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Import project thất bại: {str(e)}", exc_info=True)
            return ImportResult(
                success=False,
                message=f"Import thất bại: {str(e)}",
                statistics=statistics,
                warnings=warnings
            )
    
    @staticmethod
    async def _import_chapters(
        project_id: str,
        chapters_data: List[Dict],
        outline_mapping: Dict[str, str],
        db: AsyncSession
    ) -> int:
        """Import chương"""
        count = 0
        for ch_data in chapters_data:
            # Tìm ID dàn ý mới tương ứng theo tiêu đề dàn ý
            outline_id = None
            outline_title = ch_data.get("outline_title")
            if outline_title and outline_title in outline_mapping:
                outline_id = outline_mapping[outline_title]
            
            # Xử lý expansion_plan
            expansion_plan = ch_data.get("expansion_plan")
            if expansion_plan and isinstance(expansion_plan, dict):
                expansion_plan = json.dumps(expansion_plan, ensure_ascii=False)
            
            chapter = Chapter(
                project_id=project_id,
                title=ch_data.get("title"),
                content=ch_data.get("content"),
                summary=ch_data.get("summary"),
                chapter_number=ch_data.get("chapter_number"),
                word_count=ch_data.get("word_count", 0),
                status=ch_data.get("status", "draft"),
                outline_id=outline_id,
                sub_index=ch_data.get("sub_index"),
                expansion_plan=expansion_plan
            )
            db.add(chapter)
            count += 1
        
        return count
    
    @staticmethod
    async def _import_characters(
        project_id: str,
        characters_data: List[Dict],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Import nhân vật, trả về map từ tên tới ID"""
        char_mapping = {}
        
        for char_data in characters_data:
            # Xử lý traits
            traits = char_data.get("traits")
            if isinstance(traits, list):
                traits = json.dumps(traits, ensure_ascii=False)
            
            character = Character(
                project_id=project_id,
                name=char_data.get("name"),
                age=char_data.get("age"),
                gender=char_data.get("gender"),
                is_organization=char_data.get("is_organization", False),
                role_type=char_data.get("role_type"),
                personality=char_data.get("personality"),
                background=char_data.get("background"),
                appearance=char_data.get("appearance"),
                traits=traits,
                organization_type=char_data.get("organization_type"),
                organization_purpose=char_data.get("organization_purpose")
            )
            db.add(character)
            await db.flush()  # Lấy ID
            char_mapping[char_data.get("name")] = character.id
        
        return char_mapping
    
    @staticmethod
    async def _import_outlines(
        project_id: str,
        outlines_data: List[Dict],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Import dàn ý, trả về map từ tiêu đề tới ID"""
        outline_mapping = {}
        
        for ol_data in outlines_data:
            outline = Outline(
                project_id=project_id,
                title=ol_data.get("title"),
                content=ol_data.get("content") or "",
                structure=ol_data.get("structure"),
                order_index=ol_data.get("order_index")
            )
            db.add(outline)
            await db.flush()  # Lấy ID
            outline_mapping[ol_data.get("title")] = outline.id
        
        return outline_mapping
    
    @staticmethod
    async def _import_relationships(
        project_id: str,
        relationships_data: List[Dict],
        char_mapping: Dict[str, str],
        db: AsyncSession
    ) -> int:
        """Import quan hệ"""
        count = 0
        for rel_data in relationships_data:
            source_name = rel_data.get("source_name")
            target_name = rel_data.get("target_name")
            
            # Tìm ID nhân vật
            source_id = char_mapping.get(source_name)
            target_id = char_mapping.get(target_name)
            
            if source_id and target_id:
                relationship = CharacterRelationship(
                    project_id=project_id,
                    character_from_id=source_id,
                    character_to_id=target_id,
                    relationship_name=rel_data.get("relationship_name"),
                    intimacy_level=rel_data.get("intimacy_level", 50),
                    status=rel_data.get("status", "active"),
                    description=rel_data.get("description"),
                    started_at=rel_data.get("started_at")
                )
                db.add(relationship)
                count += 1
        
        return count
    
    @staticmethod
    async def _import_organizations(
        project_id: str,
        organizations_data: List[Dict],
        char_mapping: Dict[str, str],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Import chi tiết tổ chức, trả về map từ tên tới ID"""
        org_mapping = {}
        
        # Lượt 1: tạo mọi tổ chức (không đặt tổ chức cha)
        temp_orgs = []
        for org_data in organizations_data:
            char_name = org_data.get("character_name")
            char_id = char_mapping.get(char_name)
            
            if char_id:
                organization = Organization(
                    project_id=project_id,
                    character_id=char_id,
                    power_level=org_data.get("power_level", 50),
                    member_count=org_data.get("member_count", 0),
                    location=org_data.get("location"),
                    motto=org_data.get("motto"),
                    color=org_data.get("color")
                )
                db.add(organization)
                temp_orgs.append((organization, org_data.get("parent_org_name")))
        
        await db.flush()  # Lấy ID của mọi tổ chức
        
        # Thiết lập map từ tên tới ID
        for org, _ in temp_orgs:
            # Tìm tên nhân vật qua character_id
            result = await db.execute(
                select(Character).where(Character.id == org.character_id)
            )
            char = result.scalar_one_or_none()
            if char:
                org_mapping[char.name] = org.id
        
        # Lượt 2: đặt quan hệ tổ chức cha
        for org, parent_name in temp_orgs:
            if parent_name:
                parent_id = org_mapping.get(parent_name)
                if parent_id:
                    org.parent_org_id = parent_id
        
        return org_mapping
    
    @staticmethod
    async def _import_organization_members(
        org_members_data: List[Dict],
        char_mapping: Dict[str, str],
        org_mapping: Dict[str, str],
        db: AsyncSession
    ) -> int:
        """Import thành viên tổ chức"""
        count = 0
        for member_data in org_members_data:
            org_name = member_data.get("organization_name")
            char_name = member_data.get("character_name")
            
            org_id = org_mapping.get(org_name)
            char_id = char_mapping.get(char_name)
            
            if org_id and char_id:
                member = OrganizationMember(
                    organization_id=org_id,
                    character_id=char_id,
                    position=member_data.get("position"),
                    rank=member_data.get("rank", 0),
                    status=member_data.get("status", "active"),
                    joined_at=member_data.get("joined_at"),
                    loyalty=member_data.get("loyalty", 50),
                    contribution=member_data.get("contribution", 0),
                    notes=member_data.get("notes")
                )
                db.add(member)
                count += 1
        
        return count
    
    @staticmethod
    async def _import_writing_styles(
        project_id: str,
        styles_data: List[Dict],
        db: AsyncSession
    ) -> int:
        """Import phong cách viết (phong cách người dùng tự định nghĩa)"""
        # Lấy người dùng sở hữu project
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            return 0
        
        count = 0
        for style_data in styles_data:
            # Kiểm tra đã tồn tại phong cách trùng tên chưa (tránh import trùng)
            existing = await db.execute(
                select(WritingStyle).where(
                    WritingStyle.user_id == project.user_id,
                    WritingStyle.name == style_data.get("name")
                )
            )
            # Dùng first() để tránh lỗi khi nhiều dòng
            if existing.first():
                logger.debug(f"Phong cách {style_data.get('name')} đã tồn tại, bỏ qua import")
                continue
            
            style = WritingStyle(
                user_id=project.user_id,  # Dùng user_id thay vì project_id
                name=style_data.get("name"),
                style_type=style_data.get("style_type"),
                preset_id=style_data.get("preset_id"),
                description=style_data.get("description"),
                prompt_content=style_data.get("prompt_content"),
                order_index=style_data.get("order_index", 0)
            )
            db.add(style)
            count += 1
        
        return count
    
    @staticmethod
    async def _import_careers(
        project_id: str,
        careers_data: List[Dict],
        db: AsyncSession
    ) -> Dict[str, str]:
        """Import nghề, trả về map từ tên tới ID"""
        career_mapping = {}
        
        for career_data in careers_data:
            career = Career(
                project_id=project_id,
                name=career_data.get("name"),
                type=career_data.get("type", "main"),
                description=career_data.get("description"),
                category=career_data.get("category"),
                stages=career_data.get("stages", "[]"),
                max_stage=career_data.get("max_stage", 10),
                requirements=career_data.get("requirements"),
                special_abilities=career_data.get("special_abilities"),
                worldview_rules=career_data.get("worldview_rules"),
                attribute_bonuses=career_data.get("attribute_bonuses"),
                source=career_data.get("source", "ai")
            )
            db.add(career)
            await db.flush()
            career_mapping[career_data.get("name")] = career.id
        
        return career_mapping
    
    @staticmethod
    async def _import_character_careers(
        character_careers_data: List[Dict],
        char_mapping: Dict[str, str],
        career_mapping: Dict[str, str],
        db: AsyncSession
    ) -> int:
        """Import liên kết nghề-nhân vật"""
        count = 0
        for cc_data in character_careers_data:
            char_name = cc_data.get("character_name")
            career_name = cc_data.get("career_name")
            
            char_id = char_mapping.get(char_name)
            career_id = career_mapping.get(career_name)
            
            if char_id and career_id:
                # Kiểm tra đã tồn tại chưa (dùng first() để tránh lỗi khi nhiều dòng)
                existing = await db.execute(
                    select(CharacterCareer).where(
                        CharacterCareer.character_id == char_id,
                        CharacterCareer.career_id == career_id
                    )
                )
                if existing.first():
                    continue
                
                char_career = CharacterCareer(
                    character_id=char_id,
                    career_id=career_id,
                    career_type=cc_data.get("career_type", "main"),
                    current_stage=cc_data.get("current_stage", 1),
                    stage_progress=cc_data.get("stage_progress", 0),
                    started_at=cc_data.get("started_at"),
                    reached_current_stage_at=cc_data.get("reached_current_stage_at"),
                    notes=cc_data.get("notes")
                )
                db.add(char_career)
                count += 1
                
                # Đồng thời cập nhật thông tin nghề chính của nhân vật
                if cc_data.get("career_type") == "main":
                    char_result = await db.execute(
                        select(Character).where(Character.id == char_id)
                    )
                    char = char_result.scalar_one_or_none()
                    if char:
                        char.main_career_id = career_id
                        char.main_career_stage = cc_data.get("current_stage", 1)
        
        return count
    
    @staticmethod
    async def _import_story_memories(
        project_id: str,
        memories_data: List[Dict],
        chapter_mapping: Dict[str, str],
        char_mapping: Dict[str, str],
        db: AsyncSession
    ) -> int:
        """Import ký ức truyện"""
        count = 0
        for mem_data in memories_data:
            # Chuyển tiêu đề chương thành ID
            chapter_id = None
            chapter_title = mem_data.get("chapter_title")
            if chapter_title and chapter_title in chapter_mapping:
                chapter_id = chapter_mapping[chapter_title]
            
            # Chuyển list tên nhân vật thành list ID
            related_char_ids = None
            related_char_names = mem_data.get("related_characters")
            if related_char_names:
                related_char_ids = [
                    char_mapping.get(name)
                    for name in related_char_names
                    if char_mapping.get(name)
                ]
            
            memory = StoryMemory(
                project_id=project_id,
                chapter_id=chapter_id,
                memory_type=mem_data.get("memory_type"),
                title=mem_data.get("title"),
                content=mem_data.get("content"),
                full_context=mem_data.get("full_context"),
                related_characters=related_char_ids,
                related_locations=mem_data.get("related_locations"),
                tags=mem_data.get("tags"),
                importance_score=mem_data.get("importance_score", 0.5),
                story_timeline=mem_data.get("story_timeline", 0),
                chapter_position=mem_data.get("chapter_position", 0),
                text_length=mem_data.get("text_length", 0),
                is_foreshadow=mem_data.get("is_foreshadow", 0),
                foreshadow_strength=mem_data.get("foreshadow_strength")
            )
            db.add(memory)
            count += 1
        
        return count
    
    @staticmethod
    async def _import_plot_analysis(
        project_id: str,
        plot_data: List[Dict],
        chapter_mapping: Dict[str, str],
        db: AsyncSession,
        user_id: str = None
    ) -> int:
        """Import phân tích cốt truyện, đồng thời tạo bản ghi nhiệm vụ phân tích đã hoàn thành"""
        from datetime import datetime
        
        count = 0
        for analysis_data in plot_data:
            chapter_title = analysis_data.get("chapter_title")
            chapter_id = chapter_mapping.get(chapter_title)
            
            if not chapter_id:
                continue  # Bỏ qua phân tích không tìm thấy chương
            
            # Kiểm tra đã tồn tại phân tích của chương này chưa (dùng first() để tránh lỗi khi nhiều dòng)
            existing = await db.execute(
                select(PlotAnalysis).where(PlotAnalysis.chapter_id == chapter_id)
            )
            if existing.first():
                continue
            
            analysis = PlotAnalysis(
                project_id=project_id,
                chapter_id=chapter_id,
                plot_stage=analysis_data.get("plot_stage"),
                conflict_level=analysis_data.get("conflict_level"),
                conflict_types=analysis_data.get("conflict_types"),
                emotional_tone=analysis_data.get("emotional_tone"),
                emotional_intensity=analysis_data.get("emotional_intensity"),
                emotional_curve=analysis_data.get("emotional_curve"),
                hooks=analysis_data.get("hooks"),
                hooks_count=analysis_data.get("hooks_count", 0),
                hooks_avg_strength=analysis_data.get("hooks_avg_strength"),
                foreshadows=analysis_data.get("foreshadows"),
                foreshadows_planted=analysis_data.get("foreshadows_planted", 0),
                foreshadows_resolved=analysis_data.get("foreshadows_resolved", 0),
                plot_points=analysis_data.get("plot_points"),
                plot_points_count=analysis_data.get("plot_points_count", 0),
                character_states=analysis_data.get("character_states"),
                scenes=analysis_data.get("scenes"),
                pacing=analysis_data.get("pacing"),
                overall_quality_score=analysis_data.get("overall_quality_score"),
                pacing_score=analysis_data.get("pacing_score"),
                engagement_score=analysis_data.get("engagement_score"),
                coherence_score=analysis_data.get("coherence_score"),
                analysis_report=analysis_data.get("analysis_report"),
                suggestions=analysis_data.get("suggestions"),
                word_count=analysis_data.get("word_count"),
                dialogue_ratio=analysis_data.get("dialogue_ratio"),
                description_ratio=analysis_data.get("description_ratio")
            )
            db.add(analysis)
            
            # Đồng thời tạo bản ghi nhiệm vụ phân tích đã hoàn thành, để trang quản lý chương hiển thị trạng thái "đã phân tích"
            if user_id:
                now = datetime.utcnow()
                analysis_task = AnalysisTask(
                    chapter_id=chapter_id,
                    user_id=user_id,
                    project_id=project_id,
                    status='completed',
                    progress=100,
                    started_at=now,
                    completed_at=now
                )
                db.add(analysis_task)
            
            count += 1
        
        return count
    
    @staticmethod
    async def _import_project_default_style(
        project_id: str,
        default_style_data: Optional[Dict],
        db: AsyncSession
    ) -> bool:
        """Import phong cách mặc định của project"""
        if not default_style_data:
            return False
        
        style_name = default_style_data.get("style_name")
        if not style_name:
            return False
        
        # Lấy người dùng sở hữu project
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            return False
        
        # Tìm phong cách tương ứng (ưu tiên phong cách người dùng tự định nghĩa, sau đó là preset toàn cục)
        # Tìm phong cách người dùng tự định nghĩa trước (dùng first() để tránh lỗi khi nhiều dòng)
        style_result = await db.execute(
            select(WritingStyle).where(
                WritingStyle.user_id == project.user_id,
                WritingStyle.name == style_name
            )
        )
        style_row = style_result.first()
        style = style_row[0] if style_row else None
        
        # Nếu phong cách người dùng tự định nghĩa không tồn tại, tìm preset toàn cục
        if not style:
            style_result = await db.execute(
                select(WritingStyle).where(
                    WritingStyle.user_id.is_(None),
                    WritingStyle.name == style_name
                )
            )
            style_row = style_result.first()
            style = style_row[0] if style_row else None
        
        if not style:
            logger.warning(f"Import phong cách mặc định của project nhưng không tìm thấy phong cách: {style_name}")
            return False
        
        # Tạo liên kết phong cách mặc định của project
        default_style = ProjectDefaultStyle(
            project_id=project_id,
            style_id=style.id
        )
        db.add(default_style)
        
        logger.info(f"Import phong cách mặc định của project thành công: {style_name}, style_id={style.id}")
        return True
    
    @staticmethod
    async def export_characters(
        character_ids: List[str],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Export thẻ nhân vật/tổ chức
        
        Args:
            character_ids: list ID nhân vật/tổ chức cần export
            db: phiên làm việc cơ sở dữ liệu
            
        Returns:
            Dict: dữ liệu nhân vật được export
        """
        logger.info(f"Bắt đầu export nhân vật/tổ chức: {len(character_ids)} mục")
        
        # Truy vấn dữ liệu nhân vật
        result = await db.execute(
            select(Character).where(Character.id.in_(character_ids))
        )
        characters = result.scalars().all()
        
        if not characters:
            raise ValueError("Không tìm thấy nhân vật/tổ chức được chỉ định")
        
        # Export dữ liệu nhân vật
        exported_characters = []
        for char in characters:
            # Phân tích traits
            traits = None
            if char.traits:
                try:
                    traits = json.loads(char.traits) if isinstance(char.traits, str) else char.traits
                except Exception:
                    traits = None
            
            # Dữ liệu nhân vật cơ bản
            char_data = {
                "name": char.name,
                "age": char.age,
                "gender": char.gender,
                "is_organization": char.is_organization or False,
                "role_type": char.role_type,
                "personality": char.personality,
                "background": char.background,
                "appearance": char.appearance,
                "traits": traits,
                "organization_type": char.organization_type,
                "organization_purpose": char.organization_purpose,
                "avatar_url": char.avatar_url,
                "main_career_id": char.main_career_id,
                "main_career_stage": char.main_career_stage,
                "sub_careers": char.sub_careers,
                "created_at": char.created_at.isoformat() if char.created_at else None
            }
            
            # Nếu là tổ chức, thêm field đặc thù tổ chức
            if char.is_organization:
                org_result = await db.execute(
                    select(Organization).where(Organization.character_id == char.id)
                )
                org = org_result.scalar_one_or_none()
                
                if org:
                    char_data.update({
                        "power_level": org.power_level,
                        "location": org.location,
                        "motto": org.motto,
                        "color": org.color
                    })
                    
                    # Export dữ liệu thành viên có cấu trúc từ bảng OrganizationMember
                    members_result = await db.execute(
                        select(OrganizationMember).where(OrganizationMember.organization_id == org.id)
                    )
                    members = members_result.scalars().all()
                    if members:
                        char_data["organization_members_data"] = [
                            {
                                "character_id": m.character_id,
                                "position": m.position,
                                "rank": m.rank,
                                "loyalty": m.loyalty,
                                "contribution": m.contribution,
                                "status": m.status,
                                "joined_at": m.joined_at,
                                "source": m.source
                            }
                            for m in members
                        ]
            
            exported_characters.append(char_data)
        
        export_data = {
            "version": ImportExportService.CURRENT_VERSION,
            "export_time": datetime.utcnow().isoformat(),
            "export_type": "characters",
            "count": len(exported_characters),
            "data": exported_characters
        }
        
        logger.info(f"Export nhân vật/tổ chức hoàn tất: {len(exported_characters)} mục")
        return export_data
    
    @staticmethod
    async def import_characters(
        data: Dict,
        project_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Import thẻ nhân vật/tổ chức
        
        Args:
            data: dữ liệu JSON import
            project_id: ID project đích
            user_id: ID người dùng
            db: phiên làm việc cơ sở dữ liệu
            
        Returns:
            Dict: kết quả import
        """
        from app.models.career import CharacterCareer, Career
        
        warnings = []
        imported_characters = []
        imported_organizations = []
        skipped = []
        errors = []
        
        try:
            # Xác thực định dạng dữ liệu
            if "data" not in data:
                raise ValueError("Định dạng dữ liệu import sai: thiếu field data")
            
            characters_data = data["data"]
            if not isinstance(characters_data, list):
                raise ValueError("Định dạng dữ liệu import sai: field data phải là mảng")
            
            # Xác thực quyền project
            project_result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.user_id == user_id
                )
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise ValueError("Project không tồn tại hoặc không có quyền truy cập")
            
            logger.info(f"Bắt đầu import {len(characters_data)} nhân vật/tổ chức vào project {project_id}")
            
            # Xử lý từng nhân vật/tổ chức
            for idx, char_data in enumerate(characters_data):
                try:
                    name = char_data.get("name")
                    if not name:
                        errors.append(f"Nhân vật thứ {idx+1} thiếu field name")
                        continue
                    
                    # Kiểm tra tên trùng (dùng first() để tránh lỗi khi nhiều dòng)
                    existing_result = await db.execute(
                        select(Character).where(
                            Character.project_id == project_id,
                            Character.name == name
                        )
                    )
                    existing = existing_result.first()
                    
                    if existing:
                        warnings.append(f"Nhân vật '{name}' đã tồn tại, đã bỏ qua")
                        skipped.append(name)
                        continue
                    
                    # Xử lý traits
                    traits = char_data.get("traits")
                    if isinstance(traits, list):
                        traits = json.dumps(traits, ensure_ascii=False)
                    
                    is_organization = char_data.get("is_organization", False)
                    
                    # Tạo nhân vật
                    character = Character(
                        project_id=project_id,
                        name=name,
                        age=char_data.get("age"),
                        gender=char_data.get("gender"),
                        is_organization=is_organization,
                        role_type=char_data.get("role_type"),
                        personality=char_data.get("personality"),
                        background=char_data.get("background"),
                        appearance=char_data.get("appearance"),
                        traits=traits,
                        organization_type=char_data.get("organization_type"),
                        organization_purpose=char_data.get("organization_purpose"),
                        avatar_url=char_data.get("avatar_url"),
                        main_career_id=None,  # ID nghề cần xác thực rồi mới đặt
                        main_career_stage=char_data.get("main_career_stage"),
                        sub_careers=None  # Nghề phụ cần xác thực rồi mới đặt
                    )
                    db.add(character)
                    await db.flush()  # Lấy character.id
                    
                    # Xử lý nghề chính (nếu có)
                    main_career_id = char_data.get("main_career_id")
                    main_career_stage = char_data.get("main_career_stage")
                    
                    if main_career_id and not is_organization:
                        # Xác thực nghề có tồn tại không
                        career_result = await db.execute(
                            select(Career).where(
                                Career.id == main_career_id,
                                Career.project_id == project_id,
                                Career.type == 'main'
                            )
                        )
                        career = career_result.scalar_one_or_none()
                        
                        if career:
                            character.main_career_id = main_career_id
                            character.main_career_stage = main_career_stage or 1
                            
                            # Tạo liên kết nghề
                            char_career = CharacterCareer(
                                character_id=character.id,
                                career_id=main_career_id,
                                career_type='main',
                                current_stage=main_career_stage or 1,
                                stage_progress=0
                            )
                            db.add(char_career)
                        else:
                            warnings.append(f"ID nghề chính của nhân vật '{name}' không tồn tại, đã bỏ qua thông tin nghề")
                    
                    # Xử lý nghề phụ (nếu có)
                    sub_careers = char_data.get("sub_careers")
                    if sub_careers and not is_organization:
                        try:
                            sub_careers_data = json.loads(sub_careers) if isinstance(sub_careers, str) else sub_careers
                            
                            if isinstance(sub_careers_data, list):
                                valid_sub_careers = []
                                
                                for sub_data in sub_careers_data[:2]:  # Tối đa 2 nghề phụ
                                    if isinstance(sub_data, dict):
                                        career_id = sub_data.get('career_id')
                                        stage = sub_data.get('stage', 1)
                                        
                                        if career_id:
                                            # Xác thực nghề phụ có tồn tại không
                                            career_result = await db.execute(
                                                select(Career).where(
                                                    Career.id == career_id,
                                                    Career.project_id == project_id,
                                                    Career.type == 'sub'
                                                )
                                            )
                                            career = career_result.scalar_one_or_none()
                                            
                                            if career:
                                                valid_sub_careers.append({
                                                    'career_id': career_id,
                                                    'stage': stage
                                                })
                                                
                                                # Tạo liên kết nghề phụ
                                                char_career = CharacterCareer(
                                                    character_id=character.id,
                                                    career_id=career_id,
                                                    career_type='sub',
                                                    current_stage=stage,
                                                    stage_progress=0
                                                )
                                                db.add(char_career)
                                
                                if valid_sub_careers:
                                    character.sub_careers = json.dumps(valid_sub_careers, ensure_ascii=False)
                                elif sub_careers_data:
                                    warnings.append(f"ID nghề phụ của nhân vật '{name}' không tồn tại, đã bỏ qua thông tin nghề phụ")
                        except Exception as e:
                            warnings.append(f"Phân tích dữ liệu nghề phụ của nhân vật '{name}' thất bại: {str(e)}")
                    
                    # Nếu là tổ chức, tạo bản ghi Organization
                    if is_organization:
                        organization = Organization(
                            character_id=character.id,
                            project_id=project_id,
                            member_count=0,
                            power_level=char_data.get("power_level", 50),
                            location=char_data.get("location"),
                            motto=char_data.get("motto"),
                            color=char_data.get("color")
                        )
                        db.add(organization)
                        await db.flush()
                        
                        # Import dữ liệu thành viên tổ chức (nếu có)
                        members_data = char_data.get("organization_members_data", [])
                        if members_data and isinstance(members_data, list):
                            imported_member_count = 0
                            for m_data in members_data:
                                try:
                                    member_char_id = m_data.get("character_id")
                                    if not member_char_id:
                                        continue
                                    # Xác thực nhân vật thành viên có tồn tại trong project đích không
                                    member_char_result = await db.execute(
                                        select(Character).where(
                                            Character.id == member_char_id,
                                            Character.project_id == project_id
                                        )
                                    )
                                    if member_char_result.scalar_one_or_none():
                                        member = OrganizationMember(
                                            organization_id=organization.id,
                                            character_id=member_char_id,
                                            position=m_data.get("position", "thành viên"),
                                            rank=m_data.get("rank", 0),
                                            loyalty=m_data.get("loyalty", 50),
                                            contribution=m_data.get("contribution", 0),
                                            status=m_data.get("status", "active"),
                                            joined_at=m_data.get("joined_at"),
                                            source=m_data.get("source", "imported")
                                        )
                                        db.add(member)
                                        imported_member_count += 1
                                except Exception as me:
                                    logger.warning(f"Import thành viên tổ chức thất bại: {str(me)}")
                            
                            if imported_member_count > 0:
                                organization.member_count = imported_member_count
                                logger.info(f"Import {imported_member_count} thành viên của tổ chức '{name}'")
                        
                        imported_organizations.append(name)
                    else:
                        imported_characters.append(name)
                    
                    logger.info(f"Import {'tổ chức' if is_organization else 'nhân vật'} thành công: {name}")
                    
                except Exception as e:
                    error_msg = f"Import nhân vật '{char_data.get('name', f'thứ {idx+1}')}' thất bại: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            # Commit transaction
            await db.commit()
            
            total = len(imported_characters) + len(imported_organizations)
            
            result = {
                "success": True,
                "message": f"Import thành công {total} nhân vật/tổ chức",
                "statistics": {
                    "total": len(characters_data),
                    "imported": total,
                    "skipped": len(skipped),
                    "errors": len(errors)
                },
                "details": {
                    "imported_characters": imported_characters,
                    "imported_organizations": imported_organizations,
                    "skipped": skipped,
                    "errors": errors
                },
                "warnings": warnings
            }
            
            logger.info(f"Import nhân vật/tổ chức hoàn tất: thành công {total}, bỏ qua {len(skipped)}, thất bại {len(errors)}")
            return result
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Import nhân vật/tổ chức thất bại: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Import thất bại: {str(e)}",
                "statistics": {
                    "total": len(characters_data) if "data" in data else 0,
                    "imported": len(imported_characters) + len(imported_organizations),
                    "skipped": len(skipped),
                    "errors": len(errors)
                },
                "details": {
                    "imported_characters": imported_characters,
                    "imported_organizations": imported_organizations,
                    "skipped": skipped,
                    "errors": errors
                },
                "warnings": warnings
            }
    
    @staticmethod
    def validate_characters_import(data: Dict) -> Dict[str, Any]:
        """
        Xác thực dữ liệu import nhân vật/tổ chức
        
        Args:
            data: dữ liệu JSON import
            
        Returns:
            Dict: kết quả xác thực
        """
        errors = []
        warnings = []
        
        # Kiểm tra phiên bản
        version = data.get("version", "")
        if not version:
            errors.append("Thiếu thông tin phiên bản")
        elif version not in ImportExportService.SUPPORTED_VERSIONS:
            warnings.append(f"Phiên bản không khớp: phiên bản file import là {version}, phiên bản hỗ trợ hiện tại là {', '.join(ImportExportService.SUPPORTED_VERSIONS)}")
        
        # Kiểm tra loại export
        export_type = data.get("export_type", "")
        if export_type != "characters":
            errors.append(f"Lỗi loại export: kỳ vọng 'characters', thực tế '{export_type}'")
        
        # Kiểm tra field dữ liệu
        if "data" not in data:
            errors.append("Thiếu field data")
        elif not isinstance(data["data"], list):
            errors.append("Field data phải là mảng")
        else:
            characters_data = data["data"]
            
            # Thông tin thống kê
            character_count = sum(1 for c in characters_data if not c.get("is_organization", False))
            org_count = sum(1 for c in characters_data if c.get("is_organization", False))
            
            # Kiểm tra field bắt buộc
            for idx, char_data in enumerate(characters_data):
                if not char_data.get("name"):
                    errors.append(f"Nhân vật thứ {idx+1} thiếu field name")
            
            statistics = {
                "characters": character_count,
                "organizations": org_count
            }
        
        if "data" not in data or errors:
            statistics = {"characters": 0, "organizations": 0}
        
        return {
            "valid": len(errors) == 0,
            "version": version,
            "statistics": statistics,
            "errors": errors,
            "warnings": warnings
        }
