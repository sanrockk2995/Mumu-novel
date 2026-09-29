"""Dịch vụ tạo nghề nghiệp"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.project import Project
from app.models.career import Career
from app.services.ai_service import AIService
from app.logger import get_logger

logger = get_logger(__name__)


class CareerService:
    """Dịch vụ logic nghiệp vụ liên quan nghề nghiệp"""
    
    @staticmethod
    async def get_career_generation_prompt(
        project: Project,
        main_career_count: int = 2,
        sub_career_count: int = 6
    ) -> str:
        """
        Xây dựng prompt tạo hệ thống nghề nghiệp
        
        Args:
            project: Đối tượng dự án
            main_career_count: Số lượng nghề chính
            sub_career_count: Số lượng nghề phụ
            
        Returns:
            Prompt đầy đủ
        """
        project_context = f"""
Thông tin dự án:
- Tên sách:{project.title}
- Thể loại:{project.genre or 'Chưa thiết lập'}
- Chủ đề:{project.theme or 'Chưa thiết lập'}
- Bối cảnh thời gian:{project.world_time_period or 'Chưa thiết lập'}
- Vị trí địa lý:{project.world_location or 'Chưa thiết lập'}
- Không khí chủ đạo:{project.world_atmosphere or 'Chưa thiết lập'}
- Quy tắc thế giới:{project.world_rules or 'Chưa thiết lập'}
"""
        
        user_requirements = f"""
Yêu cầu tạo:
- Số lượng nghề chính:{main_career_count}
- Số lượng nghề phụ:{sub_career_count}
- Nghề chính phải tuân thủ nghiêm ngặt quy tắc thế giới quan, thể hiện hệ thống năng lực cốt lõi
- Nghề phụ có thể tự do linh hoạt hơn, gồm các loại sản xuất, hỗ trợ, đặc biệt
"""
        
        prompt = f"""{project_context}

{user_requirements}

Vui lòng tạo hệ thống nghề nghiệp đầy đủ cho dự án tiểu thuyết này. Trả vềJSONđịnh dạng, cấu trúc như sau:

{{
  "main_careers": [
    {{
      "name": "Tên nghề nghiệp",
      "description": "Mô tả nghề nghiệp (100-200từ)",
      "category": "Phân loại nghề nghiệp (ví dụ: hệ chiến đấu, hệ pháp thuật, hệ thể tu...)",
      "stages": [
        {{"level": 1, "name": "Tên giai đoạn", "description": "Mô tả giai đoạn"}},
        {{"level": 2, "name": "Tên giai đoạn", "description": "Mô tả giai đoạn"}},
        ...(tổng10giai đoạn)
      ],
      "max_stage": 10,
      "requirements": "Yêu cầu nghề nghiệp (ví dụ: cần thiên phú, tư chất đặc biệt...)",
      "special_abilities": "Mô tả năng lực đặc biệt",
      "worldview_rules": "Liên hệ quy tắc thế giới quan (giải thích nghề này hòa nhập thế giới quan ra sao)",
      "attribute_bonuses": {{"strength": "+10%", "intelligence": "+5%"}}
    }}
  ],
  "sub_careers": [
    {{
      "name": "Tên nghề phụ",
      "description": "Mô tả nghề nghiệp",
      "category": "hệ sản xuất/hệ hỗ trợ/hệ đặc biệt",
      "stages": [
        {{"level": 1, "name": "Tên giai đoạn", "description": "Mô tả giai đoạn"}},
        ...(5-8giai đoạn)
      ],
      "max_stage": 5,
      "requirements": "Yêu cầu nghề nghiệp",
      "special_abilities": "Năng lực đặc biệt"
    }}
  ]
}}

Lưu ý quan trọng:
1. Thiết lập giai đoạn của nghề chính phải chi tiết, thể hiện lộ trình trưởng thành rõ ràng, tên giai đoạn phải có nét đặc sắc
2. Chọn nghề nghiệp phù hợp theo thể loại tiểu thuyết:
   - Thể loại tu tiên: kiếm tu, thể tu, pháp tu, phù tu..., giai đoạn ví dụ: Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh...
   - Thể loại huyền huyễn: chiến sĩ, pháp sư, thích khách..., giai đoạn ví dụ: tập sự, sơ cấp, trung cấp, cao cấp...
   - Dị năng đô thị: phân loại dị năng giả, giai đoạn ví dụ: thức tỉnh, sơ giai, trung giai, cao giai...
   - Khoa học viễn tưởng tương lai: chiến sĩ gen, cơ giáp sư..., giai đoạn ví dụ:Ecấp, Dcấp, Ccấp, Bcấp...
