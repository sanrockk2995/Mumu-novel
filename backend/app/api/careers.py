"""API quản lý nghề nghiệp"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import json
from typing import AsyncGenerator

from app.database import get_db
from app.utils.sse_response import SSEResponse, create_sse_response, WizardProgressTracker, wrap_stream_with_heartbeat, HEARTBEAT
from app.models.career import Career, CharacterCareer
from app.models.character import Character
from app.models.project import Project
from app.schemas.career import (
    CareerCreate,
    CareerUpdate,
    CareerResponse,
    CareerListResponse,
    CareerGenerateRequest,
    CharacterCareerResponse,
    CharacterCareerDetail,
    SetMainCareerRequest,
    AddSubCareerRequest,
    UpdateCareerStageRequest,
    CareerStage
)
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.logger import get_logger, safe_preview
from app.api.settings import get_user_ai_service
from app.api.common import verify_project_access

router = APIRouter(prefix="/careers", tags=["Quản lý nghề nghiệp"])
logger = get_logger(__name__)


@router.get("", response_model=CareerListResponse, summary="Lấy danh sách nghề nghiệp")
async def get_careers(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy tất cả nghề nghiệp của dự án được chỉ định"""
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)

    # Lấy tổng số
    count_result = await db.execute(
        select(func.count(Career.id)).where(Career.project_id == project_id)
    )
    total = count_result.scalar_one()

    # Lấy danh sách nghề nghiệp
    result = await db.execute(
        select(Career)
        .where(Career.project_id == project_id)
        .order_by(Career.type, Career.created_at.desc())
    )
    careers = result.scalars().all()

    # Phân loại trả về
    main_careers = []
    sub_careers = []

    for career in careers:
        # Phân tích các trường JSON
        stages = json.loads(career.stages) if career.stages else []
        attribute_bonuses = json.loads(career.attribute_bonuses) if career.attribute_bonuses else None

        career_dict = {
            "id": career.id,
            "project_id": career.project_id,
            "name": career.name,
            "type": career.type,
            "description": career.description,
            "category": career.category,
            "stages": stages,
            "max_stage": career.max_stage,
            "requirements": career.requirements,
            "special_abilities": career.special_abilities,
            "worldview_rules": career.worldview_rules,
            "attribute_bonuses": attribute_bonuses,
            "source": career.source,
            "created_at": career.created_at,
            "updated_at": career.updated_at
        }

        if career.type == "main":
            main_careers.append(career_dict)
        else:
            sub_careers.append(career_dict)

    return CareerListResponse(
        total=total,
        main_careers=main_careers,
        sub_careers=sub_careers
    )


