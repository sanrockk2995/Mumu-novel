"""Model dữ liệu quản lý phục bút - quản lý độc lập việc gieo và thu hồi phục bút của tiểu thuyết"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Float, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Foreshadow(Base):
    """
    Bảng quản lý phục bút - quản lý độc lập phục bút tiểu thuyết

    Hỗ trợ các chức năng:
    1. Tự động đồng bộ phục bút từ kết quả phân tích chương
    2. Người dùng thêm thủ công phục bút tùy chỉnh
    3. Liên kết chương gieo và chương dự kiến thu hồi
    4. Quản lý phục bút dài tuyến
    5. Nhắc phục bút khi sinh chương
    """
    __tablename__ = "foreshadows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # === Nội dung phục bút ===
    title = Column(String(200), nullable=False, comment="Tiêu đề phục bút")
    content = Column(Text, nullable=False, comment="Nội dung chi tiết/mô tả phục bút")
    hint_text = Column(Text, comment="Văn bản gợi ý khi gieo phục bút (trích nguyên văn hoặc tóm tắt)")
    resolution_text = Column(Text, comment="Văn bản hé lộ khi thu hồi phục bút (trích nguyên văn hoặc tóm tắt)")

    # === Thông tin nguồn ===
    source_type = Column(String(20), default='manual', comment="Loại nguồn: analysis=trích xuất từ phân tích, manual=thêm thủ công")
    source_memory_id = Column(String(100), comment="ID ký ức nguồn (nếu đồng bộ từ kết quả phân tích)")
    source_analysis_id = Column(String(36), comment="ID tác vụ phân tích nguồn")

    # === Liên kết chương ===
    # Chương gieo
    plant_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="ID chương gieo")
    plant_chapter_number = Column(Integer, comment="Số chương gieo (lưu dư để tiện truy vấn)")

    # Chương dự kiến thu hồi
    target_resolve_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="ID chương dự kiến thu hồi")
    target_resolve_chapter_number = Column(Integer, comment="Số chương dự kiến thu hồi")

    # Chương thu hồi thực tế
    actual_resolve_chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="ID chương thu hồi thực tế")
    actual_resolve_chapter_number = Column(Integer, comment="Số chương thu hồi thực tế")

    # === Quản lý trạng thái ===
    status = Column(String(20), default='pending', index=True, comment="""
    Trạng thái phục bút:
    - pending: chờ gieo (đã lên kế hoạch nhưng chưa viết vào chương)
    - planted: đã gieo (đã gieo trong chương)
    - resolved: đã thu hồi (đã thu hồi trong chương)
    - partially_resolved: thu hồi một phần (phục bút dài tuyến có thể thu hồi nhiều lần)
    - abandoned: đã bỏ (quyết định không dùng phục bút này nữa)
    """)

    is_long_term = Column(Boolean, default=False, comment="Có phải phục bút dài tuyến (phục bút quan trọng xuyên nhiều chương)")

    # === Mức độ quan trọng và ưu tiên ===
    importance = Column(Float, default=0.5, comment="Điểm quan trọng 0.0-1.0")
    strength = Column(Integer, default=5, comment="Cường độ phục bút 1-10 (ảnh hưởng độc giả mạnh đến đâu)")
    subtlety = Column(Integer, default=5, comment="Độ ẩn 1-10 (càng cao càng kín đáo)")
    urgency = Column(Integer, default=0, comment="Độ khẩn cấp: 0=không khẩn cấp, 1=cần chú ý, 2=cần thu hồi gấp")

    # === Thông tin liên kết ===
    related_characters = Column(JSON, comment="Danh sách tên nhân vật liên quan: ['nhân vật 1', 'nhân vật 2']")
    related_foreshadow_ids = Column(JSON, comment="Danh sách ID phục bút khác liên quan (chuỗi phục bút)")
    tags = Column(JSON, comment="Danh sách nhãn: ['thân thế', 'hồi hộp', 'bước ngoặt']")
    category = Column(String(50), comment="Phân loại: identity(thân thế), mystery(hồi hộp), item(vật phẩm), relationship(quan hệ), event(sự kiện)")

    # === Ghi chú và giải thích ===
    notes = Column(Text, comment="Ghi chú sáng tác (chỉ tác giả thấy)")
    resolution_notes = Column(Text, comment="Giải thích cách thu hồi")

    # === Cài đặt hỗ trợ AI ===
    auto_remind = Column(Boolean, default=True, comment="Có tự động nhắc khi sinh chương không")
    remind_before_chapters = Column(Integer, default=5, comment="Bắt đầu nhắc thu hồi trước mấy chương")
    include_in_context = Column(Boolean, default=True, comment="Có đưa vào ngữ cảnh sinh không")

    # === Dấu thời gian ===
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    planted_at = Column(DateTime, comment="Thời gian gieo")
    resolved_at = Column(DateTime, comment="Thời gian thu hồi")

    def __repr__(self):
        return f"<Foreshadow(id={self.id[:8]}, title={self.title}, status={self.status})>"

    def to_dict(self):
        """Chuyển thành định dạng dict"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "content": self.content,
            "hint_text": self.hint_text,
            "resolution_text": self.resolution_text,
            "source_type": self.source_type,
            "source_memory_id": self.source_memory_id,
            "plant_chapter_id": self.plant_chapter_id,
            "plant_chapter_number": self.plant_chapter_number,
            "target_resolve_chapter_id": self.target_resolve_chapter_id,
            "target_resolve_chapter_number": self.target_resolve_chapter_number,
            "actual_resolve_chapter_id": self.actual_resolve_chapter_id,
            "actual_resolve_chapter_number": self.actual_resolve_chapter_number,
            "status": self.status,
            "is_long_term": self.is_long_term,
            "importance": self.importance,
            "strength": self.strength,
            "subtlety": self.subtlety,
            "urgency": self.urgency,
            "related_characters": self.related_characters or [],
            "related_foreshadow_ids": self.related_foreshadow_ids or [],
            "tags": self.tags or [],
            "category": self.category,
            "notes": self.notes,
            "resolution_notes": self.resolution_notes,
            "auto_remind": self.auto_remind,
            "remind_before_chapters": self.remind_before_chapters,
            "include_in_context": self.include_in_context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "planted_at": self.planted_at.isoformat() if self.planted_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def to_context_string(self) -> str:
        """
        Chuyển thành chuỗi ngữ cảnh (dùng cho prompt sinh chương)
        """
        parts = []

        # Thông tin cơ bản
        parts.append(f"Phục bút「{self.title}」")

        # Thông tin gieo
        if self.plant_chapter_number:
            parts.append(f"(gieo ở chương {self.plant_chapter_number})")

        # Tóm tắt nội dung
        content_preview = self.content[:100] if len(self.content) > 100 else self.content
        parts.append(f": {content_preview}")

        # Dự kiến thu hồi
        if self.target_resolve_chapter_number:
            parts.append(f" [dự kiến thu hồi ở chương {self.target_resolve_chapter_number}]")

        # Nhân vật liên quan
        if self.related_characters:
            parts.append(f" Liên quan: {', '.join(self.related_characters[:3])}")

        return "".join(parts)

    def get_urgency_level(self, current_chapter: int) -> int:
        """
        Tính độ khẩn cấp hiện tại

        Args:
            current_chapter: số chương hiện tại

        Returns:
            0=không khẩn cấp, 1=cần chú ý, 2=cần thu hồi gấp, 3=đã quá hạn
        """
        if self.status != 'planted' or not self.target_resolve_chapter_number:
            return 0

        chapters_remaining = self.target_resolve_chapter_number - current_chapter

        if chapters_remaining < 0:
            return 3  # Đã quá hạn
        elif chapters_remaining <= 2:
            return 2  # Cần thu hồi gấp
        elif chapters_remaining <= self.remind_before_chapters:
            return 1  # Cần chú ý
        else:
            return 0  # Không khẩn cấp
