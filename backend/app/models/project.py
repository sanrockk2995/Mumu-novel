"""Model dữ liệu dự án"""
from sqlalchemy import Column, String, Text, DateTime, Integer, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Project(Base):
    """Bảng dự án"""
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True, comment="ID người dùng")
    title = Column(String(200), nullable=False, comment="Tiêu đề dự án")
    description = Column(Text, comment="Giới thiệu dự án")
    theme = Column(Text, comment="Chủ đề")
    genre = Column(String(50), comment="Thể loại tiểu thuyết")
    target_words = Column(Integer, default=0, comment="Số chữ mục tiêu")
    current_words = Column(Integer, default=0, comment="Số chữ hiện tại")
    status = Column(String(20), default="planning", comment="Trạng thái sáng tác")
    wizard_status = Column(String(20), default="incomplete", comment="Trạng thái hoàn thành wizard: incomplete/completed")
    wizard_step = Column(Integer, default=0, comment="Bước hiện tại của wizard: 0-4")
    outline_mode = Column(String(20), nullable=False, default="one-to-many", comment="Chế độ chương dàn ý: one-to-one (chế độ truyền thống) hoặc one-to-many (chế độ tinh chỉnh)")
    
    # Trường xây dựng thế giới
    world_time_period = Column(Text, comment="Bối cảnh thời gian")
    world_location = Column(Text, comment="Vị trí địa lý")
    world_atmosphere = Column(Text, comment="Tông không khí")
    world_rules = Column(Text, comment="Quy tắc thế giới")
    
    # Cấu hình dự án
    chapter_count = Column(Integer, comment="Số lượng chương")
    narrative_perspective = Column(String(50), comment="Góc nhìn tường thuật: first_person/third_person/omniscient")
    character_count = Column(Integer, default=5, comment="Số lượng nhân vật")

    # Trường bìa
    cover_image_url = Column(String(1000), comment="Địa chỉ truy cập ảnh bìa")
    cover_prompt = Column(Text, comment="Prompt dùng lần gần nhất khi sinh bìa")
    cover_status = Column(String(20), default="none", nullable=False, comment="Trạng thái bìa: none/generating/ready/failed")
    cover_error = Column(Text, comment="Lý do thất bại lần sinh bìa gần nhất")
    cover_updated_at = Column(DateTime, comment="Thời gian sinh bìa thành công gần nhất")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        CheckConstraint(
            "outline_mode IN ('one-to-one', 'one-to-many')",
            name='check_outline_mode'
        ),
        CheckConstraint(
            "cover_status IN ('none', 'generating', 'ready', 'failed')",
            name='check_cover_status'
        ),
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, title={self.title})>"
