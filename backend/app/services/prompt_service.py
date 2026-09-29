"""Dịch vụ quản lý prompt"""
from typing import Dict, Any, Optional
import json
from app.services.skill_loader import get_all_skills_cached


class WritingStyleManager:
    """Trình quản lý phong cách viết"""
    
    @staticmethod
    def apply_style_to_prompt(base_prompt: str, style_content: str) -> str:
        """
        Áp dụng phong cách viết vào prompt cơ sở
        
        Lưu ý: phong cách viết đã được chèn qua system_prompt (system_prompt_with_style),
        phương thức này chỉ thêm chỉ dẫn đầu ra, không chèn lại style_content, tránh thông tin phong cách bị chèn hai lần.
        
        Args:
            base_prompt: prompt cơ sở
            style_content: nội dung yêu cầu phong cách (đã chèn qua system_prompt, không dùng ở đây)
            
        Returns:
            prompt sau khi đã thêm chỉ dẫn đầu ra
        """
        # Phong cách viết đã được chèn trong system_prompt, ở đây chỉ thêm chỉ dẫn định dạng đầu ra
        return f"{base_prompt}\n\nHãy xuất trực tiếp nội dung chính văn của chương, không bao gồm tiêu đề chương và các văn bản giải thích khác."


class PromptService:
    """Quản lý template prompt"""

    NOVEL_COVER_PROMPT_TEMPLATE = """Vẽ một minh họa bìa tiểu thuyết chất lượng cao, phù hợp cho bìa sách dọc.

Tiêu đề tiểu thuyết là: "{title}".
Thể loại là {genre}. Chủ đề cốt lõi là {theme}. Tóm tắt câu chuyện như sau: {description}

Hình ảnh cần mang cảm giác điện ảnh, tinh tế, giàu không khí và sức biểu cảm cảm xúc, với tiêu điểm thị giác rõ ràng và hình tượng tượng trưng mạnh mẽ. Hãy ưu tiên thể hiện cách kể chuyện bằng hình ảnh và cảm xúc phù hợp với thể loại tiểu thuyết, thay vì mô tả cứng nhắc các cảnh cụ thể.

Bức ảnh phải trông như một bìa chuyên nghiệp theo phong cách tiểu thuyết mạng hoặc ấn phẩm xuất bản.

Yêu cầu bắt buộc:
- Phải có chữ tiêu đề tiểu thuyết "{title}" ở vị trí nổi bật trong hình, cách trình bày chữ phải cực kỳ nghệ thuật và hòa hợp hoàn hảo với phong cách thể loại {genre} của tiểu thuyết.
- Bố cục dọc phù hợp với bìa tiểu thuyết tiêu chuẩn (tỷ lệ 2:3).
- Trong hình chỉ được xuất hiện chữ tiêu đề, tuyệt đối không được có tên tác giả, phụ đề hoặc các ký tự ngẫu nhiên không liên quan khác.
- Không logo (Logo).
- Không watermark.
- Không viền.
- Không có yếu tố UI.
- Không hiệu ứng trình diễn mẫu (Mockup).

Hình ảnh cuối cùng phải là một tác phẩm nghệ thuật bìa sách hoàn chỉnh, chuyên nghiệp, trong đó minh họa nền và cách trình bày tiêu đề phải bổ trợ lẫn nhau."""

    @classmethod
    async def build_novel_cover_prompt(
        cls,
        project: Any,
        user_id: str = None,
        db = None,
    ) -> str:
        """Xây dựng prompt bìa tiểu thuyết dựa trên thông tin cơ bản của dự án, hỗ trợ template tùy chỉnh của người dùng"""
        title = (getattr(project, "title", "") or "Tiểu thuyết chưa đặt tên").strip()
        genre = (getattr(project, "genre", "") or "Chưa chỉ định thể loại").strip()
        theme = (getattr(project, "theme", "") or "Chưa chỉ định chủ đề").strip()
        description = (getattr(project, "description", "") or "Không có giới thiệu thêm").strip()

        compact_description = description[:300]
        template = await cls.get_template_with_fallback(
            "NOVEL_COVER_PROMPT_TEMPLATE",
            user_id=user_id,
            db=db,
        )
        return template.format(
            title=title,
            genre=genre,
            theme=theme,
            description=compact_description,
        )
    
    # ========== Template prompt phiên bản V2 (khung RTCO) ==========
    
    # Prompt xây dựng thế giới V2 (khung RTCO)
    WORLD_BUILDING = """<system>
Bạn là nhà thiết kế thế giới quan dày dặn kinh nghiệm, chuyên xây dựng thế giới quan chân thực, nhất quán cho tiểu thuyết thể loại {genre}.
</system>

<task>
【Nhiệm vụ thiết kế】
Xây dựng thiết lập thế giới quan hoàn chỉnh cho tiểu thuyết “{title}”.

【Yêu cầu cốt lõi】
- Phù hợp chủ đề: thế giới quan phải làm nền cho chủ đề “{theme}”
- Khớp với giới thiệu: tạo bối cảnh hợp lý cho tình tiết trong phần giới thiệu
- Tương thích thể loại: phù hợp đặc trưng của thể loại {genre}
- Quy mô phù hợp: chọn quy mô thiết lập phù hợp theo đề tài
</task>

<input priority="P0">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}
Giới thiệu: {description}
</input>

<guidelines priority="P1">
【Nguyên tắc định hướng theo thể loại】

**Đô thị hiện đại/Ngôn tình/Thanh xuân**:
- Thời gian: xã hội đương đại (thập niên 2020) hoặc tương lai gần (2030-2050)
- Tránh: các khái niệm hoành tráng như đại sụp đổ, kỷ nguyên, tận thế
- Trọng tâm: môi trường thành phố cụ thể, văn hóa công sở, hiện trạng xã hội

**Lịch sử/Cổ đại**:
- Thời gian: triều đại lịch sử rõ ràng hoặc thời cổ đại hư cấu
- Trọng tâm: đặc trưng thời đại, chế độ lễ giáo, phân tầng giai cấp

**Huyền huyễn/Tiên hiệp/Tu chân**:
- Thời gian: giai đoạn cụ thể của nền văn minh tu luyện
- Trọng tâm: quy tắc tu luyện, môi trường linh khí, thế lực môn phái

**Khoa học viễn tưởng**:
- Thời gian: thời kỳ tương lai rõ ràng (như năm 2150, giai đoạn đầu thời đại liên sao)
- Trọng tâm: trình độ công nghệ, hình thái xã hội, bước ngoặt văn minh

**Kỳ ảo/Phép thuật**:
- Thời gian: giai đoạn cụ thể của nền văn minh phép thuật
- Trọng tâm: hệ thống phép thuật, quan hệ các chủng tộc, cục diện đại lục

**Kiểm soát quy mô thiết lập**:
- Đô thị hiện đại: tập trung vào một thành phố, ngành nghề, tầng lớp cụ thể
- Thanh xuân học đường: môi trường trường học, đời sống học sinh, khó khăn trưởng thành
- Ngôn tình công sở: văn hóa công ty, đặc điểm ngành nghề, áp lực nghề nghiệp
- Đề tài sử thi: mới cần kiến trúc thế giới quan hoành tráng
</guidelines>

<output priority="P0">
【Định dạng đầu ra】
Tạo đối tượng JSON gồm bốn trường sau, mỗi trường 300-500 chữ:

1. **time_period** (Bối cảnh thời gian và trạng thái xã hội)
   - Thiết lập bối cảnh thời gian có quy mô phù hợp theo thể loại
   - Đề tài hiện đại: đặc trưng xã hội cụ thể (như: Bắc Kinh năm 2024, ngành internet phát triển tốc độ cao)
   - Đề tài lịch sử: triều đại và giai đoạn rõ ràng (như: thời Gia Tĩnh nhà Minh, vùng duyên hải dưới chính sách cấm biển)
   - Đề tài giả tưởng: giai đoạn phát triển của nền văn minh, cụ thể chứ không chung chung
   - Làm rõ mâu thuẫn cốt lõi của thời đại và nỗi lo xã hội

2. **location** (Môi trường không gian và đặc trưng địa lý)
   - Môi trường không gian nơi câu chuyện chủ yếu diễn ra
   - Đề tài hiện đại: tên thành phố hoặc loại hình cụ thể
   - Môi trường ảnh hưởng thế nào đến cách sinh tồn của cư dân
   - Mô tả khung cảnh mang tính biểu tượng

3. **atmosphere** (Trải nghiệm giác quan và tông cảm xúc)
   - Chi tiết giác quan sống động như thật (thị giác, thính giác, khứu giác)
   - Phong cách thẩm mỹ và tông màu chủ đạo
   - Trạng thái tâm lý của cư dân và bầu không khí cảm xúc
   - Cộng hưởng cảm xúc với chủ đề

4. **rules** (Quy tắc thế giới và cấu trúc xã hội)
   - Quy luật cốt lõi vận hành thế giới
   - Đề tài hiện đại: quy tắc xã hội, luật ngầm trong ngành, quy luật ứng xử giữa người với người
   - Đề tài giả tưởng: hệ thống sức mạnh, đẳng cấp xã hội, phân phối tài nguyên
   - Cấu trúc quyền lực và cục diện lợi ích
   - Điều cấm kỵ của xã hội và hậu quả

【Quy chuẩn định dạng】
- Đầu ra JSON thuần túy, bắt đầu bằng {{ và kết thúc bằng}}
- Không có đánh dấu markdown, ký hiệu khối mã
- Giá trị trường là văn bản đoạn đầy đủ
- Không dùng ký hiệu đặc biệt để bao bọc nội dung
- Cung cấp nội dung gốc, đầy đặn

【Ví dụ JSON】
{{
  "time_period": "Mô tả chi tiết bối cảnh thời gian và trạng thái xã hội (300-500 chữ)",
  "location": "Mô tả chi tiết môi trường không gian và đặc trưng địa lý (300-500 chữ)",
  "atmosphere": "Mô tả chi tiết trải nghiệm giác quan và tông cảm xúc (300-500 chữ)",
  "rules": "Mô tả chi tiết quy tắc thế giới và cấu trúc xã hội (300-500 chữ)"
}}
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Khớp với giới thiệu: tạo bối cảnh hợp lý cho tình tiết trong phần giới thiệu
✅ Tương thích thể loại: phù hợp đặc trưng của {genre}
✅ Bám sát chủ đề: làm nền cho chủ đề “{theme}”
✅ Cụ thể hóa: dùng chi tiết cụ thể thay vì khái niệm rỗng
✅ Logic nhất quán: mọi thiết lập hỗ trợ lẫn nhau

【Những điều cấm】
❌ Tạo thiết lập không khớp với thể loại
❌ Dùng thế giới quan hoành tráng cho đề tài quy mô nhỏ
❌ Dùng cách diễn đạt theo mẫu, rỗng tuếch
❌ Xuất đánh dấu markdown hoặc ký hiệu khối mã
</constraints>"""

    # Prompt tạo hàng loạt nhân vật V2 (khung RTCO)
    CHARACTERS_BATCH_GENERATION = """<system>
Bạn là chuyên gia thiết lập nhân vật, giỏi tạo ra những nhân vật sống động, đầy đặn cho tiểu thuyết thể loại {genre}.
</system>

<task>
【Nhiệm vụ tạo mới】
Tạo {count} nhân vật và thực thể tổ chức.

【Yêu cầu số lượng - tuân thủ nghiêm ngặt】
Mảng phải chứa chính xác {count} đối tượng, không thừa không thiếu.

【Phân bổ loại thực thể】
- Ít nhất 1 nhân vật chính (protagonist)
- Nhiều nhân vật phụ (supporting)
- Có thể có phản diện (antagonist)
- Có thể có 1-2 tổ chức ảnh hưởng lớn (power_level: 70-95)
</task>

<worldview priority="P0">
【Thông tin thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}

Chủ đề: {theme}
Thể loại: {genre}
</worldview>

<requirements priority="P1">
【Yêu cầu đặc biệt】
{requirements}
</requirements>

<output priority="P0">
【Định dạng đầu ra】
Trả về mảng JSON thuần túy, mỗi đối tượng gồm:

**Đối tượng nhân vật**:
{{
  "name": "Tên nhân vật",
  "age": 25,
  "gender": "Nam/Nữ/Khác",
  "is_organization": false,
  "role_type": "protagonist/supporting/antagonist",
  "personality": "Đặc điểm tính cách (100-200 chữ): tính cách cốt lõi, ưu nhược điểm, thói quen đặc biệt",
  "background": "Câu chuyện nền (100-200 chữ): bối cảnh gia đình, quá trình trưởng thành, bước ngoặt quan trọng",
  "appearance": "Mô tả ngoại hình (50-100 chữ): chiều cao, vóc dáng, khuôn mặt, phong cách ăn mặc",
  "traits": ["Sở trường 1", "Sở trường 2", "Sở trường 3"],
  "relationships_array": [
    {{
      "target_character_name": "Tên nhân vật đã tạo",
      "relationship_type": "Loại quan hệ",
      "intimacy_level": 75,
      "description": "Mô tả quan hệ"
    }}
  ],
  "organization_memberships": [
    {{
      "organization_name": "Tên tổ chức đã tạo",
      "position": "Chức vụ",
      "rank": 5,
      "loyalty": 80
    }}
  ]
}}

**Đối tượng tổ chức**:
{{
  "name": "Tên tổ chức",
  "is_organization": true,
  "role_type": "supporting",
  "personality": "Đặc tính tổ chức (100-200 chữ): cách vận hành, tư tưởng cốt lõi, phong cách hành sự",
  "background": "Bối cảnh tổ chức (100-200 chữ): lịch sử thành lập, quá trình phát triển, sự kiện quan trọng",
  "appearance": "Biểu hiện bên ngoài (50-100 chữ): vị trí trụ sở, kiến trúc biểu tượng",
  "organization_type": "Loại hình tổ chức",
  "organization_purpose": "Mục đích tổ chức",
  "organization_members": ["Thành viên 1", "Thành viên 2"],
  "power_level": 85,
  "location": "Nơi đặt trụ sở hoặc khu vực hoạt động chính",
  "motto": "Châm ngôn, khẩu hiệu hoặc tôn chỉ của tổ chức",
  "color": "Màu đại diện",
  "traits": []
}}

【Tham khảo loại quan hệ】
- Gia đình: cha, mẹ, anh em trai, chị em gái, con cái, vợ/chồng, người yêu
- Xã hội: sư phụ, đồ đệ, bạn bè, bạn học, đồng nghiệp, hàng xóm, tri kỷ
- Nghề nghiệp: cấp trên, cấp dưới, đối tác
- Đối địch: kẻ thù, thù nhân, đối thủ cạnh tranh, tử địch

【Phạm vi giá trị số】
- intimacy_level: -100 đến 100 (giá trị âm biểu thị đối địch)
- loyalty: 0 đến 100
- rank: 0 đến 10 (cấp bậc chức vụ)
- power_level: 70 đến 95 (mức ảnh hưởng của tổ chức)
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Số lượng chính xác: mảng phải chứa {count} đối tượng
✅ Phù hợp thế giới quan: thiết lập nhân vật nhất quán với thế giới quan
✅ Có chiều sâu: tính cách và bối cảnh phải sống động
✅ Mạng lưới quan hệ: các nhân vật hình thành quan hệ hợp lý với nhau
✅ Tổ chức hợp lý: tổ chức là lực lượng then chốt thúc đẩy cốt truyện

【Ràng buộc quan hệ】
✅ relationships_array chỉ được tham chiếu các nhân vật đã xuất hiện trong đợt này
✅ organization_memberships chỉ được tham chiếu các tổ chức trong đợt này
✅ relationships_array của nhân vật đầu tiên phải là mảng rỗng []
✅ Cấm ảo giác: không tham chiếu nhân vật hoặc tổ chức không tồn tại

【Ràng buộc định dạng】
✅ Đầu ra mảng JSON thuần túy, không đánh dấu markdown
✅ Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung (dấu ngoặc kép, ngoặc vuông, dấu tên sách, v.v.)
✅ Danh từ riêng viết trực tiếp, không dùng ký hiệu bao bọc

【Những điều cấm】
❌ Số lượng tạo ra không khớp (nhiều hơn hoặc ít hơn {count})
❌ Tham chiếu nhân vật hoặc tổ chức không tồn tại
❌ Tạo tổ chức không đáng kể, ảnh hưởng thấp
❌ Dùng đánh dấu markdown hoặc ký hiệu khối mã
❌ Dùng ký hiệu đặc biệt trong mô tả
</constraints>"""

    # Prompt tạo dàn ý V2 (khung RTCO)
    OUTLINE_CREATE = """<system>
Bạn là nhà văn và biên kịch tiểu thuyết giàu kinh nghiệm, giỏi thiết kế phần mở đầu hấp dẫn cho tiểu thuyết thể loại {genre}.
</system>

<task>
【Nhiệm vụ sáng tác】
Tạo dàn ý cho {chapter_count} chương mở đầu của tiểu thuyết “{title}”.

【Lưu ý quan trọng】
Đây là phần mở đầu khi khởi tạo dự án, không phải dàn ý hoàn chỉnh:
- Hoàn thành thiết lập mở đầu và giới thiệu thế giới quan
- Giới thiệu các nhân vật chính, thiết lập quan hệ ban đầu
- Gieo mâu thuẫn cốt lõi và móc treo hồi hộp
- Đặt nền móng cho sự phát triển cốt truyện về sau
- Không cần khép kín hoàn toàn, để lại không gian viết tiếp
</task>

<project priority="P0">
【Thông tin dự án】
Tên sách: {title}
Chủ đề: {theme}
Thể loại: {genre}
Số chương mở đầu: {chapter_count}
Góc nhìn tự sự: {narrative_perspective}
</project>

<worldview priority="P1">
【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}
</worldview>

<characters priority="P1">
【Thông tin nhân vật】
{characters_info}
</characters>

<mcp_context priority="P2">
{mcp_references}
</mcp_context>

<requirements priority="P1">
【Yêu cầu khác】
{requirements}
</requirements>

<output priority="P0">
【Định dạng đầu ra】
Trả về mảng JSON gồm {chapter_count} đối tượng chương:

[
  {{
   "chapter_number": 1,
   "title": "Tiêu đề chương",
   "summary": "Tóm tắt chương (500-1000 chữ): tình tiết chính, tương tác nhân vật, sự kiện then chốt, xung đột và bước ngoặt",
   "scenes": ["Mô tả cảnh 1", "Mô tả cảnh 2", "Mô tả cảnh 3"],
   "characters": [
     {{"name": "Tên nhân vật 1", "type": "character"}},
     {{"name": "Tên tổ chức/thế lực 1", "type": "organization"}}
   ],
   "key_points": ["Điểm cốt truyện chính 1", "Điểm cốt truyện chính 2"],
   "emotion": "Tông cảm xúc của chương này",
   "goal": "Mục tiêu tự sự của chương này"
 }},
 {{
   "chapter_number": 2,
   "title": "Tiêu đề chương",
   "summary": "Tóm tắt chương...",
   "scenes": ["Cảnh 1", "Cảnh 2"],
   "characters": [
     {{"name": "Tên nhân vật 2", "type": "character"}},
     {{"name": "Tên tổ chức 2", "type": "organization"}}
   ],
   "key_points": ["Điểm chính 1", "Điểm chính 2"],
   "emotion": "Tông cảm xúc",
   "goal": "Mục tiêu tự sự"
 }}
]

【Giải thích trường characters】
- type là "character" nghĩa là nhân vật cá nhân, type là "organization" nghĩa là tổ chức/thế lực/môn phái/bang hội v.v.
- Phải phân biệt nhân vật và tổ chức, đừng coi tổ chức như nhân vật

【Quy chuẩn định dạng】
- Đầu ra mảng JSON thuần túy, không đánh dấu markdown
- Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
- Danh từ riêng viết trực tiếp
- Cấu trúc trường hoàn toàn nhất quán với các chương đã có
</output>

<constraints>
【Yêu cầu dàn ý mở đầu】
✅ Thiết lập mở đầu: vài chương đầu hoàn thành việc giới thiệu thế giới quan, nhân vật chính xuất hiện, trạng thái ban đầu
✅ Gieo mâu thuẫn: đưa ra xung đột cốt lõi, nhưng không vội triển khai
✅ Nhân vật ra mắt: các nhân vật chính lần lượt xuất hiện, thể hiện tính cách và quan hệ
✅ Kiểm soát nhịp độ: phần mở đầu không nên quá nhanh, cho độc giả thời gian thích nghi
✅ Đặt hồi hộp: gieo chi tiết cài cắm và móc treo, dành không gian cho phần viết tiếp
✅ Thống nhất góc nhìn: dùng góc nhìn {narrative_perspective}
✅ Nghệ thuật khoảng trống: kết thúc không khép quá chặt, để lại không gian phát triển

【Bắt buộc tuân thủ】
✅ Số lượng chính xác: mảng chứa {chapter_count} đối tượng chương
✅ Phù hợp thể loại: tình tiết phù hợp đặc trưng thể loại {genre}
✅ Bám sát chủ đề: thể hiện chủ đề “{theme}”
✅ Định vị mở đầu: là phần mở đầu chứ không phải câu chuyện hoàn chỉnh
✅ Mô tả chi tiết: mỗi summary 500-1000 chữ

【Những điều cấm】
❌ Xuất đánh dấu markdown hoặc ký hiệu khối mã
❌ Dùng ký hiệu đặc biệt trong mô tả
❌ Cố kết thúc câu chuyện ngay ở phần mở đầu
❌ Nhịp độ quá nhanh, quá tải thông tin
</constraints>"""
    
    # Prompt viết tiếp dàn ý V2 (khung RTCO - bản rút gọn)
    OUTLINE_CONTINUE = """<system>
Bạn là nhà văn và biên kịch tiểu thuyết giàu kinh nghiệm, giỏi viết tiếp dàn ý tiểu thuyết thể loại {genre}.
</system>

<task>
【Nhiệm vụ viết tiếp】
Dựa trên nội dung {current_chapter_count} chương đã có, viết tiếp dàn ý từ chương {start_chapter} đến chương {end_chapter} (tổng {chapter_count} chương).

【Giai đoạn tình tiết hiện tại】
{plot_stage_instruction}

【Hướng phát triển câu chuyện】
{story_direction}
</task>

<project priority="P0">
【Thông tin dự án】
Tên sách: {title}
Chủ đề: {theme}
Thể loại: {genre}
Góc nhìn tự sự: {narrative_perspective}
</project>

<worldview priority="P1">
【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}
</worldview>

<previous_context priority="P0">
{recent_outlines}
</previous_context>

<characters priority="P0">
【Thông tin tất cả nhân vật】
{characters_info}
</characters>

<user_input priority="P0">
【Đầu vào của người dùng】
Số chương viết tiếp: {chapter_count} chương
Giai đoạn cốt truyện: {plot_stage_instruction}
Hướng câu chuyện: {story_direction}
Yêu cầu khác: {requirements}
</user_input>

<mcp_context priority="P2">
{mcp_references}
</mcp_context>

<output priority="P0">
【Định dạng đầu ra】
Trả về mảng JSON từ chương {start_chapter} đến chương {end_chapter} (tổng {chapter_count} đối tượng):

[
  {{
   "chapter_number": {start_chapter},
   "title": "Tiêu đề chương",
   "summary": "Tóm tắt chương (500-1000 chữ): tình tiết chính, tương tác nhân vật, sự kiện then chốt, xung đột và bước ngoặt",
   "scenes": ["Mô tả cảnh 1", "Mô tả cảnh 2", "Mô tả cảnh 3"],
   "characters": [
     {{"name": "Tên nhân vật 1", "type": "character"}},
     {{"name": "Tên tổ chức/thế lực 1", "type": "organization"}}
   ],
   "key_points": ["Điểm cốt truyện chính 1", "Điểm cốt truyện chính 2"],
   "emotion": "Tông cảm xúc của chương này",
   "goal": "Mục tiêu tự sự của chương này"
 }},
 {{
   "chapter_number": {start_chapter} + 1,
   "title": "Tiêu đề chương",
   "summary": "Tóm tắt chương...",
   "scenes": ["Cảnh 1", "Cảnh 2"],
   "characters": [
     {{"name": "Tên nhân vật 2", "type": "character"}},
     {{"name": "Tên tổ chức 2", "type": "organization"}}
   ],
   "key_points": ["Điểm chính 1", "Điểm chính 2"],
   "emotion": "Tông cảm xúc",
   "goal": "Mục tiêu tự sự"
 }}
]

【Giải thích trường characters】
- type là "character" nghĩa là nhân vật cá nhân, type là "organization" nghĩa là tổ chức/thế lực/môn phái/bang hội v.v.
- Phải phân biệt nhân vật và tổ chức, đừng coi tổ chức như nhân vật

【Quy chuẩn định dạng】
- Đầu ra mảng JSON thuần túy, không đánh dấu markdown
- Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
- Danh từ riêng viết trực tiếp
- Cấu trúc trường hoàn toàn nhất quán với các chương đã có
</output>

<constraints>
【Yêu cầu viết tiếp】
✅ Cốt truyện liền mạch: nối tiếp tự nhiên với phần trước, giữ tính liên tục
✅ Phát triển nhân vật: tuân theo quỹ đạo trưởng thành của nhân vật, tận dụng đầy đủ thông tin nhân vật
✅ Giai đoạn cốt truyện: tuân thủ yêu cầu của {plot_stage_instruction}
✅ Nhất quán phong cách: giữ cùng phong cách và mức độ chi tiết với các chương đã có
✅ Dàn ý chi tiết: phân tích đầy đủ thông tin trường structure của dàn ý 10 chương gần nhất

【Bắt buộc tuân thủ】
✅ Số lượng chính xác: mảng chứa {chapter_count} chương
✅ Số chương đúng: bắt đầu từ chương {start_chapter}
✅ Mô tả chi tiết: mỗi summary 500-1000 chữ
✅ Nối trước mở sau: nối tiếp tự nhiên với phần trước

【Những điều cấm】
❌ Xuất đánh dấu markdown hoặc ký hiệu khối mã
❌ Dùng ký hiệu đặc biệt trong mô tả
❌ Mâu thuẫn hoặc rời rạc với phần trước
❌ Bỏ qua sự phát triển của các nhân vật đã có
❌ Bỏ qua manh mối cốt truyện trong dàn ý gần đây
</constraints>"""
    
    # Tạo chương - chế độ 1-N (Chương 1)
    CHAPTER_GENERATION_ONE_TO_MANY = """<system>
Bạn là tác giả của “{project_title}”, một tiểu thuyết gia mạng chuyên về thể loại {genre}.
</system>

<task>
【Nhiệm vụ sáng tác】
Viết toàn bộ chính văn của chương {chapter_number} “{chapter_title}”.

【Yêu cầu cơ bản】
- Số chữ mục tiêu: {target_word_count} chữ (cho phép dao động ±200 chữ)
- Góc nhìn tự sự: {narrative_perspective}
</task>

<outline priority="P0">
【Dàn ý chương này - bắt buộc tuân theo】
{chapter_outline}
</outline>

<characters priority="P1">
【Nhân vật của chương này - hãy tuân thủ nghiêm ngặt thiết lập nhân vật】
{characters_info}

⚠️ Lưu ý tương tác nhân vật:
- Đối thoại và hành vi giữa các nhân vật phải phù hợp với thiết lập quan hệ của họ (như sư đồ, đối địch v.v.)
- Tình tiết liên quan đến tổ chức phải thể hiện thân phận và chức vụ của nhân vật trong tổ chức
- Biểu hiện năng lực của nhân vật phải phù hợp với nghề nghiệp và giai đoạn của họ
</characters>

<careers priority="P2">
【Nghề nghiệp của chương này】
{chapter_careers}
</careers>

<foreshadow_reminders priority="P2">
【🎯 Nhắc chi tiết cài cắm】
{foreshadow_reminders}
</foreshadow_reminders>

<memory priority="P2">
【Ký ức liên quan】
{relevant_memories}
</memory>

<constraints>
【Bắt buộc tuân thủ】
✅ Đẩy cốt truyện nghiêm ngặt theo dàn ý
✅ Giữ nhất quán tính cách và cách nói chuyện của nhân vật
✅ Tương tác nhân vật phải phù hợp thiết lập quan hệ (sư đồ, bạn bè, đối địch v.v.)
✅ Tình tiết liên quan đến tổ chức phải thể hiện thân phận thành viên và cấp bậc chức vụ
✅ Số chữ nằm trong phạm vi mục tiêu
✅ Nếu có nhắc nhở chi tiết cài cắm, hãy gieo hoặc thu hồi chi tiết cài cắm tương ứng một cách phù hợp trong chương này

【Những điều cấm】
❌ Xuất tiêu đề chương, số thứ tự và các thông tin meta khác
❌ Dùng các câu tổng kết kiểu AI thường gặp như “tóm lại”, “tổng kết lại”
❌ Dùng câu hỏi tu từ mở ở phần kết
❌ Thêm chú thích tác giả hoặc lời giải thích sáng tác
❌ Hành vi nhân vật vượt quá phạm vi năng lực của giai đoạn nghề nghiệp của họ
</constraints>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung chính văn tiểu thuyết, bắt đầu từ cảnh truyện hoặc hành động.
Không cần bất kỳ lời mở đầu, lời kết hay văn bản giải thích nào.

Bắt đầu sáng tác ngay:
</output>"""

    # Tạo chương - chế độ 1-1 (Chương 1)
    CHAPTER_GENERATION_ONE_TO_ONE = """<system>
Bạn là tác giả của “{project_title}”, một tiểu thuyết gia mạng chuyên về thể loại {genre}.
</system>

<task priority="P0">
【Nhiệm vụ sáng tác】
Viết toàn bộ chính văn của chương {chapter_number} “{chapter_title}”.

【Yêu cầu cơ bản】
- Số chữ mục tiêu: {target_word_count} chữ (cho phép dao động ±200 chữ)
- Góc nhìn tự sự: {narrative_perspective}
</task>

<outline priority="P0">
【Dàn ý chương này】
{chapter_outline}
</outline>

<characters priority="P1">
【Nhân vật của chương này】
{characters_info}
</characters>

<careers priority="P2">
【Nghề nghiệp của chương này】
{chapter_careers}
</careers>

<foreshadow_reminders priority="P2">
【🎯 Nhắc chi tiết cài cắm】
{foreshadow_reminders}
</foreshadow_reminders>

<memory priority="P2">
【Ký ức liên quan】
{relevant_memories}
</memory>

<constraints>
【Bắt buộc tuân thủ】
✅ Đẩy cốt truyện nghiêm ngặt theo dàn ý
✅ Giữ nhất quán tính cách và cách nói chuyện của nhân vật
✅ Số chữ cần kiểm soát chặt chẽ trong phạm vi số chữ mục tiêu
✅ Nếu có nhắc nhở chi tiết cài cắm, hãy gieo hoặc thu hồi chi tiết cài cắm tương ứng một cách phù hợp trong chương này

【Những điều cấm】
❌ Xuất tiêu đề chương, số thứ tự và các thông tin meta khác
❌ Dùng các câu tổng kết kiểu AI thường gặp như “tóm lại”, “tổng kết lại”
❌ Thêm chú thích tác giả hoặc lời giải thích sáng tác
❌ Số chữ tạo ra không được vượt quá số chữ mục tiêu
</constraints>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung chính văn tiểu thuyết, bắt đầu từ cảnh truyện hoặc hành động.
Không cần bất kỳ lời mở đầu, lời kết hay văn bản giải thích nào.

Bắt đầu sáng tác ngay:
</output>"""

    # Tạo chương - chế độ 1-1 (Chương 2 trở đi)
    CHAPTER_GENERATION_ONE_TO_ONE_NEXT = """<system>
Bạn là tác giả của “{project_title}”, một tiểu thuyết gia mạng chuyên về thể loại {genre}.
</system>

<task priority="P0">
【Nhiệm vụ sáng tác】
Viết toàn bộ chính văn của chương {chapter_number} “{chapter_title}”.

【Yêu cầu cơ bản】
- Số chữ mục tiêu: {target_word_count} chữ (cho phép dao động ±200 chữ)
- Góc nhìn tự sự: {narrative_perspective}
</task>

<outline priority="P0">
【Dàn ý chương này】
{chapter_outline}
</outline>

<previous_chapter_summary priority="P1">
【Tóm tắt cốt truyện chương trước】
{previous_chapter_summary}
</previous_chapter_summary>

<recent_context priority="P1">
【Tóm tắt các chương gần đây - tham khảo mạch truyện】
{recent_chapters_context}
</recent_context>

<previous_chapter priority="P1">
【Toàn văn chương trước】
{previous_chapter_content}
</previous_chapter>

<characters priority="P1">
【Nhân vật của chương này】
{characters_info}
</characters>

<careers priority="P2">
【Nghề nghiệp của chương này】
{chapter_careers}
</careers>

<foreshadow_reminders priority="P2">
【🎯 Nhắc chi tiết cài cắm】
{foreshadow_reminders}
</foreshadow_reminders>

<memory priority="P2">
【Ký ức liên quan】
{relevant_memories}
</memory>

<constraints>
【Bắt buộc tuân thủ】
✅ Đẩy cốt truyện nghiêm ngặt theo dàn ý
✅ Nối tiếp tự nhiên phần cuối chương trước, giữ tính liên tục
✅ Giữ nhất quán tính cách và cách nói chuyện của nhân vật
✅ Số chữ cần kiểm soát chặt chẽ trong phạm vi số chữ mục tiêu
✅ Nếu có nhắc nhở chi tiết cài cắm, hãy gieo hoặc thu hồi chi tiết cài cắm tương ứng một cách phù hợp trong chương này

【Những điều cấm】
❌ Xuất tiêu đề chương, số thứ tự và các thông tin meta khác
❌ Dùng các câu tổng kết kiểu AI thường gặp như “tóm lại”, “tổng kết lại”
❌ Dùng câu hỏi tu từ mở ở phần kết
❌ Thêm chú thích tác giả hoặc lời giải thích sáng tác
❌ Lặp lại sự kiện đã xảy ra ở chương trước
❌ Số chữ tạo ra không được vượt quá số chữ mục tiêu
</constraints>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung chính văn tiểu thuyết, bắt đầu từ cảnh truyện hoặc hành động.
Không cần bất kỳ lời mở đầu, lời kết hay văn bản giải thích nào.

Bắt đầu sáng tác ngay:
</output>"""

    # Tạo chương - chế độ 1-N (Chương 2 trở đi)
    CHAPTER_GENERATION_ONE_TO_MANY_NEXT = """<system>
Bạn là tác giả của “{project_title}”, một tiểu thuyết gia mạng chuyên về thể loại {genre}.
</system>

<task>
【Nhiệm vụ sáng tác】
Viết toàn bộ chính văn của chương {chapter_number} “{chapter_title}”.

【Yêu cầu cơ bản】
- Số chữ mục tiêu: {target_word_count} chữ (cho phép dao động ±200 chữ)
- Góc nhìn tự sự: {narrative_perspective}
</task>

<outline priority="P0">
【Dàn ý chương này - bắt buộc tuân theo】
{chapter_outline}
</outline>

<recent_context priority="P1">
【Quy hoạch các chương gần đây - tham khảo mạch truyện】
{recent_chapters_context}
</recent_context>

<continuation priority="P0">
【Điểm neo chuyển tiếp - bắt buộc phải nối tiếp】
Toàn văn chương trước:
"{continuation_point}"

【🔴 Cốt truyện chương trước đã hoàn thành (cấm lặp lại!)】
{previous_chapter_summary}

⚠️ Cảnh báo nghiêm trọng:
1. "Cốt truyện đã hoàn thành" và "Điểm neo nối tiếp" nêu trên là nội dung **đã viết rồi**
2. Chương này phải đẩy tới **điểm tình tiết mới**, tuyệt đối không được kể lại sự kiện đã xảy ra
3. Chương này nên nối tiếp tình huống cuối chương trước để tiếp tục đẩy, đừng thuật lại toàn văn chương trước
4. Nếu chương trước kết thúc bằng đối thoại hoặc cảnh, hãy bắt đầu từ hành động, phản ứng hoặc chuyển cảnh sau khi kết thúc
</continuation>

<characters priority="P1">
【Nhân vật của chương này - hãy tuân thủ nghiêm ngặt thiết lập nhân vật】
{characters_info}

⚠️ Lưu ý tương tác nhân vật:
- Đối thoại và hành vi giữa các nhân vật phải phù hợp với thiết lập quan hệ của họ (như sư đồ, đối địch v.v.)
- Tình tiết liên quan đến tổ chức phải thể hiện thân phận và chức vụ của nhân vật trong tổ chức
- Biểu hiện năng lực của nhân vật phải phù hợp với nghề nghiệp và giai đoạn của họ
</characters>

<careers priority="P2">
【Nghề nghiệp của chương này】
{chapter_careers}
</careers>

<foreshadow_reminders priority="P1">
【🎯 Nhắc chi tiết cài cắm - cần chú ý】
{foreshadow_reminders}
</foreshadow_reminders>

<memory priority="P2">
【Ký ức liên quan - tham khảo】
{relevant_memories}
</memory>

<constraints>
【Bắt buộc tuân thủ】
✅ Đẩy cốt truyện nghiêm ngặt theo dàn ý
✅ Nối tiếp tự nhiên phần kết chương trước, không lặp lại sự kiện đã xảy ra
✅ Giữ nhất quán tính cách và cách nói chuyện của nhân vật
✅ Tương tác nhân vật phải phù hợp thiết lập quan hệ (sư đồ, bạn bè, đối địch v.v.)
✅ Tình tiết liên quan đến tổ chức phải thể hiện thân phận thành viên và cấp bậc chức vụ
✅ Số chữ nằm trong phạm vi mục tiêu
✅ Nếu có nhắc nhở chi tiết cài cắm, hãy gieo hoặc thu hồi chi tiết cài cắm tương ứng một cách phù hợp trong chương này

【🔴 Chỉ thị đặc biệt chống lặp lại】
✅ Kiểm tra phần mở đầu chương này có trùng với nội dung "Điểm neo nối tiếp" không
✅ Kiểm tra tình tiết chương này có trùng với "Cốt truyện chương trước đã hoàn thành" không
✅ Đảm bảo chương này đã đẩy tới sự kiện mới được lên kế hoạch trong dàn ý

【Những điều cấm】
❌ Xuất tiêu đề chương, số thứ tự và các thông tin meta khác
❌ Dùng các câu tổng kết kiểu AI thường gặp như “tóm lại”, “tổng kết lại”
❌ Dùng câu hỏi tu từ mở ở phần kết
❌ Thêm chú thích tác giả hoặc lời giải thích sáng tác
❌ Kể lại sự kiện đã xảy ra ở chương trước (kể cả miêu tả môi trường, hoạt động tâm lý)
❌ Dùng câu sáo rỗng ở phần mở đầu như “nối tiếp hồi trước”, “tiếp theo chương trước”
❌ Hành vi nhân vật vượt quá phạm vi năng lực của giai đoạn nghề nghiệp của họ
</constraints>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung chính văn tiểu thuyết, bắt đầu từ cảnh truyện hoặc hành động.
Không cần bất kỳ lời mở đầu, lời kết hay văn bản giải thích nào.

Bắt đầu sáng tác ngay:
</output>"""

    # Prompt tạo nhân vật đơn lẻ V2 (khung RTCO)
    SINGLE_CHARACTER_GENERATION = """<system>
Bạn là chuyên gia thiết lập nhân vật, giỏi tạo ra những nhân vật tiểu thuyết sống động, đầy đặn.
</system>

<task>
【Nhiệm vụ thiết kế】
Dựa trên nhu cầu người dùng và bối cảnh dự án, tạo một thiết lập nhân vật hoàn chỉnh.
</task>

<context priority="P0">
【Bối cảnh dự án】
{project_context}

【Nhu cầu của người dùng】
{user_input}
</context>

<output priority="P0">
【Định dạng đầu ra】
Tạo đối tượng JSON thẻ nhân vật hoàn chỉnh:

{{
  "name": "Tên nhân vật (nếu người dùng không cung cấp thì tạo tên phù hợp với thế giới quan)",
  "age": "Tuổi (con số cụ thể hoặc khoảng tuổi)",
  "gender": "Nam/Nữ/Khác",
  "appearance": "Mô tả ngoại hình (100-150 chữ): chiều cao vóc dáng, đặc điểm khuôn mặt, phong cách ăn mặc",
  "personality": "Đặc điểm tính cách (150-200 chữ): nét tính cách cốt lõi, ưu nhược điểm, thói quen đặc biệt",
  "background": "Câu chuyện nền (200-300 chữ): bối cảnh gia đình, quá trình trưởng thành, bước ngoặt quan trọng, liên hệ với chủ đề",
  "traits": ["Sở trường 1", "Sở trường 2", "Sở trường 3"],
  "relationships_text": "Mô tả quan hệ giữa các cá nhân bằng ngôn ngữ tự nhiên",
  "relationships": [
    {{
      "target_character_name": "Tên nhân vật đã tồn tại",
      "relationship_type": "Loại quan hệ",
      "intimacy_level": 75,
      "description": "Mô tả chi tiết quan hệ",
      "started_at": "Thời điểm câu chuyện khi quan hệ bắt đầu (tùy chọn)"
    }}
  ],
  "organization_memberships": [
    {{
      "organization_name": "Tên tổ chức đã tồn tại",
      "position": "Tên chức vụ",
      "rank": 8,
      "loyalty": 80,
      "joined_at": "Thời gian gia nhập (tùy chọn)",
      "status": "active"
    }}
  ],
  "career_info": {{
    "main_career_name": "Tên nghề nghiệp chọn từ danh sách nghề chính khả dụng",
    "main_career_stage": 5,
    "sub_careers": [
      {{
        "career_name": "Tên nghề nghiệp chọn từ danh sách nghề phụ khả dụng",
        "stage": 3
      }}
    ]
  }}
}}

【Giải thích thông tin nghề nghiệp】
Nếu bối cảnh dự án chứa danh sách nghề nghiệp:
- Nghề chính: chọn nghề phù hợp nhất với nhân vật từ danh sách "nghề chính khả dụng"
- Giai đoạn nghề chính: đặt giai đoạn hợp lý theo thực lực nhân vật (1 đến max_stage)
- Nghề phụ: có thể chọn 0-2 nghề phụ
- ⚠️ Điền tên nghề nghiệp chứ không phải ID, hệ thống sẽ tự động khớp
- Lựa chọn nghề nghiệp phải ăn khớp cao với bối cảnh, năng lực và định vị của nhân vật

【Tham khảo loại quan hệ】
- Gia đình: cha, mẹ, anh em trai, chị em gái, con cái, vợ/chồng, người yêu
- Xã hội: sư phụ, đồ đệ, bạn bè, bạn học, đồng nghiệp, hàng xóm, tri kỷ
- Nghề nghiệp: cấp trên, cấp dưới, đối tác
- Đối địch: kẻ thù, thù nhân, đối thủ cạnh tranh, tử địch

【Phạm vi giá trị số】
- intimacy_level: -100 đến 100 (giá trị âm biểu thị đối địch)
- loyalty: 0 đến 100
- rank: 0 đến 10
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Phù hợp thế giới quan: thiết lập nhân vật nhất quán với thế giới quan dự án
✅ Liên hệ chủ đề: câu chuyện nền gắn với chủ đề dự án
✅ Sống động đầy đặn: tính cách phức tạp có mâu thuẫn, không rập khuôn
✅ Phục vụ câu chuyện: thiết lập phải thúc đẩy cốt truyện phát triển
✅ Khớp nghề nghiệp: lựa chọn nghề nghiệp ăn khớp cao với nhân vật

【Yêu cầu định vị nhân vật】
✅ Nhân vật chính: có không gian trưởng thành và động cơ mục tiêu
✅ Phản diện: có động cơ hợp lý, không rập khuôn
✅ Nhân vật phụ: có nét độc đáo, không phải công cụ

【Ràng buộc quan hệ】
✅ relationships chỉ tham chiếu các nhân vật đã tồn tại
✅ organization_memberships chỉ tham chiếu các tổ chức đã tồn tại
✅ Khi không có quan hệ hoặc tổ chức, mảng tương ứng để trống []

【Ràng buộc định dạng】
✅ Đầu ra đối tượng JSON thuần túy, không đánh dấu markdown
✅ Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
✅ Danh từ riêng viết trực tiếp

【Những điều cấm】
❌ Xuất đánh dấu markdown hoặc ký hiệu khối mã
❌ Dùng ký hiệu đặc biệt trong mô tả (dấu ngoặc kép, ngoặc vuông v.v.)
❌ Tham chiếu nhân vật hoặc tổ chức không tồn tại
❌ Thiết lập nhân vật rập khuôn
</constraints>"""

    # Prompt tạo tổ chức đơn lẻ V2 (khung RTCO)
    SINGLE_ORGANIZATION_GENERATION = """<system>
Bạn là chuyên gia thiết lập tổ chức, giỏi tạo thiết lập tổ chức/thế lực hoàn chỉnh.
</system>

<task>
【Nhiệm vụ thiết kế】
Dựa trên nhu cầu người dùng và bối cảnh dự án, tạo một thiết lập tổ chức/thế lực hoàn chỉnh.
</task>

<context priority="P0">
【Bối cảnh dự án】
{project_context}

【Nhu cầu của người dùng】
{user_input}
</context>

<output priority="P0">
【Định dạng đầu ra】
Tạo đối tượng JSON thiết lập tổ chức hoàn chỉnh:

{{
  "name": "Tên tổ chức (nếu người dùng không cung cấp thì tạo tên phù hợp với thế giới quan)",
  "is_organization": true,
  "organization_type": "Loại hình tổ chức (bang hội/công ty/môn phái/học viện/cơ quan chính phủ/tổ chức tôn giáo v.v.)",
  "personality": "Đặc tính tổ chức (150-200 chữ): tư tưởng cốt lõi, phong cách hành sự, giá trị văn hóa, cách vận hành",
  "background": "Bối cảnh tổ chức (200-300 chữ): lịch sử thành lập, quá trình phát triển, sự kiện quan trọng, địa vị hiện tại",
  "appearance": "Biểu hiện bên ngoài (100-150 chữ): vị trí trụ sở, kiến trúc biểu tượng, biểu tượng tổ chức, đồng phục v.v.",
  "organization_purpose": "Mục đích và tôn chỉ của tổ chức: mục tiêu rõ ràng, tầm nhìn dài hạn, quy tắc hành động",
  "power_level": 75,
  "location": "Nơi đặt: khu vực hoạt động chính, phạm vi thế lực",
  "motto": "Châm ngôn hoặc khẩu hiệu của tổ chức",
  "traits": ["Đặc trưng 1", "Đặc trưng 2", "Đặc trưng 3"],
  "color": "Màu đại diện của tổ chức (như: đỏ sẫm, vàng kim, đen v.v.)",
  "organization_members": ["Thành viên quan trọng 1", "Thành viên quan trọng 2", "Thành viên quan trọng 3"]
}}

【Giải thích trường dữ liệu】
- power_level: số nguyên 0-100, biểu thị mức ảnh hưởng trong thế giới
- organization_members: danh sách tên thành viên quan trọng trong tổ chức (có thể liên kết với nhân vật đã có)
- Thời gian thành lập: mô tả trong background
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Phù hợp thế giới quan: thiết lập tổ chức nhất quán với thế giới quan dự án
✅ Liên hệ chủ đề: bối cảnh gắn với chủ đề dự án
✅ Thúc đẩy cốt truyện: tổ chức có thể thúc đẩy câu chuyện phát triển
✅ Có cấu trúc phân cấp: nội bộ có cấp bậc và cấu trúc rõ ràng
✅ Tương tác thế lực: có quan hệ tương tác với các thế lực khác

【Yêu cầu định vị tổ chức】
✅ Có sự cần thiết tồn tại: không phải phông nền thừa thãi
✅ Mục tiêu hợp lý: không quá lý tưởng hóa hoặc rập khuôn
✅ Chi tiết cụ thể: mô tả chi tiết cụ thể, tránh chung chung

【Ràng buộc định dạng】
✅ Đầu ra đối tượng JSON thuần túy, không đánh dấu markdown
✅ Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
✅ Danh từ riêng viết trực tiếp

【Những điều cấm】
❌ Xuất đánh dấu markdown hoặc ký hiệu khối mã
❌ Dùng ký hiệu đặc biệt trong mô tả (dấu ngoặc kép, ngoặc vuông v.v.)
❌ Thiết lập quá lý tưởng hóa hoặc rập khuôn
❌ Mô tả chung chung
</constraints>"""

    # Prompt phân tích cốt truyện V2 (khung RTCO + theo dõi ID chi tiết cài cắm)
    PLOT_ANALYSIS = """<system>
Bạn là biên tập viên tiểu thuyết và nhà phân tích cốt truyện chuyên nghiệp, giỏi phân tích sâu nội dung chương.
</system>

<task>
【Nhiệm vụ phân tích】
Phân tích toàn diện các yếu tố cốt truyện, móc treo, chi tiết cài cắm, xung đột và sự phát triển nhân vật của chương {chapter_number} “{title}”.

【🔴 Nhiệm vụ theo dõi chi tiết cài cắm (quan trọng)】
Hệ thống đã cung cấp 【Danh sách chi tiết cài cắm đã gieo】, khi bạn nhận ra chương có thu hồi chi tiết cài cắm:
1. Phải tìm ID chi tiết cài cắm tương ứng từ danh sách
2. Dùng trường reference_foreshadow_id trong mảng foreshadows để liên kết
3. Nếu không thể xác định là chi tiết cài cắm nào, điền null cho reference_foreshadow_id
</task>

<chapter priority="P0">
【Thông tin chương】
Chương: chương {chapter_number}
Tiêu đề: {title}
Số chữ: {word_count} chữ

【Nội dung chương】
{content}
</chapter>

<existing_foreshadows priority="P1">
【Danh sách chi tiết cài cắm đã gieo - dùng để đối chiếu khi thu hồi】
Dưới đây là các chi tiết cài cắm đã gieo nhưng chưa thu hồi trong dự án này, khi phân tích nếu phát hiện nội dung chương thu hồi chi tiết cài cắm nào, hãy dùng ID tương ứng:

{existing_foreshadows}
</existing_foreshadows>

<characters priority="P1">
【Thông tin nhân vật của dự án - dùng cho phân tích trạng thái nhân vật】
Dưới đây là danh sách nhân vật đã có trong dự án, khi phân tích character_states và relationship_changes hãy dùng tên chính xác của các nhân vật này:

{characters_info}
</characters>

<analysis_framework priority="P0">
【Khía cạnh phân tích】

**1. Móc treo cốt truyện (Hooks)**
Nhận diện các yếu tố then chốt thu hút độc giả:
- Móc treo hồi hộp: bí ẩn chưa giải, câu hỏi, điều bí ẩn
- Móc treo cảm xúc: điểm cảm xúc gây đồng cảm
- Móc treo xung đột: mâu thuẫn đối kháng, cục diện căng thẳng
- Móc treo nhận thức: thông tin đảo lộn nhận thức

Mỗi móc treo cần:
- Phân loại
- Mô tả nội dung cụ thể
- Điểm cường độ (1-10)
- Vị trí xuất hiện (đầu/giữa/cuối)
- **Từ khóa**: 【Bắt buộc】 sao chép nguyên văn đoạn văn bản 8-25 chữ từ bản gốc, dùng để định vị chính xác

**2. Phân tích chi tiết cài cắm (Foreshadowing) - 🔴 Hỗ trợ theo dõi ID**
- Chi tiết cài cắm mới được gieo: nội dung, tác dụng dự kiến, mức độ ẩn giấu (1-10)
- Chi tiết cài cắm cũ được thu hồi: 【Bắt buộc】 khớp ID từ danh sách chi tiết cài cắm đã gieo
- Chất lượng chi tiết cài cắm: sự khéo léo và tính hợp lý
- **Từ khóa**: 【Bắt buộc】 sao chép nguyên văn 8-25 chữ từ bản gốc

Mỗi chi tiết cài cắm cần:
- **title**: tiêu đề ngắn gọn (10-20 chữ, tóm lược cốt lõi chi tiết cài cắm)
  - ⚠️ Khi thu hồi chi tiết cài cắm, tiêu đề phải nhất quán với tiêu đề chi tiết cài cắm gốc, không thêm hậu tố như “thu hồi”
  - Ví dụ: tiêu đề chi tiết cài cắm gốc là “Biểu tượng thị giác tóc xanh”, khi thu hồi tiêu đề vẫn là “Biểu tượng thị giác tóc xanh”, chứ không phải “Biểu tượng thị giác tóc xanh thu hồi”
- **content**: mô tả chi tiết nội dung và tác dụng dự kiến của chi tiết cài cắm
- **type**: planted (gieo) hoặc resolved (thu hồi)
- **strength**: cường độ 1-10 (sức hút đối với độc giả)
- **subtlety**: mức độ ẩn giấu 1-10 (càng cao càng kín đáo)
- **reference_chapter**: số chương gốc đã gieo khi thu hồi, khi gieo là null
- **reference_foreshadow_id**: 【Bắt buộc khi thu hồi】 ID của chi tiết cài cắm được thu hồi (chọn từ danh sách chi tiết cài cắm đã gieo), khi gieo là null
  - 🔴 Quan trọng: khi thu hồi chi tiết cài cắm, phải tìm ID chi tiết cài cắm tương ứng trong 【Danh sách chi tiết cài cắm đã gieo】 và điền vào
  - Nếu trong danh sách có chi tiết cài cắm được gắn nhãn 【ID: xxx】, khi thu hồi phải dùng ID đó
  - Chỉ điền null khi không thể xác định là chi tiết cài cắm nào (nhưng nên cố gắng tránh)
- **keyword**: 【Bắt buộc】 văn bản định vị 8-25 chữ sao chép nguyên văn từ bản gốc
- **category**: phân loại (identity=thân thế/mystery=hồi hộp/item=vật phẩm/relationship=quan hệ/event=sự kiện/ability=năng lực/prophecy=lời tiên tri)
- **is_long_term**: có phải chi tiết cài cắm dài hạn không (thu hồi sau hơn 10 chương là true)
- **related_characters**: danh sách tên nhân vật liên quan
- **estimated_resolve_chapter**: 【Bắt buộc】 số chương dự kiến thu hồi (khi gieo bắt buộc phải dự kiến, khi thu hồi là chương hiện tại)

**3. Phân tích xung đột (Conflict)**
- Loại xung đột: người với người/người với chính mình/người với môi trường/người với xã hội
- Các bên xung đột và lập trường
- Cường độ xung đột (1-10)
- Tiến độ giải quyết (0-100%)

**4. Đường cong cảm xúc (Emotional Arc)**
- Cảm xúc chủ đạo (tối đa 10 chữ)
- Cường độ cảm xúc (1-10)
- Quỹ đạo thay đổi cảm xúc

**5. Theo dõi trạng thái nhân vật (Character Development)**
Phân tích mỗi nhân vật xuất hiện:
- Thay đổi trạng thái tâm lý (trước→sau)
- Thay đổi quan hệ
- Hành động và quyết định then chốt
- Trưởng thành hoặc thụt lùi
- **💀 Trạng thái sinh tồn (quan trọng)**:
  - survival_status: trạng thái sinh tồn hiện tại của nhân vật
  - Giá trị tùy chọn: active (bình thường)/deceased (đã chết)/missing (mất tích)/retired (rút lui)
  - Mặc định là null (nghĩa là không thay đổi), chỉ điền khi chương mô tả rõ nhân vật chết, mất tích hoặc rút lui vĩnh viễn
  - Chết/mất tích cần có căn cứ cốt truyện rõ ràng, không được suy đoán
- **Thay đổi nghề nghiệp (tùy chọn)**:
  - Chỉ điền khi chương mô tả rõ tiến triển nghề nghiệp
  - main_career_stage_change: số nguyên (+1 thăng cấp/-1 thụt lùi/0 không thay đổi)
  - sub_career_changes: mảng thay đổi nghề phụ
  - new_careers: nghề mới đạt được
  - career_breakthrough: mô tả quá trình đột phá
- **🏛️ Thay đổi tổ chức (tùy chọn)**:
  - Chỉ điền khi chương mô tả rõ thay đổi quan hệ giữa nhân vật và tổ chức
  - organization_changes: mảng biến động tổ chức
  - Mỗi mục gồm: organization_name (tên tổ chức), change_type (gia nhập joined/rời đi left/thăng cấp promoted/giáng cấp demoted/khai trừ expelled/phản bội betrayed), new_position (chức vụ mới, tùy chọn), loyalty_change (mô tả thay đổi độ trung thành, tùy chọn), description (mô tả thay đổi)

**5b. Theo dõi trạng thái tổ chức (Organization Status) - tùy chọn**
Chỉ điền khi chương liên quan đến thay đổi thế lực tổ chức, phân tích thay đổi trạng thái của tổ chức xuất hiện:
- Tên tổ chức
- Thay đổi cấp độ thế lực (power_change: số nguyên, +N tăng cường/-N suy yếu/0 không thay đổi)
- Thay đổi cứ điểm (new_location: cứ điểm mới, tùy chọn)
- Thay đổi tôn chỉ/mục tiêu (new_purpose: mục tiêu mới, tùy chọn)
- Mô tả trạng thái tổ chức (status_description: tổng quan trạng thái hiện tại)
- Sự kiện then chốt (key_event: sự kiện kích hoạt thay đổi)
- **💀 Trạng thái tồn tại của tổ chức (quan trọng)**:
  - is_destroyed: tổ chức có bị diệt vong không (true/false, mặc định false)
  - Chỉ đặt true khi chương mô tả rõ tổ chức bị tiêu diệt hoàn toàn, tan rã, diệt vong

**6. Điểm tình tiết then chốt (Plot Points)**
Liệt kê 3-5 điểm tình tiết cốt lõi:
- Nội dung tình tiết
- Loại (revelation/conflict/resolution/transition)
- Mức độ quan trọng (0.0-1.0)
- Ảnh hưởng đối với câu chuyện
- **Từ khóa**: 【Bắt buộc】 sao chép nguyên văn 8-25 chữ từ bản gốc

**7. Cảnh và nhịp độ**
- Cảnh chính
- Nhịp độ tự sự (nhanh/trung bình/chậm)
- Tỷ lệ đối thoại và miêu tả

**8. Chấm điểm chất lượng (hỗ trợ số thập phân, phân biệt nghiêm ngặt)**
Phạm vi điểm: 1.0-10.0, hỗ trợ một chữ số thập phân (như 6.5, 7.8)
Mỗi khía cạnh phải chấm điểm nghiêm ngặt theo tiêu chí dưới đây, tránh chấm mọi nội dung ở mức trung bình:

**Kiểm soát nhịp độ (pacing)**:
- 1.0-3.9 (kém): nhịp độ hỗn loạn, chỗ cần nhanh không nhanh, chỗ cần chậm không chậm; chuyển cảnh gượng gạo; đoạn miêu tả dài vô nghĩa lê thê
- 4.0-5.9 (dưới trung bình): nhịp độ cơ bản đọc được nhưng có vấn đề rõ rệt; một số cảnh quá dài dòng hoặc quá vội vàng
- 6.0-7.9 (trên trung bình): nhịp độ tổng thể trôi chảy, thỉnh thoảng có vấn đề nhỏ; nhanh chậm điều độ nhưng chưa đủ tinh tế
- 8.0-9.4 (xuất sắc): kiểm soát nhịp độ chính xác, cao trào liên tiếp; chuyển cảnh tự nhiên, chi tiết vừa phải
- 9.5-10.0 (hoàn hảo): nhịp độ đẳng cấp bậc thầy, mỗi đoạn đều vừa vặn

**Sức hút (engagement)**:
- 1.0-3.9 (kém): nội dung nhạt nhẽo, thiếu móc treo; độc giả khó tiếp tục đọc
- 4.0-5.9 (dưới trung bình): có tình tiết cơ bản nhưng thiếu điểm sáng; móc treo đặt gượng gạo hoặc thiếu
- 6.0-7.9 (trên trung bình): có sức hút nhất định, móc treo hiệu quả nhưng chưa đủ khéo
- 8.0-9.4 (xuất sắc): lôi cuốn, móc treo đặt tinh tế; khiến người đọc không thể dừng
- 9.5-10.0 (hoàn hảo): cực kỳ hấp dẫn, mỗi đoạn đều tạo động lực đọc

**Tính liền mạch (coherence)**:
- 1.0-3.9 (kém): logic hỗn loạn, trước sau mâu thuẫn; hành vi nhân vật bất hợp lý
- 4.0-5.9 (dưới trung bình): cơ bản liền mạch nhưng có lỗ hổng rõ rệt; một số tình tiết nối tiếp gượng gạo
- 6.0-7.9 (trên trung bình): tổng thể liền mạch, thỉnh thoảng có khuyết điểm nhỏ; hành vi nhân vật cơ bản hợp lý
- 8.0-9.4 (xuất sắc): logic chặt chẽ, nối tiếp tự nhiên; hành vi nhân vật nhất quán cao
- 9.5-10.0 (hoàn hảo): tính liền mạch không thể chê

**Chất lượng tổng thể (overall)**:
- Công thức tính: (pacing + engagement + coherence) / 3, giữ một chữ số thập phân
- Có thể điều chỉnh ±0.5 theo ấn tượng tổng hợp, phải giữ nhất quán với các điểm thành phần

**9. Gợi ý cải thiện (liên quan đến điểm số)**
Số lượng gợi ý phải liên quan đến điểm chất lượng tổng thể:
- overall < 4.0: phải đưa 4-5 gợi ý cải thiện cụ thể, chỉ ra vấn đề nghiêm trọng
- overall 4.0-5.9: phải đưa 3-4 gợi ý cải thiện, chỉ ra vấn đề chính
- overall 6.0-7.9: đưa 1-2 gợi ý tối ưu, chỉ ra điểm có thể nâng cao
- overall ≥ 8.0: đưa 0-1 gợi ý hoàn thiện thêm

Mỗi gợi ý phải:
- Chỉ ra vị trí hoặc loại vấn đề cụ thể
- Giải thích tại sao đó là vấn đề
- Đưa ra hướng cải thiện rõ ràng
</analysis_framework>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy (không đánh dấu markdown):

{{
  "hooks": [
    {{
      "type": "Hồi hộp",
      "content": "Mô tả cụ thể",
      "strength": 8,
      "position": "Đoạn giữa",
      "keyword": "Đoạn văn bản 8-25 chữ sao chép nguyên văn từ bản gốc"
    }}
  ],
  "foreshadows": [
    {{
      "title": "Tiêu đề ngắn gọn của chi tiết cài cắm",
      "content": "Nội dung chi tiết và tác dụng dự kiến của chi tiết cài cắm",
      "type": "planted",
      "strength": 7,
      "subtlety": 8,
      "reference_chapter": null,
      "reference_foreshadow_id": null,
      "keyword": "Đoạn văn bản 8-25 chữ sao chép nguyên văn từ bản gốc",
      "category": "mystery",
      "is_long_term": false,
      "related_characters": ["Nhân vật A", "Nhân vật B"],
      "estimated_resolve_chapter": 15
    }},
    {{
      "title": "Tiêu đề chi tiết cài cắm được thu hồi",
      "content": "Mô tả cách chi tiết cài cắm được thu hồi",
      "type": "resolved",
      "strength": 8,
      "subtlety": 6,
      "reference_chapter": 5,
      "reference_foreshadow_id": "abc123-ID của chi tiết cài cắm đã gieo",
      "keyword": "Đoạn văn bản 8-25 chữ sao chép nguyên văn từ bản gốc",
      "category": "mystery",
      "is_long_term": false,
      "related_characters": ["Nhân vật A"],
      "estimated_resolve_chapter": 10
    }}
  ],
  "conflict": {{
    "types": ["Người với người", "Người với chính mình"],
    "parties": ["Nhân vật chính-Báo thù", "Phản diện-Duy trì hiện trạng"],
    "level": 8,
    "description": "Mô tả xung đột",
    "resolution_progress": 0.3
  }},
  "emotional_arc": {{
    "primary_emotion": "Căng thẳng lo âu",
    "intensity": 8,
    "curve": "Bình tĩnh→Căng thẳng→Cao trào→Giải tỏa",
    "secondary_emotions": ["Mong đợi", "Lo âu"]
  }},
  "character_states": [
    {{
      "character_name": "Trương Tam",
      "survival_status": null,
      "state_before": "Do dự",
      "state_after": "Kiên định",
      "psychological_change": "Mô tả thay đổi tâm lý",
      "key_event": "Sự kiện kích hoạt",
      "relationship_changes": {{"Lý Tứ": "Quan hệ cải thiện"}},
      "career_changes": {{
        "main_career_stage_change": 1,
        "sub_career_changes": [{{"career_name": "Luyện đan", "stage_change": 1}}],
        "new_careers": [],
        "career_breakthrough": "Mô tả đột phá"
      }},
      "organization_changes": [
        {{
          "organization_name": "Môn phái X",
          "change_type": "promoted",
          "new_position": "Trưởng lão",
          "loyalty_change": "Độ trung thành tăng",
          "description": "Vì lập đại công nên được đề bạt làm trưởng lão"
        }}
      ]
    }}
  ],
  "plot_points": [
    {{
      "content": "Mô tả điểm tình tiết",
      "type": "revelation",
      "importance": 0.9,
      "impact": "Thúc đẩy câu chuyện phát triển",
      "keyword": "Đoạn văn bản 8-25 chữ sao chép nguyên văn từ bản gốc"
    }}
  ],
  "scenes": [
    {{
      "location": "Địa điểm",
      "atmosphere": "Không khí",
      "duration": "Ước tính thời lượng"
    }}
  ],
  "organization_states": [
    {{
      "organization_name": "Môn phái X",
      "power_change": -10,
      "new_location": null,
      "new_purpose": null,
      "status_description": "Vì nội loạn nên thế lực bị tổn hại, nhưng lực lượng cốt lõi chưa lung lay",
      "key_event": "Trưởng lão phản bội khiến chi nhánh tan rã",
      "is_destroyed": false
    }}
  ],
  "pacing": "varied",
  "dialogue_ratio": 0.4,
  "description_ratio": 0.3,
  "scores": {{
    "pacing": 6.5,
    "engagement": 5.8,
    "coherence": 7.2,
    "overall": 6.5,
    "score_justification": "Nhịp độ tổng thể trôi chảy nhưng đoạn giữa hơi lê thê; móc treo đặt hiệu quả nhưng chưa đủ khéo; logic liền mạch không có lỗ hổng rõ rệt"
  }},
  "plot_stage": "Phát triển",
  "suggestions": [
    "【Vấn đề nhịp độ】Phần miêu tả tâm lý ở cảnh thứ ba quá dài (khoảng 500 chữ), nên rút gọn xuống dưới 200 chữ, chỉ giữ cảm xúc cốt lõi",
    "【Thiếu sức hút】Đoạn giữa chương thiếu móc treo hiệu quả, nên thêm một tình tiết hồi hộp nhỏ sau khi nhân vật chính phát hiện manh mối"
  ]
}}
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Trường keyword bắt buộc: keyword của móc treo, chi tiết cài cắm, điểm tình tiết không được để trống
✅ Sao chép nguyên văn: keyword phải sao chép từ bản gốc, độ dài 8-25 chữ
✅ Định vị chính xác: keyword phải tìm thấy chính xác trong bản gốc
✅ Thay đổi nghề nghiệp tùy chọn: chỉ điền khi chương mô tả rõ ràng
✅ Thay đổi tổ chức tùy chọn: chỉ điền khi chương mô tả rõ thay đổi quan hệ giữa nhân vật và tổ chức (organization_changes trong character_states)
✅ Trạng thái tổ chức tùy chọn: chỉ điền khi chương mô tả rõ thay đổi thế lực/cứ điểm/mục tiêu của tổ chức (trường cấp cao nhất organization_states)
✅ Trạng thái sinh tồn thận trọng: chỉ điền survival_status khi chương có mô tả rõ chết/mất tích/rút lui, mặc định null
✅ Diệt vong tổ chức thận trọng: chỉ đặt is_destroyed là true khi tổ chức bị tiêu diệt hoàn toàn, tổ chức bị tổn hại không tính là diệt vong
✅ 【Theo dõi ID chi tiết cài cắm】Khi thu hồi chi tiết cài cắm, phải tìm ID khớp trong 【Danh sách chi tiết cài cắm đã gieo】 và điền vào reference_foreshadow_id
✅ 【Định dạng nghiêm ngặt của suggestions】suggestions phải là “mảng chuỗi”, mỗi phần tử phải là chuỗi thuần túy
✅ Ví dụ định dạng đúng của suggestions: "suggestions": ["【Vấn đề nhịp độ】...", "【Miêu tả chưa đủ】..."]
✅ Trong suggestions cấm trả về đối tượng, từ điển, cặp khóa-giá trị hoặc cấu trúc lồng nhau, ví dụ cấm {{"suggestion": "..."}}, {{"content": "..."}}
✅ Nếu không có gợi ý cải thiện, phải trả về mảng rỗng [], không trả về null, không được bỏ qua trường

【Ràng buộc chấm điểm - thực thi nghiêm ngặt】
✅ Chấm điểm nghiêm ngặt theo tiêu chí, hỗ trợ số thập phân (như 6.5, 7.2, 8.3)
✅ Không chấm mặc định 7.0-8.0, nội dung kém phải cho điểm thấp (1.0-5.0), nội dung tốt mới cho điểm cao (8.0-10.0)
✅ score_justification bắt buộc: giải thích ngắn gọn căn cứ của từng điểm
✅ Số lượng gợi ý phải liên quan đến điểm overall:
   - overall≤4.0 → 4-5 gợi ý
   - overall 4.0-6.0 → 3-4 gợi ý
   - overall 6.0-8.0 → 1-2 gợi ý
   - overall≥8.0 → 0-1 gợi ý
✅ Mỗi gợi ý phải gắn nhãn loại vấn đề (như 【Vấn đề nhịp độ】【Miêu tả chưa đủ】 v.v.)
✅ Mỗi gợi ý phải xuất trực tiếp văn bản đầy đủ, không được bọc thành trường đối tượng

【Những điều cấm】
❌ keyword dùng văn bản khái quát hoặc diễn đạt lại
❌ Xuất đánh dấu markdown
❌ Bỏ sót trường keyword bắt buộc
❌ Thêm thay đổi nghề nghiệp không có căn cứ
❌ Thêm thay đổi tổ chức hoặc thay đổi trạng thái tổ chức không có căn cứ
❌ Đánh dấu nhân vật chết hoặc tổ chức diệt vong khi không có căn cứ cốt truyện chắc chắn
❌ Mọi chương đều chấm “điểm an toàn” 7-8
❌ Chương điểm cao cho nhiều gợi ý, hoặc chương điểm thấp không cho gợi ý
❌ suggestions trả về mảng đối tượng kiểu {{"suggestion": "nội dung gợi ý"}}
❌ suggestions trả về bất kỳ phần tử không phải chuỗi nào như đối tượng có đánh số, đối tượng content, đối tượng explanation
</constraints>"""

    # Prompt triển khai một đợt dàn ý V2 (khung RTCO)
    OUTLINE_EXPAND_SINGLE = """<system>
Bạn là kiến trúc sư cốt truyện tiểu thuyết chuyên nghiệp, giỏi triển khai nút dàn ý thành kế hoạch chương chi tiết.
</system>

<task>
【Nhiệm vụ triển khai】
Triển khai tiết dàn ý thứ {outline_order_index} “{outline_title}” thành kế hoạch chi tiết cho {target_chapter_count} chương.

【Chiến lược triển khai】
{strategy_instruction}
</task>

<project priority="P1">
【Thông tin dự án】
Tên tiểu thuyết: {project_title}
Thể loại: {project_genre}
Chủ đề: {project_theme}
Góc nhìn tự sự: {project_narrative_perspective}

【Bối cảnh thế giới quan】
Bối cảnh thời gian: {project_world_time_period}
Vị trí địa lý: {project_world_location}
Tông không khí: {project_world_atmosphere}
</project>

<characters priority="P1">
【Thông tin nhân vật】
{characters_info}
</characters>

<outline_node priority="P0">
【Nút dàn ý hiện tại - đối tượng triển khai】
Số thứ tự: tiết thứ {outline_order_index}
Tiêu đề: {outline_title}
Nội dung: {outline_content}
</outline_node>

<context priority="P2">
【Tham khảo bối cảnh】
{context_info}
</context>

<output priority="P0">
【Định dạng đầu ra】
Trả về mảng JSON kế hoạch {target_chapter_count} chương:

[
  {{
    "sub_index": 1,
    "title": "Tiêu đề chương (thể hiện xung đột cốt lõi hoặc cảm xúc)",
    "plot_summary": "Tóm tắt cốt truyện (200-300 chữ): mô tả chi tiết sự kiện xảy ra trong chương này, chỉ giới hạn trong nội dung dàn ý hiện tại",
    "key_events": ["Sự kiện then chốt 1", "Sự kiện then chốt 2", "Sự kiện then chốt 3"],
    "character_focus": ["Nhân vật A", "Nhân vật B"],
    "emotional_tone": "Tông cảm xúc (như: căng thẳng, ấm áp, buồn)",
    "narrative_goal": "Mục tiêu tự sự (hiệu quả tự sự chương này cần đạt)",
    "conflict_type": "Loại xung đột (như: giằng xé nội tâm, xung đột giữa người với người)",
    "estimated_words": 3000{scene_field}
  }}
]

【Quy chuẩn định dạng】
- Đầu ra mảng JSON thuần túy, không có văn bản khác
- Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
</output>

<constraints>
【⚠️ Ràng buộc biên nội dung - phải tuân thủ nghiêm ngặt】
✅ Chỉ được triển khai nội dung của nút dàn ý hiện tại
✅ Đào sâu dàn ý hiện tại, không nhảy sang phần sau
✅ Làm chậm nhịp độ tự sự, trải nghiệm đầy đủ giai đoạn hiện tại

❌ Tuyệt đối không được đẩy tới nội dung dàn ý tiếp theo
❌ Đừng để cốt truyện tiến nhanh
❌ Đừng triển khai trước nội dung của 【tiết tiếp theo】

【Nguyên tắc triển khai】
✅ Tách một sự kiện đơn lẻ thành nhiều chương giàu chi tiết
✅ Đào sâu cảm xúc, tâm lý, môi trường, đối thoại
✅ Mỗi chương là một khía cạnh hoặc giai đoạn khác nhau của nội dung dàn ý hiện tại

【🔴 Ràng buộc tạo sự khác biệt giữa các chương liền kề (chống lặp lại)】
✅ Mỗi chương có cách mở đầu độc đáo (cảnh, thời điểm, trạng thái nhân vật khác nhau)
✅ Mỗi chương có cách kết thúc độc đáo (hồi hộp, bước ngoặt, kết cảm xúc khác nhau)
✅ key_events tuyệt đối không trùng lặp giữa các chương kề nhau
✅ plot_summary mô tả nội dung độc đáo của chương đó, không giống các chương khác
✅ Các giai đoạn khác nhau của cùng một sự kiện phải phân biệt rõ “trước, giữa, sau”

【Yêu cầu giữa các chương】
✅ Nối tiếp tự nhiên trôi chảy (mỗi chương bắt đầu từ điểm xuất phát khác nhau)
✅ Cốt truyện tiến triển hợp lý (nhưng không vượt biên dàn ý hiện tại)
✅ Nhịp độ nhanh chậm điều độ
✅ Mỗi chương có giá trị tự sự rõ ràng và độc đáo
✅ Chương cuối kết thúc đúng lúc hoàn thành nội dung dàn ý hiện tại
✅ Sự kiện then chốt không trùng lặp: kiểm tra key_events của các chương kề nhau

【Những điều cấm】
❌ Xuất định dạng không phải JSON
❌ Cốt truyện vượt biên sang dàn ý tiếp theo
❌ Nội dung các chương kề nhau lặp lại
❌ Sự kiện then chốt giống nhau
</constraints>"""

    # Prompt triển khai dàn ý theo đợt V2 (khung RTCO)
    OUTLINE_EXPAND_MULTI = """<system>
Bạn là kiến trúc sư cốt truyện tiểu thuyết chuyên nghiệp, giỏi triển khai nút dàn ý theo từng đợt.
</system>

<task>
【Nhiệm vụ triển khai】
Tiếp tục triển khai tiết dàn ý thứ {outline_order_index} “{outline_title}”, tạo kế hoạch chi tiết cho các tiết {start_index}-{end_index} (tổng {target_chapter_count} chương).

【Giải thích chia đợt】
- Đây là một phần của toàn bộ quá trình triển khai
- Phải nối tiếp tự nhiên với các chương đã tạo trước đó
- Đánh số bắt đầu từ tiết thứ {start_index}
- Tiếp tục đào sâu nội dung dàn ý hiện tại

【Chiến lược triển khai】
{strategy_instruction}
</task>

<project priority="P1">
【Thông tin dự án】
Tên tiểu thuyết: {project_title}
Thể loại: {project_genre}
Chủ đề: {project_theme}
Góc nhìn tự sự: {project_narrative_perspective}

【Bối cảnh thế giới quan】
Bối cảnh thời gian: {project_world_time_period}
Vị trí địa lý: {project_world_location}
Tông không khí: {project_world_atmosphere}
</project>

<characters priority="P1">
【Thông tin nhân vật】
{characters_info}
</characters>

<outline_node priority="P0">
【Nút dàn ý hiện tại - đối tượng triển khai】
Số thứ tự: tiết thứ {outline_order_index}
Tiêu đề: {outline_title}
Nội dung: {outline_content}
</outline_node>

<context priority="P2">
【Tham khảo bối cảnh】
{context_info}

【Các chương trước đã được tạo】
{previous_context}
</context>

<output priority="P0">
【Định dạng đầu ra】
Trả về mảng JSON kế hoạch chương cho các tiết {start_index}-{end_index} (tổng {target_chapter_count} đối tượng):

[
  {{
    "sub_index": {start_index},
    "title": "Tiêu đề chương",
    "plot_summary": "Tóm tắt cốt truyện (200-300 chữ): mô tả chi tiết sự kiện xảy ra trong chương này",
    "key_events": ["Sự kiện then chốt 1", "Sự kiện then chốt 2", "Sự kiện then chốt 3"],
    "character_focus": ["Nhân vật A", "Nhân vật B"],
    "emotional_tone": "Tông cảm xúc",
    "narrative_goal": "Mục tiêu tự sự",
    "conflict_type": "Loại xung đột",
    "estimated_words": 3000{scene_field}
  }}
]

【Quy chuẩn định dạng】
- Đầu ra mảng JSON thuần túy, không có văn bản khác
- Nghiêm cấm dùng ký hiệu đặc biệt trong mô tả nội dung
- sub_index bắt đầu từ {start_index}
</output>

<constraints>
【⚠️ Ràng buộc biên nội dung】
✅ Chỉ được triển khai nội dung của nút dàn ý hiện tại
✅ Đào sâu dàn ý hiện tại, không nhảy sang phần sau
✅ Làm chậm nhịp độ tự sự

❌ Tuyệt đối không được đẩy tới nội dung dàn ý tiếp theo
❌ Đừng để cốt truyện tiến nhanh

【Ràng buộc tính liên tục giữa các đợt】
✅ Nối tiếp tự nhiên với các chương đã tạo trước đó
✅ Đánh số bắt đầu từ tiết thứ {start_index}
✅ Giữ tính liên tục của tự sự

【🔴 Ràng buộc tạo sự khác biệt giữa các chương liền kề (chống lặp lại)】
✅ Mỗi chương có cách mở đầu và kết thúc độc đáo
✅ key_events tuyệt đối không trùng lặp giữa các chương kề nhau
✅ plot_summary mô tả nội dung độc đáo của chương đó
✅ Đặc biệt chú ý sự phân biệt với các chương trước
✅ Tránh lặp lại nội dung đã có

【Yêu cầu giữa các chương】
✅ Nối tiếp tự nhiên trôi chảy với các chương trước
✅ Cốt truyện tiến triển hợp lý (nhưng không vượt biên dàn ý hiện tại)
✅ Nhịp độ nhanh chậm điều độ
✅ Mỗi chương có giá trị tự sự rõ ràng và độc đáo
✅ Sự kiện then chốt không trùng lặp: kiểm tra key_events của đợt này và các chương trước

【Những điều cấm】
❌ Xuất định dạng không phải JSON
❌ Cốt truyện vượt biên sang dàn ý tiếp theo
❌ Nội dung các chương kề nhau lặp lại
❌ key_events giống với các chương trước
</constraints>"""

    # Prompt hệ thống viết lại chương V2 (khung RTCO)
    CHAPTER_REGENERATION_SYSTEM = """<system>
Bạn là biên tập viên và nhà văn tiểu thuyết chuyên nghiệp giàu kinh nghiệm, giỏi sáng tác lại chương dựa trên ý kiến phản hồi.
Nhiệm vụ của bạn là dựa trên chỉ dẫn chỉnh sửa, viết lại sâu và tối ưu chương gốc.
</system>

<task>
【Nhiệm vụ viết lại】
1. Hiểu kỹ nội dung, hướng phát triển cốt truyện và ý đồ tự sự của chương gốc
2. Phân tích nghiêm túc mọi yêu cầu chỉnh sửa, bao gồm gợi ý phân tích của AI và chỉ dẫn tùy chỉnh của người dùng
3. Đối với từng gợi ý chỉnh sửa, thực hiện cải thiện cụ thể trong phiên bản mới
4. Trên cơ sở giữ tính liên tục của câu chuyện và nhất quán nhân vật, sáng tác phiên bản mới đã cải thiện
5. Đảm bảo phiên bản mới có sự nâng cao rõ rệt về tính nghệ thuật, khả năng đọc và chất lượng tự sự
</task>

<guidelines>
【Nguyên tắc viết lại】
- **Hướng vào vấn đề**: cải thiện từng vấn đề được chỉ ra trong chỉ dẫn chỉnh sửa
- **Giữ tinh hoa**: giữ lại miêu tả, đối thoại và thiết kế tình tiết xuất sắc trong chương gốc
- **Đào sâu chi tiết**: tăng cường miêu tả cảnh, tô đậm cảm xúc và khắc họa nhân vật
- **Tối ưu nhịp độ**: điều chỉnh nhịp độ tự sự, tránh lê thê hoặc quá nhanh
- **Nhất quán phong cách**: nếu có yêu cầu phong cách viết, phải tuân thủ nghiêm ngặt

【Điểm cần chú trọng】
- Nếu chỉ dẫn chỉnh sửa đề cập vấn đề “nhịp độ”, trọng tâm điều chỉnh tốc độ tự sự và chuyển cảnh
- Nếu chỉ dẫn chỉnh sửa đề cập vấn đề “cảm xúc”, trọng tâm đào sâu diễn biến nội tâm và biểu đạt cảm xúc của nhân vật
- Nếu chỉ dẫn chỉnh sửa đề cập vấn đề “miêu tả”, trọng tâm làm giàu chi tiết môi trường và hành động
- Nếu chỉ dẫn chỉnh sửa đề cập vấn đề “đối thoại”, trọng tâm làm cho đối thoại tự nhiên hơn, cá tính hơn
- Nếu chỉ dẫn chỉnh sửa đề cập vấn đề “xung đột”, trọng tâm tăng cường mâu thuẫn và sức căng kịch tính
</guidelines>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung chính văn chương sau khi viết lại.
- Không bao gồm tiêu đề chương, số thứ tự hoặc thông tin meta khác
- Không xuất bất kỳ lời giải thích, chú thích hay lời giải thích sáng tác nào
- Bắt đầu trực tiếp từ nội dung câu chuyện, giữ tính liên tục của tự sự
</output>
"""
    # Prompt kiểm thử công cụ MCP
    MCP_TOOL_TEST = """Bạn là trợ lý kiểm thử plugin MCP, cần kiểm thử chức năng của plugin '{plugin_name}'.

⚠️ Quy tắc quan trọng: khi tạo tham số, phải dùng nghiêm ngặt tên tham số gốc được định nghĩa trong schema của công cụ, không chuyển thành snake_case hay định dạng khác.
Ví dụ: nếu trong schema là 'nextThoughtNeeded', thì phải dùng 'nextThoughtNeeded', không được đổi thành 'next_thought_needed'.

Hãy chọn một công cụ phù hợp để kiểm thử, ưu tiên công cụ tìm kiếm, truy vấn.
Tạo tham số kiểm thử thật và hợp lệ (ví dụ tìm kiếm "tiến triển mới nhất của trí tuệ nhân tạo" thay vì "test").

Bắt đầu kiểm thử plugin này ngay."""

    MCP_TOOL_TEST_SYSTEM = """Bạn là công cụ kiểm thử API chuyên nghiệp. Khi được cho danh sách công cụ, hãy chọn một công cụ và gọi nó với tham số phù hợp.

⚠️ Quy tắc then chốt: khi gọi công cụ, phải dùng nghiêm ngặt tên tham số gốc được định nghĩa trong schema, không tự ý chuyển đổi phong cách đặt tên.
- Nếu tên tham số là camelCase (như nextThoughtNeeded), thì dùng camelCase
- Nếu tên tham số là snake_case (như next_thought), thì dùng snake_case
- Giữ hoàn toàn nhất quán với định nghĩa trong schema, bao gồm chữ hoa chữ thường và phong cách đặt tên"""
    
    # Chế độ cảm hứng - tạo tên sách (prompt hệ thống)
    INSPIRATION_TITLE_SYSTEM = """Bạn là cố vấn sáng tác tiểu thuyết chuyên nghiệp.
Ý tưởng gốc của người dùng: {initial_idea}

Hãy dựa trên ý tưởng của người dùng, tạo 6 gợi ý tên sách hấp dẫn, yêu cầu:
1. Bám sát ý tưởng gốc và ý tưởng câu chuyện cốt lõi của người dùng
2. Giàu sáng tạo và sức hút
3. Bao quát các khuynh hướng phong cách khác nhau
4. Trong tên sách không được có ký hiệu "《》"

Trả về định dạng JSON:
{{
    "prompt": "Dựa trên ý tưởng của bạn, tôi đã chuẩn bị vài gợi ý tên sách:",
    "options": ["Tên sách 1", "Tên sách 2", "Tên sách 3", "Tên sách 4", "Tên sách 5", "Tên sách 6"]
}}

Chỉ trả về JSON thuần túy, không có văn bản khác."""

    # Chế độ cảm hứng - tạo tên sách (prompt người dùng)
    INSPIRATION_TITLE_USER = "Ý tưởng của người dùng: {initial_idea}\nHãy tạo 6 gợi ý tên sách"

    # Chế độ cảm hứng - tạo giới thiệu (prompt hệ thống)
    INSPIRATION_DESCRIPTION_SYSTEM = """Bạn là cố vấn sáng tác tiểu thuyết chuyên nghiệp.
Ý tưởng gốc của người dùng: {initial_idea}
Tên sách đã xác định: {title}

Hãy tạo 6 phần giới thiệu tiểu thuyết đặc sắc, yêu cầu:
1. Phải bám sát ý tưởng gốc của người dùng, đảm bảo phần giới thiệu là sự triển khai cụ thể của ý tưởng gốc
2. Phù hợp với phong cách của tên sách đã xác định
3. Ngắn gọn mạnh mẽ, mỗi phần 50-100 chữ
4. Bao gồm xung đột cốt lõi
5. Bao quát các hướng câu chuyện khác nhau, nhưng đều dựa trên ý tưởng gốc của người dùng

Trả về định dạng JSON:
{{"prompt":"Chọn một phần giới thiệu:","options":["Giới thiệu 1","Giới thiệu 2","Giới thiệu 3","Giới thiệu 4","Giới thiệu 5","Giới thiệu 6"]}}

Chỉ trả về JSON thuần túy, không có văn bản khác, không xuống dòng."""

    # Chế độ cảm hứng - tạo giới thiệu (prompt người dùng)
    INSPIRATION_DESCRIPTION_USER = "Ý tưởng gốc: {initial_idea}\nTên sách: {title}\nHãy tạo 6 lựa chọn giới thiệu"

    # Chế độ cảm hứng - tạo chủ đề (prompt hệ thống)
    INSPIRATION_THEME_SYSTEM = """Bạn là cố vấn sáng tác tiểu thuyết chuyên nghiệp.
Ý tưởng gốc của người dùng: {initial_idea}
Thông tin tiểu thuyết:
- Tên sách: {title}
- Giới thiệu: {description}

Hãy tạo 6 lựa chọn chủ đề sâu sắc, yêu cầu:
1. Phải giữ nhất quán cao với ý tưởng gốc của người dùng
2. Phù hợp với phong cách của tên sách và phần giới thiệu
3. Có chiều sâu và tính tư tưởng
4. Mỗi phần 50-150 chữ
5. Bao quát các góc độ khác nhau (như: trưởng thành, báo thù, cứu rỗi, khám phá v.v.), nhưng đều xoay quanh ý tưởng cốt lõi của người dùng

Trả về định dạng JSON:
{{"prompt":"Chủ đề cốt lõi của cuốn sách này là gì?","options":["Chủ đề 1","Chủ đề 2","Chủ đề 3","Chủ đề 4","Chủ đề 5","Chủ đề 6"]}}

Chỉ trả về JSON thuần túy, không có văn bản khác, không xuống dòng."""

    # Chế độ cảm hứng - tạo chủ đề (prompt người dùng)
    INSPIRATION_THEME_USER = "Ý tưởng gốc: {initial_idea}\nTên sách: {title}\nGiới thiệu: {description}\nHãy tạo 6 lựa chọn chủ đề"

    # Chế độ cảm hứng - tạo thể loại (prompt hệ thống)
    INSPIRATION_GENRE_SYSTEM = """Bạn là cố vấn sáng tác tiểu thuyết chuyên nghiệp.
Ý tưởng gốc của người dùng: {initial_idea}
Thông tin tiểu thuyết:
- Tên sách: {title}
- Giới thiệu: {description}
- Chủ đề: {theme}

Hãy tạo 6 nhãn thể loại phù hợp (mỗi nhãn 2-4 chữ), yêu cầu:
1. Phải phù hợp với khuynh hướng thể loại được gợi ý trong ý tưởng gốc của người dùng
2. Phù hợp với phong cách tổng thể của tiểu thuyết
3. Có thể chọn nhiều kết hợp

Các thể loại thường gặp: Huyền huyễn, Đô thị, Khoa học viễn tưởng, Võ hiệp, Tiên hiệp, Lịch sử, Ngôn tình, Huyền nghi, Kỳ ảo, Tu tiên v.v.

Trả về định dạng JSON:
{{"prompt":"Chọn nhãn thể loại (có thể chọn nhiều):","options":["Thể loại 1","Thể loại 2","Thể loại 3","Thể loại 4","Thể loại 5","Thể loại 6"]}}

Chỉ trả về JSON thuần túy gọn nhẹ, không xuống dòng, không có văn bản khác."""

    # Chế độ cảm hứng - tạo thể loại (prompt người dùng)
    INSPIRATION_GENRE_USER = "Ý tưởng gốc: {initial_idea}\nTên sách: {title}\nGiới thiệu: {description}\nChủ đề: {theme}\nHãy tạo 6 nhãn thể loại"

    # Prompt tự động hoàn thiện thông minh chế độ cảm hứng
    INSPIRATION_QUICK_COMPLETE = """Bạn là cố vấn sáng tác tiểu thuyết chuyên nghiệp. Người dùng đã cung cấp một phần thông tin tiểu thuyết, hãy hoàn thiện các trường còn thiếu.

Thông tin người dùng đã cung cấp:
{existing}

Hãy tạo phương án tiểu thuyết hoàn chỉnh, bao gồm:
1. title: tên sách (3-6 chữ, nếu người dùng đã cung cấp thì giữ nguyên)
2. description: giới thiệu (50-100 chữ, phải dựa trên thông tin người dùng cung cấp, không được lệch khỏi ý gốc)
3. theme: chủ đề cốt lõi (30-50 chữ, phải giữ nhất quán với thông tin người dùng cung cấp)
4. genre: mảng nhãn thể loại (2-3 nhãn)

Quan trọng: mọi nội dung hoàn thiện đều phải giữ liên quan cao với thông tin người dùng cung cấp, đảm bảo nhất quán trước sau.

Trả về định dạng JSON:
{{
    "title": "Tên sách",
    "description": "Nội dung giới thiệu...",
    "theme": "Nội dung chủ đề...",
    "genre": ["Thể loại 1", "Thể loại 2"]
}}

Chỉ trả về JSON thuần túy, không có văn bản khác."""
    # Prompt thu thập tư liệu thế giới quan (dùng tăng cường MCP)
    MCP_WORLD_BUILDING_PLANNING = """Bạn đang thiết kế thế giới quan cho tiểu thuyết “{title}”.

【Thông tin tiểu thuyết】
- Đề tài: {genre}
- Chủ đề: {theme}
- Giới thiệu: {description}

【Nhiệm vụ】
Hãy dùng các công cụ khả dụng để tìm kiếm tư liệu nền liên quan, giúp xây dựng thiết lập thế giới quan chân thực và sâu sắc hơn.
Bạn có thể tra cứu:
1. Bối cảnh lịch sử (nếu là đề tài lịch sử)
2. Môi trường địa lý và đặc trưng văn hóa
3. Kiến thức chuyên môn trong lĩnh vực liên quan
4. Tham khảo thiết lập của các tác phẩm tương tự

Hãy tra cứu 1 câu hỏi then chốt nhất (không quá 1 câu)."""

    # Prompt thu thập tư liệu nhân vật (dùng tăng cường MCP)
    MCP_CHARACTER_PLANNING = """Bạn đang thiết kế nhân vật cho tiểu thuyết “{title}”.

【Thông tin tiểu thuyết】
- Đề tài: {genre}
- Chủ đề: {theme}
- Bối cảnh thời đại: {time_period}
- Vị trí địa lý: {location}

【Nhiệm vụ】
Hãy dùng các công cụ khả dụng để tìm kiếm tư liệu tham khảo liên quan, giúp thiết kế nhân vật chân thực và sâu sắc hơn.
Bạn có thể tra cứu:
1. Đặc trưng nhân vật lịch sử có thật của thời đại/vùng đất đó
2. Bối cảnh văn hóa và phong tục xã hội
3. Đặc điểm nghề nghiệp và lối sống
4. Nguyên mẫu nhân vật trong lĩnh vực liên quan

Hãy tra cứu 1 câu hỏi then chốt nhất (không quá 1 câu)."""

    # Tự động đưa nhân vật mới vào - prompt phân tích dự đoán V2 (khung RTCO)
    AUTO_CHARACTER_ANALYSIS = """<system>
Bạn là cố vấn thiết kế nhân vật tiểu thuyết chuyên nghiệp, giỏi dự đoán nhu cầu nhân vật từ sự phát triển cốt truyện.
</system>

<task>
【Nhiệm vụ phân tích】
Dự đoán trong {chapter_count} chương viết tiếp sắp tới, dựa trên hướng phát triển và giai đoạn cốt truyện, có cần đưa nhân vật mới vào không.

【Lưu ý quan trọng】
Đây là phân tích dự đoán, không phải phân tích hậu kiểm dựa trên nội dung đã tạo.
</task>

<project priority="P1">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}

【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
</project>

<context priority="P0">
【Nhân vật đã có】
{existing_characters}

【Tổng quan các chương đã có】
{all_chapters_brief}

【Kế hoạch viết tiếp】
- Chương bắt đầu: chương {start_chapter}
- Số chương viết tiếp: {chapter_count} chương
- Giai đoạn cốt truyện: {plot_stage}
- Hướng phát triển: {story_direction}
</context>

<analysis_framework priority="P0">
【Khía cạnh phân tích dự đoán】

**1. Dự đoán nhu cầu cốt truyện**
Dựa trên hướng phát triển, những cảnh, xung đột nào cần nhân vật mới tham gia?

**2. Tính đầy đủ của nhân vật**
Các nhân vật hiện có có đủ để chống đỡ cốt truyện sắp xảy ra không?

**3. Thời điểm đưa vào**
Nhân vật mới nên xuất hiện ở chương nào là phù hợp nhất?

**4. Đánh giá mức độ quan trọng**
Nhân vật mới ảnh hưởng thế nào đến cốt truyện về sau?

【Căn cứ dự đoán】
- Nhu cầu nhân vật điển hình của giai đoạn cốt truyện (như: giai đoạn cao trào có thể cần đối thủ mạnh)
- Nhu cầu logic của hướng phát triển câu chuyện (như: vào địa điểm mới cần nhân vật địa phương)
- Nhu cầu nhân vật khi xung đột leo thang (như: phản diện mạnh hơn, đồng minh bất ngờ)
- Nhu cầu mở rộng thế giới quan (như: đại diện tổ chức, thế lực mới)
</analysis_framework>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy (một trong hai trường hợp):

**Trường hợp A: cần nhân vật mới**
{{
  "needs_new_characters": true,
  "reason": "Lý do phân tích dự đoán (150-200 chữ), giải thích tại sao cốt truyện sắp tới cần nhân vật mới",
  "character_count": 2,
  "character_specifications": [
    {{
      "name": "Tên nhân vật được đề xuất (tùy chọn)",
      "role_description": "Định vị và vai trò của nhân vật trong cốt truyện (100-150 chữ)",
      "suggested_role_type": "supporting/antagonist/protagonist",
      "importance": "high/medium/low",
      "appearance_chapter": {start_chapter},
      "key_abilities": ["Năng lực 1", "Năng lực 2"],
      "plot_function": "Chức năng cụ thể trong cốt truyện",
      "relationship_suggestions": [
        {{
          "target_character": "Tên nhân vật đã có",
          "relationship_type": "Loại quan hệ được đề xuất",
          "reason": "Tại sao thiết lập quan hệ này"
        }}
      ]
    }}
  ]
}}

**Trường hợp B: không cần nhân vật mới**
{{
  "needs_new_characters": false,
  "reason": "Các nhân vật hiện có đủ để chống đỡ sự phát triển cốt truyện sắp tới, nêu lý do"
}}
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Đây là phân tích dự đoán, hướng tới cốt truyện tương lai
✅ Cân nhắc sự phát triển tự nhiên và nhịp độ của cốt truyện
✅ Đảm bảo tính cần thiết khi đưa vào, không đưa vào vì mục đích đưa vào
✅ Ưu tiên vai trò lâu dài của nhân vật

【Những điều cấm】
❌ Xuất đánh dấu markdown
❌ Phân tích hậu kiểm dựa trên nội dung đã tạo
❌ Cố ép đưa nhân vật vào để đưa vào cho được
❌ Thiết kế nhân vật chức năng dùng một lần
</constraints>"""

    # Tự động đưa nhân vật mới vào - prompt tạo V2 (khung RTCO)
    AUTO_CHARACTER_GENERATION = """<system>
Bạn là chuyên gia thiết lập nhân vật, giỏi tạo thiết lập nhân vật hoàn chỉnh theo nhu cầu cốt truyện.
</system>

<task>
【Nhiệm vụ tạo mới】
Tạo thiết lập hoàn chỉnh cho nhân vật mới của tiểu thuyết, bao gồm thông tin cơ bản, tính cách bối cảnh, mạng lưới quan hệ và thông tin nghề nghiệp.
</task>

<project priority="P1">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}

【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}
</project>

<context priority="P0">
【Nhân vật đã có】
{existing_characters}

【Bối cảnh cốt truyện】
{plot_context}

【Yêu cầu đặc tả nhân vật】
{character_specification}
</context>

<mcp_context priority="P2">
【Tham khảo công cụ MCP】
{mcp_references}
</mcp_context>

<requirements priority="P0">
【Yêu cầu cốt lõi】
1. Nhân vật phải phù hợp với nhu cầu cốt truyện và thiết lập thế giới quan
2. **Phải phân tích quan hệ giữa nhân vật mới và các nhân vật đã có**, thiết lập ít nhất 1-3 quan hệ có ý nghĩa
3. Tính cách, bối cảnh phải có chiều sâu và nét độc đáo
4. Miêu tả ngoại hình phải cụ thể sinh động
5. Sở trường và năng lực phải phù hợp với định vị nhân vật
6. **Nếu 【Nhân vật đã có】 chứa danh sách nghề nghiệp, phải thiết lập nghề nghiệp cho nhân vật**

【Hướng dẫn thiết lập quan hệ】
- Xem xét kỹ danh sách 【Nhân vật đã có】, suy nghĩ nhân vật mới có liên hệ với nhân vật hiện có nào
- Dựa trên nhu cầu cốt truyện, thiết lập quan hệ nhân vật hợp lý
- Mỗi quan hệ đều phải có loại hình, độ thân thiết và mô tả rõ ràng
- Quan hệ nên phục vụ sự phát triển cốt truyện
- Nếu nhân vật mới là thành viên tổ chức, nhớ điền organization_memberships

【Yêu cầu thông tin nghề nghiệp】
Nếu phần 【Nhân vật đã có】 chứa "danh sách nghề chính khả dụng" hoặc "danh sách nghề phụ khả dụng":
- Xem kỹ danh sách nghề chính và nghề phụ khả dụng
- Dựa trên bối cảnh, năng lực, định vị câu chuyện của nhân vật, chọn nghề phù hợp nhất
- Nghề chính: chọn một nghề từ "danh sách nghề chính khả dụng", điền tên nghề nghiệp
- Giai đoạn nghề chính: dựa trên thông tin giai đoạn của nghề và thực lực nhân vật, đặt giai đoạn hiện tại hợp lý
- Nghề phụ: có thể chọn 0-2 nghề phụ
- ⚠️ Quan trọng: phải điền tên nghề nghiệp chứ không phải ID
</requirements>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy:

{{
  "name": "Tên nhân vật",
  "age": 25,
  "gender": "Nam/Nữ/Khác",
  "role_type": "supporting",
  "personality": "Mô tả chi tiết đặc điểm tính cách (100-200 chữ)",
  "background": "Mô tả chi tiết câu chuyện nền (100-200 chữ)",
  "appearance": "Mô tả ngoại hình (50-100 chữ)",
  "traits": ["Sở trường 1", "Sở trường 2", "Sở trường 3"],
  "relationships_text": "Mô tả bằng ngôn ngữ tự nhiên mạng lưới quan hệ của nhân vật này với các nhân vật khác",
  
  "relationships": [
    {{
      "target_character_name": "Tên nhân vật đã tồn tại",
      "relationship_type": "Loại quan hệ",
      "intimacy_level": 75,
      "description": "Mô tả cụ thể quan hệ",
      "status": "active"
    }}
  ],
  "organization_memberships": [
    {{
      "organization_name": "Tên tổ chức đã tồn tại",
      "position": "Chức vụ",
      "rank": 5,
      "loyalty": 80
    }}
  ],
  
  "career_info": {{
    "main_career_name": "Tên nghề nghiệp chọn từ danh sách nghề chính khả dụng",
    "main_career_stage": 5,
    "sub_careers": [
      {{
        "career_name": "Tên nghề nghiệp chọn từ danh sách nghề phụ khả dụng",
        "stage": 3
      }}
    ]
  }}
}}

【Tham khảo loại quan hệ】
Các loại quan hệ gia đình, xã hội, nghề nghiệp, đối địch v.v.

【Phạm vi giá trị số】
- intimacy_level: -100 đến 100 (giá trị âm biểu thị đối địch)
- loyalty: 0 đến 100
- rank: 0 đến 10
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Phù hợp với nhu cầu cốt truyện và thiết lập thế giới quan
✅ Mảng relationships bắt buộc: ít nhất 1-3 quan hệ
✅ target_character_name phải khớp chính xác với 【Nhân vật đã có】
✅ organization_memberships chỉ được tham chiếu các tổ chức đã tồn tại
✅ Lựa chọn nghề nghiệp phải chọn từ danh sách khả dụng

【Những điều cấm】
❌ Xuất đánh dấu markdown
❌ Dùng ký hiệu đặc biệt trong mô tả
❌ Tham chiếu nhân vật hoặc tổ chức không tồn tại
❌ Dùng ID nghề nghiệp thay vì tên nghề nghiệp
</constraints>"""

    # Tự động đưa tổ chức mới vào - prompt phân tích dự đoán (khung RTCO)
    AUTO_ORGANIZATION_ANALYSIS = """<system>
Bạn là cố vấn xây dựng thế giới tiểu thuyết chuyên nghiệp, giỏi dự đoán nhu cầu tổ chức/thế lực từ sự phát triển cốt truyện.
</system>

<task>
【Nhiệm vụ phân tích】
Dự đoán trong {chapter_count} chương viết tiếp sắp tới, dựa trên hướng phát triển và giai đoạn cốt truyện, có cần đưa tổ chức hoặc thế lực mới vào không.

【Lưu ý quan trọng】
Đây là phân tích dự đoán, không phải phân tích hậu kiểm dựa trên nội dung đã tạo.
Tổ chức bao gồm: bang hội, môn phái, công ty, cơ quan chính phủ, tổ chức bí ẩn, gia tộc v.v.
</task>

<project priority="P1">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}

【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
</project>

<context priority="P0">
【Tổ chức đã có】
{existing_organizations}

【Nhân vật đã có】
{existing_characters}

【Tổng quan các chương đã có】
{all_chapters_brief}

【Kế hoạch viết tiếp】
- Chương bắt đầu: chương {start_chapter}
- Số chương viết tiếp: {chapter_count} chương
- Giai đoạn cốt truyện: {plot_stage}
- Hướng phát triển: {story_direction}
</context>

<analysis_framework priority="P0">
【Khía cạnh phân tích dự đoán】

**1. Nhu cầu mở rộng thế giới quan**
Dựa trên hướng phát triển, có cần thế lực hoặc tổ chức mới để làm giàu thế giới quan không?

**2. Nhu cầu leo thang xung đột**
Cốt truyện có cần thế lực đối lập mới, tổ chức cạnh tranh hoặc tập đoàn bí ẩn không?

**3. Nhu cầu thuộc về của nhân vật**
Nhân vật hiện có có cần gia nhập hoặc đối kháng một tổ chức mới không?

**4. Nhu cầu thúc đẩy cốt truyện**
Tổ chức mới có thể trở thành lực lượng then chốt thúc đẩy cốt truyện không?

**5. Thời điểm đưa vào**
Tổ chức mới nên xuất hiện ở chương nào là phù hợp nhất?

【Căn cứ dự đoán】
- Nhu cầu tổ chức điển hình của giai đoạn cốt truyện (như: giai đoạn cao trào có thể cần thế lực đối địch hùng mạnh)
- Nhu cầu logic của hướng phát triển câu chuyện (như: vào địa điểm mới cần thế lực địa phương)
- Nhu cầu tính hoàn chỉnh của thế giới quan (như: cục diện quyền lực cần nhiều bên thế lực)
- Nhu cầu trưởng thành của nhân vật (như: nhân vật chính cần gia nhập hoặc lập tổ chức)
</analysis_framework>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy (một trong hai trường hợp):

**Trường hợp A: cần tổ chức mới**
{{
"needs_new_organizations": true,
"reason": "Lý do phân tích dự đoán (150-200 chữ), giải thích tại sao cốt truyện sắp tới cần tổ chức mới",
"organization_count": 1,
"organization_specifications": [
{{
  "name": "Tên tổ chức được đề xuất (tùy chọn)",
  "organization_description": "Định vị và vai trò của tổ chức trong cốt truyện (100-150 chữ)",
  "organization_type": "Bang hội/Môn phái/Công ty/Chính phủ/Gia tộc/Tổ chức bí ẩn v.v.",
  "importance": "high/medium/low",
  "appearance_chapter": {start_chapter},
  "power_level": 70,
  "plot_function": "Chức năng cụ thể trong cốt truyện",
  "location": "Nơi đặt tổ chức hoặc khu vực hoạt động",
  "motto": "Khẩu hiệu hoặc tôn chỉ của tổ chức (tùy chọn)",
  "initial_members": [
    {{
      "character_name": "Tên nhân vật đã có (nếu cần gia nhập)",
      "position": "Chức vụ",
      "reason": "Tại sao gia nhập"
    }}
  ],
  "relationship_suggestions": [
    {{
      "target_organization": "Tên tổ chức đã có",
      "relationship_type": "Loại quan hệ được đề xuất (đồng minh/đối địch/cạnh tranh/hợp tác v.v.)",
      "reason": "Tại sao thiết lập quan hệ này"
    }}
  ]
}}
]
}}

**Trường hợp B: không cần tổ chức mới**
{{
"needs_new_organizations": false,
"reason": "Các tổ chức hiện có đủ để chống đỡ sự phát triển cốt truyện sắp tới, nêu lý do"
}}
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Đây là phân tích dự đoán, hướng tới cốt truyện tương lai
✅ Cân nhắc sự phong phú và hoàn chỉnh của thế giới quan
✅ Đảm bảo tính cần thiết khi đưa vào, không đưa vào vì mục đích đưa vào
✅ Ưu tiên vai trò lâu dài của tổ chức
✅ Tổ chức nên là lực lượng then chốt thúc đẩy cốt truyện

【Những điều cấm】
❌ Xuất đánh dấu markdown
❌ Phân tích hậu kiểm dựa trên nội dung đã tạo
❌ Cố ép đưa tổ chức vào để đưa vào cho được
❌ Thiết kế tổ chức chức năng dùng một lần
❌ Tạo tổ chức trùng chức năng với tổ chức hiện có
</constraints>"""

    # Tự động đưa tổ chức mới vào - prompt tạo (khung RTCO)
    AUTO_ORGANIZATION_GENERATION = """<system>
Bạn là nhà xây dựng thế giới chuyên nghiệp, giỏi tạo thiết lập tổ chức/thế lực hoàn chỉnh theo nhu cầu cốt truyện.
</system>

<task>
【Nhiệm vụ tạo mới】
Tạo thiết lập hoàn chỉnh cho tổ chức mới của tiểu thuyết, bao gồm thông tin cơ bản, đặc tính tổ chức, lịch sử bối cảnh và cấu trúc thành viên.
</task>

<project priority="P1">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}

【Thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}
</project>

<context priority="P0">
【Tổ chức đã có】
{existing_organizations}

【Nhân vật đã có】
{existing_characters}

【Bối cảnh cốt truyện】
{plot_context}

【Yêu cầu đặc tả tổ chức】
{organization_specification}
</context>

<mcp_context priority="P2">
【Tham khảo công cụ MCP】
{mcp_references}
</mcp_context>

<requirements priority="P0">
【Yêu cầu cốt lõi】
1. Tổ chức phải phù hợp với nhu cầu cốt truyện và thiết lập thế giới quan
2. Tổ chức phải có mục đích, cấu trúc và đặc sắc rõ ràng
3. Đặc tính tổ chức, bối cảnh phải có chiều sâu và nét độc đáo
4. Biểu hiện bên ngoài phải cụ thể sinh động
5. Cân nhắc quan hệ và tương tác với các tổ chức đã có
6. Nếu cần, có thể đề xuất đưa nhân vật hiện có vào tổ chức
</requirements>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy:

{{
"name": "Tên tổ chức",
"is_organization": true,
"role_type": "supporting",
"organization_type": "Loại hình tổ chức (Bang hội/Môn phái/Công ty/Chính phủ/Gia tộc/Tổ chức bí ẩn v.v.)",
"personality": "Mô tả chi tiết đặc tính tổ chức (150-200 chữ): cách vận hành, tư tưởng cốt lõi, phong cách hành sự, giá trị văn hóa",
"background": "Câu chuyện bối cảnh tổ chức (200-300 chữ): lịch sử thành lập, quá trình phát triển, sự kiện quan trọng, địa vị hiện tại",
"appearance": "Biểu hiện bên ngoài (100-150 chữ): vị trí trụ sở, kiến trúc biểu tượng, biểu tượng tổ chức, trang phục thành viên",
"organization_purpose": "Mục đích và tôn chỉ của tổ chức: mục tiêu rõ ràng, tầm nhìn dài hạn, quy tắc hành động",
"power_level": 75,
"location": "Nơi đặt: khu vực hoạt động chính, phạm vi thế lực",
"motto": "Châm ngôn hoặc khẩu hiệu của tổ chức",
"color": "Màu đại diện của tổ chức",
"traits": ["Đặc trưng 1", "Đặc trưng 2", "Đặc trưng 3"],

"initial_members": [
{{
  "character_name": "Tên nhân vật đã tồn tại",
  "position": "Tên chức vụ",
  "rank": 8,
  "loyalty": 80,
  "joined_at": "Thời gian gia nhập (tùy chọn)",
  "status": "active"
}}
],

"organization_relationships": [
{{
  "target_organization_name": "Tên tổ chức đã tồn tại",
  "relationship_type": "Đồng minh/Đối địch/Cạnh tranh/Hợp tác/Phụ thuộc v.v.",
  "description": "Mô tả cụ thể quan hệ"
}}
]
}}

【Phạm vi giá trị số】
- power_level: số nguyên 0-100, biểu thị mức ảnh hưởng trong thế giới
- rank: 0 đến 10 (cấp bậc chức vụ)
- loyalty: 0 đến 100 (độ trung thành của thành viên)
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Phù hợp với nhu cầu cốt truyện và thiết lập thế giới quan
✅ Tổ chức phải có định vị và giá trị độc đáo
✅ character_name phải khớp chính xác với 【Nhân vật đã có】
✅ target_organization_name phải khớp chính xác với 【Tổ chức đã có】
✅ Tổ chức có thể thúc đẩy cốt truyện phát triển

【Những điều cấm】
❌ Xuất đánh dấu markdown
❌ Dùng ký hiệu đặc biệt trong mô tả
❌ Tham chiếu nhân vật hoặc tổ chức không tồn tại
❌ Tạo tổ chức trùng chức năng với tổ chức hiện có
❌ Tạo tổ chức không có tác dụng thực tế đối với cốt truyện
</constraints>"""

    # Prompt tạo hệ thống nghề nghiệp V2 (khung RTCO)
    CAREER_SYSTEM_GENERATION = """<system>
Bạn là nhà thiết kế hệ thống nghề nghiệp chuyên nghiệp, giỏi thiết kế hệ thống nghề nghiệp hoàn chỉnh cho các thế giới quan khác nhau.
</system>

<task>
【Nhiệm vụ thiết kế】
Dựa trên thông tin thế giới quan và giới thiệu dự án, thiết kế một hệ thống nghề nghiệp hoàn chỉnh và hợp lý.
Hệ thống nghề nghiệp phải ăn khớp cao với bối cảnh câu chuyện và thiết lập nhân vật trong phần giới thiệu dự án.

【Yêu cầu số lượng】
- Nghề chính: tạo chính xác 1 nghề
- Nghề phụ: tạo chính xác 1 nghề
</task>

<worldview priority="P0">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}
Giới thiệu: {description}

【Thiết lập thế giới quan】
Bối cảnh thời gian: {time_period}
Vị trí địa lý: {location}
Tông không khí: {atmosphere}
Quy tắc thế giới: {rules}
</worldview>

<design_requirements priority="P0">
【Yêu cầu thiết kế】

**1. Nghề chính (main_careers) - phải tạo chính xác 1 nghề**
- Nghề chính là hướng phát triển cốt lõi của nhân vật
- Phải tuân thủ nghiêm ngặt quy tắc thế giới quan và bối cảnh câu chuyện trong phần giới thiệu
- Số lượng giai đoạn của mỗi nghề chính có thể khác nhau (thể hiện sự khác biệt về độ phức tạp của nghề)
- Thiết kế nghề phải chống đỡ được tình tiết câu chuyện được mô tả trong phần giới thiệu

**2. Nghề phụ (sub_careers) - phải tạo chính xác 1 nghề**
- Nghề phụ bao gồm các loại sản xuất, hỗ trợ, kỹ năng đặc biệt
- Số lượng giai đoạn của mỗi nghề phụ có thể khác nhau
- Đừng để mọi nghề phụ đều có số giai đoạn giống nhau
- Nghề phụ phải hỗ trợ hoặc tăng ích cho nghề chính

**3. Thiết kế giai đoạn (stages)**
- Độ dài mảng stages của mỗi nghề phải bằng max_stage
- Tên giai đoạn phải phù hợp với bối cảnh văn hóa của thế giới quan
- Mô tả giai đoạn phải thể hiện lộ trình nâng cao năng lực rõ ràng
- Đảm bảo số lượng giai đoạn giữa các nghề có sự khác biệt
- Số giai đoạn nghề chính đề xuất: 8-12
- Số giai đoạn nghề phụ đề xuất: 5-8

**4. Độ ăn khớp với giới thiệu**
- Hệ thống nghề nghiệp phải khớp với thiết lập câu chuyện trong phần giới thiệu dự án
- Nếu phần giới thiệu đề cập nghề hoặc năng lực cụ thể, ưu tiên thiết kế nghề liên quan
- Năng lực và đặc điểm của nghề phải chống đỡ được sự phát triển tình tiết trong phần giới thiệu
</design_requirements>

<output priority="P0">
【Định dạng đầu ra】
Trả về đối tượng JSON thuần túy:

{{
"main_careers": [
{{
  "name": "Tên nghề nghiệp",
  "description": "Mô tả nghề nghiệp (100-150 chữ)",
  "category": "Phân loại nghề nghiệp",
  "stages": [
    {{"level": 1, "name": "Tên giai đoạn 1", "description": "Mô tả giai đoạn"}},
    {{"level": 2, "name": "Tên giai đoạn 2", "description": "Mô tả giai đoạn"}}
  ],
  "max_stage": số nguyên,
  "requirements": "Yêu cầu nghề nghiệp và điều kiện tiên quyết",
  "special_abilities": "Năng lực đặc biệt của nghề",
  "worldview_rules": "Mối liên hệ với quy tắc thế giới quan",
  "attribute_bonuses": {{"strength": "+10%"}}
}}
],
"sub_careers": [
{{
  "name": "Tên nghề phụ",
  "description": "Mô tả nghề nghiệp (80-120 chữ)",
  "category": "Hệ sản xuất/Hệ hỗ trợ/Hệ đặc biệt",
  "stages": [
    {{"level": 1, "name": "Tên giai đoạn 1", "description": "Mô tả giai đoạn"}}
  ],
  "max_stage": số nguyên,
  "requirements": "Yêu cầu nghề nghiệp",
  "special_abilities": "Năng lực đặc biệt"
}}
]
}}
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Số lượng nghề chính: phải tạo chính xác 1 nghề, không thừa không thiếu
✅ Số lượng nghề phụ: phải tạo chính xác 1 nghề, không thừa không thiếu
✅ Số giai đoạn nghề chính đề xuất: 8-12
✅ Số giai đoạn nghề phụ đề xuất: 5-8
✅ Độ dài mảng stages phải bằng max_stage
✅ Đảm bảo hệ thống nghề nghiệp ăn khớp cao với thế giới quan
✅ Thiết kế nghề phải chống đỡ tình tiết câu chuyện trong phần giới thiệu dự án

【Những điều cấm】
❌ Mọi nghề đều dùng số giai đoạn giống nhau
❌ Xuất đánh dấu markdown
❌ Thiết kế nghề rời rạc với thế giới quan hoặc phần giới thiệu
❌ Bỏ qua thiết lập nghề hoặc năng lực được đề cập trong phần giới thiệu
</constraints>"""

    # Prompt viết lại cục bộ (khung RTCO)
    PARTIAL_REGENERATE = """<system>
Bạn là trợ lý viết lại tiểu thuyết chuyên nghiệp, giỏi viết lại chính xác đoạn văn được chỉ định theo yêu cầu chỉnh sửa của người dùng, đồng thời đảm bảo nối tiếp liền mạch với văn bản trước sau.
</system>

<task>
【Nhiệm vụ viết lại】
Dựa trên yêu cầu chỉnh sửa của người dùng, viết lại đoạn văn bản được chọn dưới đây.

【Yêu cầu quan trọng】
1. Chỉ xuất nội dung sau khi viết lại, không bao gồm bất kỳ lời giải thích, tiền tố hay hậu tố nào
2. Giữ sự nối tiếp tự nhiên và giọng điệu liền mạch với văn bản trước sau
3. Tuân thủ nghiêm ngặt yêu cầu chỉnh sửa của người dùng
4. Giữ nhất quán phong cách tự sự tổng thể
</task>

<context priority="P0">
【Tham khảo văn bản trước】(dùng để nối tiếp, đừng lặp lại)
{context_before}

【Văn bản gốc cần viết lại】(tổng {original_word_count} chữ)
{selected_text}

【Tham khảo văn bản sau】(dùng để nối tiếp, đừng lặp lại)
{context_after}
</context>

<user_requirements priority="P0">
【Yêu cầu chỉnh sửa của người dùng】
{user_instructions}

【Yêu cầu số chữ】
{length_requirement}
</user_requirements>

<style priority="P1">
【Phong cách viết】
{style_content}
</style>

<output>
【Quy chuẩn đầu ra】
Xuất trực tiếp nội dung sau khi viết lại, bắt đầu viết từ nội dung câu chuyện.
- Không xuất bất kỳ văn bản giải thích hay thuyết minh nào
- Không xuất tiền tố như “Đã viết lại:”
- Không xuất nội dung bọc trong dấu ngoặc kép
- Đảm bảo nội dung xuất ra có thể thay thế trực tiếp văn bản gốc

Hãy xuất trực tiếp nội dung sau khi viết lại:
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Nối tiếp trước sau: nội dung xuất ra phải nối tiếp tự nhiên với văn bản trước, chuyển tiếp mượt mà với văn bản sau
✅ Nhất quán phong cách: giữ cùng phong cách tự sự, giọng điệu và ngôi kể với văn bản gốc
✅ Ưu tiên yêu cầu: thực thi nghiêm ngặt yêu cầu chỉnh sửa của người dùng
✅ Kiểm soát số chữ: tuân thủ yêu cầu số chữ

【Những điều cấm】
❌ Lặp lại nội dung văn bản trước
❌ Lặp lại nội dung văn bản sau
❌ Thêm bất kỳ thông tin meta hay lời thuyết minh nào
❌ Thay đổi ngôi kể hay góc nhìn tự sự
❌ Lệch khỏi yêu cầu chỉnh sửa của người dùng
</constraints>"""

    # Nhập sách tách - prompt trích xuất ngược dự án
    BOOK_IMPORT_REVERSE_PROJECT_SUGGESTION = """<system>
Bạn là biên tập viên hoạch định văn học mạng dày dặn kinh nghiệm, giỏi trích xuất ngược thông tin lập dự án từ chính văn tiểu thuyết.
</system>

<task>
【Nhiệm vụ】
Dựa trên nội dung 3 chương đầu được cung cấp, trích xuất thông tin lập dự án cốt lõi của tiểu thuyết này, dùng để tạo dự án mới.

【Mục tiêu】
Trên cơ sở không lệch khỏi văn bản gốc, xuất thông tin có cấu trúc có thể dùng trực tiếp cho khởi tạo dự án.
</task>

<input priority="P0">
【Thông tin đầu vào】
Tên sách: {title}
Nội dung 3 chương đầu:
{sampled_text}
</input>

<output priority="P0">
【Định dạng đầu ra】
Chỉ xuất một đối tượng JSON thuần túy (không markdown, không khối mã, không giải thích):

{{
  "description": "Giới thiệu tiểu thuyết",
  "theme": "Chủ đề cốt lõi",
  "genre": "Thể loại tiểu thuyết",
  "narrative_perspective": "Ngôi thứ nhất/Ngôi thứ ba/Góc nhìn toàn tri",
  "target_words": 100000
}}

【Yêu cầu trường dữ liệu】
1) description: 120-260 chữ, tập trung vào nhân vật chính, xung đột cốt lõi, mục tiêu tuyến chính và sức căng câu chuyện.
2) theme: 120-260 chữ, trích xuất mệnh đề cốt lõi mà tác phẩm muốn biểu đạt.
3) genre: 2-12 chữ, như đô thị, huyền huyễn, huyền nghi, khoa học viễn tưởng, ngôn tình v.v.
4) narrative_perspective: chỉ được là “Ngôi thứ nhất” hoặc “Ngôi thứ ba” hoặc “Góc nhìn toàn tri”.
5) target_words: số nguyên. Dự kiến hợp lý theo quy mô văn học mạng; không thể đánh giá thì trả về 100000.
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Dựa nghiêm ngặt vào nội dung chính văn đã cho, không tự thêm thiết lập then chốt
✅ Giữ thông tin nhất quán, tránh mâu thuẫn lẫn nhau
✅ Đầu ra phải là đối tượng JSON có thể phân tích được
✅ genre của tiểu thuyết có thể gồm nhiều thể loại

【Những điều cấm】
❌ Xuất bất kỳ văn bản nào ngoài JSON
❌ Dùng đánh dấu markdown hoặc khối mã để bọc
❌ narrative_perspective xuất nội dung ngoài các giá trị liệt kê
❌ target_words xuất giá trị không phải số nguyên
</constraints>"""

    # Nhập sách tách - tạo ngược dàn ý chương (căn chỉnh nghiêm ngặt với cấu trúc OUTLINE_CREATE)
    BOOK_IMPORT_REVERSE_OUTLINES = """<system>
Bạn là tổng biên tập văn học mạng và nhà hoạch định cốt truyện dày dặn kinh nghiệm, giỏi trích xuất ngược dàn ý chương chuẩn hóa dựa trên các chương đã hoàn thành.
</system>

<task>
【Nhiệm vụ】
Dựa trên chính văn chương được cho (mỗi đợt tối đa 5 chương), tạo ngược cấu trúc dàn ý tương ứng cho mỗi chương.

【Mục tiêu cốt lõi】
Cấu trúc đầu ra phải nhất quán nghiêm ngặt với cấu trúc tạo dàn ý hiện có của hệ thống (nhất quán với các trường OUTLINE_CREATE), dùng để nhập trực tiếp vào kho.
</task>

<project priority="P0">
【Thông tin dự án】
Tên sách: {title}
Thể loại: {genre}
Chủ đề: {theme}
Góc nhìn tự sự: {narrative_perspective}
</project>

<input priority="P0">
【Phạm vi đợt】
Chương {start_chapter} - chương {end_chapter} (tổng {expected_count} chương)

【Nội dung chương】
{chapters_text}
</input>

<output priority="P0">
【Định dạng đầu ra】
Chỉ xuất mảng JSON thuần túy (không markdown, không khối mã, không giải thích).
Độ dài mảng phải bằng chính xác {expected_count}.

Mỗi đối tượng phải có các trường nghiêm ngặt như sau:
[
  {{
    "chapter_number": 1,
    "title": "Tiêu đề chương",
    "summary": "Tóm tắt chương (200-600 chữ): tình tiết chính, tương tác nhân vật, sự kiện then chốt, xung đột và bước ngoặt",
    "scenes": ["Mô tả cảnh 1", "Mô tả cảnh 2"],
    "characters": [
      {{"name": "Tên nhân vật 1", "type": "character"}},
      {{"name": "Tên tổ chức/thế lực 1", "type": "organization"}}
    ],
    "key_points": ["Điểm cốt truyện chính 1", "Điểm cốt truyện chính 2"],
    "emotion": "Tông cảm xúc của chương này",
    "goal": "Mục tiêu tự sự của chương này"
  }}
]

【Ràng buộc trường dữ liệu】
- chapter_number: phải nhất quán với số chương đầu vào
- title: phải nhất quán với tiêu đề chương đầu vào
- summary: trích xuất ngược dựa trên chính văn chương này, không được bịa ra sự kiện then chốt chưa xuất hiện
- scenes: 2-6 mục
- characters: có thể để trống; type chỉ cho phép character hoặc organization
- key_points: 2-6 mục
- emotion: một câu
- goal: một câu
</output>

<constraints>
【Bắt buộc tuân thủ】
✅ Một chương tương ứng nghiêm ngặt một đối tượng, số lượng và thứ tự hoàn toàn nhất quán
✅ Tên trường, cấp bậc trường, kiểu trường nhất quán nghiêm ngặt
✅ Chỉ trích xuất dựa trên chính văn đầu vào, không tự ý mở rộng thiết lập
✅ Đầu ra phải có thể được JSON phân tích trực tiếp

【Những điều cấm】
❌ Xuất bất kỳ văn bản nào ngoài JSON
❌ Thiếu trường hoặc thêm trường mới
❌ chapter_number/title không nhất quán với đầu vào
❌ Dùng markdown hoặc khối mã
</constraints>"""

    @staticmethod
    def format_prompt(template: str, **kwargs) -> str:
        """
        Định dạng template prompt
        
        Args:
            template: template prompt
            **kwargs: tham số template
            
        Returns:
            prompt sau khi định dạng
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Thiếu tham số bắt buộc: {e}")
    

    @classmethod
    async def get_chapter_regeneration_prompt(cls, chapter_number: int, title: str, word_count: int, content: str,
                                        modification_instructions: str, project_context: Dict[str, Any],
                                        style_content: str, target_word_count: int,
                                        user_id: str = None, db = None) -> str:
        """
        Lấy prompt viết lại chương (hỗ trợ tùy chỉnh của người dùng)
        
        Args:
            chapter_number: số thứ tự chương
            title: tiêu đề chương
            word_count: số chữ gốc
            content: nội dung gốc
            modification_instructions: chỉ dẫn chỉnh sửa
            project_context: bối cảnh dự án
            style_content: phong cách viết
            target_word_count: số chữ mục tiêu
            user_id: ID người dùng (tùy chọn, dùng để lấy template tùy chỉnh)
            db: phiên cơ sở dữ liệu (tùy chọn, dùng để truy vấn template tùy chỉnh)
            
        Returns:
            prompt viết lại chương hoàn chỉnh
        """
        # Lấy template prompt hệ thống (hỗ trợ tùy chỉnh của người dùng)
        if user_id and db:
            system_template = await cls.get_template("CHAPTER_REGENERATION_SYSTEM", user_id, db)
        else:
            system_template = cls.CHAPTER_REGENERATION_SYSTEM
        
        prompt_parts = [system_template]
        
        # Thông tin chương gốc
        prompt_parts.append(f"""## 📖 Thông tin chương gốc

