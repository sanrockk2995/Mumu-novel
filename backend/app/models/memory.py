"""Model dữ liệu ký ức dài hạn - hỗ trợ truy xuất vector và phân tích cốt truyện"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Float, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base
import uuid


class StoryMemory(Base):
    """Bảng ký ức truyện - lưu trữ đoạn truyện có cấu trúc và metadata"""
    __tablename__ = "story_memories"
    
    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Loại ký ức
    memory_type = Column(String(50), nullable=False, index=True, comment="""
    Loại ký ức:
    - plot_point: điểm tình tiết
    - character_event: sự kiện nhân vật
    - world_detail: chi tiết thế giới quan
    - hook: móc câu (hồi hộp/xung đột)
    - foreshadow: phục bút
    - dialogue: đối thoại quan trọng
    - scene: miêu tả cảnh
    """)
    
    # Nội dung ký ức
    title = Column(String(200), comment="Tiêu đề/tóm tắt ký ức")
    content = Column(Text, nullable=False, comment="Tóm tắt nội dung ký ức (100-500 từ)")
    full_context = Column(Text, comment="Bối cảnh đầy đủ (tùy chọn, dùng để ghi chi tiết)")
    
    # Thông tin liên quan
    related_characters = Column(JSON, comment="Danh sách ID nhân vật liên quan: ['char_id_1', 'char_id_2']")
    related_locations = Column(JSON, comment="Danh sách địa điểm liên quan: ['地点1', '地点2']")
    tags = Column(JSON, comment="Danh sách nhãn: ['悬念', '转折', '伏笔', '高潮']")
    
    # Điểm quan trọng (dùng để lọc và sắp xếp)
    importance_score = Column(Float, default=0.5, comment="Điểm quan trọng 0.0-1.0")
    
    # Định vị dòng thời gian
    story_timeline = Column(Integer, nullable=False, index=True, comment="Vị trí dòng thời gian truyện (số thứ tự chương)")
    chapter_position = Column(Integer, default=0, comment="Vị trí trong chương (vị trí ký tự)")
    text_length = Column(Integer, default=0, comment="Độ dài văn bản (số ký tự)")
    
    # Trường liên quan phục bút
    is_foreshadow = Column(Integer, default=0, comment="Trạng thái phục bút: 0=ký ức thường, 1=đã gieo phục bút, 2=phục bút đã thu hồi")
    foreshadow_resolved_at = Column(String(100), ForeignKey("chapters.id", ondelete="SET NULL"), comment="ID chương thu hồi phục bút")
    foreshadow_strength = Column(Float, comment="Cường độ phục bút 0.0-1.0")
    
    # Liên kết vector database
    vector_id = Column(String(100), unique=True, comment="ID duy nhất trong vector database")
    embedding_model = Column(String(100), default="paraphrase-multilingual-MiniLM-L12-v2", comment="Model embedding sử dụng")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian tạo")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="Thời gian cập nhật")
    
    def __repr__(self):
        return f"<StoryMemory(id={self.id[:8]}, type={self.memory_type}, title={self.title})>"
    
    def to_dict(self):
        """Chuyển sang định dạng dict"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_id": self.chapter_id,
            "memory_type": self.memory_type,
            "title": self.title,
            "content": self.content,
            "related_characters": self.related_characters,
            "related_locations": self.related_locations,
            "tags": self.tags,
            "importance_score": self.importance_score,
            "story_timeline": self.story_timeline,
            "is_foreshadow": self.is_foreshadow,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PlotAnalysis(Base):
    """Bảng phân tích cốt truyện - lưu trữ cấu trúc chương và yếu tố cốt truyện do AI phân tích"""
    __tablename__ = "plot_analysis"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Phân tích cấu trúc cốt truyện
    plot_stage = Column(String(50), comment="Giai đoạn cốt truyện: 开端/发展/高潮/结局/过渡")
    conflict_level = Column(Integer, comment="Cường độ xung đột 1-10")
    conflict_types = Column(JSON, comment="Danh sách loại xung đột: ['人与人', '人与己', '人与环境']")
    
    # Phân tích cảm xúc
    emotional_tone = Column(String(100), comment="Cảm xúc chủ đạo: 紧张/温馨/悲伤/激昂/平静")
    emotional_intensity = Column(Float, comment="Cường độ cảm xúc 0.0-1.0")
    emotional_curve = Column(JSON, comment="Đường cong cảm xúc: {start: 0.3, middle: 0.7, end: 0.5}")
    
    # Phân tích hook (Hook Analysis)
    hooks = Column(JSON, comment="""Danh sách hook - yếu tố thu hút độc giả: [
        {
            "type": "悬念|情感|冲突|认知",
            "content": "Nội dung cụ thể",
            "strength": 8,
            "position": "开头|中段|结尾"
        }
    ]""")
    hooks_count = Column(Integer, default=0, comment="Số lượng hook")
    hooks_avg_strength = Column(Float, comment="Cường độ hook trung bình")
    
    # Phân tích phục bút (Foreshadowing Analysis)
    foreshadows = Column(JSON, comment="""Danh sách phục bút: [
        {
            "content": "Nội dung phục bút",
            "type": "planted|resolved",
            "strength": 7,
            "subtlety": 8,
            "reference_chapter": 3
        }
    ]""")
    foreshadows_planted = Column(Integer, default=0, comment="Số phục bút gieo trong chương này")
    foreshadows_resolved = Column(Integer, default=0, comment="Số phục bút thu hồi trong chương này")
    
    # Điểm tình tiết then chốt (Plot Points)
    plot_points = Column(JSON, comment="""Danh sách điểm tình tiết: [
        {
            "content": "Mô tả điểm tình tiết",
            "importance": 0.9,
            "type": "revelation|conflict|resolution|transition",
            "impact": "Mô tả ảnh hưởng đến câu chuyện"
        }
    ]""")
    plot_points_count = Column(Integer, default=0, comment="Số lượng điểm tình tiết")
    
    # Theo dõi trạng thái nhân vật (Character State Tracking)
    character_states = Column(JSON, comment="""Thay đổi trạng thái nhân vật: [
        {
            "character_id": "xxx",
            "character_name": "Trương Tam",
            "state_before": "Do dự bất quyết",
            "state_after": "Niềm tin kiên định",
            "psychological_change": "Mô tả nội tâm",
            "key_event": "Sự kiện kích hoạt",
            "relationship_changes": {"Lý Tứ": "Thay đổi quan hệ"}
        }
    ]""")
    
    # Cảnh và không khí
    scenes = Column(JSON, comment="Danh sách cảnh: [{location: 'Địa điểm', atmosphere: 'Không khí', duration: 'Thời lượng'}]")
    pacing = Column(String(50), comment="Nhịp độ: slow|moderate|fast|varied")
    
    # Điểm chất lượng
    overall_quality_score = Column(Float, comment="Điểm chất lượng tổng thể 0.0-10.0")
    pacing_score = Column(Float, comment="Điểm nhịp độ 0.0-10.0")
    engagement_score = Column(Float, comment="Điểm hấp dẫn 0.0-10.0")
    coherence_score = Column(Float, comment="Điểm mạch lạc 0.0-10.0")
    
    # Báo cáo phân tích văn bản
    analysis_report = Column(Text, comment="Báo cáo phân tích văn bản đầy đủ")
    suggestions = Column(JSON, comment="Danh sách gợi ý cải tiến: ['Gợi ý 1', 'Gợi ý 2']")
    
    # Thông tin thống kê
    word_count = Column(Integer, comment="Số từ của chương")
    dialogue_ratio = Column(Float, comment="Tỷ lệ hội thoại 0.0-1.0")
    description_ratio = Column(Float, comment="Tỷ lệ miêu tả 0.0-1.0")
    
    created_at = Column(DateTime, server_default=func.now(), comment="Thời gian phân tích")
    
    def __repr__(self):
        return f"<PlotAnalysis(chapter_id={self.chapter_id[:8]}, stage={self.plot_stage}, quality={self.overall_quality_score})>"
    
    def to_dict(self):
        """Chuyển sang định dạng dict"""
        return {
            "id": self.id,
            "chapter_id": self.chapter_id,
            "plot_stage": self.plot_stage,
            "conflict_level": self.conflict_level,
            "conflict_types": self.conflict_types or [],
            "emotional_tone": self.emotional_tone,
            "emotional_intensity": self.emotional_intensity or 0.0,
            "hooks": self.hooks or [],
            "hooks_count": self.hooks_count or 0,
            "foreshadows": self.foreshadows or [],
            "foreshadows_planted": self.foreshadows_planted or 0,
            "foreshadows_resolved": self.foreshadows_resolved or 0,
            "plot_points": self.plot_points or [],
            "plot_points_count": self.plot_points_count or 0,
            "character_states": self.character_states or [],
            "scenes": self.scenes or [],
            "pacing": self.pacing,
            "overall_quality_score": self.overall_quality_score or 0.0,
            "pacing_score": self.pacing_score or 0.0,
            "engagement_score": self.engagement_score or 0.0,
            "coherence_score": self.coherence_score or 0.0,
            "analysis_report": self.analysis_report,
            "suggestions": self.suggestions or [],
            "dialogue_ratio": self.dialogue_ratio or 0.0,
            "description_ratio": self.description_ratio or 0.0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }