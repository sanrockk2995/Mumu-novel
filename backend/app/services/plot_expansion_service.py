"""Dịch vụ triển khai cốt truyện dàn ý - triển khai nút dàn ý thành nhiều chương"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from app.models.outline import Outline
from app.models.project import Project
from app.models.character import Character
from app.models.chapter import Chapter
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.logger import get_logger, safe_preview

logger = get_logger(__name__)


class PlotExpansionService:
    """Dịch vụ triển khai cốt truyện dàn ý"""
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
    
    async def analyze_outline_for_chapters(
        self,
        outline: Outline,
        project: Project,
        db: AsyncSession,
        target_chapter_count: int = 3,
        expansion_strategy: str = "balanced",
        enable_scene_analysis: bool = True,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 5,
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Phân tích một dàn ý, sinh kế hoạch đa chương (hỗ trợ sinh theo đợt)
        
        Args:
            outline: đối tượng dàn ý
            project: đối tượng project
            db: phiên làm việc cơ sở dữ liệu
            target_chapter_count: số chương mục tiêu cần sinh
            expansion_strategy: chiến lược triển khai (balanced/climax/detail)
            enable_scene_analysis: có bật phân tích cấp cảnh không
            provider: nhà cung cấp AI
            model: model AI
            batch_size: số chương sinh mỗi đợt (mặc định 5 chương)
            progress_callback: hàm callback tiến độ (tùy chọn)
            
        Returns:
            Danh sách kế hoạch chương
        """
        logger.info(f"Bắt đầu phân tích dàn ý {outline.id}, mục tiêu sinh {target_chapter_count} chương")
        
        # Nếu số chương ít, sinh trực tiếp
        if target_chapter_count <= batch_size:
            return await self._generate_chapters_single_batch(
                outline=outline,
                project=project,
                db=db,
                target_chapter_count=target_chapter_count,
                expansion_strategy=expansion_strategy,
                enable_scene_analysis=enable_scene_analysis,
                provider=provider,
                model=model
            )
        
        # Số chương nhiều, sinh theo đợt
        logger.info(f"Số chương ({target_chapter_count}) vượt kích thước đợt ({batch_size}), bật sinh theo đợt")
        return await self._generate_chapters_in_batches(
            outline=outline,
            project=project,
            db=db,
            target_chapter_count=target_chapter_count,
            expansion_strategy=expansion_strategy,
            enable_scene_analysis=enable_scene_analysis,
            provider=provider,
            model=model,
            batch_size=batch_size,
            progress_callback=progress_callback
        )
    
    async def _generate_chapters_single_batch(
        self,
        outline: Outline,
        project: Project,
        db: AsyncSession,
        target_chapter_count: int,
        expansion_strategy: str,
        enable_scene_analysis: bool,
        provider: Optional[str],
        model: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Sinh kế hoạch chương cho một đợt"""
        # Lấy thông tin nhân vật
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        characters = characters_result.scalars().all()
        characters_info = "\n".join([
            f"- {char.name} ({'tổ chức' if char.is_organization else 'nhân vật'}, {char.role_type}): "
            f"{char.personality[:100] if char.personality else 'chưa có mô tả'}"
            for char in characters
        ])
        
        # Lấy context dàn ý (dàn ý trước/sau)
        context_info = await self._get_outline_context(outline, project.id, db)
        
        # Lấy template prompt tùy chỉnh
        template = await PromptService.get_template("OUTLINE_EXPAND_SINGLE", project.user_id, db)
        # Format prompt
        prompt = PromptService.format_prompt(
            template,
            project_title=project.title,
            project_genre=project.genre or 'tổng hợp',
            project_theme=project.theme or 'chưa đặt',
            project_narrative_perspective=project.narrative_perspective or 'ngôi thứ ba',
            project_world_time_period=project.world_time_period or 'chưa đặt',
            project_world_location=project.world_location or 'chưa đặt',
            project_world_atmosphere=project.world_atmosphere or 'chưa đặt',
            characters_info=characters_info or 'chưa có nhân vật',
            outline_order_index=outline.order_index,
            outline_title=outline.title,
            outline_content=outline.content,
            context_info=context_info,
            strategy_instruction=expansion_strategy,
            target_chapter_count=target_chapter_count,
            scene_instruction="", # tạm thời để trống
            scene_field="" # tạm thời để trống
        )
        
        # Gọi AI sinh kế hoạch chương
        logger.info(f"Gọi AI sinh kế hoạch chương...")
        accumulated_text = ""
        async for chunk in self.ai_service.generate_text_stream(
            prompt=prompt,
            provider=provider,
            model=model
        ):
            accumulated_text += chunk
        
        # Trích nội dung
        ai_content = accumulated_text
        
        # Parse phản hồi AI
        chapter_plans = self._parse_expansion_response(ai_content, outline.id)
        
        logger.info(f"Sinh thành công {len(chapter_plans)} kế hoạch chương")
        return chapter_plans
    
    async def _generate_chapters_in_batches(
        self,
        outline: Outline,
        project: Project,
        db: AsyncSession,
        target_chapter_count: int,
        expansion_strategy: str,
        enable_scene_analysis: bool,
        provider: Optional[str],
        model: Optional[str],
        batch_size: int,
        progress_callback: Optional[callable]
    ) -> List[Dict[str, Any]]:
        """Sinh kế hoạch chương theo đợt (bản tăng cường khác biệt hóa)"""
        # Tính số đợt
        total_batches = (target_chapter_count + batch_size - 1) // batch_size
        logger.info(f"Kế hoạch sinh theo đợt: tổng {target_chapter_count} chương, {total_batches} đợt, mỗi đợt {batch_size} chương")
        
        # Lấy thông tin nhân vật (dùng chung mọi đợt)
        characters_result = await db.execute(
            select(Character).where(Character.project_id == project.id)
        )
        characters = characters_result.scalars().all()
        characters_info = "\n".join([
            f"- {char.name} ({'tổ chức' if char.is_organization else 'nhân vật'}, {char.role_type}): "
            f"{char.personality[:100] if char.personality else 'chưa có mô tả'}"
            for char in characters
        ])
        
        # Lấy context dàn ý
        context_info = await self._get_outline_context(outline, project.id, db)
        
        all_chapter_plans = []
        
        # 🔧 Thu thập mọi sự kiện then chốt đã dùng, để tránh lặp
        used_key_events = set()
        
        for batch_num in range(total_batches):
            # Tính số chương của đợt hiện tại
            remaining_chapters = target_chapter_count - len(all_chapter_plans)
            current_batch_size = min(batch_size, remaining_chapters)
            current_start_index = len(all_chapter_plans) + 1
            
            logger.info(f"Bắt đầu sinh đợt {batch_num + 1}/{total_batches}, phạm vi chương: {current_start_index}-{current_start_index + current_batch_size - 1}")
            
            # Callback báo tiến độ
            if progress_callback:
                await progress_callback(batch_num + 1, total_batches, current_start_index, current_batch_size)
            
            # 🔧 Xây dựng context tăng cường (gồm thông tin khác biệt hóa đầy đủ)
            previous_context = ""
            if all_chapter_plans:
                # Xây dựng tóm tắt đầy đủ các chương đã sinh (gồm sự kiện then chốt)
                previous_summaries = []
                for ch in all_chapter_plans: # Hiển thị mọi chương đã sinh
                    key_events_str = "、".join(ch.get('key_events', [])[:3]) if ch.get('key_events') else "không có"
                    previous_summaries.append(
                        f"Phần {ch['sub_index']}《{ch['title']}》:\n"
                        f" - Cốt truyện: {ch.get('plot_summary', '')[:150]}\n"
                        f" - Sự kiện then chốt: {key_events_str}\n"
                        f" - Cách kết thúc: {ch.get('ending_type', 'không rõ')}"
                    )
                
                # Trích mọi sự kiện then chốt đã dùng
                all_used_events = []
                for ch in all_chapter_plans:
                    all_used_events.extend(ch.get('key_events', []))
                used_events_str = "、".join(all_used_events[-20:]) if all_used_events else "chưa có"
                
                previous_context = f"""
【🔴 Thông tin đầy đủ các chương đã sinh (phải tham khảo để đảm bảo khác biệt hóa)】
{chr(10).join(previous_summaries)}

【🔴 Các sự kiện then chốt đã dùng (đợt này không được dùng lại)】
{used_events_str}

【🔴 Yêu cầu bắt buộc về khác biệt hóa】
⚠️ Hiện là phần {current_start_index}-{current_start_index + current_batch_size - 1} (đợt {batch_num + 1} trong tổng {target_chapter_count} phần)
⚠️ Mỗi chương mới phải hoàn toàn khác biệt ở:
   1. Cảnh mở đầu (địa điểm/thời gian/trạng thái nhân vật khác nhau)
   2. Sự kiện cốt lõi (không trùng sự kiện then chốt của chương đã sinh)
   3. Treo ở kết (hook thuộc loại khác nhau)
⚠️ key_events của chương mới không được giống hoặc tương tự bất kỳ sự kiện nào trong 【Các sự kiện then chốt đã dùng】 ở trên
"""
            # Lấy template prompt tùy chỉnh
            template = await PromptService.get_template("OUTLINE_EXPAND_MULTI", project.user_id, db)
            # Format prompt
            prompt = PromptService.format_prompt(
                template,
                project_title=project.title,
                project_genre=project.genre or 'tổng hợp',
                project_theme=project.theme or 'chưa đặt',
                project_narrative_perspective=project.narrative_perspective or 'ngôi thứ ba',
                project_world_time_period=project.world_time_period or 'chưa đặt',
                project_world_location=project.world_location or 'chưa đặt',
                project_world_atmosphere=project.world_atmosphere or 'chưa đặt',
                characters_info=characters_info or 'chưa có nhân vật',
                outline_order_index=outline.order_index,
                outline_title=outline.title,
                outline_content=outline.content,
                context_info=context_info,
                previous_context=previous_context,
                strategy_instruction=expansion_strategy,
                start_index=current_start_index,
                end_index=current_start_index + current_batch_size - 1,
                target_chapter_count=current_batch_size,
                scene_instruction="", # tạm thời để trống
                scene_field="" # tạm thời để trống
            )
            
            # Gọi AI sinh đợt hiện tại
            logger.info(f"Gọi AI sinh đợt {batch_num + 1}...")
            accumulated_text = ""
            async for chunk in self.ai_service.generate_text_stream(
                prompt=prompt,
                provider=provider,
                model=model
            ):
                accumulated_text += chunk
            
            # Trích nội dung
            ai_content = accumulated_text
            
            # Parse phản hồi AI
            batch_plans = self._parse_expansion_response(ai_content, outline.id)
            
            # Điều chỉnh sub_index để giữ liên tục
            for i, plan in enumerate(batch_plans):
                plan["sub_index"] = current_start_index + i
            
            all_chapter_plans.extend(batch_plans)
            
            logger.info(f"Đợt {batch_num + 1} sinh xong, đợt này {len(batch_plans)} chương, lũy kế {len(all_chapter_plans)} chương")
        
        logger.info(f"Sinh theo đợt hoàn tất, tổng {len(all_chapter_plans)} kế hoạch chương")
        return all_chapter_plans
    
    async def batch_expand_outlines(
        self,
        project_id: str,
        db: AsyncSession,
        ai_service: AIService,
        target_chapters_per_outline: int = 3,
        expansion_strategy: str = "balanced",
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Triển khai hàng loạt mọi dàn ý thành chương
        
        Returns:
            {
                "total_outlines": tổng số dàn ý,
                "total_chapters_planned": tổng số chương đã lên kế hoạch,
                "expansions": [kết quả triển khai của mỗi dàn ý]
            }
        """
        logger.info(f"Bắt đầu triển khai hàng loạt mọi dàn ý của project {project_id}")
        
        # Lấy project
        project_result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} không tồn tại")
        
        # Lấy mọi dàn ý
        outlines_result = await db.execute(
            select(Outline)
            .where(Outline.project_id == project_id)
            .order_by(Outline.order_index)
        )
        outlines = outlines_result.scalars().all()
        
        if not outlines:
            logger.warning(f"Project {project_id} không có dàn ý")
            return {
                "total_outlines": 0,
                "total_chapters_planned": 0,
                "expansions": []
            }
        
        # Triển khai từng dàn ý
        expansions = []
        total_chapters = 0
        
        for outline in outlines:
            try:
                chapter_plans = await self.analyze_outline_for_chapters(
                    outline=outline,
                    project=project,
                    db=db,
                    target_chapter_count=target_chapters_per_outline,
                    expansion_strategy=expansion_strategy,
                    provider=provider,
                    model=model
                )
                
                expansions.append({
                    "outline_id": outline.id,
                    "outline_title": outline.title,
                    "chapter_plans": chapter_plans,
                    "chapter_count": len(chapter_plans)
                })
                
                total_chapters += len(chapter_plans)
                logger.info(f"Dàn ý {outline.title} triển khai thành {len(chapter_plans)} chương")
                
            except Exception as e:
                logger.error(f"Triển khai dàn ý {outline.id} thất bại: {str(e)}")
                expansions.append({
                    "outline_id": outline.id,
                    "outline_title": outline.title,
                    "error": str(e),
                    "chapter_count": 0
                })
        
        result = {
            "total_outlines": len(outlines),
            "total_chapters_planned": total_chapters,
            "expansions": expansions
        }
        
        logger.info(f"Triển khai hàng loạt hoàn tất: {len(outlines)} dàn ý → {total_chapters} kế hoạch chương")
        return result
    
    async def create_chapters_from_plans(
        self,
        outline_id: str,
        chapter_plans: List[Dict[str, Any]],
        project_id: str,
        db: AsyncSession,
        start_chapter_number: int = None
    ) -> List[Chapter]:
        """
        Tạo bản ghi chương thực tế theo kế hoạch chương
        
        Args:
            outline_id: ID dàn ý
            chapter_plans: danh sách kế hoạch chương
            project_id: ID project
            db: phiên làm việc cơ sở dữ liệu
            start_chapter_number: số chương bắt đầu (nếu None thì tự tính)
            
        Returns:
            Danh sách chương đã tạo
        """
        logger.info(f"Tạo {len(chapter_plans)} bản ghi chương theo kế hoạch")
        
        # Nếu chưa chỉ định số chương bắt đầu, tự tính theo thứ tự dàn ý
        if start_chapter_number is None:
            # 1. Lấy thông tin dàn ý hiện tại
            outline_result = await db.execute(
                select(Outline).where(Outline.id == outline_id)
            )
            current_outline = outline_result.scalar_one_or_none()
            
            if not current_outline:
                raise ValueError(f"Dàn ý {outline_id} không tồn tại")
            
            # 2. Truy vấn mọi dàn ý trước dàn ý hiện tại (sắp xếp theo order_index)
            prev_outlines_result = await db.execute(
                select(Outline)
                .where(
                    Outline.project_id == project_id,
                    Outline.order_index < current_outline.order_index
                )
                .order_by(Outline.order_index)
            )
            prev_outlines = prev_outlines_result.scalars().all()
            
            # 3. Tính tổng số chương đã triển khai của mọi dàn ý phía trước
            total_prev_chapters = 0
            for prev_outline in prev_outlines:
                count_result = await db.execute(
                    select(func.count(Chapter.id))
                    .where(
                        Chapter.project_id == project_id,
                        Chapter.outline_id == prev_outline.id
                    )
                )
                total_prev_chapters += count_result.scalar() or 0
            
            # 4. Số chương bắt đầu = số chương của mọi dàn ý phía trước + 1
            start_chapter_number = total_prev_chapters + 1
            logger.info(f"Tự tính số chương bắt đầu: {start_chapter_number} (dựa trên order_index dàn ý={current_outline.order_index}, số chương phía trước={total_prev_chapters})")
        
        chapters = []
        for idx, plan in enumerate(chapter_plans):
            # Lưu dữ liệu kế hoạch triển khai đầy đủ (định dạng JSON)
            expansion_plan_json = json.dumps({
                "key_events": plan.get("key_events", []),
                "character_focus": plan.get("character_focus", []),
                "emotional_tone": plan.get("emotional_tone", ""),
                "narrative_goal": plan.get("narrative_goal", ""),
                "conflict_type": plan.get("conflict_type", ""),
                "estimated_words": plan.get("estimated_words", 3000),
                "scenes": plan.get("scenes", []) if plan.get("scenes") else None
            }, ensure_ascii=False)
            
            chapter = Chapter(
                project_id=project_id,
                outline_id=outline_id,
                chapter_number=start_chapter_number + idx,
                sub_index=plan.get("sub_index", idx + 1),
                title=plan.get("title", f"Chương {start_chapter_number + idx}"),
                summary=plan.get("plot_summary", ""),
                expansion_plan=expansion_plan_json,
                status="draft"
            )
            db.add(chapter)
            chapters.append(chapter)
        
        await db.commit()
        
        for chapter in chapters:
            await db.refresh(chapter)
        
        logger.info(f"Tạo thành công {len(chapters)} bản ghi chương (đã lưu dữ liệu kế hoạch triển khai)")
        
        # Sắp xếp lại mọi chương sau dàn ý hiện tại
        await self._renumber_subsequent_chapters(
            project_id=project_id,
            current_outline_id=outline_id,
            db=db
        )
        
        return chapters
    
    async def _get_outline_context(
        self,
        outline: Outline,
        project_id: str,
        db: AsyncSession
    ) -> str:
        """Lấy context của dàn ý (dàn ý trước/sau)"""
        # Lấy dàn ý trước
        prev_result = await db.execute(
            select(Outline)
            .where(
                Outline.project_id == project_id,
                Outline.order_index < outline.order_index
            )
            .order_by(Outline.order_index.desc())
            .limit(1)
        )
        prev_outline = prev_result.scalar_one_or_none()
        
        # Lấy dàn ý sau
        next_result = await db.execute(
            select(Outline)
            .where(
                Outline.project_id == project_id,
                Outline.order_index > outline.order_index
            )
            .order_by(Outline.order_index)
            .limit(1)
        )
        next_outline = next_result.scalar_one_or_none()
        
        context = ""
        if prev_outline:
                        context += f"【Phần trước】{prev_outline.title}: {prev_outline.content[:200]}...\n\n"
        if next_outline:
                        context += f"【Phần sau】{next_outline.title}: {next_outline.content[:200]}...\n"
        
        return context if context else "(không có context trước/sau)"
    
    
    def _parse_expansion_response(
        self,
        ai_response: str,
        outline_id: str
    ) -> List[Dict[str, Any]]:
        """Parse phản hồi triển khai của AI (dùng phương pháp làm sạch JSON thống nhất, tăng cường field khác biệt hóa)"""
        try:
            # Dùng phương pháp làm sạch JSON thống nhất
            cleaned_text = self.ai_service._clean_json_response(ai_response)
            
            # Parse JSON
            chapter_plans = loads_json(cleaned_text)
            
            # Đảm bảo là list
            if not isinstance(chapter_plans, list):
                chapter_plans = [chapter_plans]
            
            # Thêm outline_id và dấu hiệu khác biệt hóa cho mỗi kế hoạch chương
            for idx, plan in enumerate(chapter_plans):
                plan["outline_id"] = outline_id
                
                # 🔧 Đảm bảo có field ending_type (để theo dõi khác biệt hóa)
                if "ending_type" not in plan:
                    # Suy ra kiểu kết thúc theo mục tiêu tự sự
                    narrative_goal = plan.get("narrative_goal", "")
                    if "treo" in narrative_goal or "hồi hộp" in narrative_goal or "nghi vấn" in narrative_goal or "câu hỏi" in narrative_goal:
                        plan["ending_type"] = "treo"
                    elif "xung đột" in narrative_goal or "đối đầu" in narrative_goal:
                        plan["ending_type"] = "xung đột leo thang"
                    elif "bước ngoặt" in narrative_goal or "chuyển biến" in narrative_goal:
                        plan["ending_type"] = "bước ngoặt cốt truyện"
                    elif "cảm xúc" in narrative_goal or "tình cảm" in narrative_goal:
                        plan["ending_type"] = "kết thúc cảm xúc"
                    else:
                        plan["ending_type"] = f"chuyển tiếp tự nhiên-{idx + 1}"
                
                # 🔧 Đảm bảo key_events là list và không rỗng
                if not plan.get("key_events"):
                    plan["key_events"] = [f"sự kiện cốt lõi chương {idx + 1}"]
            
            logger.info(f"✅ Parse thành công {len(chapter_plans)} kế hoạch chương (gồm dấu hiệu khác biệt hóa)")
            return chapter_plans
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Parse phản hồi AI thất bại: {e}, xem trước phản hồi: {safe_preview(ai_response, 300)}")
            # Trả về một kế hoạch cơ sở
            return [{
                "outline_id": outline_id,
                "sub_index": 1,
                "title": "Chương mặc định khi AI parse thất bại",
                "plot_summary": ai_response[:500],
                "key_events": ["parse thất bại"],
                "character_focus": [],
                "emotional_tone": "không rõ",
                "narrative_goal": "cần sinh lại",
                "conflict_type": "không rõ",
                "ending_type": "không rõ",
                "estimated_words": 3000
            }]
        except Exception as e:
            logger.error(f"❌ Ngoại lệ khi parse: {str(e)}")
            return [{
                "outline_id": outline_id,
                "sub_index": 1,
                "title": "Chương mặc định khi parse gặp ngoại lệ",
                "plot_summary": "Lỗi hệ thống",
                "key_events": [],
                "character_focus": [],
                "emotional_tone": "không rõ",
                "narrative_goal": "cần sinh lại",
                "conflict_type": "không rõ",
                "ending_type": "không rõ",
                "estimated_words": 3000
            }]


    async def _renumber_subsequent_chapters(
        self,
        project_id: str,
        current_outline_id: str,
        db: AsyncSession
    ):
        """
        Tính lại số thứ tự chương của mọi dàn ý sau dàn ý hiện tại
        
        Args:
            project_id: ID project
            current_outline_id: ID dàn ý hiện tại
            db: phiên làm việc cơ sở dữ liệu
        """
        logger.info(f"Bắt đầu sắp xếp lại mọi chương sau dàn ý {current_outline_id}")
        
        # 1. Lấy thông tin dàn ý hiện tại
        current_outline_result = await db.execute(
            select(Outline).where(Outline.id == current_outline_id)
        )
        current_outline = current_outline_result.scalar_one_or_none()
        
        if not current_outline:
            logger.warning(f"Dàn ý {current_outline_id} không tồn tại, bỏ qua sắp xếp lại")
            return
        
        # 2. Lấy dàn ý hiện tại và mọi dàn ý sau đó (sắp xếp theo order_index)
        subsequent_outlines_result = await db.execute(
            select(Outline)
            .where(
                Outline.project_id == project_id,
                Outline.order_index >= current_outline.order_index
            )
            .order_by(Outline.order_index)
        )
        subsequent_outlines = subsequent_outlines_result.scalars().all()
        
        # 3. Tính số chương bắt đầu của mỗi dàn ý
        current_chapter_number = 1
        
        # Tính trước tổng số chương của các dàn ý phía trước
        prev_outlines_result = await db.execute(
            select(Outline)
            .where(
                Outline.project_id == project_id,
                Outline.order_index < current_outline.order_index
            )
            .order_by(Outline.order_index)
        )
        prev_outlines = prev_outlines_result.scalars().all()
        
        for prev_outline in prev_outlines:
            count_result = await db.execute(
                select(func.count(Chapter.id))
                .where(
                    Chapter.project_id == project_id,
                    Chapter.outline_id == prev_outline.id
                )
            )
            current_chapter_number += count_result.scalar() or 0
        
        # 4. Cập nhật số thứ tự chương cho từng dàn ý
        updated_count = 0
        for outline in subsequent_outlines:
            # Lấy mọi chương của dàn ý đó (sắp xếp theo sub_index)
            chapters_result = await db.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == project_id,
                    Chapter.outline_id == outline.id
                )
                .order_by(Chapter.sub_index)
            )
            chapters = chapters_result.scalars().all()
            
            # Cập nhật chapter_number của mỗi chương
            for chapter in chapters:
                if chapter.chapter_number != current_chapter_number:
                    logger.debug(f"Cập nhật chương {chapter.id}: {chapter.chapter_number} -> {current_chapter_number}")
                    chapter.chapter_number = current_chapter_number
                    updated_count += 1
                current_chapter_number += 1
        
        # 5. Commit cập nhật
        await db.commit()
        logger.info(f"Sắp xếp lại hoàn tất, đã cập nhật số thứ tự của {updated_count} chương")


# Hàm factory
def create_plot_expansion_service(ai_service: AIService) -> PlotExpansionService:
    """Tạo instance dịch vụ triển khai cốt truyện"""
    return PlotExpansionService(ai_service)