@router.post("", response_model=CareerResponse, summary="Tạo nghề nghiệp")
async def create_career(
    career_data: CareerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Tạo nghề nghiệp thủ công"""
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(career_data.project_id, user_id, db)

    try:
        # Chuyển stages thành chuỗi JSON
        stages_json = json.dumps([stage.model_dump() for stage in career_data.stages], ensure_ascii=False)
        attribute_bonuses_json = json.dumps(career_data.attribute_bonuses, ensure_ascii=False) if career_data.attribute_bonuses else None

        # Tạo nghề nghiệp
        career = Career(
            project_id=career_data.project_id,
            name=career_data.name,
            type=career_data.type,
            description=career_data.description,
            category=career_data.category,
            stages=stages_json,
            max_stage=career_data.max_stage,
            requirements=career_data.requirements,
            special_abilities=career_data.special_abilities,
            worldview_rules=career_data.worldview_rules,
            attribute_bonuses=attribute_bonuses_json,
            source=career_data.source
        )
        db.add(career)
        await db.commit()
        await db.refresh(career)

        logger.info(f"✅ Tạo nghề nghiệp thành công: {career.name} (ID: {career.id}, loại: {career.type})")

        return CareerResponse(
            id=career.id,
            project_id=career.project_id,
            name=career.name,
            type=career.type,
            description=career.description,
            category=career.category,
            stages=career_data.stages,
            max_stage=career.max_stage,
            requirements=career.requirements,
            special_abilities=career.special_abilities,
            worldview_rules=career.worldview_rules,
            attribute_bonuses=career_data.attribute_bonuses,
            source=career.source,
            created_at=career.created_at,
            updated_at=career.updated_at
        )

    except Exception as e:
        logger.error(f"Tạo nghề nghiệp thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tạo nghề nghiệp thất bại: {str(e)}")


@router.post("/generate-system", summary="AI tạo nghề nghiệp mới (tăng dần, streaming)")
async def generate_career_system(
    request_data: CareerGenerateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Dùng AI tạo nghề nghiệp mới (tăng dần, bổ sung dựa trên các nghề nghiệp hiện có, hỗ trợ hiển thị tiến trình streaming SSE)

    Trả về thông tin tiến trình theo thời gian thực qua Server-Sent Events
    """
    async def generate() -> AsyncGenerator[str, None]:
        tracker = WizardProgressTracker("Hệ thống nghề nghiệp")
        try:
            # Kiểm tra quyền người dùng và dự án có tồn tại không
            user_id = getattr(http_request.state, 'user_id', None)
            project_id = request_data.project_id
            main_career_count = request_data.main_career_count
            sub_career_count = request_data.sub_career_count
            user_requirements = request_data.user_requirements
            project = await verify_project_access(project_id, user_id, db)

            yield await tracker.start()

            # Lấy danh sách nghề nghiệp hiện có
            yield await tracker.loading("Đang phân tích các nghề nghiệp hiện có...", 0.3)

            existing_careers_result = await db.execute(
                select(Career).where(Career.project_id == project_id)
            )
            existing_careers = existing_careers_result.scalars().all()

            # Xây dựng tóm tắt nghề nghiệp hiện có
            existing_main_careers = []
            existing_sub_careers = []
            for career in existing_careers:
                career_summary = f"- {career.name} ({career.category or 'Chưa phân loại'}, {career.max_stage} cấp)"
                if career.description:
                    career_summary += f": {career.description[:50]}"

                if career.type == "main":
                    existing_main_careers.append(career_summary)
                else:
                    existing_sub_careers.append(career_summary)

            existing_careers_text = ""
            if existing_main_careers:
                existing_careers_text += f"\nNghề chính hiện có ({len(existing_main_careers)} nghề):\n" + "\n".join(existing_main_careers)
            if existing_sub_careers:
                existing_careers_text += f"\n\nNghề phụ hiện có ({len(existing_sub_careers)} nghề):\n" + "\n".join(existing_sub_careers)

            if not existing_careers_text:
                existing_careers_text = "\nHiện tại chưa có nghề nghiệp nào, đây là lần đầu tạo hệ thống nghề nghiệp."

            # Xây dựng ngữ cảnh dự án
            yield await tracker.loading("Đang phân tích thế giới quan dự án...", 0.6)

            project_context = f"""
Thông tin dự án:
- Tên sách: {project.title}
- Thể loại: {project.genre or 'Chưa đặt'}
- Chủ đề: {project.theme or 'Chưa đặt'}
- Bối cảnh thời gian: {project.world_time_period or 'Chưa đặt'}
- Vị trí địa lý: {project.world_location or 'Chưa đặt'}
- Tông màu không khí: {project.world_atmosphere or 'Chưa đặt'}
- Quy tắc thế giới: {project.world_rules or 'Chưa đặt'}
"""

            sanitized_user_requirements = user_requirements.strip()
            extra_requirement_text = ""
            if sanitized_user_requirements:
                extra_requirement_text = f"""
Yêu cầu thêm của người dùng:
{sanitized_user_requirements}

Yêu cầu thực hiện:
- Ưu tiên đáp ứng hướng nghề nghiệp, phong cách năng lực, điều kiện giới hạn và các điều cần tránh mà người dùng đề ra
- Nếu yêu cầu của người dùng rất giống nghề nghiệp hiện có, hãy giữ cốt lõi nhu cầu nhưng tạo nghề nghiệp mới có định vị khác biệt rõ ràng
- Nếu yêu cầu của người dùng xung đột với thế giới quan dự án, hãy viết lại và bản địa hóa một cách hợp lý mà không vi phạm thế giới quan
"""

            generation_requirements = f"""
Tình hình nghề nghiệp hiện có: {existing_careers_text}

Yêu cầu tạo (tăng dần):
- Số nghề chính tạo mới lần này: {main_career_count} nghề
- Số nghề phụ tạo mới lần này: {sub_career_count} nghề
- ⚠️ Quan trọng: hãy tạo nghề nghiệp mới **không trùng lặp** với các nghề nghiệp hiện có, tạo thành hệ thống bổ sung cho nhau
- Nghề nghiệp mới nên lấp đầy khoảng trống trong hệ thống nghề nghiệp hiện có, làm phong phú tính đa dạng nghề nghiệp
- Nghề chính phải tuân thủ nghiêm ngặt quy tắc thế giới quan, thể hiện hệ thống năng lực cốt lõi
- Nghề phụ có thể tự do linh hoạt hơn, gồm các loại sản xuất, hỗ trợ, đặc thù

{extra_requirement_text}"""

            yield await tracker.preparing("Đang xây dựng prompt AI...")

            # Xây dựng prompt
            prompt = f"""{project_context}

{generation_requirements}

Hãy tạo các nghề nghiệp bổ sung mới cho dự án tiểu thuyết này (tăng dần). Yêu cầu:
1. **Phân tích kỹ các nghề nghiệp hiện có**, tránh tạo nghề nghiệp trùng lặp hoặc tương tự
2. **Lấp đầy khoảng trống của hệ thống nghề nghiệp**, giúp hệ thống nghề nghiệp hoàn thiện và đa dạng hơn
3. Nếu số nghề nghiệp hiện có ít, có thể tạo các nghề nghiệp nền tảng cốt lõi
4. Nếu số nghề nghiệp hiện có nhiều, có thể tạo các nghề nghiệp đặc sắc, chuyên sâu

Trả về định dạng JSON, cấu trúc như sau:

{{
  "main_careers": [
    {{
      "name": "Tên nghề nghiệp",
      "description": "Mô tả nghề nghiệp",
      "category": "Phân loại nghề nghiệp (ví dụ: hệ chiến đấu, hệ pháp thuật, v.v.)",
      "stages": [
        {{"level": 1, "name": "Tên cấp", "description": "Mô tả cấp"}},
        {{"level": 2, "name": "Tên cấp", "description": "Mô tả cấp"}},
        ...
      ],
      "max_stage": 10,
      "requirements": "Yêu cầu nghề nghiệp",
      "special_abilities": "Năng lực đặc thù",
      "worldview_rules": "Liên quan quy tắc thế giới quan",
      "attribute_bonuses": {{"strength": "+10%", "intelligence": "+5%"}}
    }}
  ],
  "sub_careers": [
    {{
      "name": "Tên nghề phụ",
      "description": "Mô tả nghề nghiệp",
      "category": "Hệ sản xuất/Hệ hỗ trợ/Hệ đặc thù",
      "stages": [...],
      "max_stage": 5,
      "requirements": "Yêu cầu nghề nghiệp",
      "special_abilities": "Năng lực đặc thù"
    }}
  ]
}}

Lưu ý:
1. **Tránh trùng lặp**: tên và định vị của nghề nghiệp tạo ra không được trùng với nghề nghiệp hiện có
2. **Tính bổ sung**: nghề nghiệp mới nên bổ sung cho các nghề nghiệp hiện có, làm phong phú hệ thống nghề nghiệp
3. Cấp của nghề chính phải chi tiết, thể hiện lộ trình trưởng thành rõ ràng
4. Tên cấp phải phù hợp đặc sắc thế giới quan
5. Nghề phụ có thể đơn giản hơn, nhưng phải có nét độc đáo
6. Mọi nghề nghiệp đều phải phù hợp thiết lập thế giới quan tổng thể của dự án
7. Nếu có yêu cầu thêm của người dùng, hãy ưu tiên đáp ứng; nếu xung đột với thế giới quan, phải lấy thế giới quan làm chuẩn để viết lại hợp lý
8. Chỉ trả về JSON thuần túy, không thêm bất kỳ chữ giải thích nào
"""

            yield await tracker.generating(0, max(3000, len(prompt) * 8), "Đang gọi AI tạo nghề nghiệp mới...")
            logger.info(f"🎯 Bắt đầu tạo nghề nghiệp mới cho dự án {project_id} (tăng dần, hiện có {len(existing_careers)} nghề nghiệp)")

            try:
                # Dùng tạo streaming thay cho tạo không streaming
                ai_response = ""
                chunk_count = 0
                estimated_total = max(3000, len(prompt) * 8)

                async for chunk in wrap_stream_with_heartbeat(
                    user_ai_service.generate_text_stream(prompt=prompt),
                    heartbeat_interval=15.0
                ):
                    # Sentinel heartbeat: gửi heartbeat giữ kết nối, không trộn vào response AI
                    if chunk is HEARTBEAT:
                        yield await tracker.heartbeat()
                        continue

                    chunk_count += 1
                    ai_response += chunk

                    # Gửi khối nội dung
                    yield await SSEResponse.send_chunk(chunk)

                    # Cập nhật tiến trình mượt mà (tránh quá thường xuyên)
                    if chunk_count % 10 == 0:
                        yield await tracker.generating(len(ai_response), estimated_total)

                    # Heartbeat
                    if chunk_count % 20 == 0:
                        yield await tracker.heartbeat()

            except Exception as ai_error:
                logger.error(f"❌ Lỗi gọi dịch vụ AI: {str(ai_error)}")
                yield await tracker.error(f"Gọi dịch vụ AI thất bại: {str(ai_error)}")
                return

            if not ai_response or not ai_response.strip():
                yield await tracker.error("Dịch vụ AI trả về response rỗng")
                return

            yield await tracker.parsing("Đang phân tích response AI...", 0.5)

            # Làm sạch và phân tích JSON
            try:
                cleaned_response = user_ai_service._clean_json_response(ai_response)
                career_data = loads_json(cleaned_response)
                logger.info(f"✅ Phân tích JSON hệ thống nghề nghiệp thành công")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Phân tích JSON hệ thống nghề nghiệp thất bại: {e}")
                logger.debug(f"   Xem trước response gốc: {safe_preview(ai_response, 200)}")
                yield await tracker.error(f"Nội dung AI trả về không phân tích được thành JSON: {str(e)}")
                return

            yield await tracker.saving("Đang lưu nghề chính vào cơ sở dữ liệu...", 0.3)

            # Lưu nghề chính
            main_careers_created = []
            for idx, career_info in enumerate(career_data.get("main_careers", [])):
                try:
                    stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                    attribute_bonuses = career_info.get("attribute_bonuses")
                    attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None

                    career = Career(
                        project_id=project_id,
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

            yield await tracker.saving("Đang lưu nghề phụ vào cơ sở dữ liệu...", 0.6)

            # Lưu nghề phụ
            sub_careers_created = []
            for idx, career_info in enumerate(career_data.get("sub_careers", [])):
                try:
                    stages_json = json.dumps(career_info.get("stages", []), ensure_ascii=False)
                    attribute_bonuses = career_info.get("attribute_bonuses")
                    attribute_bonuses_json = json.dumps(attribute_bonuses, ensure_ascii=False) if attribute_bonuses else None

                    career = Career(
                        project_id=project_id,
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

            await db.commit()

            total_main = len(existing_main_careers) + len(main_careers_created)
            total_sub = len(existing_sub_careers) + len(sub_careers_created)

            logger.info(f"🎉 Hoàn tất tạo nghề nghiệp mới: thêm {len(main_careers_created)} nghề chính, {len(sub_careers_created)} nghề phụ")
            logger.info(f"   Tổng hệ thống nghề nghiệp: {total_main} nghề chính, {total_sub} nghề phụ")

            yield await tracker.complete(f"Hoàn tất tạo nghề nghiệp mới! ({total_main} nghề chính, {total_sub} nghề phụ)")

            # Gửi dữ liệu kết quả
            yield await tracker.result({
                "main_careers_count": len(main_careers_created),
                "sub_careers_count": len(sub_careers_created),
                "main_careers": main_careers_created,
                "sub_careers": sub_careers_created
            })

            yield await tracker.done()

        except HTTPException as he:
            logger.error(f"Ngoại lệ HTTP: {he.detail}")
            yield await tracker.error(he.detail, he.status_code)
        except Exception as e:
            logger.error(f"Tạo hệ thống nghề nghiệp thất bại: {str(e)}")
            yield await tracker.error(f"Tạo nghề nghiệp mới thất bại: {str(e)}")

    return create_sse_response(generate())


@router.put("/{career_id}", response_model=CareerResponse, summary="Cập nhật nghề nghiệp")
async def update_career(
    career_id: str,
    career_update: CareerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật thông tin nghề nghiệp"""
    result = await db.execute(
        select(Career).where(Career.id == career_id)
    )
    career = result.scalar_one_or_none()

    if not career:
        raise HTTPException(status_code=404, detail="Nghề nghiệp không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(career.project_id, user_id, db)

    # Cập nhật các trường
    update_data = career_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "stages" and value is not None:
            # Chuyển thành chuỗi JSON
            # model_dump() đã chuyển model lồng nhau thành dict, nên các phần tử trong value đã là dict
            stages_list = [
                stage if isinstance(stage, dict) else stage.model_dump()
                for stage in value
            ]
            setattr(career, field, json.dumps(stages_list, ensure_ascii=False))
        elif field == "attribute_bonuses" and value is not None:
            # Chuyển thành chuỗi JSON
            setattr(career, field, json.dumps(value, ensure_ascii=False))
        else:
            setattr(career, field, value)

    await db.commit()
    await db.refresh(career)

    logger.info(f"✅ Cập nhật nghề nghiệp thành công: {career.name} (ID: {career_id})")

    # Phân tích JSON để trả về
    stages = json.loads(career.stages) if career.stages else []
    attribute_bonuses = json.loads(career.attribute_bonuses) if career.attribute_bonuses else None

    return CareerResponse(
        id=career.id,
        project_id=career.project_id,
        name=career.name,
        type=career.type,
        description=career.description,
        category=career.category,
        stages=stages,
        max_stage=career.max_stage,
        requirements=career.requirements,
        special_abilities=career.special_abilities,
        worldview_rules=career.worldview_rules,
        attribute_bonuses=attribute_bonuses,
        source=career.source,
        created_at=career.created_at,
        updated_at=career.updated_at
    )


@router.delete("/{career_id}", summary="Xóa nghề nghiệp")
async def delete_career(
    career_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa nghề nghiệp"""
    result = await db.execute(
        select(Career).where(Career.id == career_id)
    )
    career = result.scalar_one_or_none()

    if not career:
        raise HTTPException(status_code=404, detail="Nghề nghiệp không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(career.project_id, user_id, db)

    # Kiểm tra có nhân vật nào đang dùng nghề nghiệp này không
    char_career_result = await db.execute(
        select(func.count(CharacterCareer.id)).where(CharacterCareer.career_id == career_id)
    )
    usage_count = char_career_result.scalar_one()

    if usage_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Nghề nghiệp này đang được {usage_count} nhân vật sử dụng, không thể xóa. Hãy gỡ liên kết nghề nghiệp của nhân vật trước."
        )

    await db.delete(career)
    await db.commit()

    logger.info(f"✅ Xóa nghề nghiệp thành công: {career.name} (ID: {career_id})")

    return {"message": "Xóa nghề nghiệp thành công"}


@router.get("/{career_id}", response_model=CareerResponse, summary="Lấy chi tiết nghề nghiệp")
async def get_career(
    career_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết nghề nghiệp theo ID"""
    result = await db.execute(
        select(Career).where(Career.id == career_id)
    )
    career = result.scalar_one_or_none()

    if not career:
        raise HTTPException(status_code=404, detail="Nghề nghiệp không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(career.project_id, user_id, db)

    # Phân tích các trường JSON
    stages = json.loads(career.stages) if career.stages else []
    attribute_bonuses = json.loads(career.attribute_bonuses) if career.attribute_bonuses else None

    return CareerResponse(
        id=career.id,
        project_id=career.project_id,
        name=career.name,
        type=career.type,
        description=career.description,
        category=career.category,
        stages=stages,
        max_stage=career.max_stage,
        requirements=career.requirements,
        special_abilities=career.special_abilities,
        worldview_rules=career.worldview_rules,
        attribute_bonuses=attribute_bonuses,
        source=career.source,
        created_at=career.created_at,
        updated_at=career.updated_at
    )


# ===== API liên kết nghề nghiệp nhân vật =====

@router.get("/character/{character_id}/careers", response_model=CharacterCareerResponse, summary="Lấy thông tin nghề nghiệp của nhân vật")
async def get_character_careers(
    character_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy tất cả thông tin nghề nghiệp của nhân vật (nghề chính và nghề phụ)"""
    # Kiểm tra nhân vật tồn tại
    char_result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = char_result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Lấy tất cả liên kết nghề nghiệp của nhân vật
    result = await db.execute(
        select(CharacterCareer, Career)
        .join(Career, CharacterCareer.career_id == Career.id)
        .where(CharacterCareer.character_id == character_id)
        .order_by(CharacterCareer.career_type.desc())  # main xếp trước
    )
    career_relations = result.all()

    main_career = None
    sub_careers = []

    for char_career, career in career_relations:
        # Phân tích thông tin cấp của nghề nghiệp
        stages = json.loads(career.stages) if career.stages else []

        # Tìm thông tin cấp hiện tại
        stage_name = "Cấp không xác định"
        stage_description = None
        for stage in stages:
            if stage.get("level") == char_career.current_stage:
                stage_name = stage.get("name", f"Cấp {char_career.current_stage}")
                stage_description = stage.get("description")
                break

        career_detail = CharacterCareerDetail(
            id=char_career.id,
            character_id=char_career.character_id,
            career_id=char_career.career_id,
            career_name=career.name,
            career_type=char_career.career_type,
            current_stage=char_career.current_stage,
            stage_name=stage_name,
            stage_description=stage_description,
            stage_progress=char_career.stage_progress,
            max_stage=career.max_stage,
            started_at=char_career.started_at,
            reached_current_stage_at=char_career.reached_current_stage_at,
            notes=char_career.notes,
            created_at=char_career.created_at,
            updated_at=char_career.updated_at
        )

        if char_career.career_type == "main":
            main_career = career_detail
        else:
            sub_careers.append(career_detail)

    return CharacterCareerResponse(
        main_career=main_career,
        sub_careers=sub_careers
    )


@router.post("/character/{character_id}/careers/main", summary="Đặt nghề chính cho nhân vật")
async def set_main_career(
    character_id: str,
    career_request: SetMainCareerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Đặt hoặc đổi nghề chính của nhân vật"""
    # Kiểm tra nhân vật tồn tại
    char_result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = char_result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Kiểm tra nghề nghiệp tồn tại và là loại nghề chính
    career_result = await db.execute(
        select(Career).where(
            Career.id == career_request.career_id,
            Career.project_id == character.project_id
        )
    )
    career = career_result.scalar_one_or_none()

    if not career:
        raise HTTPException(status_code=404, detail="Nghề nghiệp không tồn tại")

    if career.type != "main":
        raise HTTPException(status_code=400, detail="Nghề nghiệp này không phải loại nghề chính, không thể đặt làm nghề chính")

    # Kiểm tra tính hợp lệ của cấp
    if career_request.current_stage > career.max_stage:
        raise HTTPException(
            status_code=400,
            detail=f"Cấp vượt quá phạm vi, cấp tối đa của nghề nghiệp này là {career.max_stage}"
        )

    # Kiểm tra đã có nghề chính chưa
    existing_main = await db.execute(
        select(CharacterCareer).where(
            CharacterCareer.character_id == character_id,
            CharacterCareer.career_type == "main"
        )
    )
    current_main = existing_main.scalar_one_or_none()

    if current_main:
        # Xóa nghề chính cũ
        await db.delete(current_main)
        logger.info(f"  Gỡ liên kết nghề chính cũ: {current_main.career_id}")

    # Tạo liên kết nghề chính mới
    char_career = CharacterCareer(
        character_id=character_id,
        career_id=career_request.career_id,
        career_type="main",
        current_stage=career_request.current_stage,
        stage_progress=0,
        started_at=career_request.started_at,
        reached_current_stage_at=career_request.started_at
    )
    db.add(char_career)
    await db.commit()

    logger.info(f"✅ Đặt nghề chính thành công: nhân vật {character.name} -> {career.name} (cấp {career_request.current_stage})")

    return {"message": "Đặt nghề chính thành công", "career_name": career.name}


@router.post("/character/{character_id}/careers/sub", summary="Thêm nghề phụ cho nhân vật")
async def add_sub_career(
    character_id: str,
    career_request: AddSubCareerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Thêm nghề phụ cho nhân vật"""
    # Kiểm tra nhân vật tồn tại
    char_result = await db.execute(
        select(Character).where(Character.id == character_id)
    )
    character = char_result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail="Nhân vật không tồn tại")

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Kiểm tra nghề nghiệp tồn tại và là loại nghề phụ
    career_result = await db.execute(
        select(Career).where(
            Career.id == career_request.career_id,
            Career.project_id == character.project_id
        )
    )
    career = career_result.scalar_one_or_none()

    if not career:
        raise HTTPException(status_code=404, detail="Nghề nghiệp không tồn tại")

    if career.type != "sub":
        raise HTTPException(status_code=400, detail="Nghề nghiệp này không phải loại nghề phụ, không thể thêm làm nghề phụ")

    # Kiểm tra tính hợp lệ của cấp
    if career_request.current_stage > career.max_stage:
        raise HTTPException(
            status_code=400,
            detail=f"Cấp vượt quá phạm vi, cấp tối đa của nghề nghiệp này là {career.max_stage}"
        )

    # Kiểm tra đã tồn tại chưa
    existing_check = await db.execute(
        select(CharacterCareer).where(
            CharacterCareer.character_id == character_id,
            CharacterCareer.career_id == career_request.career_id
        )
    )
    if existing_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nhân vật này đã có nghề phụ này")

    # Kiểm tra giới hạn số nghề phụ (tùy chọn, ở đây đặt tối đa 5)
    sub_count_result = await db.execute(
        select(func.count(CharacterCareer.id)).where(
            CharacterCareer.character_id == character_id,
            CharacterCareer.career_type == "sub"
        )
    )
    sub_count = sub_count_result.scalar_one()

    if sub_count >= 5:
        raise HTTPException(status_code=400, detail="Số nghề phụ đã đạt giới hạn (tối đa 5 nghề)")

    # Tạo liên kết nghề phụ
    char_career = CharacterCareer(
        character_id=character_id,
        career_id=career_request.career_id,
        career_type="sub",
        current_stage=career_request.current_stage,
        stage_progress=0,
        started_at=career_request.started_at,
        reached_current_stage_at=career_request.started_at
    )
    db.add(char_career)
    await db.commit()

    logger.info(f"✅ Thêm nghề phụ thành công: nhân vật {character.name} -> {career.name} (cấp {career_request.current_stage})")

    return {"message": "Thêm nghề phụ thành công", "career_name": career.name}


@router.put("/character/{character_id}/careers/{career_id}/stage", summary="Cập nhật cấp nghề nghiệp")
async def update_career_stage(
    character_id: str,
    career_id: str,
    stage_request: UpdateCareerStageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Cập nhật cấp của nhân vật trong một nghề nghiệp"""
    # Kiểm tra liên kết nghề nghiệp nhân vật tồn tại
    result = await db.execute(
        select(CharacterCareer, Career, Character)
        .join(Career, CharacterCareer.career_id == Career.id)
        .join(Character, CharacterCareer.character_id == Character.id)
        .where(
            CharacterCareer.character_id == character_id,
            CharacterCareer.career_id == career_id
        )
    )
    relation_data = result.one_or_none()

    if not relation_data:
        raise HTTPException(status_code=404, detail="Liên kết nghề nghiệp nhân vật không tồn tại")

    char_career, career, character = relation_data

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Kiểm tra tính hợp lệ của cấp mới
    if stage_request.current_stage > career.max_stage:
        raise HTTPException(
            status_code=400,
            detail=f"Cấp vượt quá phạm vi, cấp tối đa của nghề nghiệp này là {career.max_stage}"
        )

    # Kiểm tra quy tắc tăng cấp (không được lùi, trừ khi hạ cấp)
    if stage_request.current_stage < char_career.current_stage:
        logger.warning(f"⚠️ Cấp nghề {career.name} của nhân vật {character.name} bị hạ: {char_career.current_stage} -> {stage_request.current_stage}")

    # Cập nhật thông tin cấp
    char_career.current_stage = stage_request.current_stage
    char_career.stage_progress = stage_request.stage_progress
    if stage_request.reached_current_stage_at:
        char_career.reached_current_stage_at = stage_request.reached_current_stage_at
    if stage_request.notes is not None:
        char_career.notes = stage_request.notes

    await db.commit()

    logger.info(f"✅ Cập nhật cấp nghề nghiệp thành công: {character.name} - {career.name} -> cấp {stage_request.current_stage}")

    return {
        "message": "Cập nhật cấp nghề nghiệp thành công",
        "career_name": career.name,
        "new_stage": stage_request.current_stage
    }


@router.delete("/character/{character_id}/careers/{career_id}", summary="Xóa nghề phụ của nhân vật")
async def remove_sub_career(
    character_id: str,
    career_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa nghề phụ của nhân vật"""
    # Kiểm tra liên kết nghề nghiệp nhân vật tồn tại
    result = await db.execute(
        select(CharacterCareer, Character)
        .join(Character, CharacterCareer.character_id == Character.id)
        .where(
            CharacterCareer.character_id == character_id,
            CharacterCareer.career_id == career_id
        )
    )
    relation_data = result.one_or_none()

    if not relation_data:
        raise HTTPException(status_code=404, detail="Liên kết nghề nghiệp nhân vật không tồn tại")

    char_career, character = relation_data

    # Kiểm tra quyền người dùng
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(character.project_id, user_id, db)

    # Không cho phép xóa nghề chính
    if char_career.career_type == "main":
        raise HTTPException(status_code=400, detail="Không thể xóa nghề chính, chỉ có thể đổi")

    await db.delete(char_career)
    await db.commit()

    logger.info(f"✅ Xóa nghề phụ thành công: nhân vật {character.name} gỡ nghề {career_id}")

    return {"message": "Xóa nghề phụ thành công"}
