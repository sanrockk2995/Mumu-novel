"""Dịch vụ phân tích cốt truyện - Tự động phân tích các yếu tố hook, phục bút, xung đột của chương"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.logger import get_logger, safe_preview
import json
import re
import asyncio

logger = get_logger(__name__)

# Định nghĩa kiểu callback thử lại
OnRetryCallback = Callable[[int, int, int, str], Awaitable[None]]
# tham số: (Số lần thử lại hiện tại, Số lần thử lại tối đa, Số giây chờ, Nguyên nhân lỗi)


class PlotAnalyzer:
    """Trình phân tích cốt truyện - sử dụngAIPhân tích nội dung chương"""
    
    def __init__(self, ai_service: AIService):
        """
        Khởi tạo trình phân tích cốt truyện
        
        Args:
            ai_service: Thể hiện dịch vụ AI
        """
        self.ai_service = ai_service
        logger.info("✅ PlotAnalyzerkhởi tạothành công")
    
    async def analyze_chapter(
        self,
        chapter_number: int,
        title: str,
        content: str,
        word_count: int,
        user_id: str = None,
        db: AsyncSession = None,
        max_retries: int = 3,
        existing_foreshadows: Optional[List[Dict[str, Any]]] = None,
        on_retry: Optional[OnRetryCallback] = None,
        characters_info: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Phân tích nội dung một chương (kèm cơ chế thử lại)
        
        Args:
            chapter_number: Số chương
            title: tiêu đề chương
            content: Nội dung chương
            word_count: Số từ
            user_id: người dùngID(dùng để lấy prompt tùy chỉnh)
            db: Phiên cơ sở dữ liệu (dùng để truy vấn prompt tùy chỉnh)
            max_retries: Số lần thử lại tối đa, mặc định3lần
            existing_foreshadows: Danh sách phục bút đã gieo (dùng để khớp thu hồi)
            on_retry: Hàm callback khi thử lại, tham số là (Số lần thử lại hiện tại, Số lần thử lại tối đa, Số giây chờ, Nguyên nhân lỗi)
            characters_info: Văn bản thông tin nhân vật của dự án (dùng để khớp tên nhân vật)
        
        Returns:
            Dict kết quả phân tích,thất bạitrả vềNone
        """
        logger.info(f"🔍 Bắt đầu phân tíchChương {chapter_number}: {title}")
        
        # Nếu nội dung quá dài,cắt lấy8000từ(tránh vượt quátoken)
        analysis_content = content[:8000] if len(content) > 8000 else content
        
        # Lấy mẫu prompt tùy chỉnh
        try:
            if user_id and db:
                template = await PromptService.get_template("PLOT_ANALYSIS", user_id, db)
            else:
                # Hạ cấp về mẫu mặc định của hệ thống
                template = PromptService.PLOT_ANALYSIS
        except Exception as e:
            logger.warning(f"⚠️ Lấy mẫu prompt thất bại, dùng mẫu mặc định: {str(e)}")
            template = PromptService.PLOT_ANALYSIS
        
        # Định dạng danh sách phục bút đã có
        foreshadows_text = self._format_existing_foreshadows(existing_foreshadows)
        
        # Định dạng prompt
        prompt = PromptService.format_prompt(
            template,
            chapter_number=chapter_number,
            title=title,
            word_count=word_count,
            content=analysis_content,
            existing_foreshadows=foreshadows_text,
            characters_info=characters_info if characters_info else "(Tạm thời chưa có thông tin nhân vật)"
        )
        
        last_error = None
        logger.debug(f"Hoàn tất prompt phân tích chương: chapter_number={chapter_number}, prompt_length={len(prompt)}")
        for attempt in range(1, max_retries + 1):
            try:
                # gọiAITiến hành phân tích
                logger.info(f"  📡 gọiAIphân tích(Độ dài nội dung: {len(analysis_content)}từ, thử {attempt}/{max_retries})...")
                accumulated_text = ""
                
                try:
                    async for chunk in self.ai_service.generate_text_stream(
                        prompt=prompt,
                        temperature=0.3  # Giảm temperature để có đầu ra JSON ổn định hơn
                    ):
                        accumulated_text += chunk
                except asyncio.CancelledError:
                    raise
                except GeneratorExit:
                    # Phản hồi streaming bị gián đoạn
                    logger.warning(f"⚠️ Phản hồi streaming bị gián đoạn(GeneratorExit), đã tích lũy {len(accumulated_text)} ký tự")
                    # Nếu đã tích lũy đủ nội dung, tiếp tục thử phân tích
                    if len(accumulated_text) < 100:
                        raise Exception("Phản hồi streaming bị gián đoạn, nội dung không đủ")
                except Exception as stream_error:
                    logger.error(f"❌ Tạo streaming bị lỗi: {str(stream_error)}")
                    raise
                
                # Kiểm tra phản hồi có trống không
                if not accumulated_text or len(accumulated_text.strip()) < 10:
                    logger.warning(f"⚠️ AIPhản hồi trống hoặc quá ngắn(độ dài: {len(accumulated_text)}), thử {attempt}/{max_retries}")
                    last_error = "AIPhản hồi trống hoặc quá ngắn"
                    if attempt < max_retries:
                        wait_time = min(2 ** attempt, 10)
                        logger.info(f"  ⏳ chờ {wait_time} giây rồi thử lại...")
                        # Gọi callback thử lại, thông báo bên gọi đang thử lại
                        if on_retry:
                            try:
                                await on_retry(attempt, max_retries, wait_time, last_error)
                            except Exception as callback_error:
                                logger.warning(f"⚠️ Thực thi callback thử lại thất bại: {callback_error}")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ Chương {chapter_number}phân tíchthất bại: AIPhản hồi trống, đã đạt số lần thử lại tối đa")
                        return None
                
                # Trích xuất nội dung
                response_text = accumulated_text
                logger.debug(f"  Đã nhậnAIphản hồi, độ dài: {len(response_text)} ký tự")
                
                # phân tíchJSONkết quả
                analysis_result = self._parse_analysis_response(response_text)
                
                if analysis_result:
                    logger.info(f"✅ Chương {chapter_number}phân tíchhoàn thành (thử {attempt}/{max_retries})")
                    logger.info(f"  - hook: {len(analysis_result.get('hooks', []))}")
                    logger.info(f"  - phục bút: {len(analysis_result.get('foreshadows', []))}")
                    logger.info(f"  - điểm cốt truyện: {len(analysis_result.get('plot_points', []))}")
                    logger.info(f"  - Điểm tổng thể: {analysis_result.get('scores', {}).get('overall', 'N/A')}")
                    return analysis_result
                else:
                    # JSONPhân tích thất bại, thử lại
                    logger.warning(f"⚠️ JSONPhân tích thất bại, thử {attempt}/{max_retries}")
                    last_error = "JSONPhân tích thất bại"
                    if attempt < max_retries:
                        wait_time = min(2 ** attempt, 10)
                        logger.info(f"  ⏳ chờ {wait_time} giây rồi thử lại...")
                        # Gọi callback thử lại, thông báo bên gọi đang thử lại
                        if on_retry:
                            try:
                                await on_retry(attempt, max_retries, wait_time, last_error)
                            except Exception as callback_error:
                                logger.warning(f"⚠️ Thực thi callback thử lại thất bại: {callback_error}")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ Chương {chapter_number}phân tíchthất bại: JSONLỗi phân tích, đã đạt số lần thử lại tối đa")
                        return None
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Phân tích chương gặp ngoại lệ(thử {attempt}/{max_retries}): {last_error}")
                
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 10)
                    logger.info(f"  ⏳ chờ {wait_time} giây rồi thử lại...")
                    # Gọi callback thử lại, thông báo bên gọi đang thử lại
                    if on_retry:
                        try:
                            await on_retry(attempt, max_retries, wait_time, last_error)
                        except Exception as callback_error:
                            logger.warning(f"⚠️ Thực thi callback thử lại thất bại: {callback_error}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Chương {chapter_number}phân tíchthất bại: {last_error}, đã đạt số lần thử lại tối đa")
                    return None
        
        # Không nên tới đây, nhưng như một biện pháp an toàn
        logger.error(f"❌ Chương {chapter_number}phân tíchthất bại: {last_error}")
        return None
    
    def _format_existing_foreshadows(self, foreshadows: Optional[List[Dict[str, Any]]]) -> str:
        """
        Định dạng danh sách phục bút đã gieo, dùng để tiêm vào prompt phân tích
        
        Chiến lược cốt lõi (bản tái cấu trúc):
        - Hiển thị phân tầng mọi phục bút đã gieo, đểAIcó thể nhận biết"thu hồi tự nhiên"
        - Tầng 1: phục bút phải thu hồi trong chương này (chi tiết nhất)
        - Tầng 2: phục bút quá hạn (chi tiết hơn)
        - Tầng 3: các phục bút đã gieo khác (thông tin rút gọn, để AI phán đoán đã thu hồi tự nhiên hay chưa)
        
        Args:
            foreshadows: Danh sách phục bút, mỗi mục chứa id, title, content, plant_chapter_number, resolve_status v.v.
        
        Returns:
            Văn bản đã định dạng
        """
        if not foreshadows:
            return "(Tạm thời chưa có phục bút nào được gieo)"
        
        # Phân loại phục bút
        must_resolve = [fs for fs in foreshadows if fs.get('resolve_status') == 'must_resolve_now']
        overdue = [fs for fs in foreshadows if fs.get('resolve_status') == 'overdue']
        others = [fs for fs in foreshadows if fs.get('resolve_status') not in ('must_resolve_now', 'overdue')]
        
        lines = []
        
        # === Tầng 1: phục bút phải thu hồi trong chương này (chi tiết nhất) ===
        if must_resolve:
            lines.append("=" * 40)
            lines.append("[🎯 Phục bút phải thu hồi trong chương này]")
            lines.append("=" * 40)
            for i, fs in enumerate(must_resolve, 1):
                fs_id = fs.get('id', 'unknown')
                fs_title = fs.get('title', 'Phục bút chưa đặt tên')
                fs_content = fs.get('content', '')[:200]
                plant_chapter = fs.get('plant_chapter_number', '?')
                hint_text = fs.get('hint_text', '')
                
                lines.append(f"{i}. [ID: {fs_id}]{fs_title}")
                lines.append(f"   Chương gieo: chương {plant_chapter}")
                lines.append(f"   Nội dung phục bút:{fs_content}{'...' if len(fs.get('content', '')) > 200 else ''}")
                if hint_text:
                    lines.append(f"   Gợi ý gieo:{hint_text[:100]}")
                lines.append(f"   ⚠️ Khi thu hồi, điền reference_foreshadow_id: {fs_id}")
                lines.append("")
        
        # === Tầng 2: phục bút quá hạn ===
        if overdue:
            lines.append("[⚠️ Phục bút quá hạn chưa thu hồi - nếu nội dung chương đã thu hồi thì đánh dấu]")
            for fs in overdue[:5]:
                fs_id = fs.get('id', 'unknown')
                fs_title = fs.get('title', '')
                plant_chapter = fs.get('plant_chapter_number', '?')
                lines.append(f"- [ID: {fs_id}]{fs_title} (chương {plant_chapter} gieo)")
            lines.append("")
        
        # === Tầng 3: các phục bút đã gieo khác (rút gọn) ===
        if others:
            lines.append("[📋 Các phục bút đã gieo khác - nếu nội dung chương đã thu hồi tự nhiên thì đánh dấu]")
            for fs in others[:10]:
                fs_id = fs.get('id', 'unknown')
                fs_title = fs.get('title', '')
                plant_chapter = fs.get('plant_chapter_number', '?')
                lines.append(f"- [ID: {fs_id}]{fs_title} (chương {plant_chapter} gieo)")
            if len(others) > 10:
                lines.append(f"  ... Còn {len(others) - 10} phục bút chưa liệt kê")
            lines.append("")
        
        # Hướng dẫn thao tác
        lines.append("Gợi ý: nếu nội dung chương đã thu hồi bất kỳ phục bút nào ở trên, trong foreshadows mảng")
        lines.append("Thêm bản ghi type='resolved', và điền ID tương ứng trong reference_foreshadow_id.")
        
        return "\n".join(lines)
    
    def _parse_analysis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        phân tíchAIKết quả phân tích trả về (dùngJSONphương thức làm sạch thống nhất)
        
        Args:
            response: AIVăn bản trả về
        
        Returns:
            Dict sau phân tích,thất bạitrả vềNone
        """
        try:
            # Dùng phương thức làm sạch JSON thống nhất
            cleaned = self.ai_service._clean_json_response(response)
            
            # Thử phân tíchJSON
            result = loads_json(cleaned)
            
            # Xác thực các trường bắt buộc
            required_fields = ['hooks', 'plot_points', 'scores']
            for field in required_fields:
                if field not in result:
                    logger.warning(f"⚠️ Kết quả phân tích thiếu trường: {field}")
                    result[field] = [] if field != 'scores' else {}
            
            logger.info("✅ Phân tích kết quả phân tích thành công")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSONPhân tích thất bại: {str(e)}")
            logger.error(f"  Xem trước phản hồi gốc: {safe_preview(response, 200)}")
            return None
        except Exception as e:
            logger.error(f"❌ Phân tích gặp ngoại lệ: {str(e)}")
            return None
    
    def extract_memories_from_analysis(
        self,
        analysis: Dict[str, Any],
        chapter_id: str,
        chapter_number: int,
        chapter_content: str = "",
        chapter_title: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Trích xuất đoạn ký ức từ kết quả phân tích
        
        Args:
            analysis: phân tíchkết quả
            chapter_id: chươngID
            chapter_number: Số chương
            chapter_content: Nội dung đầy đủ của chương(dùng để tính vị trí)
            chapter_title: tiêu đề chương
        
        Returns:
            Danh sách đoạn ký ức
        """
        memories = []
        
        try:
            # [mới]0. Trích xuất tóm tắt chương làm ký ức (dùng để truy xuất ngữ nghĩa các chương liên quan)
            chapter_summary = ""
            
            # Thử lấy tóm tắt từ kết quả phân tích
            if analysis.get('summary'):
                chapter_summary = analysis.get('summary')
            # hoặc tạo tóm tắt từ việc kết hợp các điểm cốt truyện
            elif analysis.get('plot_points'):
                plot_summaries = [p.get('content', '') for p in analysis.get('plot_points', [])[:3]]
                chapter_summary = ";".join(plot_summaries)
            # hoặc dùng300từ
            elif chapter_content:
                chapter_summary = chapter_content[:300] + ("..." if len(chapter_content) > 300 else "")
            
            # Nếu có tóm tắt, thêm vào ký ức
            if chapter_summary:
                memories.append({
                    'type': 'chapter_summary',
                    'content': chapter_summary,
                    'title': f"Chương {chapter_number}«{chapter_title}»tóm tắt",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': 0.6,  # Mức quan trọng trung bình
                        'tags': ['tóm tắt', 'Tổng quan chương', chapter_title],
                        'is_foreshadow': 0,
                        'text_position': 0,
                        'text_length': len(chapter_summary)
                    }
                })
                logger.info(f"  ✅ Thêm ký ức tóm tắt chương: {len(chapter_summary)}từ")
            
            # 1. Trích xuất hook làm ký ức
            for i, hook in enumerate(analysis.get('hooks', [])):
                if hook.get('strength', 0) >= 6:  # Chỉ lưu hook có cường độ>=6
                    keyword = hook.get('keyword', '')
                    position, length = self._find_text_position(chapter_content, keyword)
                    
                    logger.info(f"  Vị trí hook: keyword='{keyword[:30]}...', pos={position}, len={length}")
                    
                    memories.append({
                        'type': 'hook',
                        'content': f"[{hook.get('type', 'không rõ')}hook] {hook.get('content', '')}",
                        'title': f"{hook.get('type', 'hook')} - {hook.get('position', '')}",
                        'metadata': {
                            'chapter_id': chapter_id,
                            'chapter_number': chapter_number,
                            'importance_score': min(hook.get('strength', 5) / 10, 1.0),
                            'tags': [hook.get('type', 'hook'), hook.get('position', '')],
                            'is_foreshadow': 0,
                            'keyword': keyword,
                            'text_position': position,
                            'text_length': length,
                            'strength': hook.get('strength', 5),
                            'position_desc': hook.get('position', '')
                        }
                    })
            
            # 2. Trích xuất phục bút làm ký ức
            for i, foreshadow in enumerate(analysis.get('foreshadows', [])):
                is_planted = foreshadow.get('type') == 'planted'
                keyword = foreshadow.get('keyword', '')
                position, length = self._find_text_position(chapter_content, keyword)
                
                logger.info(f"  Vị trí phục bút: keyword='{keyword[:30]}...', pos={position}, len={length}")
                
                memories.append({
                    'type': 'foreshadow',
                    'content': foreshadow.get('content', ''),
                    'title': f"{'Gieo phục bút' if is_planted else 'Thu hồi phục bút'}",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': min(foreshadow.get('strength', 5) / 10, 1.0),
                        'tags': ['phục bút', foreshadow.get('type', 'planted')],
                        'is_foreshadow': 1 if is_planted else 2,
                        'reference_chapter': foreshadow.get('reference_chapter'),
                        'keyword': keyword,
                        'text_position': position,
                        'text_length': length,
                        'foreshadow_type': foreshadow.get('type', 'planted'),
                        'strength': foreshadow.get('strength', 5)
                    }
                })
            
            # 3. Trích xuất các điểm cốt truyện then chốt
            for i, plot_point in enumerate(analysis.get('plot_points', [])):
                if plot_point.get('importance', 0) >= 0.6:  # Chỉ lưu các điểm cốt truyện có mức quan trọng>=0.6
                    keyword = plot_point.get('keyword', '')
                    position, length = self._find_text_position(chapter_content, keyword)
                    
                    logger.info(f"  Vị trí điểm cốt truyện: keyword='{keyword[:30]}...', pos={position}, len={length}")
                    
                    memories.append({
                        'type': 'plot_point',
                        'content': f"{plot_point.get('content', '')}. Ảnh hưởng: {plot_point.get('impact', '')}",
                        'title': f"điểm cốt truyện - {plot_point.get('type', 'không rõ')}",
                        'metadata': {
                            'chapter_id': chapter_id,
                            'chapter_number': chapter_number,
                            'importance_score': plot_point.get('importance', 0.5),
                            'tags': ['điểm cốt truyện', plot_point.get('type', 'không rõ')],
                            'is_foreshadow': 0,
                            'keyword': keyword,
                            'text_position': position,
                            'text_length': length
                        }
                    })
            
            # 4. Trích xuất thay đổi trạng thái nhân vật
            for i, char_state in enumerate(analysis.get('character_states', [])):
                char_name = char_state.get('character_name', 'Nhân vật không rõ')
                memories.append({
                    'type': 'character_event',
                    'content': f"Thay đổi trạng thái của {char_name}: {char_state.get('state_before', '')} → {char_state.get('state_after', '')}. {char_state.get('psychological_change', '')}",
                    'title': f"Thay đổi của {char_name}",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': 0.7,
                        'tags': ['nhân vật', char_name, 'thay đổi trạng thái'],
                        'related_characters': [char_name],
                        'is_foreshadow': 0
                    }
                })
            
            # 5. Nếu có xung đột quan trọng,cũng ghi lại
            conflict = analysis.get('conflict', {})
            
            if conflict and conflict.get('level', 0) >= 7:
                # Đảm bảo parties và types đều là danh sách chuỗi
                parties = conflict.get('parties', [])
                if parties and isinstance(parties, list):
                    parties = [str(p) for p in parties]
                
                types = conflict.get('types', [])
                if types and isinstance(types, list):
                    types = [str(t) for t in types]
                
                memories.append({
                    'type': 'plot_point',
                    'content': f"Xung đột quan trọng: {conflict.get('description', '')}. Các bên xung đột: {', '.join(parties)}",
                    'title': f"xung đột - cường độ{conflict.get('level', 0)}",
                    'metadata': {
                        'chapter_id': chapter_id,
                        'chapter_number': chapter_number,
                        'importance_score': min(conflict.get('level', 5) / 10, 1.0),
                        'tags': ['xung đột'] + types,
                        'is_foreshadow': 0
                    }
                })
            
            logger.info(f"📝 Đã trích xuất {len(memories)} ký ức từ phân tích")
            return memories
            
        except Exception as e:
            logger.error(f"❌ Trích xuất ký ức thất bại: {str(e)}")
            return []
    
    def _find_text_position(self, full_text: str, keyword: str) -> tuple[int, int]:
        """
        Tìm vị trí từ khóa trong toàn văn
        
        Args:
            full_text: Văn bản đầy đủ
            keyword: từ khóa
        
        Returns:
            (vị trí bắt đầu, độ dài) Trả về (-1, 0) nếu không tìm thấy
        """
        if not keyword or not full_text:
            return (-1, 0)
        
        try:
            # 1. Khớp chính xác
            pos = full_text.find(keyword)
            if pos != -1:
                return (pos, len(keyword))
            
            # 2. Khớp sau khi loại bỏ dấu câu
            import re
            clean_keyword = re.sub(r'[，。！？、；：""''（）《》【】]', '', keyword)
            clean_text = re.sub(r'[，。！？、；：""''（）《》【】]', '', full_text)
            pos = clean_text.find(clean_keyword)
            
            if pos != -1:
                # Ánh xạ ngược về vị trí văn gốc (xử lý đơn giản hóa)
                return (pos, len(clean_keyword))
            
            # 3. Khớp mờ: tìm nửa đầu của từ khóa
            if len(keyword) > 10:
                partial = keyword[:min(15, len(keyword))]
                pos = full_text.find(partial)
                if pos != -1:
                    return (pos, len(partial))
            
            # 4. Không tìm thấy
            logger.debug(f"Không tìm thấy vị trí từ khóa: {keyword[:30]}...")
            return (-1, 0)
            
        except Exception as e:
            logger.error(f"Tìm vị trí thất bại: {str(e)}")
            return (-1, 0)
    
    def generate_analysis_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Tạo văn bản tóm tắt phân tích
        
        Args:
            analysis: phân tíchkết quả
        
        Returns:
            Văn bản tóm tắt đã định dạng
        """
        try:
            lines = ["=== Báo cáo phân tích chương ===\n"]
            
            # Điểm tổng thể
            scores = analysis.get('scores', {})
            lines.append(f"[Điểm tổng thể]")
            lines.append(f"  Chất lượng tổng thể: {scores.get('overall', 'N/A')}/10")
            lines.append(f"  Kiểm soát nhịp độ: {scores.get('pacing', 'N/A')}/10")
            lines.append(f"  Sức hấp dẫn: {scores.get('engagement', 'N/A')}/10")
            lines.append(f"  Tính liên tục: {scores.get('coherence', 'N/A')}/10\n")
            
            # Giai đoạn cốt truyện
            lines.append(f"[Giai đoạn cốt truyện]{analysis.get('plot_stage', 'không rõ')}\n")
            
            # Thống kê hook
            hooks = analysis.get('hooks', [])
            if hooks:
                lines.append(f"[Phân tích hook]tổng{len(hooks)}")
                for hook in hooks[:3]:  # chỉ hiển thị3
                    lines.append(f"  • [{hook.get('type')}] {hook.get('content', '')[:50]}... (cường độ:{hook.get('strength', 0)})")
                lines.append("")
            
            # Thống kê phục bút
            foreshadows = analysis.get('foreshadows', [])
            if foreshadows:
                planted = sum(1 for f in foreshadows if f.get('type') == 'planted')
                resolved = sum(1 for f in foreshadows if f.get('type') == 'resolved')
                lines.append(f"[Phân tích phục bút]Đã gieo{planted}, đã thu hồi{resolved}\n")
            
            # Phân tích xung đột
            conflict = analysis.get('conflict', {})
            if conflict:
                lines.append(f"[Phân tích xung đột]")
                lines.append(f"  loại: {', '.join(conflict.get('types', []))}")
                lines.append(f"  cường độ: {conflict.get('level', 0)}/10")
                lines.append(f"  tiến độ: {int(conflict.get('resolution_progress', 0) * 100)}%\n")
            
            # Gợi ý cải thiện
            suggestions = analysis.get('suggestions', [])
            if suggestions:
                lines.append(f"[Gợi ý cải thiện]")
                for i, sug in enumerate(suggestions, 1):
                    lines.append(f"  {i}. {sug}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"❌ Tạo tóm tắt thất bại: {str(e)}")
            return "Tạo tóm tắt phân tích thất bại"


# Tạo thể hiện toàn cục(Khởi tạo thủ công khi cần)
_plot_analyzer_instance = None

def get_plot_analyzer(ai_service: AIService) -> PlotAnalyzer:
    """Lấy thể hiện trình phân tích cốt truyện"""
    global _plot_analyzer_instance
    if _plot_analyzer_instance is None:
        _plot_analyzer_instance = PlotAnalyzer(ai_service)
    return _plot_analyzer_instance
