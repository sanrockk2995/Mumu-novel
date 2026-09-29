"""Dịch vụ tái sinh chương"""
from typing import Dict, Any, AsyncGenerator, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service, PromptService
from app.models.chapter import Chapter
from app.models.memory import PlotAnalysis
from app.schemas.regeneration import ChapterRegenerateRequest, PreserveElementsConfig
from app.logger import get_logger
import difflib

logger = get_logger(__name__)


class ChapterRegenerator:
    """Dịch vụ tái sinh chương"""
    
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        logger.info("✅ Khởi tạo ChapterRegenerator thành công")
    
    async def regenerate_with_feedback(
        self,
        chapter: Chapter,
        analysis: Optional[PlotAnalysis],
        regenerate_request: ChapterRegenerateRequest,
        project_context: Dict[str, Any],
        style_content: str = "",
        user_id: str = None,
        db: AsyncSession = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Tái sinh chương theo feedback (streaming)
        
        Args:
            chapter: object chương gốc
            analysis: kết quả phân tích (tùy chọn)
            regenerate_request: tham số request tái sinh
            project_context: context project (thông tin project, nhân vật, dàn ý, v.v.)
            style_content: phong cách viết
            user_id: ID người dùng (để lấy prompt tùy chỉnh)
            db: session database (để truy vấn prompt tùy chỉnh)
        
        Yields:
            dict chứa loại và dữ liệu: {'type': 'progress'/'chunk', 'data':...}
        """
        try:
            logger.info(f"🔄 Bắt đầu tái sinh chương: chương {chapter.chapter_number}")
            
            # 1. Xây dựng chỉ thị chỉnh sửa
            yield {'type': 'progress', 'progress': 5, 'message': 'Đang xây dựng chỉ thị chỉnh sửa...'}
            modification_instructions = self._build_modification_instructions(
                analysis=analysis,
                regenerate_request=regenerate_request
            )
            
            logger.info(f"📝 Xây dựng chỉ thị chỉnh sửa hoàn tất, độ dài: {len(modification_instructions)} ký tự")
            
            # 2. Xây dựng prompt đầy đủ
            yield {'type': 'progress', 'progress': 10, 'message': 'Đang xây dựng prompt sinh...'}
            full_prompt = await self._build_regeneration_prompt(
                chapter=chapter,
                modification_instructions=modification_instructions,
                project_context=project_context,
                regenerate_request=regenerate_request,
                style_content=style_content,
                user_id=user_id,
                db=db
            )

            logger.info(f"🎯 Xây dựng prompt hoàn tất, bắt đầu sinh bằng AI")
            yield {'type': 'progress', 'progress': 15, 'message': 'Bắt đầu sinh nội dung bằng AI...'}
            
            # 3. Xây dựng system prompt (tiêm phong cách viết)
            system_prompt_with_style = None
            if style_content:
                system_prompt_with_style = f"""【🎨 Yêu cầu về phong cách viết - ưu tiên cao nhất】

{style_content}

⚠️ Vui lòng tuân thủ nghiêm ngặt các yêu cầu phong cách viết trên khi viết lại, đây là chỉ thị quan trọng nhất!
Đảm bảo luôn giữ sự nhất quán của phong cách trong suốt quá trình viết lại chương."""
                logger.info(f"✅ Đã tiêm phong cách viết vào system prompt ({len(style_content)} ký tự)")
            
            # 4. Sinh streaming nội dung mới, đồng thời theo dõi tiến trình
            target_word_count = regenerate_request.target_word_count
            accumulated_length = 0
            
            async for chunk in self.ai_service.generate_text_stream(
                prompt=full_prompt,
                system_prompt=system_prompt_with_style,
                temperature=0.7
            ):
                # Gửi block nội dung
                yield {'type': 'chunk', 'content': chunk}
                
                # Cập nhật số từ tích lũy và tính tiến trình (15%-95%)
                accumulated_length += len(chunk)
                # Tiến trình bắt đầu từ 15%, kết thúc ở 95%, dành 5% cho hậu xử lý
                generation_progress = min(15 + (accumulated_length / target_word_count) * 80, 95)
                yield {'type': 'progress', 'progress': int(generation_progress), 'word_count': accumulated_length}
            
            logger.info(f"✅ Tái sinh chương hoàn tất, tổng cộng sinh {accumulated_length} từ")
            yield {'type': 'progress', 'progress': 100, 'message': 'Sinh hoàn tất'}
            
        except Exception as e:
            logger.error(f"❌ Tái sinh thất bại: {str(e)}", exc_info=True)
            raise
    
    def _build_modification_instructions(
        self,
        analysis: Optional[PlotAnalysis],
        regenerate_request: ChapterRegenerateRequest
    ) -> str:
        """Xây dựng chỉ thị chỉnh sửa"""
        
        instructions = []
        
        # Tiêu đề
        instructions.append("# Chỉ thị chỉnh sửa chương\n")
        
        # 1. Gợi ý từ phân tích
        if (analysis and 
            regenerate_request.selected_suggestion_indices and 
            analysis.suggestions):
            
            instructions.append("## 📋 Vấn đề cần cải thiện (từ phân tích AI):\n")
            for idx in regenerate_request.selected_suggestion_indices:
                if 0 <= idx < len(analysis.suggestions):
                    suggestion = analysis.suggestions[idx]
                    instructions.append(f"{idx + 1}. {suggestion}")
            instructions.append("")
        
        # 2. Chỉ thị tùy chỉnh của người dùng
        if regenerate_request.custom_instructions:
            instructions.append("## ✍️ Yêu cầu chỉnh sửa tùy chỉnh của người dùng:\n")
            instructions.append(regenerate_request.custom_instructions)
            instructions.append("")
        
        # 3. Hướng tối ưu trọng điểm
        if regenerate_request.focus_areas:
            instructions.append("## 🎯 Hướng tối ưu trọng điểm:\n")
            focus_map = {
                "pacing": "Kiểm soát nhịp độ - điều chỉnh tốc độ kể chuyện, tránh lê thê hoặc quá nhanh",
                "emotion": "Kết xuất cảm xúc - đào sâu biểu đạt cảm xúc nhân vật, tăng sức lay động",
                "description": "Miêu tả cảnh - làm giàu chi tiết môi trường, tăng cảm giác hình ảnh",
                "dialogue": "Chất lượng hội thoại - khiến hội thoại tự nhiên chân thực hơn, thúc đẩy cốt truyện",
                "conflict": "Cường độ xung đột - tăng cường mâu thuẫn xung đột, nâng cao kịch tính",
            }
            
            for area in regenerate_request.focus_areas:
                if area in focus_map:
                    instructions.append(f"- {focus_map[area]}")
            instructions.append("")
        
        # 4. Yêu cầu giữ lại
        if regenerate_request.preserve_elements:
            preserve = regenerate_request.preserve_elements
            instructions.append("## 🔒 Các yếu tố phải giữ lại:\n")
            
            if preserve.preserve_structure:
                instructions.append("- Giữ nguyên cấu trúc tổng thể và khung cốt truyện của chương gốc")
            
            if preserve.preserve_dialogues:
                instructions.append("- Phải giữ lại các hội thoại then chốt sau:")
                for dialogue in preserve.preserve_dialogues:
                    instructions.append(f"  * {dialogue}")
            
            if preserve.preserve_plot_points:
                instructions.append("- Phải giữ lại các điểm cốt truyện then chốt sau:")
                for plot in preserve.preserve_plot_points:
                    instructions.append(f"  * {plot}")
            
            if preserve.preserve_character_traits:
                instructions.append("- Giữ sự nhất quán về đặc điểm tính cách và mô thức hành vi của mọi nhân vật")
            
            instructions.append("")
        
        return "\n".join(instructions)
    
    async def _build_regeneration_prompt(
        self,
        chapter: Chapter,
        modification_instructions: str,
        project_context: Dict[str, Any],
        regenerate_request: ChapterRegenerateRequest,
        style_content: str = "",
        user_id: str = None,
        db: AsyncSession = None
    ) -> str:
        """Xây dựng prompt tái sinh đầy đủ"""
        # Dùng phương thức get_chapter_regeneration_prompt của PromptService
        # Phương thức này xử lý tải template tùy chỉnh và xây dựng prompt đầy đủ
        return await PromptService.get_chapter_regeneration_prompt(
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            word_count=chapter.word_count,
            content=chapter.content,
            modification_instructions=modification_instructions,
            project_context=project_context,
            style_content=style_content,
            target_word_count=regenerate_request.target_word_count,
            user_id=user_id,
            db=db
        )
    
    def calculate_content_diff(
        self,
        original_content: str,
        new_content: str
    ) -> Dict[str, Any]:
        """
        Tính sự khác biệt giữa hai phiên bản
        
        Returns:
            Thông tin thống kê sự khác biệt
        """
        # Thống kê cơ bản
        diff_stats = {
            'original_length': len(original_content),
            'new_length': len(new_content),
            'length_change': len(new_content) - len(original_content),
            'length_change_percent': round((len(new_content) - len(original_content)) / len(original_content) * 100, 2) if len(original_content) > 0 else 0
        }
        
        # Tính độ tương đồng
        similarity = difflib.SequenceMatcher(None, original_content, new_content).ratio()
        diff_stats['similarity'] = round(similarity * 100, 2)
        diff_stats['difference'] = round((1 - similarity) * 100, 2)
        
        # Thống kê đoạn văn
        original_paragraphs = [p for p in original_content.split('\n\n') if p.strip()]
        new_paragraphs = [p for p in new_content.split('\n\n') if p.strip()]
        diff_stats['original_paragraph_count'] = len(original_paragraphs)
        diff_stats['new_paragraph_count'] = len(new_paragraphs)
        
        return diff_stats


# Instance toàn cục
_regenerator_instance = None

def get_chapter_regenerator(ai_service: AIService) -> ChapterRegenerator:
    """Lấy instance bộ tái sinh chương"""
    global _regenerator_instance
    if _regenerator_instance is None:
        _regenerator_instance = ChapterRegenerator(ai_service)
    return _regenerator_instance