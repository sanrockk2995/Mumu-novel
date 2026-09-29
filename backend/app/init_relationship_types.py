"""Khởi tạo dữ liệu loại quan hệ"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.relationship import RelationshipType
from app.logger import get_logger

logger = get_logger(__name__)


async def init_relationship_types():
    """Khởi tạo dữ liệu loại quan hệ preset"""
    
    # Dữ liệu loại quan hệ preset
    relationship_types = [
        # Quan hệ gia đình
        {"name": "Cha", "category": "family", "reverse_name": "Con cái", "intimacy_range": "high", "icon": "👨"},
        {"name": "Mẹ", "category": "family", "reverse_name": "Con cái", "intimacy_range": "high", "icon": "👩"},
        {"name": "Anh em", "category": "family", "reverse_name": "Anh em", "intimacy_range": "high", "icon": "👬"},
        {"name": "Chị em", "category": "family", "reverse_name": "Chị em", "intimacy_range": "high", "icon": "👭"},
        {"name": "Con cái", "category": "family", "reverse_name": "Cha mẹ", "intimacy_range": "high", "icon": "👶"},
        {"name": "Vợ/Chồng", "category": "family", "reverse_name": "Vợ/Chồng", "intimacy_range": "high", "icon": "💑"},
        {"name": "Người yêu", "category": "family", "reverse_name": "Người yêu", "intimacy_range": "high", "icon": "💕"},
        
        # Quan hệ xã hội
        {"name": "Sư phụ", "category": "social", "reverse_name": "Đồ đệ", "intimacy_range": "high", "icon": "🎓"},
        {"name": "Đồ đệ", "category": "social", "reverse_name": "Sư phụ", "intimacy_range": "high", "icon": "📚"},
        {"name": "Bạn bè", "category": "social", "reverse_name": "Bạn bè", "intimacy_range": "medium", "icon": "🤝"},
        {"name": "Bạn học", "category": "social", "reverse_name": "Bạn học", "intimacy_range": "medium", "icon": "🎒"},
        {"name": "Hàng xóm", "category": "social", "reverse_name": "Hàng xóm", "intimacy_range": "low", "icon": "🏘️"},
        {"name": "Tri kỷ", "category": "social", "reverse_name": "Tri kỷ", "intimacy_range": "high", "icon": "💙"},
        
        # Quan hệ nghề nghiệp
        {"name": "Cấp trên", "category": "professional", "reverse_name": "Cấp dưới", "intimacy_range": "low", "icon": "👔"},
        {"name": "Cấp dưới", "category": "professional", "reverse_name": "Cấp trên", "intimacy_range": "low", "icon": "💼"},
        {"name": "Đồng nghiệp", "category": "professional", "reverse_name": "Đồng nghiệp", "intimacy_range": "medium", "icon": "🤵"},
        {"name": "Đối tác", "category": "professional", "reverse_name": "Đối tác", "intimacy_range": "medium", "icon": "🤜🤛"},
        
        # Quan hệ thù địch
        {"name": "Kẻ địch", "category": "hostile", "reverse_name": "Kẻ địch", "intimacy_range": "low", "icon": "⚔️"},
        {"name": "Kẻ thù", "category": "hostile", "reverse_name": "Kẻ thù", "intimacy_range": "low", "icon": "💢"},
        {"name": "Đối thủ cạnh tranh", "category": "hostile", "reverse_name": "Đối thủ cạnh tranh", "intimacy_range": "low", "icon": "🎯"},
        {"name": "Kình địch", "category": "hostile", "reverse_name": "Kình địch", "intimacy_range": "low", "icon": "⚡"},
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            # Kiểm tra đã có dữ liệu chưa
            result = await session.execute(select(RelationshipType))
            existing = result.scalars().first()
            
            if existing:
                logger.info("Dữ liệu loại quan hệ đã tồn tại, bỏ qua khởi tạo")
                return
            
            # Chèn dữ liệu preset
            logger.info("Bắt đầu chèn dữ liệu loại quan hệ...")
            for rt_data in relationship_types:
                relationship_type = RelationshipType(**rt_data)
                session.add(relationship_type)
            
            await session.commit()
            logger.info(f"Chèn thành công {len(relationship_types)} dòng dữ liệu loại quan hệ")
            
        except Exception as e:
            logger.error(f"Khởi tạo dữ liệu loại quan hệ thất bại: {str(e)}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(init_relationship_types())