"""
Model dữ liệu người dùng - lưu thông tin cơ bản của người dùng
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """Model người dùng - lưu thông tin OAuth và người dùng cục bộ"""
    __tablename__ = "users"
    
    user_id = Column(String(100), primary_key=True, index=True, comment="ID người dùng, định dạng: linuxdo_{id} hoặc local_{id}")
    username = Column(String(100), nullable=False, index=True, comment="Tên người dùng")
    display_name = Column(String(200), nullable=False, comment="Tên hiển thị")
    avatar_url = Column(String(500), nullable=True, comment="URL avatar")
    trust_level = Column(Integer, default=0, comment="Cấp độ tin cậy (chỉ dùng để hiển thị)")
    is_admin = Column(Boolean, default=False, comment="Có phải quản trị viên không")
    linuxdo_id = Column(String(100), nullable=False, unique=True, index=True, comment="ID người dùng LinuxDO hoặc ID người dùng cục bộ")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Thời gian tạo")
    last_login = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Thời gian đăng nhập cuối")
    
    def to_dict(self):
        """Chuyển thành dict"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "trust_level": self.trust_level,
            "is_admin": self.is_admin,
            "linuxdo_id": self.linuxdo_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class UserPassword(Base):
    """Model mật khẩu người dùng - lưu thông tin mật khẩu người dùng"""
    __tablename__ = "user_passwords"
    
    user_id = Column(String(100), primary_key=True, index=True, comment="ID người dùng")
    username = Column(String(100), nullable=False, comment="Tên người dùng")
    password_hash = Column(String(255), nullable=False, comment="Hash mật khẩu")
    has_custom_password = Column(Boolean, default=False, comment="Có phải mật khẩu tùy chỉnh không")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