**Chương**: chương {chapter_number}
**Tiêu đề**: {title}
**Số chữ**: {word_count} chữ

**Nội dung gốc**:
{content}

---
""")
        
        # Chỉ dẫn chỉnh sửa
        prompt_parts.append(modification_instructions)
        prompt_parts.append("\n---\n")
        
        # Thông tin bối cảnh dự án
        prompt_parts.append(f"""## 🌍 Thông tin bối cảnh dự án

**Tiêu đề tiểu thuyết**: {project_context.get('project_title', 'Không rõ')}
**Đề tài**: {project_context.get('genre', 'Chưa đặt')}
**Chủ đề**: {project_context.get('theme', 'Chưa đặt')}
**Góc nhìn tự sự**: {project_context.get('narrative_perspective', 'Ngôi thứ ba')}
**Thiết lập thế giới quan**:
- Bối cảnh thời đại: {project_context.get('time_period', 'Chưa đặt')}
- Vị trí địa lý: {project_context.get('location', 'Chưa đặt')}
- Tông không khí: {project_context.get('atmosphere', 'Chưa đặt')}

---
""")
        
        # Thông tin nhân vật
        if project_context.get('characters_info'):
            prompt_parts.append(f"""## 👥 Thông tin nhân vật

{project_context['characters_info']}

