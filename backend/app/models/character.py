"""Model dữ liệu nhân vật"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.sql import func
from app.database import Base
import uuid


class Character(Base):
    """Bảng nhân vật (gồm nhân vật và tổ chức)"""
    __tablename__ = "characters"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Thông tin cơ bản
    name = Column(String(100), nullable=False, comment="Tên nhân vật/tổ chức")
    age = Column(String(50), comment="Tuổi")
    gender = Column(String(50), comment="Giới tính")
    is_organization = Column(Boolean, default=False, comment="Có phải tổ chức hay không")
    
    # Loại nhân vật: protagonist (nhân vật chính)/supporting (nhân vật phụ)/antagonist (phản diện)
    role_type = Column(String(50), comment="Loại nhân vật")
    
    # Thông tin chi tiết nhân vật
    personality = Column(Text, comment="Đặc điểm tính cách/đặc trưng tổ chức")
    background = Column(Text, comment="Bối cảnh truyện")
    appearance = Column(Text, comment="Mô tả ngoại hình")
    relationships = Column(Text, comment="Quan hệ nhân vật (JSON)")
    
    # Trường riêng của tổ chức
    organization_type = Column(String(100), comment="Loại tổ chức")
    organization_purpose = Column(String(500), comment="Mục đích tổ chức")
    organization_members = Column(Text, comment="Thành viên tổ chức (JSON)")
    
    # Trạng thái tồn tại của nhân vật/tổ chức
    status = Column(String(20), default="active", comment="Trạng thái: active/deceased/missing/retired/destroyed")
    status_changed_chapter = Column(Integer, comment="Số chương thay đổi trạng thái")
    
    # Theo dõi trạng thái tâm lý (tự động cập nhật bởi phân tích chương)
    current_state = Column(Text, comment="Trạng thái tâm lý hiện tại của nhân vật (tự động cập nhật bởi phân tích)")
    state_updated_chapter = Column(Integer, comment="Số chương cập nhật trạng thái tâm lý gần nhất")
    
    # Trường liên quan nghề nghiệp (trường dư thừa, dùng để tăng hiệu năng truy vấn)
    main_career_id = Column(String(36), ForeignKey("careers.id", ondelete="SET NULL"), comment="ID nghề nghiệp chính")
    main_career_stage = Column(Integer, comment="Giai đoạn hiện tại của nghề nghiệp chính")
    sub_careers = Column(Text, comment="Danh sách nghề nghiệp phụ (JSON): [{\"career_id\": \"xxx\", \"stage\": 3}, ...]")
    
    # Khác
    avatar_url = Column(String(500), comment="URL ảnh đại diện")
    traits = Column(Text, comment="Nhãn đặc trưng (JSON)")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        entity_type = "Tổ chức" if self.is_organization else "Nhân vật"
        return f"<Character(id={self.id}, name={self.name}, type={entity_type})>"