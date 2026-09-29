"""Model dữ liệu phong cách viết"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from app.database import Base


class WritingStyle(Base):
    """Bảng phong cách viết"""
    __tablename__ = "writing_styles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True, comment="ID người dùng sở hữu (NULL nghĩa là phong cách preset toàn cục)")
    name = Column(String(100), nullable=False, comment="Tên phong cách")
    style_type = Column(String(50), nullable=False, comment="Loại phong cách: preset/custom")
    preset_id = Column(String(50), comment="ID phong cách preset: natural/classical/modern v.v.")
    description = Column(Text, comment="Mô tả phong cách")
    prompt_content = Column(Text, nullable=False, comment="Nội dung prompt phong cách")
    order_index = Column(Integer, default=0, comment="Số thứ tự sắp xếp")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<WritingStyle(id={self.id}, name={self.name}, user_id={self.user_id})>"