---
""")
        
        # Dàn ý chương
        if project_context.get('chapter_outline'):
            prompt_parts.append(f"""## 📝 Dàn ý chương này

{project_context['chapter_outline']}

---
""")
        
        # Bối cảnh các chương trước
        if project_context.get('previous_context'):
            prompt_parts.append(f"""## 📚 Bối cảnh các chương trước

{project_context['previous_context']}

---
""")
        
        # Yêu cầu phong cách viết
        if style_content:
            prompt_parts.append(f"""## 🎨 Yêu cầu phong cách viết

{style_content}

Hãy tuân thủ nghiêm ngặt phong cách viết trên khi sáng tác lại.

---
""")
        
        # Yêu cầu sáng tác
        prompt_parts.append(f"""## ✨ Yêu cầu sáng tác

1. **Giải quyết vấn đề**: cải thiện mọi vấn đề được đề cập trong chỉ dẫn chỉnh sửa trên
2. **Giữ tính liên tục**: đảm bảo nhất quán với cốt truyện, nhân vật, phong cách của các chương trước sau
3. **Nâng cao chất lượng**: rõ ràng vượt trội hơn bản gốc về nhịp độ, cảm xúc, miêu tả
4. **Giữ tinh hoa**: giữ lại những phần xuất sắc và tình tiết then chốt của chương gốc
5. **Kiểm soát số chữ**: số chữ mục tiêu khoảng {target_word_count} chữ (có thể dao động ±20%)
{f'6. **Nhất quán phong cách**: sáng tác nghiêm ngặt theo phong cách viết trên' if style_content else ''}

