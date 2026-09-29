"""Dịch vụ quản lý phục bút - Xử lý CRUD và logic nghiệp vụ của phục bút"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, delete, update
from datetime import datetime
import uuid
import hashlib

from app.models.foreshadow import Foreshadow
from app.models.chapter import Chapter
from app.models.memory import PlotAnalysis, StoryMemory
from app.models.project import Project
from app.services.memory_service import memory_service
from app.schemas.foreshadow import (
    ForeshadowCreate, ForeshadowUpdate,
    PlantForeshadowRequest, ResolveForeshadowRequest,
    SyncFromAnalysisRequest
)
from app.logger import get_logger

logger = get_logger(__name__)


def generate_stable_foreshadow_id(chapter_id: str, content: str, foreshadow_type: str = "planted") -> str:
    """
    Tạo định danh duy nhất ổn định cho phục bút
    
    Dùng chapter_id + content_hash, đảm bảo:
    1. Phục bút cùng chương, cùng nội dung chỉ có một ID duy nhất
    2. Phân tích lại cùng một chương sẽ không tạo ID mới
    3. Định danh đủ ngắn và dễ đọc
    
    Args:
        chapter_id: chươngID
        content: Nội dung phục bút
        foreshadow_type: Loại phục bút (planted/resolved)
    
    Returns:
        Định danh duy nhất ổn định, định dạng: {type}_{chapter_id_hash}_{content_hash}
    """
    # Tạo hash nội dung (lấy12ký tự, đủ để phân biệt)
    content_normalized = content.strip().lower()
    content_hash = hashlib.md5(content_normalized.encode('utf-8')).hexdigest()[:12]
    
    # TạoIDhash (lấy8ký tự)
    chapter_hash = hashlib.md5(chapter_id.encode('utf-8')).hexdigest()[:8]
    
    return f"{foreshadow_type}_{chapter_hash}_{content_hash}"


class ForeshadowService:
    """Dịch vụ quản lý phục bút"""
    
    async def get_project_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        status: Optional[str] = None,
        category: Optional[str] = None,
        source_type: Optional[str] = None,
        is_long_term: Optional[bool] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Lấy danh sách phục bút của dự án
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            status: Lọc theo trạng thái
            category: Lọc theo phân loại
            source_type: Lọc theo nguồn
            is_long_term: Có phải phục bút dài hạn không
            page: Số trang
            limit: Số lượng mỗi trang
        
        Returns:
            Dict chứa danh sách và thống kê
        """
        try:
            # Xây dựng điều kiện truy vấn
            conditions = [Foreshadow.project_id == project_id]
            
            if status:
                conditions.append(Foreshadow.status == status)
            if category:
                conditions.append(Foreshadow.category == category)
            if source_type:
                conditions.append(Foreshadow.source_type == source_type)
            if is_long_term is not None:
                conditions.append(Foreshadow.is_long_term == is_long_term)
            
            # Truy vấn tổng số
            count_query = select(func.count(Foreshadow.id)).where(and_(*conditions))
            total_result = await db.execute(count_query)
            total = total_result.scalar() or 0
            
            # Truy vấn danh sách
            query = (
                select(Foreshadow)
                .where(and_(*conditions))
                .order_by(
                    Foreshadow.plant_chapter_number.asc().nulls_last(),
                    desc(Foreshadow.importance),
                    desc(Foreshadow.created_at)
                )
                .offset((page - 1) * limit)
                .limit(limit)
            )
            
            result = await db.execute(query)
            foreshadows = result.scalars().all()
            
            # Lấy thống kê
            stats = await self.get_stats(db, project_id)
            
            return {
                "total": total,
                "items": [f.to_dict() for f in foreshadows],
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"❌ Lấy danh sách phục bút thất bại: {str(e)}")
            raise
    
    async def get_foreshadow(
        self,
        db: AsyncSession,
        foreshadow_id: str
    ) -> Optional[Foreshadow]:
        """Lấy một phục bút"""
        result = await db.execute(
            select(Foreshadow).where(Foreshadow.id == foreshadow_id)
        )
        return result.scalar_one_or_none()
    
    async def create_foreshadow(
        self,
        db: AsyncSession,
        data: ForeshadowCreate
    ) -> Foreshadow:
        """
        Tạo phục bút
        
        Args:
            db: cơ sở dữ liệuphiên
            data: Dữ liệu tạo
        
        Returns:
            Đối tượng phục bút đã tạo
        """
        try:
            foreshadow = Foreshadow(
                id=str(uuid.uuid4()),
                project_id=data.project_id,
                title=data.title,
                content=data.content,
                hint_text=data.hint_text,
                resolution_text=data.resolution_text,
                source_type="manual",
                plant_chapter_number=data.plant_chapter_number,
                target_resolve_chapter_number=data.target_resolve_chapter_number,
                status="pending",
                is_long_term=data.is_long_term,
                importance=data.importance,
                strength=data.strength,
                subtlety=data.subtlety,
                urgency=0,
                related_characters=data.related_characters,
                tags=data.tags,
                category=data.category,
                notes=data.notes,
                resolution_notes=data.resolution_notes,
                auto_remind=data.auto_remind,
                remind_before_chapters=data.remind_before_chapters,
                include_in_context=data.include_in_context
            )
            
            db.add(foreshadow)
            await db.commit()
            await db.refresh(foreshadow)
            
            logger.info(f"✅ Tạo phục bút thành công: {foreshadow.title}")
            return foreshadow
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Tạo phục bút thất bại: {str(e)}")
            raise
    
    async def update_foreshadow(
        self,
        db: AsyncSession,
        foreshadow_id: str,
        data: ForeshadowUpdate
    ) -> Optional[Foreshadow]:
        """
        Cập nhật phục bút
        
        Args:
            db: cơ sở dữ liệuphiên
            foreshadow_id: phục bútID
            data: Dữ liệu cập nhật
        
        Returns:
            Đối tượng phục bút đã cập nhật
        """
        try:
            foreshadow = await self.get_foreshadow(db, foreshadow_id)
            if not foreshadow:
                return None
            
            # Trường cập nhật
            update_data = data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if hasattr(foreshadow, key):
                    setattr(foreshadow, key, value)
            
            await db.commit()
            await db.refresh(foreshadow)
            
            logger.info(f"✅ Cập nhật phục bút thành công: {foreshadow.title}")
            return foreshadow
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Cập nhật phục bút thất bại: {str(e)}")
            raise
    
    async def delete_foreshadow(
        self,
        db: AsyncSession,
        foreshadow_id: str
    ) -> bool:
        """Xóa phục bút, đồng thời dọn dẹp đồng bộ dữ liệu ký ức liên quan và tham chiếu phân tích lịch sử"""
        try:
            foreshadow = await self.get_foreshadow(db, foreshadow_id)
            if not foreshadow:
                return False

            project_result = await db.execute(
                select(Project).where(Project.id == foreshadow.project_id)
            )
            project = project_result.scalar_one_or_none()

            deleted_memory_rows = 0
            deleted_vector_memories = 0
            cleaned_analysis_refs = 0
            cleaned_analysis_rows = 0
            foreshadow_keywords = []
            content_snippet = (foreshadow.content or "")[:50].strip()

            if foreshadow.title and foreshadow.title.strip():
                foreshadow_keywords.append(foreshadow.title.strip())

            if content_snippet:
                foreshadow_keywords.append(content_snippet)

            memory_conditions = [
                StoryMemory.project_id == foreshadow.project_id,
                StoryMemory.memory_type == "foreshadow"
            ]
            keyword_conditions = []
            for keyword in foreshadow_keywords:
                keyword_conditions.append(StoryMemory.content.contains(keyword))
                keyword_conditions.append(StoryMemory.title.contains(keyword))

            if keyword_conditions:
                delete_memory_query = delete(StoryMemory).where(
                    and_(*memory_conditions, or_(*keyword_conditions))
                )
                delete_memory_result = await db.execute(delete_memory_query)
                deleted_memory_rows = delete_memory_result.rowcount or 0

            if project and project.user_id and foreshadow_keywords:
                deleted_vector_memories = await memory_service.delete_foreshadow_memories(
                    user_id=project.user_id,
                    project_id=foreshadow.project_id,
                    foreshadow_keywords=foreshadow_keywords
                )

            analysis_result = await db.execute(
                select(PlotAnalysis).where(PlotAnalysis.project_id == foreshadow.project_id)
            )
            project_analyses = analysis_result.scalars().all()

            for analysis in project_analyses:
                analysis_foreshadows = analysis.foreshadows or []
                if not analysis_foreshadows:
                    continue

                original_count = len(analysis_foreshadows)
                filtered_foreshadows = []
                removed_count = 0

                for item in analysis_foreshadows:
                    if not isinstance(item, dict):
                        filtered_foreshadows.append(item)
                        continue

                    should_remove = False

                    # 1. Dọn dẹp tham chiếu thu hồi lịch sử
                    if item.get("reference_foreshadow_id") == foreshadow_id:
                        should_remove = True

                    # 2. Dọn dẹp bản ghi gieo lịch sử, tránh“Đồng bộ thủ công phục bút phân tích”lại từ PlotAnalysis Tái tạo phục bút đã xóa
                    if not should_remove and foreshadow.source_type == "analysis":
                        item_type = item.get("type")
                        item_content = (item.get("content") or "").strip()
                        item_title = (item.get("title") or "").strip()
                        item_source_memory_id = None

                        if item_type == "planted" and item_content and analysis.chapter_id == foreshadow.plant_chapter_id:
                            item_source_memory_id = generate_stable_foreshadow_id(
                                analysis.chapter_id,
                                item_content,
                                item_type
                            )

                            if foreshadow.source_memory_id and item_source_memory_id == foreshadow.source_memory_id:
                                should_remove = True
                            elif (
                                item_title
                                and foreshadow.title
                                and item_title == foreshadow.title.strip()
                                and content_snippet
                                and content_snippet in item_content
                            ):
                                should_remove = True

                    if should_remove:
                        removed_count += 1
                        continue

                    filtered_foreshadows.append(item)

                if removed_count > 0:
                    analysis.foreshadows = filtered_foreshadows
                    analysis.foreshadows_planted = sum(
                        1 for f in filtered_foreshadows
                        if isinstance(f, dict) and f.get('type') == 'planted'
                    )
                    analysis.foreshadows_resolved = sum(
                        1 for f in filtered_foreshadows
                        if isinstance(f, dict) and f.get('type') == 'resolved'
                    )
                    cleaned_analysis_refs += removed_count
                    cleaned_analysis_rows += 1
                    logger.info(
                        f"🧹 Đã dọn dẹp phân tích chương {analysis.chapter_id[:8]}: {removed_count} bản ghi lịch sử phục bút đã xóa "
                        f"(Số lượng gốc: {original_count}, Số lượng hiện tại: {len(filtered_foreshadows)})"
                    )

            await db.delete(foreshadow)
            await db.commit()

            logger.info(
                f"✅ Xóa phục bút thành công: {foreshadow.title} "
                f"(Dọn dẹp ký ức quan hệ: {deleted_memory_rows}, dọn dẹp ký ức vector: {deleted_vector_memories}, "
                f"Dọn dẹp tham chiếu phân tích lịch sử: {cleaned_analysis_refs}/{cleaned_analysis_rows} phân tích)"
            )
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Xóa phục bút thất bại: {str(e)}")
            raise
    
    async def mark_as_planted(
        self,
        db: AsyncSession,
        foreshadow_id: str,
        data: PlantForeshadowRequest
    ) -> Optional[Foreshadow]:
        """
        Đánh dấu phục bút là đã gieo
        
        Args:
            db: cơ sở dữ liệuphiên
            foreshadow_id: phục bútID
            data: Thông tin gieo
        
        Returns:
            Đối tượng phục bút đã cập nhật
        """
        try:
            foreshadow = await self.get_foreshadow(db, foreshadow_id)
            if not foreshadow:
                return None
            
            foreshadow.status = "planted"
            foreshadow.plant_chapter_id = data.chapter_id
            foreshadow.plant_chapter_number = data.chapter_number
            foreshadow.planted_at = datetime.now()
            
            if data.hint_text:
                foreshadow.hint_text = data.hint_text
            
            await db.commit()
            await db.refresh(foreshadow)
            
            logger.info(f"✅ Phục bút đã được đánh dấu gieo: {foreshadow.title} (chương {data.chapter_number})")
            return foreshadow
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Đánh dấu gieo phục bút thất bại: {str(e)}")
            raise
    
    async def mark_as_resolved(
        self,
        db: AsyncSession,
        foreshadow_id: str,
        data: ResolveForeshadowRequest
    ) -> Optional[Foreshadow]:
        """
        Đánh dấu phục bút là đã thu hồi
        
        Args:
            db: cơ sở dữ liệuphiên
            foreshadow_id: phục bútID
            data: Thông tin thu hồi
        
        Returns:
            Đối tượng phục bút đã cập nhật
        """
        try:
            foreshadow = await self.get_foreshadow(db, foreshadow_id)
            if not foreshadow:
                return None
            
            if data.is_partial:
                foreshadow.status = "partially_resolved"
            else:
                foreshadow.status = "resolved"
            
            foreshadow.actual_resolve_chapter_id = data.chapter_id
            foreshadow.actual_resolve_chapter_number = data.chapter_number
            foreshadow.resolved_at = datetime.now()
            
            if data.resolution_text:
                foreshadow.resolution_text = data.resolution_text
            
            await db.commit()
            await db.refresh(foreshadow)
            
            logger.info(f"✅ Phục bút đã được đánh dấu thu hồi: {foreshadow.title} (Chương {data.chapter_number})")
            return foreshadow
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Đánh dấu thu hồi phục bút thất bại: {str(e)}")
            raise
    
    async def mark_as_abandoned(
        self,
        db: AsyncSession,
        foreshadow_id: str,
        reason: Optional[str] = None
    ) -> Optional[Foreshadow]:
        """Đánh dấu phục bút là đã loại bỏ"""
        try:
            foreshadow = await self.get_foreshadow(db, foreshadow_id)
            if not foreshadow:
                return None
            
            foreshadow.status = "abandoned"
            if reason:
                foreshadow.notes = f"{foreshadow.notes or ''}\n[Lý do loại bỏ] {reason}".strip()
            
            await db.commit()
            await db.refresh(foreshadow)
            
            logger.info(f"✅ Phục bút đã được đánh dấu loại bỏ: {foreshadow.title}")
            return foreshadow
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Đánh dấu loại bỏ phục bút thất bại: {str(e)}")
            raise
    
    async def sync_from_analysis(
        self,
        db: AsyncSession,
        project_id: str,
        data: SyncFromAnalysisRequest
    ) -> Dict[str, Any]:
        """
        Đồng bộ phục bút từ kết quả phân tích chương (bản tái cấu trúc)
        
        Tái sử dụng thống nhất auto_update_from_analysis logic cốt lõi của , tránh lặp mã.
        Phương thức này chỉ chịu trách nhiệm đọc dữ liệu từ PlotAnalysis bảng, sau đó ủy thác xử lý.
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            data: Dữ liệu yêu cầu đồng bộ
        
        Returns:
            Kết quả đồng bộ
        """
        try:
            total_stats = {
                "synced_count": 0,
                "skipped_count": 0,
                "resolved_count": 0,
                "new_foreshadows": [],
                "skipped_reasons": []
            }
            
            # Lấy kết quả phân tích
            query = select(PlotAnalysis).where(PlotAnalysis.project_id == project_id)
            if data.chapter_ids:
                query = query.where(PlotAnalysis.chapter_id.in_(data.chapter_ids))
            
            result = await db.execute(query)
            analyses = result.scalars().all()
            
            for analysis in analyses:
                if not analysis.foreshadows:
                    continue
                
                # Lấy thông tin chương
                chapter_result = await db.execute(
                    select(Chapter).where(Chapter.id == analysis.chapter_id)
                )
                chapter = chapter_result.scalar_one_or_none()
                if not chapter:
                    continue
                
                # Ủy thác cho phương thức xử lý thống nhất
                chapter_stats = await self.auto_update_from_analysis(
                    db=db,
                    project_id=project_id,
                    chapter_id=chapter.id,
                    chapter_number=chapter.chapter_number,
                    analysis_foreshadows=analysis.foreshadows
                )
                
                # Tổng hợp thống kê
                total_stats["synced_count"] += chapter_stats.get("planted_count", 0) + chapter_stats.get("resolved_count", 0)
                total_stats["resolved_count"] += chapter_stats.get("resolved_count", 0)
                total_stats["skipped_count"] += chapter_stats.get("skipped_resolve_count", 0)
            
            logger.info(f"✅ Đồng bộ phục bút hoàn tất: đồng bộ {total_stats['synced_count']} (trong đó thu hồi {total_stats['resolved_count']}), bỏ qua {total_stats['skipped_count']}")
            
            return total_stats
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Đồng bộ phục bút thất bại: {str(e)}")
            raise
    
    async def get_pending_resolve_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        current_chapter: int,
        lookahead: int = 5
    ) -> List[Foreshadow]:
        """
        Lấy các phục bút sắp cần thu hồi
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            current_chapter: số chương hiện tại
            lookahead: Nhìn trước mấy chương
        
        Returns:
            Danh sách phục bút chờ thu hồi
        """
        try:
            # Truy vấn các phục bút đã gieo và dự kiến thu hồi trong vài chương tới
            query = (
                select(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.status == "planted",
                        Foreshadow.target_resolve_chapter_number != None,
                        Foreshadow.target_resolve_chapter_number <= current_chapter + lookahead,
                        Foreshadow.auto_remind == True
                    )
                )
                .order_by(Foreshadow.target_resolve_chapter_number)
            )
            
            result = await db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"❌ Lấy phục bút chờ thu hồi thất bại: {str(e)}")
            return []
    
    async def get_overdue_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        current_chapter: int
    ) -> List[Foreshadow]:
        """
        Lấy các phục bút quá hạn chưa thu hồi
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            current_chapter: số chương hiện tại
        
        Returns:
            Danh sách phục bút quá hạn
        """
        try:
            query = (
                select(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.status == "planted",
                        Foreshadow.target_resolve_chapter_number != None,
                        Foreshadow.target_resolve_chapter_number < current_chapter
                    )
                )
                .order_by(Foreshadow.target_resolve_chapter_number)
            )
            
            result = await db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"❌ Lấy phục bút quá hạn thất bại: {str(e)}")
            return []
    
    async def get_must_resolve_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int
    ) -> List[Foreshadow]:
        """
        Lấy các phục bút phải thu hồi trong chương này (target_resolve_chapter_number == chapter_number)
        
        Các phục bút này là do người dùng chỉ định rõ thu hồi trong chương này, phải hoàn tất thu hồi trong chương này
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_number: số chương hiện tại
        
        Returns:
            Danh sách phục bút phải thu hồi
        """
        try:
            query = (
                select(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.status == "planted",
                        Foreshadow.target_resolve_chapter_number == chapter_number
                    )
                )
                .order_by(desc(Foreshadow.importance))
            )
            
            result = await db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"❌ Lấy phục bút phải thu hồi trong chương này thất bại: {str(e)}")
            return []
    
    async def get_foreshadows_to_plant(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int
    ) -> List[Foreshadow]:
        """
        Lấy các phục bút dự kiến gieo trong chương này
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_number: số chương
        
        Returns:
            Danh sách phục bút chờ gieo
        """
        try:
            query = (
                select(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.status == "pending",
                        Foreshadow.plant_chapter_number == chapter_number
                    )
                )
                .order_by(desc(Foreshadow.importance))
            )
            
            result = await db.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"❌ Lấy phục bút chờ gieo thất bại: {str(e)}")
            return []
    
    async def build_chapter_context(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_number: int,
        include_pending: bool = True,
        include_overdue: bool = True,
        lookahead: int = 5
    ) -> Dict[str, Any]:
        """
        Xây dựng ngữ cảnh phục bút cho việc tạo chương (chiến lược nhắc nhở phân tầng thông minh)
        
        Chiến lược cốt lõi:
        1. Phục bút phải thu hồi trong chương này → Yêu cầu rõ ràng thu hồi
        2. Phục bút quá hạn → Nhấn mạnh cần thu hồi sớm
        3. Phục bút sắp thu hồi → Chỉ làm thông tin nền, cấm rõ ràng thu hồi trước
        4. Phục bút xa → Không gửi, tránh gây nhiễu
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_number: số chương
            include_pending: Bao gồm phục bút chờ gieo
            include_overdue: Bao gồm phục bút quá hạn
            lookahead: Nhìn trước mấy chương (dùng để nhắc nền, không bắt buộc thu hồi)
        
        Returns:
            Thông tin ngữ cảnh phục bút
        """
        try:
            lines = []
            to_plant = []
            must_resolve = []  # Phải thu hồi trong chương này
            overdue = []       # Quá hạn chờ thu hồi
            upcoming = []      # Sắp thu hồi (chỉ tham khảo)
            
            # 1. Lấy các phục bút phải thu hồi trong chương này (target_resolve_chapter_number == chapter_number)
            must_resolve = await self.get_must_resolve_foreshadows(db, project_id, chapter_number)
            if must_resolve:
                lines.append("[🎯 Phục bút phải thu hồi trong chương này - hãy hoàn tất thu hồi trong chương này]")
                for f in must_resolve:
                    lines.append(f"- ID:{f.id[:8]} | {f.title}")
                    lines.append(f"  Chương gieo: chương {f.plant_chapter_number}")
                    lines.append(f"  Nội dung phục bút:{f.content[:100]}{'...' if len(f.content) > 100 else ''}")
                    if f.resolution_notes:
                        lines.append(f"  Gợi ý thu hồi:{f.resolution_notes}")
                    lines.append("")
            
            # 2. Phục bút quá hạn (đã qua chương thu hồi mục tiêu nhưng chưa thu hồi)
            if include_overdue:
                overdue = await self.get_overdue_foreshadows(db, project_id, chapter_number)
                if overdue:
                    lines.append("[⚠️ Phục bút quá hạn chờ thu hồi - hãy thu hồi sớm]")
                    for f in overdue[:3]:
                        overdue_chapters = chapter_number - (f.target_resolve_chapter_number or 0)
                        lines.append(f"- ID:{f.id[:8]} | {f.title} [quá hạn {overdue_chapters} chương]")
                        lines.append(f"  Chương gieo: chương {f.plant_chapter_number}, ban đầu dự kiến thu hồi ở chương {f.target_resolve_chapter_number}")
                        lines.append(f"  Nội dung phục bút:{f.content[:80]}...")
                    lines.append("")
            
            # 3. Phục bút sắp cần thu hồi (chỉ làm tham khảo nền, cấm rõ ràng thu hồi trước)
            upcoming_raw = await self.get_pending_resolve_foreshadows(
                db, project_id, chapter_number, lookahead
            )
            # Lọc: loại trừ các phục bút phải thu hồi trong chương này và quá hạn, chỉ giữ lại các phục bút của chương tương lai
            upcoming = [f for f in upcoming_raw
                       if (f.target_resolve_chapter_number or 0) > chapter_number]
            
            if upcoming:
                lines.append("[📋 Phục bút sắp chờ thu hồi (chỉ tham khảo, không thu hồi trong chương này)]")
                lines.append("⚠️ Các phục bút dưới đây chưa đến thời điểm thu hồi, trong chương này không thu hồi trước, chỉ tìm hiểu như bối cảnh cốt truyện")
                for f in upcoming[:5]:
                    remaining = (f.target_resolve_chapter_number or 0) - chapter_number
                    lines.append(f"- {f.title}(kế hoạchChương {f.target_resolve_chapter_number}thu hồi,Còn{remaining}chương)")
                lines.append("")
            
            # 4. Phục bút chờ gieo trong chương này
            if include_pending:
                to_plant = await self.get_foreshadows_to_plant(db, project_id, chapter_number)
                if to_plant:
                    lines.append("[✨ Phục bút dự kiến gieo trong chương này]")
                    for f in to_plant:
                        content_preview = f.content[:80] if len(f.content) > 80 else f.content
                        lines.append(f"- {f.title}")
                        lines.append(f"  Nội dung phục bút:{content_preview}")
                        if f.hint_text:
                            lines.append(f"  Gợi ý gieo:{f.hint_text}")
                    lines.append("")
            
            context_text = "\n".join(lines) if lines else ""
            
            return {
                "chapter_number": chapter_number,
                "context_text": context_text,
                "pending_plant": [f.to_dict() for f in to_plant],
                "must_resolve": [f.to_dict() for f in must_resolve],
                "pending_resolve": [f.to_dict() for f in upcoming],
                "overdue": [f.to_dict() for f in overdue],
                "recently_planted": []  # có thể mở rộng
            }
            
        except Exception as e:
            logger.error(f"❌ Xây dựng ngữ cảnh phục bút thất bại: {str(e)}")
            return {
                "chapter_number": chapter_number,
                "context_text": "",
                "pending_plant": [],
                "must_resolve": [],
                "pending_resolve": [],
                "overdue": [],
                "recently_planted": []
            }
    
    async def get_stats(
        self,
        db: AsyncSession,
        project_id: str,
        current_chapter: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Lấy thống kê phục bút
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            current_chapter: số chương hiện tại (dùng để tính quá hạn)
        
        Returns:
            Dict thông tin thống kê
        """
        try:
            # Thống kê từng trạng thái
            stats_query = (
                select(
                    Foreshadow.status,
                    func.count(Foreshadow.id).label('count')
                )
                .where(Foreshadow.project_id == project_id)
                .group_by(Foreshadow.status)
            )
            
            result = await db.execute(stats_query)
            status_counts = {row.status: row.count for row in result}
            
            # Tổng số
            total = sum(status_counts.values())
            
            # Số lượng phục bút dài hạn
            long_term_query = (
                select(func.count(Foreshadow.id))
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.is_long_term == True
                    )
                )
            )
            long_term_result = await db.execute(long_term_query)
            long_term_count = long_term_result.scalar() or 0
            
            # Số lượng quá hạn
            overdue_count = 0
            if current_chapter:
                overdue = await self.get_overdue_foreshadows(db, project_id, current_chapter)
                overdue_count = len(overdue)
            
            return {
                "total": total,
                "pending": status_counts.get("pending", 0),
                "planted": status_counts.get("planted", 0),
                "resolved": status_counts.get("resolved", 0),
                "partially_resolved": status_counts.get("partially_resolved", 0),
                "abandoned": status_counts.get("abandoned", 0),
                "long_term_count": long_term_count,
                "overdue_count": overdue_count
            }
            
        except Exception as e:
            logger.error(f"❌ Lấy thống kê phục bút thất bại: {str(e)}")
            return {
                "total": 0,
                "pending": 0,
                "planted": 0,
                "resolved": 0,
                "partially_resolved": 0,
                "abandoned": 0,
                "long_term_count": 0,
                "overdue_count": 0
            }
    
    async def get_planted_foreshadows_for_analysis(
        self,
        db: AsyncSession,
        project_id: str,
        current_chapter_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Lấy danh sách phục bút đã gieo để tiêm khi phân tích (bản lọc thông minh)
        
        Chiến lược:
        1. Chỉ trả về status='planted' phục bút
        2. Nếu chỉ định số chương hiện tại, sẽ đánh dấu phục bút nào nên thu hồi trong chương này
        3. Phân biệt phục bút "có thể thu hồi" và "không thể thu hồi", giúp AI nhận biết chính xác
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            current_chapter_number: Số chương hiện tại (tùy chọn, dùng để đánh dấu thông minh)
        
        Returns:
            Danh sách phục bút (kèm đánh dấu thu hồi)
        """
        try:
            query = (
                select(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.status == "planted"
                    )
                )
                .order_by(Foreshadow.plant_chapter_number)
            )
            
            result = await db.execute(query)
            foreshadows = result.scalars().all()
            
            formatted_list = []
            for f in foreshadows:
                item = {
                    "id": f.id,
                    "title": f.title,
                    "content": f.content,
                    "hint_text": f.hint_text, 
                    "plant_chapter_number": f.plant_chapter_number,
                    "target_resolve_chapter_number": f.target_resolve_chapter_number,
                    "category": f.category,
                    "related_characters": f.related_characters or [],
                    "is_long_term": f.is_long_term
                }
                
                # Đánh dấu thông minh trạng thái thu hồi
                if current_chapter_number and f.target_resolve_chapter_number:
                    if f.target_resolve_chapter_number == current_chapter_number:
                        item["resolve_status"] = "must_resolve_now"  # Phải thu hồi trong chương này
                        item["resolve_hint"] = "Chương này phải thu hồi phục bút này"
                    elif f.target_resolve_chapter_number < current_chapter_number:
                        item["resolve_status"] = "overdue"  # Đã quá hạn
                        item["resolve_hint"] = f"Đã quá hạn {current_chapter_number - f.target_resolve_chapter_number} chương, nên thu hồi sớm"
                    else:
                        item["resolve_status"] = "not_yet"  # Chưa đến hạn
                        item["resolve_hint"] = f"Dự kiến thu hồi ở chương {f.target_resolve_chapter_number}, không thu hồi trước"
                else:
                    item["resolve_status"] = "no_plan"  # Không có kế hoạch rõ ràng
                    item["resolve_hint"] = "Không có kế hoạch thu hồi rõ ràng, thu hồi tự nhiên theo cốt truyện"
                
                formatted_list.append(item)
            
            return formatted_list
            
        except Exception as e:
            logger.error(f"❌ Lấy phục bút đã gieo thất bại: {str(e)}")
            return []
    
    async def delete_chapter_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: str,
        only_analysis_source: bool = True
    ) -> Dict[str, Any]:
        """
        Xóa các phục bút liên quan đến chương chỉ định
        
        Gọi khi nội dung chương bị xóa hoặc tạo lại, dọn dẹp dữ liệu còn lại
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_id: chươngID
            only_analysis_source: có chỉ xóa các phục bút có nguồn là analysis không (mặc định True)
                                  Nếu là False, thì xóa mọi phục bút liên quan đến chương đó
        
        Returns:
            Thông tin thống kê xóa
        """
        try:
            # 1. Trước tiên qua PlotAnalysis tìm phân tích của chương đóID
            # Đây là điểm then chốt: các phục bút do sync_from_analysis tạo dùng source_analysis_id để liên kết
            analysis_query = select(PlotAnalysis.id).where(PlotAnalysis.chapter_id == chapter_id)
            analysis_result = await db.execute(analysis_query)
            analysis_ids = [row[0] for row in analysis_result.fetchall()]
            
            logger.debug(f"🔍 Tìm chương {chapter_id[:8]} phân tích củaID: {len(analysis_ids)} ")
            
            # 2. Xây dựng điều kiện truy vấn: tìm các phục bút liên quan đến chương đó
            # Cách khớp:
            # 1. Chương gieo là chương đó (plant_chapter_id)
            # 2. Chương thu hồi là chương đó (actual_resolve_chapter_id)
            # 3. Nguồn phân tíchIDtương ứng với phân tích của chương đó (source_analysis_id)
            or_conditions = [
                Foreshadow.plant_chapter_id == chapter_id,
                Foreshadow.actual_resolve_chapter_id == chapter_id,
            ]
            
            # Nếu đã tìm thấy phân tíchID, thêm source_analysis_id Điều kiện khớp
            if analysis_ids:
                or_conditions.append(Foreshadow.source_analysis_id.in_(analysis_ids))
            
            conditions = [
                Foreshadow.project_id == project_id,
                or_(*or_conditions)
            ]
            
            # Nếu chỉ xóa các phục bút có nguồn phân tích
            if only_analysis_source:
                conditions.append(Foreshadow.source_type == "analysis")
            
            # Truy vấn các phục bút cần xóa
            query = select(Foreshadow).where(and_(*conditions))
            result = await db.execute(query)
            foreshadows_to_delete = result.scalars().all()
            
            deleted_count = len(foreshadows_to_delete)
            deleted_ids = [f.id for f in foreshadows_to_delete]
            deleted_titles = [f.title for f in foreshadows_to_delete]
            
            # Thực thi xóa
            for foreshadow in foreshadows_to_delete:
                await db.delete(foreshadow)
            
            await db.commit()
            
            if deleted_count > 0:
                logger.info(f"🗑️ Đã xóa chương {chapter_id[:8]} liên quan {deleted_count} phục bút")
                for title in deleted_titles[:5]:  # chỉ in5
                    logger.debug(f"  - {title}")
                if deleted_count > 5:
                    logger.debug(f"  ... Còn {deleted_count - 5} ")
            
            return {
                "deleted_count": deleted_count,
                "deleted_ids": deleted_ids,
                "deleted_titles": deleted_titles
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Xóa phục bút chương thất bại: {str(e)}")
            raise
    
    async def clean_chapter_analysis_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: str
    ) -> Dict[str, Any]:
        """
        Dọn dẹp các phục bút do phân tích chương tạo ra (dùng để dọn dẹp trước khi phân tích lại)
        
        Thao tác hai bước:
        1. Xóa các phục bút có source_type='analysis' và plant_chapter_id == chapter_id
        2. Khôi phục các phục bút bị thu hồi trong chương này (chuyển chúng từ resolved thành planted)
        
        Giữ lại các phục bút tạo thủ công
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_id: chươngID
        
        Returns:
            Thông tin thống kê dọn dẹp
        """
        try:
            # bước1: Xóa các phục bút phân tích gieo trong chương này
            query = select(Foreshadow).where(
                and_(
                    Foreshadow.project_id == project_id,
                    Foreshadow.source_type == "analysis",
                    Foreshadow.plant_chapter_id == chapter_id
                )
            )
            
            result = await db.execute(query)
            foreshadows_to_clean = result.scalars().all()
            
            cleaned_count = len(foreshadows_to_clean)
            cleaned_ids = [f.id for f in foreshadows_to_clean]
            
            for foreshadow in foreshadows_to_clean:
                await db.delete(foreshadow)
            
            # bước2: Khôi phục các phục bút bị thu hồi trong chương này (khôi phục thành planted trạng thái)
            reverted_count = await self._revert_chapter_resolutions(db, project_id, chapter_id)
            
            await db.commit()
            
            if cleaned_count > 0 or reverted_count > 0:
                logger.info(f"🧹 Đã dọn dẹp chương {chapter_id[:8]}: xóa {cleaned_count} phục bút phân tích, khôi phục {reverted_count} trạng thái thu hồi")
            
            return {
                "cleaned_count": cleaned_count,
                "cleaned_ids": cleaned_ids,
                "reverted_count": reverted_count
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Dọn dẹp phục bút phân tích chương thất bại: {str(e)}")
            raise
    
    async def _revert_chapter_resolutions(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: str
    ) -> int:
        """
        Khôi phục các phục bút bị thu hồi trong chương chỉ định
        
        Các phục bút có actual_resolve_chapter_id == chapter_id và status là resolved/partially_resolved
        khôi phục thành trạng thái planted, để khi phân tích lại có thể khớp thu hồi lại
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_id: chươngID
        
        Returns:
            Số lượng phục bút được khôi phục
        """
        try:
            update_query = (
                update(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.actual_resolve_chapter_id == chapter_id,
                        Foreshadow.status.in_(["resolved", "partially_resolved"])
                    )
                )
                .values(
                    status="planted",
                    actual_resolve_chapter_id=None,
                    actual_resolve_chapter_number=None,
                    resolved_at=None,
                    resolution_text=None
                )
            )
            result = await db.execute(update_query)
            reverted_count = result.rowcount
            
            if reverted_count > 0:
                logger.info(f"↩️ Đã khôi phục {reverted_count} phục bút trong chương {chapter_id[:8]} bị thu hồi")
            
            return reverted_count
            
        except Exception as e:
            logger.error(f"❌ Khôi phục thu hồi chương thất bại: {str(e)}")
            return 0

    async def clear_project_foreshadows_for_reset(
        self,
        db: AsyncSession,
        project_id: str
    ) -> Dict[str, int]:
        """
        Dọn dẹp phục bút dự án khi tạo hoàn toàn mới
        
        1. Xóa tất cả source_type='analysis' phục bút
        2. Đặt lại tất cả source_type='manual' phục bút thành pending trạng thái
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            
        Returns:
            Dọn dẹp thống kê
        """
        try:
            # 1. Xóa các phục bút do phân tích tạo ra
            delete_query = delete(Foreshadow).where(
                and_(
                    Foreshadow.project_id == project_id,
                    Foreshadow.source_type == "analysis"
                )
            )
            delete_result = await db.execute(delete_query)
            deleted_count = delete_result.rowcount
            
            # 2. Đặt lại các phục bút tạo thủ công
            # Đặt lại trạng thái planted/resolved/partially_resolved thành pending
            # Xóa thông tin liên kết chương
            update_query = (
                update(Foreshadow)
                .where(
                    and_(
                        Foreshadow.project_id == project_id,
                        Foreshadow.source_type == "manual",
                        Foreshadow.status.in_(["planted", "resolved", "partially_resolved"])
                    )
                )
                .values(
                    status="pending",
                    plant_chapter_id=None,
                    plant_chapter_number=None,
                    actual_resolve_chapter_id=None,
                    actual_resolve_chapter_number=None,
                    planted_at=None,
                    resolved_at=None,
                    target_resolve_chapter_id=None,
                    target_resolve_chapter_number=None
                )
            )
            update_result = await db.execute(update_query)
            reset_count = update_result.rowcount
            
            await db.commit()
            
            logger.info(f"🧹 Dọn dẹp phục bút dự án {project_id} hoàn tất: xóa {deleted_count} phục bút phân tích, đặt lại {reset_count} phục bút thủ công")
            
            return {
                "deleted_count": deleted_count,
                "reset_count": reset_count
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Dọn dẹp phục bút dự án thất bại: {str(e)}")
            raise

    async def auto_update_from_analysis(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: str,
        chapter_number: int,
        analysis_foreshadows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Tự động cập nhật trạng thái phục bút theo kết quả phân tích chương
        
        Chức năng:
        1. Tự động đánh dấu phục bút mới gieo là planted
        2. Theo reference_foreshadow_id Tự động thu hồi phục bút đã có
        3. Nếu không có reference_foreshadow_id, dùng cơ chế dự phòng khớp nội dung
        4. Tạo bản ghi phục bút mới phát hiện
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_id: chươngID
            chapter_number: số chương
            analysis_foreshadows: Danh sách phục bút trong kết quả phân tích
        
        Returns:
            Cập nhật thống kê
        """
        try:
            stats = {
                "planted_count": 0,      # Phục bút mới gieo
                "resolved_count": 0,     # Phục bút đã thu hồi
                "created_count": 0,      # Bản ghi phục bút mới tạo
                "updated_ids": [],       # Phục bút đã cập nhậtID
                "created_ids": [],       # Phục bút đã tạoID
                "matched_by_content": 0, # Số lượng thu hồi qua khớp nội dung
                "errors": []             # Thông tin lỗi
            }
            
            # Lấy trước mọi phục bút đã gieo, dùng để khớp nội dung
            planted_foreshadows = await self.get_planted_foreshadows_for_analysis(db, project_id)
            
            # Số lượng phục bút mới tối đa mỗi chương được tạo
            MAX_NEW_FORESHADOWS_PER_CHAPTER = 5
            new_foreshadow_count = 0

            for fs_data in analysis_foreshadows:
                try:
                    fs_type = fs_data.get("type", "planted")
                    reference_id = fs_data.get("reference_foreshadow_id")
                    
                    if fs_type == "resolved":
                        existing = None
                        matched_by_content = False
                        
                        # chiến lược1: Ưu tiên dùng reference_id khớp chính xác
                        # Quan trọng: nếu kết quả phân tích đã cho reference_foreshadow_id,
                        # nhưng phục bút đó đã bị người dùng xóa hoặc không còn thuộc dự án hiện tại, thì bỏ qua trực tiếp,
                        # không quay lại khớp nội dung, tránh việc“phục bút đã xóa”kết quả phân tích cũ đồng bộ nhầm sang các/phục bút tương tự khác.
                        if reference_id:
                            existing = await self.get_foreshadow(db, reference_id)
                            if existing and existing.project_id == project_id:
                                logger.info(f"🎯 QuaIDKhớp chính xác phục bút: {existing.title}")
                            else:
                                existing = None
                                logger.warning(f"⚠️ phục bútIDkhông tồn tại hoặc không thuộc dự án đó, bỏ qua đồng bộ thu hồi lần này: {reference_id}")
                                stats["skipped_resolve_count"] = stats.get("skipped_resolve_count", 0) + 1
                                stats["errors"].append(f"reference_foreshadow_id không hợp lệ hoặc đã xóa: {reference_id}")
                                continue
                        
                        # chiến lược2: Cơ chế dự phòng khớp nội dung (chỉ khi analysis không cung cấp reference_id mới bật)
                        if not reference_id and not existing and planted_foreshadows:
                            matched = self._match_foreshadow_by_content(
                                fs_data, planted_foreshadows
                            )
                            if matched:
                                matched_by_content = True
                                logger.info(f"🔍 Tìm phục bút qua khớp nội dung: {matched.get('title')}")
                                # Lấy lại đối tượng phục bút đầy đủ
                                existing = await self.get_foreshadow(db, matched.get('id'))
                        
                        # Kiểm tra phục bút đã bị thu hồi chưa (tránh thu hồi lặp)
                        if existing:
                            if existing.status == "resolved" and existing.actual_resolve_chapter_number == chapter_number:
                                logger.info(f"ℹ️ Phục bút đã được thu hồi trong chương này, bỏ qua: {existing.title}")
                                continue
                            elif existing.status == "resolved":
                                logger.warning(f"⚠️ Phục bút đã thu hồi ở chương {existing.actual_resolve_chapter_number}, bỏ qua: {existing.title}")
                                continue
                        
                        # Thực thi thu hồi
                        if existing and existing.status == "planted":
                            # Cập nhật thành trạng thái đã thu hồi
                            existing.status = "resolved"
                            existing.actual_resolve_chapter_id = chapter_id
                            existing.actual_resolve_chapter_number = chapter_number
                            existing.resolved_at = datetime.now()
                            
                            # Cập nhật văn bản thu hồi
                            if fs_data.get("content"):
                                existing.resolution_text = fs_data.get("content")
                            
                            await db.flush()
                            await db.refresh(existing)
                            
                            stats["resolved_count"] += 1
                            stats["updated_ids"].append(existing.id)
                            if matched_by_content:
                                stats["matched_by_content"] += 1
                            logger.info(f"✅ Tự động thu hồi phục bút: {existing.title} (ID: {existing.id}, status: {existing.status})")
                            
                            # Loại khỏi danh sách chờ khớp các phục bút đã thu hồi
                            planted_foreshadows = [f for f in planted_foreshadows if f['id'] != existing.id]
                        elif existing:
                            logger.warning(f"⚠️ Trạng thái phục bút không phảiplanted, bỏ qua thu hồi: {existing.title} (status: {existing.status})")
                        else:
                            # Không tìm thấy phục bút đã gieo khớp, bỏ qua (không tạo bản ghi mới!)
                            # Nguyên tắc cốt lõi: chỉ"gieo"thao tác mới tạo bản ghi phục bút,"thu hồi"chỉ cập nhật bản ghi đã có
                            # Nếu không có phục bút nào được gieo, thì không thể có thu hồi
                            fs_title = fs_data.get("title", fs_data.get("content", "")[:30])
                            logger.warning(f"⚠️ Không tìm thấy phục bút đã gieo khớp, bỏ qua thu hồi (không tạo bản ghi mới): {fs_title}")
                            logger.warning(f"   Gợi ý:AIcó thể đã nhận nhầm phục bút thu hồi, hoặc reference_foreshadow_id không điền đúng")
                            stats["skipped_resolve_count"] = stats.get("skipped_resolve_count", 0) + 1
                            continue
                    
                    elif fs_type == "planted":
                        fs_content = fs_data.get("content", "")
                        if not fs_content:
                            logger.warning(f"⚠️ Nội dung phục bút trống, bỏ qua")
                            continue
                        
                        fs_title = fs_data.get("title", "")
                        if not fs_title:
                            fs_title = fs_content[:50] + ("..." if len(fs_content) > 50 else "")
                        
                        # Dùng định danh duy nhất ổn định (dựa trên chapter_id + content_hash)
                        source_memory_id = generate_stable_foreshadow_id(
                            chapter_id, fs_content, fs_type
                        )
                        
                        # Kiểm tra đã tồn tại chưa (dùngIDloại trùng, tránh phân tích lặp tạo bản ghi trùng lặp)
                        existing_check = await db.execute(
                            select(Foreshadow).where(
                                and_(
                                    Foreshadow.project_id == project_id,
                                    or_(
                                        # Cách 1: khớp chính xác qua source_memory_id ổn định
                                        Foreshadow.source_memory_id == source_memory_id,
                                        # Cách 2: khớp qua tiêu đề + số chương (tương thích dữ liệu cũ)
                                        and_(
                                            Foreshadow.title == fs_title,
                                            Foreshadow.plant_chapter_id == chapter_id,
                                            Foreshadow.source_type == "analysis"
                                        )
                                    )
                                )
                            )
                        )
                        existing_fs = existing_check.scalar_one_or_none()
                        
                        if existing_fs:
                            # Cập nhật phục bút đã tồn tại, tránh tạo trùng
                            existing_fs.title = fs_title
                            existing_fs.content = fs_content
                            existing_fs.strength = fs_data.get("strength", existing_fs.strength)
                            existing_fs.subtlety = fs_data.get("subtlety", existing_fs.subtlety)
                            existing_fs.hint_text = fs_data.get("keyword", existing_fs.hint_text)
                            existing_fs.category = fs_data.get("category", existing_fs.category)
                            existing_fs.is_long_term = fs_data.get("is_long_term", existing_fs.is_long_term)
                            existing_fs.related_characters = fs_data.get("related_characters", existing_fs.related_characters)
                            if fs_data.get("estimated_resolve_chapter"):
                                existing_fs.target_resolve_chapter_number = fs_data.get("estimated_resolve_chapter")
                            # Cập nhật thànhsource_memory_id
                            existing_fs.source_memory_id = source_memory_id
                            await db.flush()
                            stats["updated_ids"].append(existing_fs.id)
                            logger.info(f"📝 Cập nhật phục bút đã tồn tại (tránh trùng): {fs_title} (ID: {existing_fs.id})")
                        else:
                            # Tạo phục bút mới
                            # Kiểm tra giới hạn số lượng phục bút mới mỗi chương
                            if new_foreshadow_count >= MAX_NEW_FORESHADOWS_PER_CHAPTER:
                                logger.info(f"🚫 Đã đạt giới hạn phục bút mới mỗi chương({MAX_NEW_FORESHADOWS_PER_CHAPTER}), bỏ qua: {fs_title}")
                                continue
                            
                            # Không còn cho estimated_resolve_chapter đặt giá trị mặc định, tránh báo nhầm"quá hạn"
                            estimated_resolve = fs_data.get("estimated_resolve_chapter")
                            if estimated_resolve is None:
                                logger.info(f"ℹ️ AIchưa điềnestimated_resolve_chapter, không đặt giá trị mặc định, đánh dấu là không có kế hoạch thu hồi rõ ràng")
                            
                            new_foreshadow = Foreshadow(
                                id=str(uuid.uuid4()),
                                project_id=project_id,
                                title=fs_title,
                                content=fs_content,
                                hint_text=fs_data.get("keyword"),
                                source_type="analysis",
                                source_memory_id=source_memory_id,  # Dùng định danh duy nhất ổn định
                                plant_chapter_id=chapter_id,
                                plant_chapter_number=chapter_number,
                                planted_at=datetime.now(),
                                target_resolve_chapter_number=estimated_resolve,
                                status="planted",
                                is_long_term=fs_data.get("is_long_term", False),
                                importance=min(fs_data.get("strength", 5) / 10.0, 1.0),
                                strength=fs_data.get("strength", 5),
                                subtlety=fs_data.get("subtlety", 5),
                                category=fs_data.get("category"),
                                related_characters=fs_data.get("related_characters"),
                                auto_remind=True,
                                remind_before_chapters=5,
                                include_in_context=True
                            )
                            
                            db.add(new_foreshadow)
                            await db.flush()
                            
                            new_foreshadow_count += 1
                            stats["planted_count"] += 1
                            stats["created_count"] += 1
                            stats["created_ids"].append(new_foreshadow.id)
                            logger.info(f"✅ Tự động tạo phục bút: {fs_title} (ID: {new_foreshadow.id}) [{new_foreshadow_count}/{MAX_NEW_FORESHADOWS_PER_CHAPTER}]")
                    
                except Exception as item_error:
                    error_msg = f"Xử lý phục bút bị lỗi: {str(item_error)}"
                    stats["errors"].append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            await db.commit()
            
            logger.info(f"📊 Tự động cập nhật phục bút hoàn tất: gieo{stats['planted_count']}, thu hồi{stats['resolved_count']}, Tạo{stats['created_count']}")
            return stats
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Tự động cập nhật phục bút thất bại: {str(e)}")
            raise
    
    async def auto_plant_pending_foreshadows(
        self,
        db: AsyncSession,
        project_id: str,
        chapter_id: str,
        chapter_number: int,
        chapter_content: str
    ) -> Dict[str, Any]:
        """
        Tự động đánh dấu các phục bút dự kiến gieo trong chương này là đã gieo
        
        Kiểm tra các phục bút có trạng thái pending và plant_chapter_number == chapter_number,
        Nếu nội dung chương chứa từ khóa liên quan, thì tự động đánh dấu là planted
        
        Args:
            db: cơ sở dữ liệuphiên
            project_id: dự ánID
            chapter_id: chươngID
            chapter_number: số chương
            chapter_content: Nội dung chương
        
        Returns:
            Cập nhật thống kê
        """
        try:
            stats = {
                "checked_count": 0,
                "planted_count": 0,
                "planted_ids": []
            }
            
            # Lấy các phục bút dự kiến gieo trong chương này
            pending_foreshadows = await self.get_foreshadows_to_plant(
                db, project_id, chapter_number
            )
            
            stats["checked_count"] = len(pending_foreshadows)
            
            for fs in pending_foreshadows:
                # Người dùng đã chỉ định rõ các phục bút gieo trong chương này, tự động đánh dấu là đã gieo
                # Lưu ý: chỉ các phục bút có trạng thái pending và plant_chapter_number == chapter_number
                # mới bị get_foreshadows_to_plant tìm ra, nên ở đây đánh dấu trực tiếp là được
                should_plant = True
                
                if should_plant:
                    fs.status = "planted"
                    fs.plant_chapter_id = chapter_id
                    fs.planted_at = datetime.now()
                    await db.flush()
                    
                    stats["planted_count"] += 1
                    stats["planted_ids"].append(fs.id)
                    logger.info(f"✅ Tự động đánh dấu phục bút đã gieo: {fs.title} (Chương {chapter_number})")
            
            await db.commit()
            
            if stats["planted_count"] > 0:
                logger.info(f"📊 Tự động gieo phục bút: kiểm tra{stats['checked_count']}, gieo{stats['planted_count']}")
            
            return stats
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Tự động gieo phục bút thất bại: {str(e)}")
            return {"checked_count": 0, "planted_count": 0, "planted_ids": [], "error": str(e)}


    def _match_foreshadow_by_content(
        self,
        resolved_fs_data: Dict[str, Any],
        planted_foreshadows: List[Dict[str, Any]],
        min_similarity: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """
        Khớp phục bút qua độ tương đồng nội dung (cơ chế dự phòng)
        
        Chiến lược khớp (theo mức ưu tiên):
        1. Tiêu đề khớp hoàn toàn (thức cao nhất)
        2. Tiêu đề khớp một phần (quan hệ bao hàm)
        3. Từ khóa tiêu đề khớp (loại bỏ"thu hồi"và các hậu tố khác)
        4. khớp từ khóa
        5. khớp từ khóa nội dung
        6. khớp vai trò liên quan + khớp phân loại
        
        Args:
            resolved_fs_data: Dữ liệu phục bút thu hồi trong kết quả phân tích
            planted_foreshadows: Danh sách phục bút đã gieo
            min_similarity: Ngưỡng độ tương đồng tối thiểu
        
        Returns:
            Đối tượng phục bút khớp nhất hoặcNone
        """
        if not planted_foreshadows:
            return None
        
        resolved_title = resolved_fs_data.get("title", "").strip()
        resolved_content = resolved_fs_data.get("content", "").strip()
        resolved_keyword = resolved_fs_data.get("keyword", "").strip()
        resolved_category = resolved_fs_data.get("category")
        resolved_characters = set(resolved_fs_data.get("related_characters", []))
        reference_chapter = resolved_fs_data.get("reference_chapter")
        
        # Xử lý hậu tố tiêu đề (cơ chế đảm bảo)
        resolved_title_clean = resolved_title
        for suffix in ["回收", "揭示", "解答", "兑现"]:
            if resolved_title.endswith(suffix):
                resolved_title_clean = resolved_title[:-len(suffix)]
                logger.debug(f"🔍 Loại bỏ hậu tố tiêu đề: '{resolved_title}' -> '{resolved_title_clean}'")
                break
        
        best_match = None
        best_score = 0.0
        
        for fs in planted_foreshadows:
            score = 0.0
            fs_title = fs.get("title", "").strip()
            fs_content = fs.get("content", "").strip()
            fs_category = fs.get("category")
            fs_characters = set(fs.get("related_characters", []))
            fs_plant_chapter = fs.get("plant_chapter_number")
            
            # chiến lược1: Khớp tiêu đề
            if resolved_title and fs_title:
                if resolved_title == fs_title:
                    score = 1.0
                    logger.debug(f"🎯 Tiêu đề khớp hoàn toàn: '{resolved_title}' == '{fs_title}'")
                elif resolved_title_clean and resolved_title_clean == fs_title:
                    score = 0.95
                    logger.debug(f"🎯 Khớp tiêu đề đã làm sạch: '{resolved_title_clean}' == '{fs_title}'")
                elif resolved_title in fs_title or fs_title in resolved_title:
                    score = max(score, 0.8)
                    logger.debug(f"🔍 Tiêu đề bao hàm khớp: '{resolved_title}' <-> '{fs_title}'")
                elif resolved_title_clean and (resolved_title_clean in fs_title or fs_title in resolved_title_clean):
                    score = max(score, 0.75)
                    logger.debug(f"🔍 Khớp bao hàm tiêu đề đã làm sạch: '{resolved_title_clean}' <-> '{fs_title}'")
                else:
                    title_overlap = self._calculate_word_overlap(resolved_title, fs_title)
                    score = max(score, title_overlap * 0.7)
                    if title_overlap > 0.3:
                        logger.debug(f"📊 Từ tiêu đề trùng lặp: overlap={title_overlap:.2f}")
            
            # chiến lược2: khớp từ khóa
            if resolved_keyword and fs_content:
                if resolved_keyword in fs_content:
                    score = max(score, 0.75)
            
            # chiến lược3: khớp từ khóa nội dung
            if resolved_content and fs_content:
                content_overlap = self._calculate_word_overlap(resolved_content, fs_content)
                score = max(score, content_overlap * 0.6)
            
            # chiến lược4: Khớp số chương tham chiếu (nếu kết quả phân tích córeference_chapter)
            if reference_chapter and fs_plant_chapter:
                if reference_chapter == fs_plant_chapter:
                    score += 0.15  # cộng điểm
            
            # chiến lược5: khớp phân loại
            if resolved_category and fs_category:
                if resolved_category == fs_category:
                    score += 0.1
            
            # chiến lược6: khớp vai trò liên quan
            if resolved_characters and fs_characters:
                character_overlap = len(resolved_characters & fs_characters) / max(len(resolved_characters | fs_characters), 1)
                score += character_overlap * 0.1
            
            # Cập nhật khớp tốt nhất
            if score > best_score and score >= min_similarity:
                best_score = score
                best_match = fs
        
        if best_match:
            logger.info(f"🎯 Khớp nội dung thành công: '{resolved_title}' -> '{best_match.get('title')}' (độ tương đồng: {best_score:.2f})")
        
        return best_match
    
    def _calculate_word_overlap(self, text1: str, text2: str) -> float:
        """
        Tính độ trùng lặp từ của hai văn bản
        
        Dùng tính toán độ tương đồng n-gram ở cấp độ ký tự
        
        Args:
            text1: văn bản1
            text2: văn bản2
        
        Returns:
            0-1điểm độ tương đồng giữa
        """
        if not text1 or not text2:
            return 0.0
        
        # Dùng2-gramvà3-gram
        def get_ngrams(text: str, n: int) -> set:
            text = text.lower().replace(" ", "").replace("\n", "")
            if len(text) < n:
                return {text}
            return {text[i:i+n] for i in range(len(text) - n + 1)}
        
        # Tính độ tương đồng 2-gram
        ngrams1_2 = get_ngrams(text1, 2)
        ngrams2_2 = get_ngrams(text2, 2)
        overlap_2 = len(ngrams1_2 & ngrams2_2) / max(len(ngrams1_2 | ngrams2_2), 1)
        
        # Tính độ tương đồng 3-gram
        ngrams1_3 = get_ngrams(text1, 3)
        ngrams2_3 = get_ngrams(text2, 3)
        overlap_3 = len(ngrams1_3 & ngrams2_3) / max(len(ngrams1_3 | ngrams2_3), 1)
        
        # Điểm tổng hợp (3-gramtrọng số cao hơn, vì chính xác hơn)
        return overlap_2 * 0.4 + overlap_3 * 0.6


# Tạo thể hiện dịch vụ toàn cục
foreshadow_service = ForeshadowService()