3. Nghề phụ phải có tính thực dụng và thú vị, ví dụ: luyện đan sư, luyện khí sư, trận pháp sư, thuần thú sư, y sư...
4. Mọi nghề nghiệp đều phải phù hợp với thiết lập thế giới quan tổng thể của dự án
5. Mô tả giai đoạn phải ngắn gọn rõ ràng, thể hiện đặc trưng cốt lõi của giai đoạn đó
6. **Chỉ trả về thuầnJSONobject, không thêm bất kỳ chữ giải thích haymarkdownđánh dấu**
"""
        
        return prompt
    
    @staticmethod
    async def parse_and_save_careers(
        career_data: Dict[str, Any],
        project_id: str,
        db: AsyncSession
    ) -> Dict[str, List[str]]:
        """
        Phân tíchAIdữ liệu nghề nghiệp trả về và lưu vào cơ sở dữ liệu
        
        Args:
            career_data: AIdữ liệu nghề nghiệp trả về (đã phân tích thànhdict)
            project_id: dự ánID
            db: cơ sở dữ liệuphiên
            
        Returns:
            {"main_careers": [...], "sub_careers": [...]} Danh sách tên nghề nghiệp đã tạo
        """
        result = {
            "main_careers": [],
            "sub_careers": []
        }
        
        # Lưu nghề chính
        for idx, career_info in enumerate(career_data.get("main_careers", [])):
            try:
                stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                attribute_bonuses = career_info.get("attribute_bonuses")
                attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None
                
                career = Career(
                    project_id=project_id,
                    name=career_info.get("name", f"Nghề chính chưa đặt tên{idx+1}"),
                    type="main",
                    description=career_info.get("description"),
                    category=career_info.get("category"),
                    stages=stages_json,
                    max_stage=career_info.get("max_stage", 10),
                    requirements=career_info.get("requirements"),
                    special_abilities=career_info.get("special_abilities"),
                    worldview_rules=career_info.get("worldview_rules"),
                    attribute_bonuses=attribute_bonuses_json,
                    source="ai"
                )
                db.add(career)
                await db.flush()
                result["main_careers"].append(career.name)
                logger.info(f"  ✅ Tạo nghề chính:{career.name}")
            except Exception as e:
                logger.error(f"  ❌ Tạo nghề chính thất bại:{str(e)}")
                continue
        
        # Lưu nghề phụ
        for idx, career_info in enumerate(career_data.get("sub_careers", [])):
            try:
                stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                attribute_bonuses = career_info.get("attribute_bonuses")
                attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None
                
                career = Career(
                    project_id=project_id,
                    name=career_info.get("name", f"Nghề phụ chưa đặt tên{idx+1}"),
                    type="sub",
                    description=career_info.get("description"),
                    category=career_info.get("category"),
                    stages=stages_json,
                    max_stage=career_info.get("max_stage", 5),
                    requirements=career_info.get("requirements"),
                    special_abilities=career_info.get("special_abilities"),
                    worldview_rules=career_info.get("worldview_rules"),
                    attribute_bonuses=attribute_bonuses_json,
                    source="ai"
                )
                db.add(career)
                await db.flush()
                result["sub_careers"].append(career.name)
                logger.info(f"  ✅ Tạo nghề phụ:{career.name}")
            except Exception as e:
                logger.error(f"  ❌ Tạo nghề phụ thất bại:{str(e)}")
                continue
        
        await db.commit()
        
        return result
    
    @staticmethod
    async def get_project_careers_summary(project_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Lấy tóm tắt hệ thống nghề nghiệp của dự án
        
        Args:
            project_id: dự ánID
            db: cơ sở dữ liệuphiên
            
        Returns:
            Thông tin tóm tắt hệ thống nghề nghiệp
        """
        result = await db.execute(
            select(Career).where(Career.project_id == project_id)
        )
        careers = result.scalars().all()
        
        main_careers = []
        sub_careers = []
        
        for career in careers:
            career_info = {
                "id": career.id,
                "name": career.name,
                "category": career.category,
                "max_stage": career.max_stage
            }
            
            if career.type == "main":
                main_careers.append(career_info)
            else:
                sub_careers.append(career_info)
        
        return {
            "main_careers": main_careers,
            "sub_careers": sub_careers,
            "total_count": len(careers)
        }


# Tạo thể hiện dịch vụ toàn cục
career_service = CareerService()