---

## 🎬 Bắt đầu sáng tác

Hãy bắt đầu sáng tác nội dung chương phiên bản mới đã cải thiện ngay.

**Lưu ý quan trọng**:
- Xuất trực tiếp nội dung chính văn chương, bắt đầu viết từ nội dung câu chuyện
- **Không** xuất tiêu đề chương (như "Chương X", "Chương X: XXX" v.v.)
- **Không** xuất bất kỳ lời thuyết minh, chú thích hay siêu dữ liệu bổ sung nào
- Chỉ cần nội dung chính văn câu chuyện thuần túy

Bắt đầu ngay:
""")
        
        return "\n".join(prompt_parts)

    @classmethod
    async def get_mcp_tool_test_prompts(
        cls,
        plugin_name: str,
        user_id: str = None,
        db = None
    ) -> Dict[str, str]:
        """
        Lấy prompt kiểm thử công cụ MCP (hỗ trợ tùy chỉnh)
        
        Args:
            plugin_name: tên plugin
            user_id: ID người dùng (tùy chọn)
            db: phiên cơ sở dữ liệu (tùy chọn)
            
        Returns:
            từ điển chứa prompt user và system
        """
        # Lấy prompt user tùy chỉnh của người dùng hoặc mặc định của hệ thống
        if user_id and db:
            user_template = await cls.get_template("MCP_TOOL_TEST", user_id, db)
        else:
            user_template = cls.MCP_TOOL_TEST
        
        # Lấy prompt system tùy chỉnh của người dùng hoặc mặc định của hệ thống
        if user_id and db:
            system_template = await cls.get_template("MCP_TOOL_TEST_SYSTEM", user_id, db)
        else:
            system_template = cls.MCP_TOOL_TEST_SYSTEM
        
        return {
            "user": cls.format_prompt(user_template, plugin_name=plugin_name),
            "system": system_template
        }

    # ========== Hỗ trợ prompt tùy chỉnh ==========
    
    @classmethod
    async def get_template_with_fallback(cls,
                                        template_key: str,
                                        user_id: str = None,
                                        db = None) -> str:
        """
        Lấy template prompt (ưu tiên tùy chỉnh của người dùng, hỗ trợ hạ cấp)
        
        Args:
            template_key: tên khóa template
            user_id: ID người dùng (tùy chọn, nếu không cung cấp thì trả về mặc định của hệ thống trực tiếp)
            db: phiên cơ sở dữ liệu (tùy chọn)
            
        Returns:
            nội dung template prompt
        """
        # Nếu không cung cấp user_id hoặc db, trả về mặc định của hệ thống trực tiếp
        if not user_id or not db:
            return getattr(cls, template_key, None)
        
        # Thử lấy template tùy chỉnh của người dùng
        return await cls.get_template(template_key, user_id, db)
    
    @classmethod
    async def get_template(cls,
                          template_key: str,
                          user_id: str,
                          db) -> str:
        """
        Lấy template prompt (ưu tiên tùy chỉnh của người dùng)
        
        Args:
            template_key: tên khóa template
            user_id: ID người dùng
            db: phiên cơ sở dữ liệu
            
        Returns:
            nội dung template prompt
        """
        from sqlalchemy import select
        from app.models.prompt_template import PromptTemplate
        from app.logger import get_logger
        
        logger = get_logger(__name__)
        
        # 1. Thử lấy template tùy chỉnh của người dùng từ cơ sở dữ liệu
        result = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.user_id == user_id,
                PromptTemplate.template_key == template_key,
                PromptTemplate.is_active == True
            )
        )
        custom_template = result.scalar_one_or_none()
        
        if custom_template:
            logger.info(f"✅ Dùng prompt tùy chỉnh của người dùng: user_id={user_id}, template_key={template_key}, template_name={custom_template.template_name}")
            return custom_template.template_content
        
        # 2. Hạ cấp về template mặc định của hệ thống
        logger.info(f"⚪ Dùng prompt mặc định của hệ thống: user_id={user_id}, template_key={template_key} (không tìm thấy template tùy chỉnh)")
        
        # Lấy template mặc định của hệ thống trực tiếp từ thuộc tính lớp
        template_content = getattr(cls, template_key, None)
        
        if template_content is None:
            logger.warning(f"⚠️ Không tìm thấy template mặc định của hệ thống: {template_key}")
        
        return template_content
    
    @classmethod
    def get_all_system_templates(cls) -> list:
        """
        Lấy thông tin của mọi template mặc định của hệ thống
        
        Returns:
            danh sách template hệ thống
        """
        templates = []
        
        # Định nghĩa mọi template và thông tin meta của chúng
        template_definitions = {
            "NOVEL_COVER_PROMPT_TEMPLATE": {
                "name": "Tạo bìa tiểu thuyết",
                "category": "Tạo bìa",
                "description": "Tạo prompt vẽ bìa tiểu thuyết dựa trên thông tin cơ bản của dự án, phù hợp cho bìa sách dọc",
                "parameters": ["title", "genre", "theme", "description"]
            },
            "WORLD_BUILDING": {
                "name": "Xây dựng thế giới",
                "category": "Xây dựng thế giới",
                "description": "Dùng để tạo thiết lập thế giới quan tiểu thuyết, bao gồm bối cảnh thời gian, vị trí địa lý, tông không khí và quy tắc thế giới",
                "parameters": ["title", "theme", "genre", "description"]
            },
            "BOOK_IMPORT_REVERSE_PROJECT_SUGGESTION": {
                "name": "Nhập sách tách-Trích xuất ngược dự án",
                "category": "Nhập sách tách",
                "description": "Trích xuất ngược giới thiệu, chủ đề, thể loại, góc nhìn tự sự và số chữ mục tiêu dựa trên nội dung 3 chương đầu",
                "parameters": ["title", "sampled_text"]
            },
            "BOOK_IMPORT_REVERSE_OUTLINES": {
                "name": "Nhập sách tách-Dàn ý chương ngược",
                "category": "Nhập sách tách",
                "description": "Tạo ngược dàn ý có cấu trúc nhất quán với OUTLINE_CREATE dựa trên chính văn chương (5 chương một đợt)",
                "parameters": [
                    "title", "genre", "theme", "narrative_perspective",
                    "start_chapter", "end_chapter", "expected_count", "chapters_text"
                ]
            },
            "CHARACTERS_BATCH_GENERATION": {
                "name": "Tạo hàng loạt nhân vật",
                "category": "Tạo nhân vật",
                "description": "Tạo hàng loạt nhiều nhân vật và tổ chức, xây dựng mạng lưới quan hệ nhân vật",
                "parameters": ["count", "time_period", "location", "atmosphere", "rules", "theme", "genre", "requirements"]
            },
            "SINGLE_CHARACTER_GENERATION": {
                "name": "Tạo nhân vật đơn lẻ",
                "category": "Tạo nhân vật",
                "description": "Tạo thiết lập chi tiết cho một nhân vật",
                "parameters": ["project_context", "user_input"]
            },
            "SINGLE_ORGANIZATION_GENERATION": {
                "name": "Tạo tổ chức",
                "category": "Tạo nhân vật",
                "description": "Tạo thiết lập chi tiết cho tổ chức/thế lực",
                "parameters": ["project_context", "user_input"]
            },
            "OUTLINE_CREATE": {
                "name": "Tạo dàn ý",
                "category": "Tạo dàn ý",
                "description": "Tạo dàn ý chương hoàn chỉnh dựa trên thông tin dự án",
                "parameters": ["title", "theme", "genre", "chapter_count", "narrative_perspective", "target_words",
                             "time_period", "location", "atmosphere", "rules", "characters_info", "requirements", "mcp_references"]
            },
            "OUTLINE_CONTINUE": {
                "name": "Viết tiếp dàn ý",
                "category": "Tạo dàn ý",
                "description": "Viết tiếp dàn ý dựa trên các chương đã có",
                "parameters": ["title", "theme", "genre", "narrative_perspective", "chapter_count", "time_period",
                             "location", "atmosphere", "rules", "characters_info", "current_chapter_count",
                             "all_chapters_brief", "recent_plot", "memory_context", "mcp_references",
                             "plot_stage_instruction", "start_chapter", "end_chapter", "story_direction", "requirements"]
            },
            "CHAPTER_GENERATION_ONE_TO_MANY": {
                "name": "Sáng tác chương-Chế độ 1-N (Chương 1)",
                "category": "Sáng tác chương",
                "description": "Chế độ 1-N: sáng tác nội dung chương dựa trên dàn ý (dùng cho chương 1, không có chương trước)",
                "parameters": ["project_title", "genre", "chapter_number", "chapter_title", "chapter_outline",
                             "target_word_count", "narrative_perspective", "characters_info"]
            },
            "CHAPTER_GENERATION_ONE_TO_MANY_NEXT": {
                "name": "Sáng tác chương-Chế độ 1-N (Chương 2 trở đi)",
                "category": "Sáng tác chương",
                "description": "Chế độ 1-N: sáng tác chương mới dựa trên nội dung chương trước (dùng cho chương 2 trở đi)",
                "parameters": ["project_title", "genre", "chapter_number", "chapter_title", "chapter_outline",
                             "target_word_count", "narrative_perspective", "characters_info", "continuation_point",
                             "foreshadow_reminders", "relevant_memories", "story_skeleton", "previous_chapter_summary"]
            },
            "CHAPTER_GENERATION_ONE_TO_ONE": {
                "name": "Sáng tác chương-Chế độ 1-1 (Chương 1)",
                "category": "Sáng tác chương",
                "description": "Chế độ 1-1: sáng tác chương (dùng cho chương 1, không có chương trước)",
                "parameters": ["project_title", "genre", "chapter_number", "chapter_title", "chapter_outline",
                             "target_word_count", "narrative_perspective", "characters_info", "chapter_careers"]
            },
            "CHAPTER_GENERATION_ONE_TO_ONE_NEXT": {
                "name": "Sáng tác chương-Chế độ 1-1 (Chương 2 trở đi)",
                "category": "Sáng tác chương",
                "description": "Chế độ 1-1: sáng tác chương mới dựa trên nội dung chương trước (dùng cho chương 2 trở đi)",
                "parameters": ["project_title", "genre", "chapter_number", "chapter_title", "chapter_outline",
                             "target_word_count", "narrative_perspective", "previous_chapter_content",
                             "characters_info", "chapter_careers", "foreshadow_reminders", "relevant_memories"]
            },
            "CHAPTER_REGENERATION_SYSTEM": {
                "name": "Prompt hệ thống viết lại chương",
                "category": "Viết lại chương",
                "description": "Prompt hệ thống dùng để viết lại chương",
                "parameters": ["chapter_number", "title", "word_count", "content", "modification_instructions",
                             "project_context", "style_content", "target_word_count"]
            },
            "PARTIAL_REGENERATE": {
                "name": "Viết lại cục bộ",
                "category": "Viết lại chương",
                "description": "Viết lại nội dung đoạn được chọn theo yêu cầu chỉnh sửa của người dùng",
                "parameters": ["context_before", "original_word_count", "selected_text", "context_after",
                             "user_instructions", "length_requirement", "style_content"]
            },
            "PLOT_ANALYSIS": {
                "name": "Phân tích cốt truyện",
                "category": "Phân tích cốt truyện",
                "description": "Phân tích sâu cốt truyện, móc treo, chi tiết cài cắm v.v. của chương",
                "parameters": ["chapter_number", "title", "content", "word_count"]
            },
            "OUTLINE_EXPAND_SINGLE": {
                "name": "Triển khai dàn ý một đợt",
                "category": "Triển khai cốt truyện",
                "description": "Triển khai nút dàn ý thành kế hoạch chương chi tiết (một đợt)",
                "parameters": ["project_title", "project_genre", "project_theme", "project_narrative_perspective",
                             "project_world_time_period", "project_world_location", "project_world_atmosphere",
                             "characters_info", "outline_order_index", "outline_title", "outline_content",
                             "context_info", "strategy_instruction", "target_chapter_count", "scene_instruction", "scene_field"]
            },
            "OUTLINE_EXPAND_MULTI": {
                "name": "Triển khai dàn ý theo đợt",
                "category": "Triển khai cốt truyện",
                "description": "Triển khai nút dàn ý thành kế hoạch chương chi tiết (theo đợt)",
                "parameters": ["project_title", "project_genre", "project_theme", "project_narrative_perspective",
                             "project_world_time_period", "project_world_location", "project_world_atmosphere",
                             "characters_info", "outline_order_index", "outline_title", "outline_content",
                             "context_info", "previous_context", "strategy_instruction", "start_index",
                             "end_index", "target_chapter_count", "scene_instruction", "scene_field"]
            },
            "MCP_TOOL_TEST": {
                "name": "Kiểm thử công cụ MCP (prompt người dùng)",
                "category": "Kiểm thử MCP",
                "description": "Prompt người dùng dùng để kiểm thử chức năng plugin MCP",
                "parameters": ["plugin_name"]
            },
            "MCP_TOOL_TEST_SYSTEM": {
                "name": "Kiểm thử công cụ MCP (prompt hệ thống)",
                "category": "Kiểm thử MCP",
                "description": "Prompt hệ thống dùng để kiểm thử chức năng plugin MCP",
                "parameters": []
            },
            "MCP_WORLD_BUILDING_PLANNING": {
                "name": "Hoạch định thế giới quan MCP",
                "category": "Tăng cường MCP",
                "description": "Dùng công cụ MCP tìm kiếm tư liệu hỗ trợ thiết kế thế giới quan",
                "parameters": ["title", "genre", "theme", "description"]
            },
            "MCP_CHARACTER_PLANNING": {
                "name": "Hoạch định nhân vật MCP",
                "category": "Tăng cường MCP",
                "description": "Dùng công cụ MCP tìm kiếm tư liệu hỗ trợ thiết kế nhân vật",
                "parameters": ["title", "genre", "theme", "time_period", "location"]
            },
            "AUTO_CHARACTER_ANALYSIS": {
                "name": "Phân tích nhân vật tự động",
                "category": "Tự động đưa nhân vật vào",
                "description": "Phân tích dàn ý mới tạo, đánh giá có cần đưa nhân vật mới vào không",
                "parameters": ["title", "genre", "theme", "time_period", "location", "atmosphere",
                             "existing_characters", "new_outlines", "start_chapter", "end_chapter"]
            },
            "AUTO_CHARACTER_GENERATION": {
                "name": "Tạo nhân vật tự động",
                "category": "Tự động đưa nhân vật vào",
                "description": "Tự động tạo thiết lập hoàn chỉnh cho nhân vật mới theo nhu cầu cốt truyện",
                "parameters": ["title", "genre", "theme", "time_period", "location", "atmosphere", "rules",
                             "existing_characters", "plot_context", "character_specification", "mcp_references"]
            },
            "AUTO_ORGANIZATION_ANALYSIS": {
                "name": "Phân tích tổ chức tự động",
                "category": "Tự động đưa tổ chức vào",
                "description": "Phân tích dàn ý mới tạo, đánh giá có cần đưa tổ chức mới vào không",
                "parameters": ["title", "genre", "theme", "time_period", "location", "atmosphere",
                             "existing_organizations", "existing_characters", "all_chapters_brief", "start_chapter", "chapter_count", "plot_stage", "story_direction"]
            },
            "AUTO_ORGANIZATION_GENERATION": {
                "name": "Tạo tổ chức tự động",
                "category": "Tự động đưa tổ chức vào",
                "description": "Tự động tạo thiết lập hoàn chỉnh cho tổ chức mới theo nhu cầu cốt truyện",
                "parameters": ["title", "genre", "theme", "time_period", "location", "atmosphere", "rules",
                             "existing_organizations", "existing_characters", "plot_context", "organization_specification", "mcp_references"]
            },
            "CAREER_SYSTEM_GENERATION": {
                "name": "Tạo hệ thống nghề nghiệp",
                "category": "Xây dựng thế giới",
                "description": "Tự động tạo hệ thống nghề nghiệp hoàn chỉnh dựa trên thế giới quan và giới thiệu dự án, bao gồm nghề chính và nghề phụ",
                "parameters": ["title", "genre", "theme", "description", "time_period", "location", "atmosphere", "rules"]
            },
            "INSPIRATION_TITLE_SYSTEM": {
                "name": "Chế độ cảm hứng-Tạo tên sách (prompt hệ thống)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt hệ thống tạo 6 gợi ý tên sách dựa trên ý tưởng gốc của người dùng",
                "parameters": ["initial_idea"]
            },
            "INSPIRATION_TITLE_USER": {
                "name": "Chế độ cảm hứng-Tạo tên sách (prompt người dùng)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt người dùng tạo 6 gợi ý tên sách dựa trên ý tưởng gốc của người dùng",
                "parameters": ["initial_idea"]
            },
            "INSPIRATION_DESCRIPTION_SYSTEM": {
                "name": "Chế độ cảm hứng-Tạo giới thiệu (prompt hệ thống)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt hệ thống tạo 6 lựa chọn giới thiệu dựa trên ý tưởng người dùng và tên sách",
                "parameters": ["initial_idea", "title"]
            },
            "INSPIRATION_DESCRIPTION_USER": {
                "name": "Chế độ cảm hứng-Tạo giới thiệu (prompt người dùng)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt người dùng tạo 6 lựa chọn giới thiệu dựa trên ý tưởng người dùng và tên sách",
                "parameters": ["initial_idea", "title"]
            },
            "INSPIRATION_THEME_SYSTEM": {
                "name": "Chế độ cảm hứng-Tạo chủ đề (prompt hệ thống)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt hệ thống tạo 6 lựa chọn chủ đề sâu sắc dựa trên tên sách và phần giới thiệu",
                "parameters": ["initial_idea", "title", "description"]
            },
            "INSPIRATION_THEME_USER": {
                "name": "Chế độ cảm hứng-Tạo chủ đề (prompt người dùng)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt người dùng tạo 6 lựa chọn chủ đề sâu sắc dựa trên tên sách và phần giới thiệu",
                "parameters": ["initial_idea", "title", "description"]
            },
            "INSPIRATION_GENRE_SYSTEM": {
                "name": "Chế độ cảm hứng-Tạo thể loại (prompt hệ thống)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt hệ thống tạo 6 nhãn thể loại phù hợp dựa trên thông tin tiểu thuyết",
                "parameters": ["initial_idea", "title", "description", "theme"]
            },
            "INSPIRATION_GENRE_USER": {
                "name": "Chế độ cảm hứng-Tạo thể loại (prompt người dùng)",
                "category": "Chế độ cảm hứng",
                "description": "Prompt người dùng tạo 6 nhãn thể loại phù hợp dựa trên thông tin tiểu thuyết",
                "parameters": ["initial_idea", "title", "description", "theme"]
            },
            "INSPIRATION_QUICK_COMPLETE": {
                "name": "Chế độ cảm hứng-Tự động hoàn thiện thông minh",
                "category": "Chế độ cảm hứng",
                "description": "Tự động hoàn thiện thông minh phương án tiểu thuyết hoàn chỉnh dựa trên một phần thông tin người dùng cung cấp",
                "parameters": ["existing"]
            }
        }
        
        for key, info in template_definitions.items():
            template_content = getattr(cls, key, None)
            if template_content:
                templates.append({
                    "template_key": key,
                    "template_name": info["name"],
                    "category": info["category"],
                    "description": info["description"],
                    "parameters": info["parameters"],
                    "content": template_content
                })
        
        # Tải template prompt Skill
        try:
            skill_templates = get_all_skills_cached()
            templates.extend(skill_templates)
        except Exception as e:
            from app.logger import get_logger
            get_logger(__name__).warning(f"Tải template Skill thất bại: {e}")
        
        return templates
    
    @classmethod
    def get_system_template_info(cls, template_key: str) -> dict:
        """
        Lấy thông tin của template hệ thống được chỉ định
        
        Args:
            template_key: tên khóa template
            
        Returns:
            từ điển thông tin template
        """
        all_templates = cls.get_all_system_templates()
        for template in all_templates:
            if template["template_key"] == template_key:
                return template
        return None

# ========== Thể hiện toàn cục ==========
prompt_service = PromptService()
