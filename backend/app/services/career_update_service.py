"""Dịch vụ cập nhật nghề nghiệp - tự động cập nhật thông tin nghề nghiệp nhân vật theo phân tích chương"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.character import Character
from app.models.career import Career, CharacterCareer
from app.logger import get_logger

logger = get_logger(__name__)


class CareerUpdateService:
    """Dịch vụ cập nhật nghề nghiệp - tự động cập nhật nghề nghiệp nhân vật theo kết quả phân tích chương"""
    
    @staticmethod
    async def update_careers_from_analysis(
        db: AsyncSession,
        project_id: str,
        character_states: List[Dict[str, Any]],
        chapter_id: str,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Cập nhật nghề nghiệp nhân vật theo kết quả phân tích chương
        
        Args:
            db: session database
            project_id: ID project
            character_states: danh sách thay đổi trạng thái nhân vật (từ PlotAnalysis)
            chapter_id: ID chương
            chapter_number: số thứ tự chương
            
        Returns:
            dict kết quả cập nhật, gồm số lượng cập nhật và nhật ký thay đổi
        """
        if not character_states:
            logger.info("📋 Danh sách trạng thái nhân vật rỗng, bỏ qua cập nhật nghề nghiệp")
            return {"updated_count": 0, "changes": []}
        
        updated_count = 0
        changes_log = []
        
        logger.info(f"🔍 Bắt đầu phân tích thay đổi nghề nghiệp nhân vật của chương {chapter_number}...")
        
        for char_state in character_states:
            char_name = char_state.get('character_name')
            career_changes = char_state.get('career_changes', {})
            
            # Nếu không có thông tin thay đổi nghề nghiệp, bỏ qua
            if not career_changes or not isinstance(career_changes, dict):
                continue
            
            # Kiểm tra có thay đổi nghề nghiệp thực chất không
            main_stage_change = career_changes.get('main_career_stage_change', 0)
            sub_career_changes = career_changes.get('sub_career_changes', [])
            new_careers = career_changes.get('new_careers', [])
            
            if main_stage_change == 0 and not sub_career_changes and not new_careers:
                continue
            
            logger.info(f"  👤 Phát hiện nhân vật [{char_name}] có thay đổi nghề nghiệp")
            
            # 1. Truy vấn nhân vật
            char_result = await db.execute(
                select(Character).where(
                    Character.name == char_name,
                    Character.project_id == project_id
                )
            )
            character = char_result.scalar_one_or_none()
            
            if not character:
                logger.warning(f"  ⚠️ Nhân vật không tồn tại: {char_name}, bỏ qua")
                continue
            
            # 2. Cập nhật giai đoạn nghề nghiệp chính
            if main_stage_change != 0 and character.main_career_id:
                success = await CareerUpdateService._update_main_career_stage(
                    db=db,
                    character=character,
                    stage_change=main_stage_change,
                    chapter_number=chapter_number,
                    career_changes=career_changes,
                    changes_log=changes_log
                )
                if success:
                    updated_count += 1
            
            # 3. Cập nhật nghề nghiệp phụ (nếu có)
            if sub_career_changes and isinstance(sub_career_changes, list):
                for sub_change in sub_career_changes:
                    success = await CareerUpdateService._update_sub_career_stage(
                        db=db,
                        character=character,
                        project_id=project_id,
                        sub_change=sub_change,
                        chapter_number=chapter_number,
                        changes_log=changes_log
                    )
                    if success:
                        updated_count += 1
            
            # 4. Thêm nghề nghiệp mới (nếu có)
            if new_careers and isinstance(new_careers, list):
                for new_career_name in new_careers:
                    success = await CareerUpdateService._add_new_career(
                        db=db,
                        character=character,
                        project_id=project_id,
                        career_name=new_career_name,
                        chapter_number=chapter_number,
                        changes_log=changes_log
                    )
                    if success:
                        updated_count += 1
        
        # Commit mọi thay đổi
        if updated_count > 0:
            await db.commit()
            logger.info(f"✅ Cập nhật nghề nghiệp hoàn tất: đã cập nhật thông tin nghề nghiệp của {updated_count} nhân vật")
        else:
            logger.info("📋 Chương này không có thay đổi nghề nghiệp nhân vật")
        
        return {
            "updated_count": updated_count,
            "changes": changes_log
        }
    
    @staticmethod
    async def _update_main_career_stage(
        db: AsyncSession,
        character: Character,
        stage_change: int,
        chapter_number: int,
        career_changes: Dict[str, Any],
        changes_log: List[Dict[str, Any]]
    ) -> bool:
        """Cập nhật giai đoạn nghề nghiệp chính"""
        try:
            # Truy vấn liên kết nghề nghiệp chính
            char_career_result = await db.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == character.id,
                    CharacterCareer.career_type == 'main'
                )
            )
            char_career = char_career_result.scalar_one_or_none()
            
            if not char_career:
                logger.warning(f"  ⚠️ {character.name} không có bản ghi liên kết nghề nghiệp chính")
                return False
            
            # Truy vấn thông tin nghề nghiệp
            career_result = await db.execute(
                select(Career).where(Career.id == char_career.career_id)
            )
            career = career_result.scalar_one_or_none()
            
            if not career:
                logger.warning(f"  ⚠️ ID nghề nghiệp {char_career.career_id} không tồn tại")
                return False
            
            # Tính giai đoạn mới (không vượt quá giai đoạn tối đa, không thấp hơn 1)
            old_stage = char_career.current_stage
            new_stage = min(max(1, old_stage + stage_change), career.max_stage)
            
            # Nếu không có thay đổi thực tế, bỏ qua
            if new_stage == old_stage:
                logger.info(f"  📊 {career.name} của {character.name} đã đạt giới hạn, không thể thay đổi")
                return False
            
            # Cập nhật bảng CharacterCareer
            char_career.current_stage = new_stage
            
            # Đồng bộ cập nhật field dư thừa của bảng Character
            character.main_career_stage = new_stage
            
            # Ghi nhật ký thay đổi
            change_desc = f"{'Thăng cấp' if stage_change > 0 else 'Giáng cấp'}"
            breakthrough_desc = career_changes.get('career_breakthrough', '')
            
            changes_log.append({
                'character': character.name,
                'career': career.name,
                'career_type': 'main',
                'old_stage': old_stage,
                'new_stage': new_stage,
                'change': stage_change,
                'chapter': chapter_number,
                'description': breakthrough_desc
            })
            
            logger.info(
                f"  ✨ Nghề nghiệp chính [{career.name}] của {character.name} "
                f"giai đoạn {old_stage} → giai đoạn {new_stage} ({change_desc})"
            )
            if breakthrough_desc:
                logger.info(f"     Mô tả đột phá: {breakthrough_desc[:50]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Cập nhật nghề nghiệp chính thất bại: {str(e)}")
            return False
    
    @staticmethod
    async def _update_sub_career_stage(
        db: AsyncSession,
        character: Character,
        project_id: str,
        sub_change: Dict[str, Any],
        chapter_number: int,
        changes_log: List[Dict[str, Any]]
    ) -> bool:
        """Cập nhật giai đoạn nghề nghiệp phụ"""
        try:
            career_name = sub_change.get('career_name')
            stage_change = sub_change.get('stage_change', 0)
            
            if not career_name or stage_change == 0:
                return False
            
            # 1. Truy vấn nghề nghiệp (theo tên)
            career_result = await db.execute(
                select(Career).where(
                    Career.name == career_name,
                    Career.project_id == project_id,
                    Career.type == 'sub'
                )
            )
            career = career_result.scalar_one_or_none()
            
            if not career:
                logger.warning(f"  ⚠️ Nghề nghiệp phụ [{career_name}] không tồn tại")
                return False
            
            # 2. Truy vấn liên kết nhân vật-nghề nghiệp
            char_career_result = await db.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == character.id,
                    CharacterCareer.career_id == career.id,
                    CharacterCareer.career_type == 'sub'
                )
            )
            char_career = char_career_result.scalar_one_or_none()
            
            if not char_career:
                logger.warning(f"  ⚠️ {character.name} không có nghề nghiệp phụ [{career_name}]")
                return False
            
            # 3. Tính giai đoạn mới
            old_stage = char_career.current_stage
            new_stage = min(max(1, old_stage + stage_change), career.max_stage)
            
            if new_stage == old_stage:
                return False
            
            # 4. Cập nhật giai đoạn
            char_career.current_stage = new_stage
            
            # 5. Đồng bộ cập nhật field JSON sub_careers của bảng Character
            import json
            sub_careers = json.loads(character.sub_careers) if character.sub_careers else []
            for sc in sub_careers:
                if sc.get('career_id') == career.id:
                    sc['stage'] = new_stage
                    break
            character.sub_careers = json.dumps(sub_careers, ensure_ascii=False)
            
            # 6. Ghi thay đổi
            changes_log.append({
                'character': character.name,
                'career': career.name,
                'career_type': 'sub',
                'old_stage': old_stage,
                'new_stage': new_stage,
                'change': stage_change,
                'chapter': chapter_number
            })
            
            logger.info(
                f"  ✨ Nghề nghiệp phụ [{career.name}] của {character.name} "
                f"giai đoạn {old_stage} → giai đoạn {new_stage}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Cập nhật nghề nghiệp phụ thất bại: {str(e)}")
            return False
    
    @staticmethod
    async def _add_new_career(
        db: AsyncSession,
        character: Character,
        project_id: str,
        career_name: str,
        chapter_number: int,
        changes_log: List[Dict[str, Any]]
    ) -> bool:
        """Thêm nghề nghiệp mới cho nhân vật"""
        try:
            # 1. Truy vấn nghề nghiệp
            career_result = await db.execute(
                select(Career).where(
                    Career.name == career_name,
                    Career.project_id == project_id
                )
            )
            career = career_result.scalar_one_or_none()
            
            if not career:
                logger.warning(f"  ⚠️ Nghề nghiệp [{career_name}] không tồn tại, không thể thêm")
                return False
            
            # 2. Kiểm tra đã tồn tại chưa
            existing_result = await db.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == character.id,
                    CharacterCareer.career_id == career.id
                )
            )
            if existing_result.scalar_one_or_none():
                logger.info(f"  📋 {character.name} đã sở hữu [{career_name}], bỏ qua")
                return False
            
            # 3. Thêm theo loại nghề nghiệp
            if career.type == 'main':
                # Kiểm tra đã có nghề nghiệp chính chưa
                if character.main_career_id:
                    logger.warning(f"  ⚠️ {character.name} đã có nghề nghiệp chính, không thể thêm nghề nghiệp chính mới")
                    return False
                
                # Thêm nghề nghiệp chính
                import uuid
                new_char_career = CharacterCareer(
                    id=str(uuid.uuid4()),
                    character_id=character.id,
                    career_id=career.id,
                    career_type='main',
                    current_stage=1
                )
                db.add(new_char_career)
                
                # Cập nhật bảng Character
                character.main_career_id = career.id
                character.main_career_stage = 1
                
                logger.info(f"  ✨ {character.name} nhận nghề nghiệp chính mới [{career_name}]")
                
            else:  # Nghề nghiệp sub
                # Kiểm tra số lượng nghề nghiệp phụ (tối đa 2)
                sub_count_result = await db.execute(
                    select(CharacterCareer).where(
                        CharacterCareer.character_id == character.id,
                        CharacterCareer.career_type == 'sub'
                    )
                )
                if len(sub_count_result.scalars().all()) >= 2:
                    logger.warning(f"  ⚠️ Nghề nghiệp phụ của {character.name} đã đạt giới hạn (2)")
                    return False
                
                # Thêm nghề nghiệp phụ
                import uuid
                new_char_career = CharacterCareer(
                    id=str(uuid.uuid4()),
                    character_id=character.id,
                    career_id=career.id,
                    career_type='sub',
                    current_stage=1
                )
                db.add(new_char_career)
                
                # Cập nhật JSON sub_careers của bảng Character
                import json
                sub_careers = json.loads(character.sub_careers) if character.sub_careers else []
                sub_careers.append({
                    'career_id': career.id,
                    'stage': 1
                })
                character.sub_careers = json.dumps(sub_careers, ensure_ascii=False)
                
                logger.info(f"  ✨ {character.name} nhận nghề nghiệp phụ mới [{career_name}]")
            
            # Ghi thay đổi
            changes_log.append({
                'character': character.name,
                'career': career.name,
                'career_type': career.type,
                'action': 'new',
                'chapter': chapter_number
            })
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Thêm nghề nghiệp mới thất bại: {str(e)}")
            return False