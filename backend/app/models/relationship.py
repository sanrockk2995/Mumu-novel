"""Model dữ liệu quan hệ nhân vật và quản lý tổ chức"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base
import uuid


class RelationshipType(Base):
    """Bảng định nghĩa loại quan hệ"""
    __tablename__ = "relationship_types"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False, comment="Tên quan hệ")
    category = Column(String(20), nullable=False, comment="Phân loại: family/social/hostile/professional")
    reverse_name = Column(String(50), comment="Tên quan hệ ngược")
    intimacy_range = Column(String(20), comment="Phạm vi thân mật: high/medium/low")
    icon = Column(String(50), comment="Định danh biểu tượng")
    description = Column(Text, comment="Mô tả quan hệ")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    
    def __repr__(self):
        return f"<RelationshipType(id={self.id}, name={self.name}, category={self.category})>"


class CharacterRelationship(Base):
    """Bảng quan hệ nhân vật"""
    __tablename__ = "character_relationships"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID quan hệ")
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID dự án")
    
    # Hai bên quan hệ
    character_from_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID nhân vật A")
    character_to_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID nhân vật B")
    
    # Loại quan hệ
    relationship_type_id = Column(Integer, ForeignKey("relationship_types.id"), index=True, comment="ID loại quan hệ")
    relationship_name = Column(String(100), comment="Tên quan hệ tùy chỉnh")
    
    # Thuộc tính quan hệ
    intimacy_level = Column(Integer, default=50, comment="Mức thân mật: -100 đến 100")
    status = Column(String(20), default="active", comment="Trạng thái: active/broken/past/complicated")
    description = Column(Text, comment="Mô tả chi tiết quan hệ")
    
    # Dòng thời gian trong truyện
    started_at = Column(String(100), comment="Thời gian bắt đầu quan hệ (thời gian trong truyện)")
    ended_at = Column(String(100), comment="Thời gian kết thúc quan hệ (thời gian trong truyện)")
    
    # Định danh nguồn
    source = Column(String(20), default="ai", comment="Nguồn: ai/manual/imported")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<CharacterRelationship(id={self.id}, from={self.character_from_id}, to={self.character_to_id})>"


class Organization(Base):
    """Bảng chi tiết tổ chức"""
    __tablename__ = "organizations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID tổ chức")
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True, comment="ID nhân vật liên kết")
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID dự án")
    
    # Cấp tổ chức
    parent_org_id = Column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), comment="ID tổ chức cha")
    level = Column(Integer, default=0, comment="Cấp tổ chức")
    
    # Thuộc tính tổ chức
    power_level = Column(Integer, default=50, comment="Cấp độ thế lực: 0-100")
    member_count = Column(Integer, default=0, comment="Số lượng thành viên")
    location = Column(Text, comment="Nơi đặt")
    
    # Đặc trưng tổ chức
    motto = Column(String(200), comment="Tôn chỉ/khẩu hiệu")
    color = Column(String(100), comment="Màu đại diện")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<Organization(id={self.id}, character_id={self.character_id})>"


class OrganizationMember(Base):
    """Bảng quan hệ thành viên tổ chức"""
    __tablename__ = "organization_members"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment="ID quan hệ thành viên")
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID tổ chức")
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True, comment="ID nhân vật")
    
    # Thông tin chức vụ
    position = Column(String(100), nullable=False, comment="Tên chức vụ")
    rank = Column(Integer, default=0, comment="Cấp chức vụ")
    
    # Trạng thái thành viên
    status = Column(String(20), default="active", comment="Trạng thái: active/retired/expelled/deceased")
    joined_at = Column(String(100), comment="Thời gian gia nhập (thời gian trong truyện)")
    left_at = Column(String(100), comment="Thời gian rời đi (thời gian trong truyện)")
    
    # Thuộc tính thành viên
    loyalty = Column(Integer, default=50, comment="Mức trung thành: 0-100")
    contribution = Column(Integer, default=0, comment="Mức đóng góp: 0-100")
    
    # Định danh nguồn
    source = Column(String(20), default="ai", comment="Nguồn: ai/manual")
    
    notes = Column(Text, comment="Ghi chú")
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<OrganizationMember(id={self.id}, org={self.organization_id}, char={self.character_id})>"