"""API streaming tạo dự án theo hướng dẫn — dùng SSE để tránh timeout"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, AsyncGenerator
import json
import re

from app.database import get_db
from app.models.project import Project
from app.models.character import Character
from app.models.outline import Outline
from app.models.chapter import Chapter
from app.models.career import Career, CharacterCareer
from app.models.relationship import CharacterRelationship, Organization, OrganizationMember, RelationshipType
from app.models.writing_style import WritingStyle
from app.models.project_default_style import ProjectDefaultStyle
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.services.prompt_service import prompt_service, PromptService
from app.services.plot_expansion_service import PlotExpansionService
from app.logger import get_logger, safe_preview
from app.utils.sse_response import SSEResponse, create_sse_response, WizardProgressTracker
from app.api.settings import get_user_ai_service

router = APIRouter(prefix="/wizard-stream", tags=["Hướng dẫn tạo dự án (streaming)"])
logger = get_logger(__name__)


async def get_owned_project(db: AsyncSession, project_id: str, user_id: str | None) -> Project | None:
    if not project_id or not user_id:
        return None
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def world_building_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo streaming xây dựng thế giới — hỗ trợ tăng cường bằng công cụ MCP"""
    # Đánh dấu session cơ sở dữ liệu đã được commit hay chưa
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Thế giới quan")

    try:
        # Gửi thông điệp bắt đầu
        yield await tracker.start()

        # Trích xuất tham số
        title = data.get("title")
        description = data.get("description")
        theme = data.get("theme")
        genre = data.get("genre")
        narrative_perspective = data.get("narrative_perspective")
        target_words = data.get("target_words")
        chapter_count = data.get("chapter_count")
        character_count = data.get("character_count")
        outline_mode = data.get("outline_mode", "one-to-many")  # Chế độ dàn ý, mặc định một-nhiều
        provider = data.get("provider")
        model = data.get("model")
        enable_mcp = data.get("enable_mcp", True)  # Mặc định bật MCP
        user_id = data.get("user_id")  # Tiêm từ middleware

        if not title or not description or not theme or not genre:
            yield await tracker.error("title, description, theme và genre là các tham số bắt buộc", 400)
            return

        # Lấy prompt cơ bản (hỗ trợ tùy chỉnh)
        yield await tracker.preparing("Đang chuẩn bị prompt AI...")
        template = await PromptService.get_template("WORLD_BUILDING", user_id, db)
        base_prompt = PromptService.format_prompt(
            template,
            title=title,
            theme=theme,
            genre=genre or "Thể loại chung",
            description=description or "Chưa có giới thiệu"
        )

        # Thiết lập thông tin người dùng để bật MCP
        if user_id:
            user_ai_service.user_id = user_id
            user_ai_service.db_session = db

        # ===== Tạo streaming thế giới quan (có cơ chế thử lại) =====
        MAX_WORLD_RETRIES = 3  # Tối đa thử lại 3 lần
        world_retry_count = 0
        world_generation_success = False
        world_data = {}
        estimated_total = 1000

        while world_retry_count < MAX_WORLD_RETRIES and not world_generation_success:
            try:
                # Khi thử lại thì đặt lại tiến trình tạo
                if world_retry_count > 0:
                    tracker.reset_generating_progress()

                yield await tracker.generating(
                    current_chars=0,
                    estimated_total=estimated_total,
                    retry_count=world_retry_count,
                    max_retries=MAX_WORLD_RETRIES
                )

                # Tạo streaming thế giới quan
                accumulated_text = ""
                chunk_count = 0

                async for chunk in user_ai_service.generate_text_stream(
                    prompt=base_prompt,
                    provider=provider,
                    model=model,
                    tool_choice="required",
                ):
                    chunk_count += 1
                    accumulated_text += chunk

                    # Gửi khối nội dung
                    yield await tracker.generating_chunk(chunk)

                    # Cập nhật tiến trình định kỳ
                    current_len = len(accumulated_text)
                    if chunk_count % 10 == 0:
                        yield await tracker.generating(
                            current_chars=current_len,
                            estimated_total=estimated_total,
                            retry_count=world_retry_count,
                            max_retries=MAX_WORLD_RETRIES
                        )

                    # Mỗi 20 khối gửi một heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()

                # Kiểm tra có trả về response rỗng không
                if not accumulated_text or not accumulated_text.strip():
                    logger.warning(f"⚠️ AI trả về thế giới quan rỗng (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES})")
                    world_retry_count += 1
                    if world_retry_count < MAX_WORLD_RETRIES:
                        yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "AI trả về rỗng")
                        continue
                    else:
                        # Đạt số lần thử tối đa, dùng giá trị mặc định
                        logger.error("❌ Tạo thế giới quan nhiều lần trả về response rỗng")
                        world_data = {
                            "time_period": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "location": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "atmosphere": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "rules": "AI nhiều lần trả về rỗng, hãy thử lại sau"
                        }
                        world_generation_success = True  # Đánh dấu thành công để tiếp tục luồng
                        break

                # Phân tích kết quả - dùng phương thức làm sạch JSON thống nhất
                yield await tracker.parsing("Đang phân tích dữ liệu thế giới quan...")

                try:
                    logger.info(f"🔍 Bắt đầu làm sạch JSON, độ dài gốc: {len(accumulated_text)}")
                    logger.debug(f"   Xem trước nội dung gốc: {safe_preview(accumulated_text, 300)}")

                    # ✅ Dùng phương thức làm sạch thống nhất của AIService
                    cleaned_text = user_ai_service._clean_json_response(accumulated_text)
                    logger.info(f"✅ Làm sạch JSON xong, độ dài sau khi làm sạch: {len(cleaned_text)}")
                    logger.debug(f"   Xem trước sau khi làm sạch: {safe_preview(cleaned_text, 300)}")

                    world_data = loads_json(cleaned_text)
                    logger.info(f"✅ Phân tích JSON thế giới quan thành công (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES})")
                    world_generation_success = True  # Phân tích thành công, đánh dấu hoàn tất

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Phân tích JSON xây dựng thế giới thất bại (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES}): {e}")
                    logger.error(f"   Độ dài nội dung gốc: {len(accumulated_text)}")
                    logger.debug(f"   Xem trước nội dung gốc: {safe_preview(accumulated_text, 200)}")
                    world_retry_count += 1
                    if world_retry_count < MAX_WORLD_RETRIES:
                        yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "Phân tích JSON thất bại")
                        continue
                    else:
                        # Đạt số lần thử tối đa, dùng giá trị mặc định
                        world_data = {
                            "time_period": "AI trả về sai định dạng, hãy thử lại",
                            "location": "AI trả về sai định dạng, hãy thử lại",
                            "atmosphere": "AI trả về sai định dạng, hãy thử lại",
                            "rules": "AI trả về sai định dạng, hãy thử lại"
                        }
                        world_generation_success = True  # Đánh dấu thành công để tiếp tục luồng

            except Exception as e:
                logger.error(f"❌ Ngoại lệ khi tạo xây dựng thế giới (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES}): {type(e).__name__}: {e}")
                world_retry_count += 1
                if world_retry_count < MAX_WORLD_RETRIES:
                    yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "Ngoại lệ khi tạo")
                    continue
                else:
                    # Lần thử cuối vẫn thất bại, ném ngoại lệ
                    logger.error(f"   độ dài accumulated_text: {len(accumulated_text) if 'accumulated_text' in locals() else 'N/A'}")
                    raise

        # Lưu vào cơ sở dữ liệu
        yield await tracker.saving("Đang lưu thế giới quan vào cơ sở dữ liệu...")

        # Đảm bảo user_id tồn tại
        if not user_id:
            yield await SSEResponse.send_error("Thiếu ID người dùng, không thể tạo dự án", 401)
            return

        project = Project(
            user_id=user_id,  # Thêm trường user_id
            title=title,
            description=description,
            theme=theme,
            genre=genre,
            world_time_period=world_data.get("time_period"),
            world_location=world_data.get("location"),
            world_atmosphere=world_data.get("atmosphere"),
            world_rules=world_data.get("rules"),
            narrative_perspective=narrative_perspective,
            target_words=target_words,
            chapter_count=chapter_count,
            character_count=character_count,
            outline_mode=outline_mode,  # Thiết lập chế độ dàn ý
            wizard_status="incomplete",
            wizard_step=1,
            status="planning"
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        # Tự động đặt phong cách viết mặc định là phong cách preset toàn cục đầu tiên
        try:
            result = await db.execute(
                select(WritingStyle).where(
                    WritingStyle.user_id.is_(None),
                    WritingStyle.order_index == 1
                ).limit(1)
            )
            first_style = result.scalar_one_or_none()

            if first_style:
                default_style = ProjectDefaultStyle(
                    project_id=project.id,
                    style_id=first_style.id
                )
                db.add(default_style)
                await db.commit()
                logger.info(f"Tự động đặt phong cách mặc định cho dự án {project.id}: {first_style.name}")
            else:
                logger.warning(f"Không tìm thấy phong cách preset toàn cục có order_index=1, dự án {project.id} chưa được đặt phong cách mặc định")
        except Exception as e:
            logger.warning(f"Đặt phong cách viết mặc định thất bại: {e}, không ảnh hưởng việc tạo dự án")

        # Cập nhật trạng thái bước hướng dẫn thành 1 (thế giới quan đã hoàn thành)
        # wizard_step: 0=chưa bắt đầu, 1=thế giới quan đã hoàn thành, 2=hệ thống nghề nghiệp đã hoàn thành, 3=nhân vật đã hoàn thành, 4=dàn ý đã hoàn thành
        project.wizard_step = 1
        await db.commit()

        # ===== Hoàn tất tạo thế giới quan =====
        db_committed = True

        yield await tracker.complete()

        # Gửi kết quả thế giới quan
        yield await tracker.result({
            "project_id": project.id,
            "time_period": world_data.get("time_period"),
            "location": world_data.get("location"),
            "atmosphere": world_data.get("atmosphere"),
            "rules": world_data.get("rules")
        })

        # Gửi tín hiệu hoàn tất thế giới quan
        yield await tracker.done()

        logger.info(f"✅ Hoàn tất tạo thế giới quan, ID dự án: {project.id}")

    except GeneratorExit:
        # Kết nối SSE bị ngắt, rollback giao dịch chưa commit
        logger.warning("Trình tạo xây dựng thế giới bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch xây dựng thế giới (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo streaming xây dựng thế giới thất bại: {str(e)}")
        # Rollback giao dịch khi ngoại lệ
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch xây dựng thế giới (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")


@router.post("/world-building", summary="Tạo streaming xây dựng thế giới")
async def generate_world_building_stream(
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE tạo streaming xây dựng thế giới, tránh timeout
    Frontend dùng EventSource để nhận tiến trình và kết quả theo thời gian thực
    """
    # Tiêm user_id từ middleware vào data
    if hasattr(request.state, 'user_id'):
        data['user_id'] = request.state.user_id

    return create_sse_response(world_building_generator(data, db, user_ai_service))


async def career_system_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo streaming hệ thống nghề nghiệp - API độc lập"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Hệ thống nghề nghiệp")

    try:
        yield await tracker.start()

        # Trích xuất tham số
        project_id = data.get("project_id")
        provider = data.get("provider")
        model = data.get("model")
        user_id = data.get("user_id")

        if not project_id:
            yield await tracker.error("project_id là tham số bắt buộc", 400)
            return

        # Lấy thông tin dự án
        yield await tracker.loading("Đang tải thông tin dự án...")
        project = await get_owned_project(db, project_id, user_id)
        if not project:
            yield await tracker.error("Dự án không tồn tại hoặc không có quyền truy cập", 404)
            return

        # Thiết lập thông tin người dùng để bật MCP
        if user_id:
            user_ai_service.user_id = user_id
            user_ai_service.db_session = db

        # Lấy dữ liệu thế giới quan
        world_data = {
            "time_period": project.world_time_period or "Chưa đặt",
            "location": project.world_location or "Chưa đặt",
            "atmosphere": project.world_atmosphere or "Chưa đặt",
            "rules": project.world_rules or "Chưa đặt"
        }

        # Lấy mẫu prompt tạo nghề nghiệp (hỗ trợ người dùng tùy chỉnh)
        yield await tracker.preparing("Đang chuẩn bị prompt AI...")
        template = await PromptService.get_template("CAREER_SYSTEM_GENERATION", user_id, db)
        career_prompt = PromptService.format_prompt(
            template,
            title=project.title,
            genre=project.genre or 'Chưa đặt',
            theme=project.theme or 'Chưa đặt',
            description=project.description or 'Chưa có giới thiệu',
            time_period=world_data.get('time_period', 'Chưa đặt'),
            location=world_data.get('location', 'Chưa đặt'),
            atmosphere=world_data.get('atmosphere', 'Chưa đặt'),
            rules=world_data.get('rules', 'Chưa đặt')
        )

        estimated_total = 5000
        MAX_CAREER_RETRIES = 3  # Tối đa thử lại 3 lần
        career_retry_count = 0
        career_generation_success = False

        while career_retry_count < MAX_CAREER_RETRIES and not career_generation_success:
            try:
                # Khi thử lại thì đặt lại tiến trình tạo
                if career_retry_count > 0:
                    tracker.reset_generating_progress()

                yield await tracker.generating(
                    current_chars=0,
                    estimated_total=estimated_total,
                    retry_count=career_retry_count,
                    max_retries=MAX_CAREER_RETRIES
                )

                # Dùng streaming để tạo hệ thống nghề nghiệp
                career_response = ""
                chunk_count = 0

                async for chunk in user_ai_service.generate_text_stream(
                    prompt=career_prompt,
                    provider=provider,
                    model=model,
                ):
                    chunk_count += 1
                    career_response += chunk

                    # Gửi khối nội dung
                    yield await tracker.generating_chunk(chunk)

                    # Cập nhật tiến trình định kỳ
                    current_len = len(career_response)
                    if chunk_count % 10 == 0:
                        yield await tracker.generating(
                            current_chars=current_len,
                            estimated_total=estimated_total,
                            retry_count=career_retry_count,
                            max_retries=MAX_CAREER_RETRIES
                        )

                    # Mỗi 20 khối gửi một heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()

                if not career_response or not career_response.strip():
                    logger.warning(f"⚠️ AI trả về hệ thống nghề nghiệp rỗng (lần thử {career_retry_count+1}/{MAX_CAREER_RETRIES})")
                    career_retry_count += 1
                    if career_retry_count < MAX_CAREER_RETRIES:
                        yield await tracker.retry(career_retry_count, MAX_CAREER_RETRIES, "AI trả về rỗng")
                        continue
                    else:
                        yield await tracker.error("Tạo hệ thống nghề nghiệp thất bại (AI nhiều lần trả về rỗng)")
                        return

                yield await tracker.parsing("Đang phân tích dữ liệu hệ thống nghề nghiệp...")

                # Làm sạch và phân tích JSON
                try:
                    cleaned_response = user_ai_service._clean_json_response(career_response)
                    career_data = loads_json(cleaned_response)
                    logger.info(f"✅ Phân tích JSON hệ thống nghề nghiệp thành công (lần thử {career_retry_count+1}/{MAX_CAREER_RETRIES})")

                    yield await tracker.saving("Đang lưu dữ liệu nghề nghiệp...")

                    # Lưu nghề chính
                    main_careers_created = []
                    for idx, career_info in enumerate(career_data.get("main_careers", [])):
                        try:
                            stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                            attribute_bonuses = career_info.get("attribute_bonuses")
                            attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None

                            career = Career(
                                project_id=project.id,
                                name=career_info.get("name", f"Nghề chính chưa đặt tên {idx+1}"),
                                type="main",
                                description=career_info.get("description"),
                                category=career_info.get("category"),
                                stages=stages_json,
                                max_stage=career_info.get("max_stage", 10),
                                requirements=career_info.get("requirements"),
                                special_abilities=career_info.get("special_abilities"),
                                worldview_rules=career_info.get("worldview_rules"),
                                attribute_bonuses=attribute_bonuses_json,
                                source="ai"
                            )
                            db.add(career)
                            await db.flush()
                            main_careers_created.append(career.name)
                            logger.info(f"  ✅ Tạo nghề chính: {career.name}")
                        except Exception as e:
                            logger.error(f"  ❌ Tạo nghề chính thất bại: {str(e)}")
                            continue

                    # Lưu nghề phụ
                    sub_careers_created = []
                    for idx, career_info in enumerate(career_data.get("sub_careers", [])):
                        try:
                            stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                            attribute_bonuses = career_info.get("attribute_bonuses")
                            attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None

                            career = Career(
                                project_id=project.id,
                                name=career_info.get("name", f"Nghề phụ chưa đặt tên {idx+1}"),
                                type="sub",
                                description=career_info.get("description"),
                                category=career_info.get("category"),
                                stages=stages_json,
                                max_stage=career_info.get("max_stage", 5),
                                requirements=career_info.get("requirements"),
                                special_abilities=career_info.get("special_abilities"),
                                worldview_rules=career_info.get("worldview_rules"),
                                attribute_bonuses=attribute_bonuses_json,
                                source="ai"
                            )
                            db.add(career)
                            await db.flush()
                            sub_careers_created.append(career.name)
                            logger.info(f"  ✅ Tạo nghề phụ: {career.name}")
                        except Exception as e:
                            logger.error(f"  ❌ Tạo nghề phụ thất bại: {str(e)}")
                            continue
                    # Cập nhật trạng thái bước hướng dẫn thành 2 (hệ thống nghề nghiệp đã hoàn thành)
                    # wizard_step: 0=chưa bắt đầu, 1=thế giới quan đã hoàn thành, 2=hệ thống nghề nghiệp đã hoàn thành, 3=nhân vật đã hoàn thành, 4=dàn ý đã hoàn thành
                    project.wizard_step = 2
                    
                    await db.commit()
                    db_committed = True
                    
                    # Đánh dấu thành công
                    career_generation_success = True
                    logger.info(f"🎉 Hoàn tất tạo hệ thống nghề nghiệp: {len(main_careers_created)} nghề chính, {len(sub_careers_created)} nghề phụ")
                    
                    yield await tracker.complete()
                    
                    # Gửi kết quả
                    yield await tracker.result({
                        "project_id": project.id,
                        "main_careers_count": len(main_careers_created),
                        "sub_careers_count": len(sub_careers_created),
                        "main_careers": main_careers_created,
                        "sub_careers": sub_careers_created
                    })
                    
                    yield await tracker.done()
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Phân tích JSON hệ thống nghề nghiệp thất bại (lần thử {career_retry_count+1}/{MAX_CAREER_RETRIES}): {e}")
                    career_retry_count += 1
                    if career_retry_count < MAX_CAREER_RETRIES:
                        yield await tracker.retry(career_retry_count, MAX_CAREER_RETRIES, "Phân tích JSON thất bại")
                        continue
                    else:
                        yield await tracker.error("Phân tích hệ thống nghề nghiệp thất bại (đã đạt số lần thử tối đa)")
                        return
                except Exception as e:
                    logger.error(f"❌ Lưu hệ thống nghề nghiệp thất bại (lần thử {career_retry_count+1}/{MAX_CAREER_RETRIES}): {e}")
                    career_retry_count += 1
                    if career_retry_count < MAX_CAREER_RETRIES:
                        yield await tracker.retry(career_retry_count, MAX_CAREER_RETRIES, "Lưu thất bại")
                        continue
                    else:
                        yield await tracker.error("Lưu hệ thống nghề nghiệp thất bại (đã đạt số lần thử tối đa)")
                        return
            
            except Exception as e:
                logger.error(f"❌ Ngoại lệ khi tạo hệ thống nghề nghiệp (lần thử {career_retry_count+1}/{MAX_CAREER_RETRIES}): {e}")
                career_retry_count += 1
                if career_retry_count < MAX_CAREER_RETRIES:
                    yield await tracker.retry(career_retry_count, MAX_CAREER_RETRIES, "Ngoại lệ khi tạo")
                    continue
                else:
                    yield await tracker.error(f"Tạo hệ thống nghề nghiệp thất bại: {str(e)}")
                    return
        
    except GeneratorExit:
        logger.warning("Trình tạo hệ thống nghề nghiệp bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch hệ thống nghề nghiệp (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo streaming hệ thống nghề nghiệp thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch hệ thống nghề nghiệp (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")


@router.post("/career-system", summary="Tạo streaming hệ thống nghề nghiệp")
async def generate_career_system_stream(
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE tạo streaming hệ thống nghề nghiệp, tránh timeout
    Frontend dùng EventSource để nhận tiến trình và kết quả theo thời gian thực
    """
    # Tiêm user_id từ middleware vào data
    if hasattr(request.state, 'user_id'):
        data['user_id'] = request.state.user_id
    
    return create_sse_response(career_system_generator(data, db, user_ai_service))


async def characters_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo streaming tạo hàng loạt nhân vật - bản tối ưu: chia lô + thử lại + tăng cường công cụ MCP"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Nhân vật")
    
    try:
        yield await tracker.start()
        
        project_id = data.get("project_id")
        count = data.get("count", 5)
        world_context = data.get("world_context")
        theme = data.get("theme", "")
        genre = data.get("genre", "")
        requirements = data.get("requirements", "")
        provider = data.get("provider")
        model = data.get("model")
        enable_mcp = data.get("enable_mcp", True) # Mặc định bật MCP
        user_id = data.get("user_id") # Tiêm từ middleware
        
        # Kiểm tra dự án
        yield await tracker.loading("Đang kiểm tra dự án...", 0.3)
        project = await get_owned_project(db, project_id, user_id)
        if not project:
            yield await tracker.error("Dự án không tồn tại hoặc không có quyền truy cập", 404)
            return
        
        project.wizard_step = 2
        
        world_context = world_context or {
            "time_period": project.world_time_period or "Chưa đặt",
            "location": project.world_location or "Chưa đặt",
            "atmosphere": project.world_atmosphere or "Chưa đặt",
            "rules": project.world_rules or "Chưa đặt"
        }
        
        # Thiết lập thông tin người dùng để bật MCP
        if user_id:
            user_ai_service.user_id = user_id
            user_ai_service.db_session = db
        
        # Lấy danh sách nghề nghiệp của dự án để phân nghề cho nhân vật
        yield await tracker.loading("Đang tải hệ thống nghề nghiệp...", 0.8)
        career_result = await db.execute(
            select(Career).where(Career.project_id == project_id).order_by(Career.type, Career.id)
        )
        careers = career_result.scalars().all()
        
        main_careers = [c for c in careers if c.type == "main"]
        sub_careers = [c for c in careers if c.type == "sub"]
        
        # Xây dựng ngữ cảnh nghề nghiệp
        careers_context = ""
        if main_careers or sub_careers:
            careers_context = "\n\n【Hệ thống nghề nghiệp】\n"
            if main_careers:
                careers_context += "Nghề chính:\n"
                for career in main_careers:
                    careers_context += f"- {career.name}: {career.description or 'Chưa có mô tả'}\n"
            if sub_careers:
                careers_context += "\nNghề phụ:\n"
                for career in sub_careers:
                    careers_context += f"- {career.name}: {career.description or 'Chưa có mô tả'}\n"
            
            careers_context += "\nHãy phân nghề cho mỗi nhân vật:\n"
            careers_context += "- Mỗi nhân vật phải có 1 nghề chính (chọn trong các nghề chính trên)\n"
            careers_context += "- Mỗi nhân vật có thể có 0-2 nghề phụ (chọn trong các nghề phụ trên, tùy chọn)\n"
            careers_context += "- Cấp khởi đầu của nghề chính nên là 1-3\n"
            careers_context += "- Cấp khởi đầu của nghề phụ nên là 1-2\n"
            careers_context += "- Hãy đưa trường career_assignment vào JSON trả về:\n"
            careers_context += ' {"main_career": "Tên nghề", "main_stage": 2, "sub_careers": [{"career": "Tên nghề phụ", "stage": 1}]}\n'
            logger.info(f"✅ Đã tải {len(main_careers)} nghề chính và {len(sub_careers)} nghề phụ")
        else:
            logger.warning("⚠️ Dự án chưa có hệ thống nghề nghiệp, bỏ qua phân nghề")
        
        # Chiến lược chia lô tối ưu: mỗi lô tạo 5, cân bằng hiệu suất và tỷ lệ thành công
        BATCH_SIZE = 5 # Mỗi lô tạo 5 nhân vật
        MAX_RETRIES = 3 # Mỗi lô tối đa thử lại 3 lần
        all_characters = []
        total_batches = (count + BATCH_SIZE - 1) // BATCH_SIZE
        
        for batch_idx in range(total_batches):
            # Tính chính xác số lượng lô hiện tại cần tạo
            remaining = count - len(all_characters)
            current_batch_size = min(BATCH_SIZE, remaining)
            
            # Nếu đã đạt số lượng mục tiêu, thoát luôn
            if current_batch_size <= 0:
                logger.info(f"Đã tạo {len(all_characters)} nhân vật, đạt số lượng mục tiêu {count}")
                break
            
            batch_progress = 15 + (batch_idx * 60 // total_batches)
            
            # Logic thử lại
            retry_count = 0
            batch_success = False
            batch_error_message = ""
            
            while retry_count < MAX_RETRIES and not batch_success:
                try:
                    # Khi thử lại thì đặt lại tiến trình tạo
                    if retry_count > 0:
                        tracker.reset_generating_progress()
                    
                    yield await tracker.generating(
                        current_chars=0,
                        estimated_total=BATCH_SIZE * 800,
                        message=f"Đang tạo lô nhân vật {batch_idx+1}/{total_batches} ({current_batch_size} nhân vật)",
                        retry_count=retry_count,
                        max_retries=MAX_RETRIES
                    )
                    
                    # Xây dựng yêu cầu theo lô - kèm thông tin nhân vật đã tạo để giữ tính liền mạch
                    existing_chars_context = ""
                    if all_characters:
                        existing_chars_context = "\n\n【Nhân vật đã tạo】:\n"
                        for char in all_characters:
                            existing_chars_context += f"- {char.get('name')}: {char.get('role_type', 'Không xác định')}, {char.get('personality', 'Chưa có')[:50]}...\n"
                        existing_chars_context += "\nHãy đảm bảo nhân vật mới và nhân vật đã có tạo thành mạng lưới quan hệ và tương tác hợp lý.\n"
                    
                    # Xây dựng yêu cầu chính xác theo lô, nói rõ với AI số lượng cần tạo
                    if batch_idx == 0:
                        if current_batch_size == 1:
                            batch_requirements = f"{requirements}\nHãy tạo 1 nhân vật chính (protagonist)"
                        else:
                            batch_requirements = f"{requirements}\nHãy tạo chính xác {current_batch_size} nhân vật: 1 nhân vật chính (protagonist) và {current_batch_size-1} nhân vật phụ cốt lõi (supporting)"
                    else:
                        batch_requirements = f"{requirements}\nHãy tạo chính xác {current_batch_size} nhân vật{existing_chars_context}"
                        if batch_idx == total_batches - 1:
                            batch_requirements += "\nCó thể gồm tổ chức hoặc phản diện (antagonist)"
                        else:
                            batch_requirements += "\nChủ yếu là nhân vật phụ (supporting) và phản diện (antagonist)"
                    
                    # Lấy mẫu prompt tùy chỉnh
                    template = await PromptService.get_template("CHARACTERS_BATCH_GENERATION", user_id, db)
                    # Xây dựng prompt cơ bản
                    base_prompt = PromptService.format_prompt(
                        template,
                        count=current_batch_size, # Truyền số lượng chính xác
                        time_period=world_context.get("time_period", ""),
                        location=world_context.get("location", ""),
                        atmosphere=world_context.get("atmosphere", ""),
                        rules=world_context.get("rules", ""),
                        theme=theme or project.theme or "",
                        genre=genre or project.genre or "",
                        requirements=batch_requirements + careers_context # Thêm ngữ cảnh nghề nghiệp
                    )
                    
                    prompt = base_prompt
                    
                    # Tạo streaming (kèm đếm số từ)
                    accumulated_text = ""
                    chunk_count = 0
                    
                    estimated_total = BATCH_SIZE * 800
                    
                    async for chunk in user_ai_service.generate_text_stream(
                        prompt=prompt,
                        provider=provider,
                        model=model,
                        tool_choice="required",
                    ):
                        chunk_count += 1
                        accumulated_text += chunk

                        # Gửi khối nội dung
                        yield await tracker.generating_chunk(chunk)

                        # Cập nhật tiến trình định kỳ
                        current_len = len(accumulated_text)
                        if chunk_count % 10 == 0:
                            yield await tracker.generating(
                                current_chars=current_len,
                                estimated_total=estimated_total,
                                message=f"Đang tạo lô nhân vật {batch_idx+1}/{total_batches}",
                                retry_count=retry_count,
                                max_retries=MAX_RETRIES
                            )

                        # Mỗi 20 khối gửi một heartbeat
                        if chunk_count % 20 == 0:
                            yield await tracker.heartbeat()

                    # Phân tích kết quả lô - dùng phương thức làm sạch JSON thống nhất
                    cleaned_text = user_ai_service._clean_json_response(accumulated_text)
                    characters_data = loads_json(cleaned_text)
                    if not isinstance(characters_data, list):
                        characters_data = [characters_data]

                    # Kiểm tra nghiêm ngặt số lượng tạo có khớp chính xác không
                    if len(characters_data) != current_batch_size:
                        error_msg = f"Lô {batch_idx+1} tạo sai số lượng: kỳ vọng {current_batch_size} nhân vật, thực tế {len(characters_data)} nhân vật"
                        logger.error(error_msg)

                        # Nếu còn cơ hội thử lại, tiếp tục thử lại
                        if retry_count < MAX_RETRIES - 1:
                            retry_count += 1
                            yield await tracker.retry(retry_count, MAX_RETRIES, error_msg)
                            continue
                        else:
                            # Lần thử cuối vẫn thất bại, trả lỗi luôn
                            yield await tracker.error(error_msg)
                            return

                    all_characters.extend(characters_data)
                    batch_success = True
                    logger.info(f"Lô {batch_idx+1} thêm thành công {len(characters_data)} nhân vật, hiện tổng {len(all_characters)}/{count}")

                except json.JSONDecodeError as e:
                    logger.error(f"Lô {batch_idx+1} phân tích thất bại (lần thử {retry_count+1}/{MAX_RETRIES}): {e}")
                    batch_error_message = f"Phân tích JSON thất bại: {str(e)}"
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        yield await tracker.retry(retry_count, MAX_RETRIES, "Phân tích JSON thất bại")
                except Exception as e:
                    logger.error(f"Lô {batch_idx+1} ngoại lệ khi tạo (lần thử {retry_count+1}/{MAX_RETRIES}): {e}")
                    batch_error_message = f"Ngoại lệ khi tạo: {str(e)}"
                    retry_count += 1
                    if retry_count < MAX_RETRIES:
                        yield await tracker.retry(retry_count, MAX_RETRIES, "Ngoại lệ khi tạo")

            # Kiểm tra lô có thành công không
            if not batch_success:
                error_msg = f"Lô {batch_idx+1} sau {MAX_RETRIES} lần thử vẫn thất bại"
                if batch_error_message:
                    error_msg += f": {batch_error_message}"
                logger.error(error_msg)
                yield await tracker.error(error_msg)
                return

        # Lưu vào cơ sở dữ liệu - xử lý theo giai đoạn để đảm bảo nhất quán
        yield await tracker.parsing("Đang kiểm tra dữ liệu nhân vật...")

        # Tiền xử lý: xây dựng tập hợp tên mọi thực thể của lô này
        valid_entity_names = set()
        valid_organization_names = set()

        for char_data in all_characters:
            entity_name = char_data.get("name", "")
            if entity_name:
                valid_entity_names.add(entity_name)
                if char_data.get("is_organization", False):
                    valid_organization_names.add(entity_name)

        # Dọn dẹp các tham chiếu ảo giác (hallucination)
        cleaned_count = 0
        for char_data in all_characters:
            # Dọn dẹp tham chiếu không hợp lệ trong mảng quan hệ
            if "relationships_array" in char_data and isinstance(char_data["relationships_array"], list):
                original_rels = char_data["relationships_array"]
                valid_rels = []
                for rel in original_rels:
                    target_name = rel.get("target_character_name", "")
                    if target_name in valid_entity_names:
                        valid_rels.append(rel)
                    else:
                        cleaned_count += 1
                        logger.debug(f"  🧹 Dọn tham chiếu quan hệ không hợp lệ: {char_data.get('name')} -> {target_name}")
                char_data["relationships_array"] = valid_rels

            # Dọn dẹp tham chiếu không hợp lệ trong quan hệ thành viên tổ chức
            if "organization_memberships" in char_data and isinstance(char_data["organization_memberships"], list):
                original_orgs = char_data["organization_memberships"]
                valid_orgs = []
                for org_mem in original_orgs:
                    org_name = org_mem.get("organization_name", "")
                    if org_name in valid_organization_names:
                        valid_orgs.append(org_mem)
                    else:
                        cleaned_count += 1
                        logger.debug(f"  🧹 Dọn tham chiếu tổ chức không hợp lệ: {char_data.get('name')} -> {org_name}")
                char_data["organization_memberships"] = valid_orgs

        if cleaned_count > 0:
            logger.info(f"✨ Đã dọn {cleaned_count} tham chiếu ảo giác của AI")
            yield await tracker.parsing(f"Đã dọn {cleaned_count} tham chiếu không hợp lệ", 0.7)

        yield await tracker.saving("Đang lưu nhân vật vào cơ sở dữ liệu...")

        # Giai đoạn 1: tạo mọi bản ghi Character
        created_characters = []
        character_name_to_obj = {}  # Ánh xạ tên -> đối tượng, dùng để tạo quan hệ sau này

        for char_data in all_characters:
            # Trích mô tả văn bản từ relationships_array để tương thích ngược
            relationships_text = ""
            relationships_array = char_data.get("relationships_array", [])
            if relationships_array and isinstance(relationships_array, list):
                # Chuyển mảng quan hệ thành văn bản dễ đọc
                rel_descriptions = []
                for rel in relationships_array:
                    target = rel.get("target_character_name", "Không xác định")
                    rel_type = rel.get("relationship_type", "quan hệ")
                    desc = rel.get("description", "")
                    rel_descriptions.append(f"{target}({rel_type}): {desc}")
                relationships_text = "; ".join(rel_descriptions)
            # Tương thích định dạng cũ
            elif isinstance(char_data.get("relationships"), dict):
                relationships_text = json.dumps(char_data.get("relationships"), ensure_ascii=False)
            elif isinstance(char_data.get("relationships"), str):
                relationships_text = char_data.get("relationships")

            # Xác định có phải tổ chức không
            is_organization = char_data.get("is_organization", False)

            character = Character(
                project_id=project_id,
                name=char_data.get("name", "Nhân vật chưa đặt tên"),
                age=str(char_data.get("age", "")) if not is_organization else None,
                gender=char_data.get("gender") if not is_organization else None,
                is_organization=is_organization,
                role_type=char_data.get("role_type", "supporting"),
                personality=char_data.get("personality", ""),
                background=char_data.get("background", ""),
                appearance=char_data.get("appearance", ""),
                relationships=relationships_text,
                organization_type=char_data.get("organization_type") if is_organization else None,
                organization_purpose=char_data.get("organization_purpose") if is_organization else None,
                traits=json.dumps(char_data.get("traits", []), ensure_ascii=False) if char_data.get("traits") else None
            )
            db.add(character)
            created_characters.append((character, char_data))

        await db.flush()  # Lấy ID của mọi nhân vật

        # Giai đoạn 2: phân nghề cho nhân vật và tạo liên kết CharacterCareer
        if main_careers or sub_careers:
            yield await tracker.saving("Đang phân nghề cho nhân vật...", 0.3)
            careers_assigned = 0

            # Xây dựng ánh xạ tên nghề -> đối tượng
            career_name_to_obj = {c.name: c for c in careers}

            for character, char_data in created_characters:
                # Bỏ qua tổ chức
                if character.is_organization:
                    continue

                try:
                    career_assignment = char_data.get("career_assignment", {})

                    # Phân nghề chính
                    main_career_name = career_assignment.get("main_career")
                    main_career_stage = career_assignment.get("main_stage", 1)

                    if main_career_name and main_career_name in career_name_to_obj:
                        main_career = career_name_to_obj[main_career_name]

                        # Tạo liên kết CharacterCareer
                        char_career = CharacterCareer(
                            character_id=character.id,
                            career_id=main_career.id,
                            career_type="main",
                            current_stage=min(main_career_stage, main_career.max_stage),
                            stage_progress=0
                        )
                        db.add(char_career)

                        # Cập nhật trường dư thừa của Character
                        character.main_career_id = main_career.id
                        character.main_career_stage = char_career.current_stage

                        careers_assigned += 1
                        logger.info(f"  ✅ Phân nghề chính: {character.name} -> {main_career.name} (cấp {char_career.current_stage})")
                    else:
                        if main_career_name:
                            logger.warning(f"  ⚠️ Nghề chính không tồn tại: {character.name} -> {main_career_name}")

                    # Phân nghề phụ
                    sub_career_assignments = career_assignment.get("sub_careers", [])
                    sub_career_list = []

                    for sub_assign in sub_career_assignments[:2]:  # Tối đa 2 nghề phụ
                        sub_career_name = sub_assign.get("career")
                        sub_career_stage = sub_assign.get("stage", 1)

                        if sub_career_name and sub_career_name in career_name_to_obj:
                            sub_career = career_name_to_obj[sub_career_name]

                            # Tạo liên kết CharacterCareer
                            char_career = CharacterCareer(
                                character_id=character.id,
                                career_id=sub_career.id,
                                career_type="sub",
                                current_stage=min(sub_career_stage, sub_career.max_stage),
                                stage_progress=0
                            )
                            db.add(char_career)

                            # Thêm vào danh sách nghề phụ
                            sub_career_list.append({
                                "career_id": sub_career.id,
                                "stage": char_career.current_stage
                            })

                            careers_assigned += 1
                            logger.info(f"  ✅ Phân nghề phụ: {character.name} -> {sub_career.name} (cấp {char_career.current_stage})")
                        else:
                            if sub_career_name:
                                logger.warning(f"  ⚠️ Nghề phụ không tồn tại: {character.name} -> {sub_career_name}")

                    # Cập nhật trường dư thừa của Character
                    if sub_career_list:
                        character.sub_careers = json.dumps(sub_career_list, ensure_ascii=False)

                except Exception as e:
                    logger.warning(f"  ❌ Phân nghề thất bại: {character.name} - {str(e)}")
                    continue

            await db.flush()
            logger.info(f"💼 Hoàn tất phân nghề: tổng cộng đã phân {careers_assigned} nghề")
            yield await tracker.saving(f"Đã phân {careers_assigned} nghề", 0.4)

        # Làm mới và xây dựng ánh xạ tên
        for character, _ in created_characters:
            await db.refresh(character)
            character_name_to_obj[character.name] = character
            logger.info(f"Hướng dẫn tạo nhân vật: {character.name} (ID: {character.id}, có phải tổ chức: {character.is_organization})")

        # Giai đoạn 3: tạo bản ghi Organization cho nhân vật có is_organization=True
        yield await tracker.saving("Đang tạo bản ghi tổ chức...", 0.5)
        organization_name_to_obj = {}  # Ánh xạ tên tổ chức -> đối tượng Organization

        for character, char_data in created_characters:
            if character.is_organization:
                # Kiểm tra đã tồn tại bản ghi Organization chưa
                org_check = await db.execute(
                    select(Organization).where(Organization.character_id == character.id)
                )
                existing_org = org_check.scalar_one_or_none()

                if not existing_org:
                    # Tạo bản ghi Organization
                    org = Organization(
                        character_id=character.id,
                        project_id=project_id,
                        member_count=0,  # Ban đầu là 0, sẽ cập nhật khi thêm thành viên
                        power_level=char_data.get("power_level", 50),
                        location=char_data.get("location"),
                        motto=char_data.get("motto"),
                        color=char_data.get("color")
                    )
                    db.add(org)
                    logger.info(f"Hướng dẫn tạo bản ghi tổ chức: {character.name}")
                else:
                    org = existing_org

                # Xây dựng ánh xạ tên tổ chức (dù mới tạo hay đã tồn tại)
                organization_name_to_obj[character.name] = org

        await db.flush()  # Đảm bảo bản ghi Organization có ID

        # Làm mới nhân vật để lấy ID
        for character, _ in created_characters:
            await db.refresh(character)

        # Giai đoạn 4: tạo quan hệ giữa các nhân vật
        yield await tracker.saving("Đang tạo quan hệ nhân vật...", 0.7)
        relationships_created = 0

        for character, char_data in created_characters:
            # Bỏ qua xử lý quan hệ nhân vật của thực thể tổ chức (tổ chức liên kết qua quan hệ thành viên)
            if character.is_organization:
                continue

            # Xử lý mảng relationships
            relationships_data = char_data.get("relationships_array", [])
            if not relationships_data and isinstance(char_data.get("relationships"), list):
                relationships_data = char_data.get("relationships")

            if relationships_data and isinstance(relationships_data, list):
                for rel in relationships_data:
                    try:
                        target_name = rel.get("target_character_name")
                        if not target_name:
                            logger.debug(f"  ⚠️  Quan hệ của {character.name} thiếu target_character_name, bỏ qua")
                            continue

                        # Dùng ánh xạ tên để tìm nhanh
                        target_char = character_name_to_obj.get(target_name)

                        if target_char:
                            # Tránh tạo quan hệ trùng lặp
                            existing_rel = await db.execute(
                                select(CharacterRelationship).where(
                                    CharacterRelationship.project_id == project_id,
                                    CharacterRelationship.character_from_id == character.id,
                                    CharacterRelationship.character_to_id == target_char.id
                                )
                            )
                            if existing_rel.scalar_one_or_none():
                                logger.debug(f"  ℹ️  Quan hệ đã tồn tại: {character.name} -> {target_name}")
                                continue

                            relationship = CharacterRelationship(
                                project_id=project_id,
                                character_from_id=character.id,
                                character_to_id=target_char.id,
                                relationship_name=rel.get("relationship_type", "Quan hệ không xác định"),
                                intimacy_level=rel.get("intimacy_level", 50),
                                description=rel.get("description", ""),
                                started_at=rel.get("started_at"),
                                source="ai"
                            )

                            # Khớp loại quan hệ định nghĩa sẵn
                            rel_type_result = await db.execute(
                                select(RelationshipType).where(
                                    RelationshipType.name == rel.get("relationship_type")
                                )
                            )
                            rel_type = rel_type_result.scalar_one_or_none()
                            if rel_type:
                                relationship.relationship_type_id = rel_type.id

                            db.add(relationship)
                            relationships_created += 1
                            logger.info(f"  ✅ Hướng dẫn tạo quan hệ: {character.name} -> {target_name} ({rel.get('relationship_type')})")
                        else:
                            logger.warning(f"  ⚠️  Nhân vật mục tiêu không tồn tại: {character.name} -> {target_name} (có thể là ảo giác của AI)")
                    except Exception as e:
                        logger.warning(f"  ❌ Hướng dẫn tạo quan hệ thất bại: {character.name} - {str(e)}")
                        continue

        # Giai đoạn 5: tạo quan hệ thành viên tổ chức
        yield await tracker.saving("Đang tạo quan hệ thành viên tổ chức...", 0.9)
        members_created = 0

        for character, char_data in created_characters:
            # Bỏ qua chính thực thể tổ chức
            if character.is_organization:
                continue

            # Xử lý quan hệ thành viên tổ chức
            org_memberships = char_data.get("organization_memberships", [])
            if org_memberships and isinstance(org_memberships, list):
                for membership in org_memberships:
                    try:
                        org_name = membership.get("organization_name")
                        if not org_name:
                            logger.debug(f"  ⚠️  Quan hệ thành viên tổ chức của {character.name} thiếu organization_name, bỏ qua")
                            continue

                        # Dùng ánh xạ để tìm tổ chức nhanh
                        org = organization_name_to_obj.get(org_name)

                        if org:
                            # Kiểm tra đã tồn tại quan hệ thành viên chưa
                            existing_member = await db.execute(
                                select(OrganizationMember).where(
                                    OrganizationMember.organization_id == org.id,
                                    OrganizationMember.character_id == character.id
                                )
                            )
                            if existing_member.scalar_one_or_none():
                                logger.debug(f"  ℹ️  Quan hệ thành viên đã tồn tại: {character.name} -> {org_name}")
                                continue

                            # Tạo quan hệ thành viên
                            member = OrganizationMember(
                                organization_id=org.id,
                                character_id=character.id,
                                position=membership.get("position", "Thành viên"),
                                rank=membership.get("rank", 0),
                                loyalty=membership.get("loyalty", 50),
                                joined_at=membership.get("joined_at"),
                                status=membership.get("status", "active"),
                                source="ai"
                            )
                            db.add(member)

                            # Cập nhật số lượng thành viên tổ chức
                            org.member_count += 1

                            members_created += 1
                            logger.info(f"  ✅ Hướng dẫn thêm thành viên: {character.name} -> {org_name} ({membership.get('position')})")
                        else:
                            # Về lý thuyết trường hợp này đã được dọn ở bước tiền xử lý, nhưng giữ log đề phòng
                            logger.debug(f"  ℹ️  Tham chiếu tổ chức đã được dọn: {character.name} -> {org_name}")
                    except Exception as e:
                        logger.warning(f"  ❌ Hướng dẫn thêm thành viên tổ chức thất bại: {character.name} - {str(e)}")
                        continue

        logger.info(f"📊 Thống kê dữ liệu hướng dẫn:")
        logger.info(f"  - Đã tạo nhân vật/tổ chức: {len(created_characters)} mục")
        logger.info(f"  - Đã tạo chi tiết tổ chức: {len(organization_name_to_obj)} mục")
        logger.info(f"  - Đã tạo quan hệ nhân vật: {relationships_created} mục")
        logger.info(f"  - Đã tạo thành viên tổ chức: {members_created} mục")

        # Cập nhật số lượng nhân vật của dự án và trạng thái bước hướng dẫn thành 3 (nhân vật đã hoàn thành)
        # wizard_step: 0=chưa bắt đầu, 1=thế giới quan đã hoàn thành, 2=hệ thống nghề nghiệp đã hoàn thành, 3=nhân vật đã hoàn thành, 4=dàn ý đã hoàn thành
        project.character_count = len(created_characters)
        project.wizard_step = 3
        logger.info(f"✅ Cập nhật số lượng nhân vật của dự án: {project.character_count}")

        await db.commit()
        db_committed = True

        # Trích lại đối tượng character
        created_characters = [char for char, _ in created_characters]

        yield await tracker.complete()

        # Gửi kết quả
        yield await tracker.result({
            "message": f"Tạo thành công {len(created_characters)} nhân vật/tổ chức (hoàn thành trong {total_batches} lô)",
            "count": len(created_characters),
            "batches": total_batches,
            "characters": [
                {
                    "id": char.id,
                    "project_id": char.project_id,
                    "name": char.name,
                    "age": char.age,
                    "gender": char.gender,
                    "is_organization": char.is_organization,
                    "role_type": char.role_type,
                    "personality": char.personality,
                    "background": char.background,
                    "appearance": char.appearance,
                    "relationships": "",
                    "organization_type": char.organization_type,
                    "organization_purpose": char.organization_purpose,
                    "organization_members": "",
                    "traits": char.traits,
                    "created_at": char.created_at.isoformat() if char.created_at else None,
                    "updated_at": char.updated_at.isoformat() if char.updated_at else None
                } for char in created_characters
            ]
        })

        yield await tracker.done()

    except GeneratorExit:
        logger.warning("Trình tạo nhân vật bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo nhân vật (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo nhân vật thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo nhân vật (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")


@router.post("/characters", summary="Tạo streaming hàng loạt nhân vật")
async def generate_characters_stream(
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE tạo streaming hàng loạt nhân vật, tránh timeout
    Hỗ trợ tăng cường bằng công cụ MCP
    """
    # Tiêm user_id từ middleware vào data
    if hasattr(request.state, 'user_id'):
        data['user_id'] = request.state.user_id
    return create_sse_response(characters_generator(data, db, user_ai_service))


async def outline_generator(
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo streaming dàn ý - hướng dẫn chỉ tạo nút dàn ý, không triển khai chương (tránh phải chờ quá lâu)"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Dàn ý")
    
    try:
        yield await tracker.start()
        
        project_id = data.get("project_id")
        # Hướng dẫn cố định tạo 3 nút dàn ý (không triển khai)
        outline_count = data.get("chapter_count", 3)
        narrative_perspective = data.get("narrative_perspective")
        target_words = data.get("target_words", 100000)
        requirements = data.get("requirements", "")
        provider = data.get("provider")
        model = data.get("model")
        enable_mcp = data.get("enable_mcp", True) # Mặc định bật MCP
        user_id = data.get("user_id") # Tiêm từ middleware
        
        # Lấy thông tin dự án
        yield await tracker.loading("Đang tải thông tin dự án...", 0.3)
        project = await get_owned_project(db, project_id, user_id)
        if not project:
            yield await tracker.error("Dự án không tồn tại hoặc không có quyền truy cập", 404)
            return

        # Thiết lập thông tin người dùng để bật MCP, và đảm bảo bước tự bổ sung nhân vật/tổ chức sau này dùng ngữ cảnh dịch vụ AI của request hiện tại
        if user_id:
            user_ai_service.user_id = user_id
            user_ai_service.db_session = db
        
        # Lấy thông tin nhân vật
        yield await tracker.loading("Đang tải thông tin nhân vật...", 0.8)
        result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = result.scalars().all()
        
        characters_info = "\n".join([
            f"- {char.name} ({'Tổ chức' if char.is_organization else 'Nhân vật'}, {char.role_type}): {char.personality[:100] if char.personality else 'Chưa có mô tả'}"
            for char in characters
        ])
        
        # Chuẩn bị prompt
        yield await tracker.preparing(f"Đang chuẩn bị tạo {outline_count} nút dàn ý...")
        
        outline_requirements = f"{requirements}\n\n【Lưu ý quan trọng】Đây là phần mở đầu của tiểu thuyết, hãy tạo {outline_count} nút dàn ý, tập trung vào:\n"
        outline_requirements += "1. Giới thiệu nhân vật chính và thiết lập thế giới quan\n"
        outline_requirements += "2. Xây dựng xung đột chính và móc câu chuyện\n"
        outline_requirements += "3. Triển khai cốt truyện giai đoạn đầu, gieo manh mối ẩn cho diễn biến sau\n"
        outline_requirements += "4. Đừng cố kết thúc câu chuyện, đây chỉ là phần bắt đầu\n"
        outline_requirements += "5. Không dùng dấu ngoặc kép tiếng Trung (\"\"'') trong giá trị chuỗi JSON, hãy dùng 【】 hoặc 《》 để đánh dấu\n"
        
        # Lấy mẫu prompt tùy chỉnh
        template = await PromptService.get_template("OUTLINE_CREATE", user_id, db)
        outline_prompt = PromptService.format_prompt(
            template,
            title=project.title,
            theme=project.theme or "Chưa đặt",
            genre=project.genre or "Chung",
            chapter_count=outline_count,
            narrative_perspective=narrative_perspective,
            target_words=target_words // 10, # Phần mở đầu chiếm khoảng 1/10 tổng số từ
            time_period=project.world_time_period or "Chưa đặt",
            location=project.world_location or "Chưa đặt",
            atmosphere=project.world_atmosphere or "Chưa đặt",
            rules=project.world_rules or "Chưa đặt",
            characters_info=characters_info or "Chưa có thông tin nhân vật",
            mcp_references="",
            requirements=outline_requirements
        )
        
        # Tạo streaming dàn ý
        estimated_total = 1000
        accumulated_text = ""
        chunk_count = 0
        
        yield await tracker.generating(current_chars=0, estimated_total=estimated_total)
        
        async for chunk in user_ai_service.generate_text_stream(
            prompt=outline_prompt,
            provider=provider,
            model=model,
        ):
            chunk_count += 1
            accumulated_text += chunk
            
            # Gửi khối nội dung
            yield await tracker.generating_chunk(chunk)
            
            # Cập nhật tiến trình định kỳ
            current_len = len(accumulated_text)
            if chunk_count % 10 == 0:
                yield await tracker.generating(
                    current_chars=current_len,
                    estimated_total=estimated_total
                )
            
            # Mỗi 20 khối gửi một heartbeat
            if chunk_count % 20 == 0:
                yield await tracker.heartbeat()
        
        # Phân tích kết quả dàn ý - dùng phương thức làm sạch JSON thống nhất
        yield await tracker.parsing("Đang phân tích dữ liệu dàn ý...")
        
        try:
            cleaned_text = user_ai_service._clean_json_response(accumulated_text)
            outline_data = loads_json(cleaned_text)
            if not isinstance(outline_data, list):
                outline_data = [outline_data]
        except json.JSONDecodeError as e:
            logger.error(f"Phân tích JSON dàn ý thất bại: {e}")
            yield await tracker.error("Tạo dàn ý thất bại, hãy thử lại")
            return
        
        # Lưu dàn ý vào cơ sở dữ liệu
        yield await tracker.saving("Đang lưu dàn ý vào cơ sở dữ liệu...")
        created_outlines = []
        for index, outline_item in enumerate(outline_data[:outline_count], 1):
            outline = Outline(
                project_id=project_id,
                title=outline_item.get("title", f"Phần {index}"),
                content=outline_item.get("summary") or outline_item.get("content") or "",
                structure=json.dumps(outline_item, ensure_ascii=False),
                order_index=index
            )
            db.add(outline)
            created_outlines.append(outline)
        
        await db.flush() # Lấy ID dàn ý
        for outline in created_outlines:
            await db.refresh(outline)
        
        logger.info(f"✅ Tạo thành công {len(created_outlines)} nút dàn ý")
        
        # 🎭 Kiểm tra nhân vật: kiểm tra characters trong structure của dàn ý có nhân vật tương ứng không
        yield await tracker.saving("🎭 Đang kiểm tra thông tin nhân vật...", 0.5)
        try:
            from app.services.auto_character_service import get_auto_character_service
            
            auto_char_service = get_auto_character_service(user_ai_service)
            char_check_result = await auto_char_service.check_and_create_missing_characters(
                project_id=project_id,
                outline_data_list=outline_data[:outline_count],
                db=db,
                user_id=user_id,
                enable_mcp=enable_mcp
            )
            if char_check_result["created_count"] > 0:
                created_names = [c.name for c in char_check_result["created_characters"]]
                logger.info(f"🎭 Dàn ý hướng dẫn: tự động tạo {char_check_result['created_count']} nhân vật: {', '.join(created_names)}")
                yield await tracker.saving(
                    f"🎭 Đã tự động tạo {char_check_result['created_count']} nhân vật: {', '.join(created_names)}",
                    0.6
                )
        except Exception as e:
            logger.error(f"⚠️ Kiểm tra nhân vật dàn ý hướng dẫn thất bại (không ảnh hưởng luồng chính): {e}")
        
        # 🏛️ Kiểm tra tổ chức: kiểm tra characters (type=organization) trong structure của dàn ý có tổ chức tương ứng không
        yield await tracker.saving("🏛️ Đang kiểm tra thông tin tổ chức...", 0.55)
        try:
            from app.services.auto_organization_service import get_auto_organization_service
            
            auto_org_service = get_auto_organization_service(user_ai_service)
            org_check_result = await auto_org_service.check_and_create_missing_organizations(
                project_id=project_id,
                outline_data_list=outline_data[:outline_count],
                db=db,
                user_id=user_id,
                enable_mcp=enable_mcp
            )
            if org_check_result["created_count"] > 0:
                created_names = [c.name for c in org_check_result["created_organizations"]]
                logger.info(f"🏛️ Dàn ý hướng dẫn: tự động tạo {org_check_result['created_count']} tổ chức: {', '.join(created_names)}")
                yield await tracker.saving(
                    f"🏛️ Đã tự động tạo {org_check_result['created_count']} tổ chức: {', '.join(created_names)}",
                    0.65
                )
        except Exception as e:
            logger.error(f"⚠️ Kiểm tra tổ chức dàn ý hướng dẫn thất bại (không ảnh hưởng luồng chính): {e}")
        
        # Quyết định có tự động tạo chương không dựa vào chế độ dàn ý của dự án
        created_chapters = []
        if project.outline_mode == 'one-to-one':
            # Chế độ một-một: tự động tạo chương tương ứng cho mỗi dàn ý
            yield await tracker.saving("Chế độ một-một: đang tự động tạo chương...", 0.7)
            
            for outline in created_outlines:
                chapter = Chapter(
                    project_id=project_id,
                    title=outline.title,
                    content="", # Nội dung rỗng, chờ người dùng tạo
                    outline_id=None, # Chế độ một-một không liên kết outline_id
                    chapter_number=outline.order_index, # Dùng chapter_number thay vì order_index
                    status="pending"
                )
                db.add(chapter)
                created_chapters.append(chapter)
            
            await db.flush()
            for chapter in created_chapters:
                await db.refresh(chapter)
            
            logger.info(f"✅ Chế độ một-một: tự động tạo {len(created_chapters)} chương")
            yield await tracker.saving(f"Đã tự động tạo {len(created_chapters)} chương", 0.9)
        else:
            # Chế độ một-nhiều: bỏ qua tự động tạo, người dùng có thể triển khai thủ công
            yield await tracker.saving("Chế độ chi tiết: bỏ qua tự động tạo chương", 0.9)
            logger.info(f"📝 Chế độ chi tiết: bỏ qua tạo chương, người dùng có thể triển khai thủ công trên trang dàn ý")
        
        # Cập nhật thông tin dự án
        # wizard_step: 0=chưa bắt đầu, 1=thế giới quan đã hoàn thành, 2=hệ thống nghề nghiệp đã hoàn thành, 3=nhân vật đã hoàn thành, 4=dàn ý đã hoàn thành
        project.chapter_count = len(created_chapters) # Ghi số chương thực tế đã tạo
        project.narrative_perspective = narrative_perspective
        project.target_words = target_words
        project.status = "writing"
        project.wizard_status = "completed"
        project.wizard_step = 4
        
        await db.commit()
        db_committed = True
        
        logger.info(f"📊 Hoàn tất tạo dàn ý hướng dẫn:")
        logger.info(f" - Đã tạo nút dàn ý: {len(created_outlines)} mục")
        logger.info(f" - Đã tạo chương: {len(created_chapters)} mục")
        logger.info(f" - Chế độ dàn ý: {project.outline_mode}")
        
        # Xây dựng thông điệp kết quả
        if project.outline_mode == 'one-to-one':
            result_message = f"Tạo thành công {len(created_outlines)} nút dàn ý và tự động tạo {len(created_chapters)} chương (chế độ truyền thống)"
            result_note = "Đã tự động tạo chương, có thể tạo nội dung trực tiếp"
        else:
            result_message = f"Tạo thành công {len(created_outlines)} nút dàn ý (chế độ chi tiết, có thể triển khai thủ công trên trang dàn ý)"
            result_note = "Có thể triển khai thành nhiều chương trên trang dàn ý"
        
        yield await tracker.complete()
        
        # Gửi kết quả
        yield await tracker.result({
            "message": result_message,
            "outline_count": len(created_outlines),
            "chapter_count": len(created_chapters),
            "outline_mode": project.outline_mode,
            "outlines": [
                {
                    "id": outline.id,
                    "order_index": outline.order_index,
                    "title": outline.title,
                    "content": outline.content[:100] + "..." if len(outline.content) > 100 else outline.content,
                    "note": result_note
                } for outline in created_outlines
            ],
            "chapters": [
                {
                    "id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "status": chapter.status
                } for chapter in created_chapters
            ] if created_chapters else []
        })

        yield await tracker.done()

    except GeneratorExit:
        logger.warning("Trình tạo dàn ý bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo dàn ý (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo dàn ý thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo dàn ý (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")

@router.post("/outline", summary="Tạo streaming dàn ý đầy đủ")
async def generate_outline_stream(
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE tạo streaming dàn ý đầy đủ, tránh timeout
    """
    # Tiêm user_id từ middleware vào data để outline_generator kiểm tra quyền sở hữu dự án
    if hasattr(request.state, 'user_id'):
        data['user_id'] = request.state.user_id

    return create_sse_response(outline_generator(data, db, user_ai_service))


async def world_building_regenerate_generator(
    project_id: str,
    data: Dict[str, Any],
    db: AsyncSession,
    user_ai_service: AIService
) -> AsyncGenerator[str, None]:
    """Trình tạo streaming tạo lại thế giới quan"""
    db_committed = False
    # Khởi tạo bộ theo dõi tiến trình chuẩn
    tracker = WizardProgressTracker("Thế giới quan")

    try:
        yield await tracker.start("Bắt đầu tạo lại thế giới quan...")

        # Trích xuất tham số
        provider = data.get("provider")
        model = data.get("model")
        enable_mcp = data.get("enable_mcp", True)
        user_id = data.get("user_id")

        # Lấy thông tin dự án
        yield await tracker.loading("Đang tải thông tin dự án...")
        project = await get_owned_project(db, project_id, user_id)
        if not project:
            yield await tracker.error("Dự án không tồn tại hoặc không có quyền truy cập", 404)
            return

        # Lấy prompt cơ bản (hỗ trợ tùy chỉnh)
        yield await tracker.preparing("Đang chuẩn bị prompt AI...")
        template = await PromptService.get_template("WORLD_BUILDING", user_id, db)
        base_prompt = PromptService.format_prompt(
            template,
            title=project.title,
            theme=project.theme or "Chưa đặt",
            genre=project.genre or "Chung",
            description=project.description or "Chưa có giới thiệu"
        )

        # Thiết lập thông tin người dùng để bật MCP
        if user_id:
            user_ai_service.user_id = user_id
            user_ai_service.db_session = db

        # ===== Tạo streaming thế giới quan (có cơ chế thử lại) =====
        MAX_WORLD_RETRIES = 3  # Tối đa thử lại 3 lần
        world_retry_count = 0
        world_generation_success = False
        world_data = {}
        estimated_total = 1000

        while world_retry_count < MAX_WORLD_RETRIES and not world_generation_success:
            try:
                # Khi thử lại thì đặt lại tiến trình tạo
                if world_retry_count > 0:
                    tracker.reset_generating_progress()

                yield await tracker.generating(
                    current_chars=0,
                    estimated_total=estimated_total,
                    message="Tạo lại thế giới quan",
                    retry_count=world_retry_count,
                    max_retries=MAX_WORLD_RETRIES
                )

                # Tạo streaming thế giới quan
                accumulated_text = ""
                chunk_count = 0

                async for chunk in user_ai_service.generate_text_stream(
                    prompt=base_prompt,
                    provider=provider,
                    model=model,
                    tool_choice="required",
                ):
                    chunk_count += 1
                    accumulated_text += chunk

                    yield await tracker.generating_chunk(chunk)

                    # Cập nhật tiến trình định kỳ
                    current_len = len(accumulated_text)
                    if chunk_count % 10 == 0:
                        yield await tracker.generating(
                            current_chars=current_len,
                            estimated_total=estimated_total,
                            message="Tạo lại thế giới quan",
                            retry_count=world_retry_count,
                            max_retries=MAX_WORLD_RETRIES
                        )

                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()

                # Kiểm tra có trả về response rỗng không
                if not accumulated_text or not accumulated_text.strip():
                    logger.warning(f"⚠️ AI trả về thế giới quan rỗng (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES})")
                    world_retry_count += 1
                    if world_retry_count < MAX_WORLD_RETRIES:
                        yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "AI trả về rỗng")
                        continue
                    else:
                        # Đạt số lần thử tối đa, dùng giá trị mặc định
                        logger.error("❌ Tạo lại thế giới quan nhiều lần trả về response rỗng")
                        world_data = {
                            "time_period": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "location": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "atmosphere": "AI nhiều lần trả về rỗng, hãy thử lại sau",
                            "rules": "AI nhiều lần trả về rỗng, hãy thử lại sau"
                        }
                        world_generation_success = True
                        break

                # Phân tích kết quả - dùng phương thức làm sạch JSON thống nhất
                yield await tracker.parsing("Đang phân tích kết quả AI trả về...")

                try:
                    logger.info(f"🔍 Bắt đầu làm sạch JSON, độ dài gốc: {len(accumulated_text)}")
                    cleaned_text = user_ai_service._clean_json_response(accumulated_text)
                    logger.info(f"✅ Làm sạch JSON xong, độ dài sau khi làm sạch: {len(cleaned_text)}")

                    world_data = loads_json(cleaned_text)
                    logger.info(f"✅ Phân tích JSON tạo lại thế giới quan thành công (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES})")
                    world_generation_success = True

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Phân tích JSON xây dựng thế giới thất bại (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES}): {e}")
                    logger.error(f"   Độ dài nội dung gốc: {len(accumulated_text)}")
                    logger.debug(f"   Xem trước nội dung gốc: {safe_preview(accumulated_text, 200)}")
                    world_retry_count += 1
                    if world_retry_count < MAX_WORLD_RETRIES:
                        yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "Phân tích JSON thất bại")
                        continue
                    else:
                        # Đạt số lần thử tối đa, dùng giá trị mặc định
                        world_data = {
                            "time_period": "AI trả về sai định dạng, hãy thử lại",
                            "location": "AI trả về sai định dạng, hãy thử lại",
                            "atmosphere": "AI trả về sai định dạng, hãy thử lại",
                            "rules": "AI trả về sai định dạng, hãy thử lại"
                        }
                        world_generation_success = True

            except Exception as e:
                logger.error(f"❌ Ngoại lệ khi tạo lại thế giới quan (lần thử {world_retry_count+1}/{MAX_WORLD_RETRIES}): {type(e).__name__}: {e}")
                world_retry_count += 1
                if world_retry_count < MAX_WORLD_RETRIES:
                    yield await tracker.retry(world_retry_count, MAX_WORLD_RETRIES, "Ngoại lệ khi tạo")
                    continue
                else:
                    # Lần thử cuối vẫn thất bại, ném ngoại lệ
                    logger.error(f"   độ dài accumulated_text: {len(accumulated_text) if 'accumulated_text' in locals() else 'N/A'}")
                    raise

        # Không lưu vào cơ sở dữ liệu, chỉ trả kết quả tạo cho người dùng xem trước
        yield await tracker.saving("Đã tạo xong, chờ người dùng xác nhận...", 0.5)

        yield await tracker.complete()

        # Gửi kết quả cuối (không có project_id nghĩa là chưa lưu)
        yield await tracker.result({
            "time_period": world_data.get("time_period"),
            "location": world_data.get("location"),
            "atmosphere": world_data.get("atmosphere"),
            "rules": world_data.get("rules")
        })

        yield await tracker.done()

    except GeneratorExit:
        logger.warning("Trình tạo lại thế giới quan bị đóng sớm")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo lại thế giới quan (GeneratorExit)")
    except Exception as e:
        logger.error(f"Tạo lại thế giới quan thất bại: {str(e)}")
        if not db_committed and db.in_transaction():
            await db.rollback()
            logger.info("Đã rollback giao dịch tạo lại thế giới quan (ngoại lệ)")
        yield await tracker.error(f"Tạo thất bại: {str(e)}")


@router.post("/world-building/{project_id}/regenerate", summary="Tạo streaming lại thế giới quan")
async def regenerate_world_building_stream(
    project_id: str,
    request: Request,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng SSE tạo streaming lại thế giới quan, tránh timeout
    Frontend dùng EventSource để nhận tiến trình và kết quả theo thời gian thực
    """
    # Tiêm user_id từ middleware vào data
    if hasattr(request.state, 'user_id'):
        data['user_id'] = request.state.user_id
    return create_sse_response(world_building_regenerate_generator(project_id, data, db, user_ai_service))
