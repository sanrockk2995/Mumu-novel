"""Model dữ liệu nghề nghiệp"""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Career(Base):
    """Bảng nghề nghiệp"""
    __tablename__ = "careers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Thông tin cơ bản
    name = Column(String(100), nullable=False, comment="Tên nghề nghiệp")
    type = Column(String(20), nullable=False, comment="Loại nghề nghiệp: main (nghề chính)/sub (nghề phụ)")
    description = Column(Text, comment="Mô tả nghề nghiệp")
    category = Column(String(50), comment="Phân loại nghề nghiệp (ví dụ: hệ chiến đấu, hệ sản xuất, hệ hỗ trợ)")
    
    # Thiết lập giai đoạn
    stages = Column(Text, nullable=False, comment="Danh sách giai đoạn nghề nghiệp (JSON): [{level:1, name:"", description:""}], ...")
    max_stage = Column(Integer, nullable=False, default=10, comment="Số giai đoạn tối đa")
    
    # Đặc tính nghề nghiệp
    requirements = Column(Text, comment="Yêu cầu/hạn chế nghề nghiệp")
    special_abilities = Column(Text, comment="Mô tả năng lực đặc biệt")
    worldview_rules = Column(Text, comment="Liên kết quy tắc thế giới quan")
    
    # Cộng thuộc tính nghề nghiệp (tùy chọn, định dạng JSON)
    attribute_bonuses = Column(Text, comment="Cộng thuộc tính (JSON): {strength: \"+10%\", intelligence: \"+5%\"}")
    
    # Metadata
    source = Column(String(20), default='ai', comment="Nguồn: ai/manual")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_project_id', 'project_id'),
        Index('idx_type', 'type'),
    )
    
    def __repr__(self):
        return f"<Career(id={self.id}, name={self.name}, type={self.type})>"


class CharacterCareer(Base):
    """Bảng liên kết nhân vật - nghề nghiệp"""
    __tablename__ = "character_careers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    career_id = Column(String(36), ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    career_type = Column(String(20), nullable=False, comment="main (nghề chính)/sub (nghề phụ)")
    
    # Tiến độ giai đoạn
    current_stage = Column(Integer, nullable=False, default=1, comment="Giai đoạn hiện tại (giá trị tương ứng trong nghề nghiệp)")
    stage_progress = Column(Integer, default=0, comment="Tiến độ trong giai đoạn (0-100)")
    
    # Ghi nhận thời gian
    started_at = Column(String(100), comment="Thời gian bắt đầu tu luyện (dòng thời gian tiểu thuyết)")
    reached_current_stage_at = Column(String(100), comment="Thời gian đạt giai đoạn hiện tại")
    
    # Ghi chú
    notes = Column(Text, comment="Ghi chú (ví dụ: tâm đắc tu luyện, sự kiện đặc biệt)")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    __table_args__ = (
        Index('idx_character_id', 'character_id'),
        Index('idx_career_type', 'career_type'),
        Index('idx_character_career', 'character_id', 'career_id', unique=True),
    )
    
    def __repr__(self):
        return f"<CharacterCareer(character_id={self.character_id}, career_id={self.career_id}, type={self.career_type})>"