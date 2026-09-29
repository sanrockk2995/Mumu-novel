"""API quản lý mẫu prompt"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, Optional
from datetime import datetime
import json
import hashlib

from app.database import get_db
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    PromptTemplateCategoryResponse,
    PromptTemplateExport,
    PromptTemplateExportItem,
    PromptTemplateImportResult,
    PromptTemplatePreviewRequest
)
from app.services.prompt_service import PromptService
from app.logger import get_logger

logger = get_logger(__name__)

def calculate_content_hash(content: str) -> str:
    """Tính giá trị băm SHA256 của nội dung mẫu"""
    return hashlib.sha256(content.strip().encode('utf-8')).hexdigest()[:16]

router = APIRouter(prefix="/prompt-templates", tags=["Quản lý mẫu prompt"])


@router.get("", response_model=PromptTemplateListResponse)
async def get_all_templates(
    request: Request,
    category: Optional[str] = Query(None, description="Lọc theo phân loại"),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái bật"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả mẫu prompt của người dùng
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    query = select(PromptTemplate).where(PromptTemplate.user_id == user_id)

    if category:
        query = query.where(PromptTemplate.category == category)
    if is_active is not None:
        query = query.where(PromptTemplate.is_active == is_active)

    query = query.order_by(PromptTemplate.category, PromptTemplate.template_key)

    result = await db.execute(query)
    templates = result.scalars().all()

    # Lấy tất cả phân loại
    categories_result = await db.execute(
        select(PromptTemplate.category)
        .where(PromptTemplate.user_id == user_id)
        .distinct()
    )
    categories = [c for c in categories_result.scalars().all() if c]

    return PromptTemplateListResponse(
        templates=templates,
        total=len(templates),
        categories=sorted(categories)
    )


@router.get("/categories", response_model=List[PromptTemplateCategoryResponse])
async def get_templates_by_category(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy mẫu prompt theo phân loại (gộp tùy chỉnh của người dùng và mặc định hệ thống)
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # 1. Truy vấn mẫu tùy chỉnh của người dùng
    result = await db.execute(
        select(PromptTemplate)
        .where(PromptTemplate.user_id == user_id)
        .order_by(PromptTemplate.category, PromptTemplate.template_key)
    )
    user_templates = result.scalars().all()

    # 2. Lấy tất cả mẫu mặc định hệ thống
    system_templates = PromptService.get_all_system_templates()

    # 3. Xây dựng tập hợp khóa của các mẫu tùy chỉnh
    user_template_keys = {t.template_key for t in user_templates}

    # 4. Gộp mẫu: mẫu tùy chỉnh + mẫu mặc định hệ thống chưa tùy chỉnh
    all_templates = []
    current_time = datetime.now()

    # Thêm các mẫu tùy chỉnh của người dùng
    for user_template in user_templates:
        user_template.is_system_default = False  # Đánh dấu đã tùy chỉnh
        all_templates.append(user_template)

    # Thêm các mẫu mặc định hệ thống chưa tùy chỉnh
    for sys_template in system_templates:
        if sys_template['template_key'] not in user_template_keys:
            # Mẫu hệ thống này người dùng chưa tùy chỉnh, tạo đối tượng tạm thời
            template_obj = PromptTemplate(
                id=sys_template['template_key'],  # Dùng template_key làm ID tạm thời
                user_id=user_id,
                template_key=sys_template['template_key'],
                template_name=sys_template['template_name'],
                template_content=sys_template['content'],
                description=sys_template['description'],
                category=sys_template['category'],
                parameters=json.dumps(sys_template['parameters']),
                is_active=True,
                is_system_default=True,
                created_at=current_time,
                updated_at=current_time
            )
            all_templates.append(template_obj)

    # 5. Nhóm theo phân loại
    category_dict = {}
    for template in all_templates:
        cat = template.category or "Chưa phân loại"
        if cat not in category_dict:
            category_dict[cat] = []
        category_dict[cat].append(template)

    # 6. Xây dựng response
    response = []
    for category, temps in sorted(category_dict.items()):
        # Sắp xếp theo template_key, đảm bảo thứ tự nhất quán
        temps.sort(key=lambda t: t.template_key)
        response.append(PromptTemplateCategoryResponse(
            category=category,
            count=len(temps),
            templates=temps
        ))

    return response


@router.get("/system-defaults")
async def get_system_defaults(
    request: Request
):
    """
    Lấy tất cả mẫu prompt mặc định hệ thống
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Lấy tất cả mẫu mặc định hệ thống từ PromptService
    system_templates = PromptService.get_all_system_templates()

    return {
        "templates": system_templates,
        "total": len(system_templates)
    }


@router.get("/{template_key}", response_model=PromptTemplateResponse)
async def get_template(
    template_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy mẫu prompt được chỉ định
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.user_id == user_id,
            PromptTemplate.template_key == template_key
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail=f"Mẫu {template_key} không tồn tại")

    return template


@router.post("", response_model=PromptTemplateResponse)
async def create_or_update_template(
    data: PromptTemplateCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo hoặc cập nhật mẫu prompt (Upsert)
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Tìm mẫu hiện có
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.user_id == user_id,
            PromptTemplate.template_key == data.template_key
        )
    )
    template = result.scalar_one_or_none()

    if template:
        # Cập nhật mẫu hiện có
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(template, key, value)
        logger.info(f"Người dùng {user_id} cập nhật mẫu {data.template_key}")
    else:
        # Tạo mẫu mới
        template = PromptTemplate(
            user_id=user_id,
            **data.model_dump()
        )
        db.add(template)
        logger.info(f"Người dùng {user_id} tạo mẫu {data.template_key}")

    await db.commit()
    await db.refresh(template)

    return template


@router.put("/{template_key}", response_model=PromptTemplateResponse)
async def update_template(
    template_key: str,
    data: PromptTemplateUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật mẫu prompt
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.user_id == user_id,
            PromptTemplate.template_key == template_key
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail=f"Mẫu {template_key} không tồn tại")

    # Cập nhật mẫu
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    await db.commit()
    await db.refresh(template)
    logger.info(f"Người dùng {user_id} cập nhật mẫu {template_key}")

    return template


@router.delete("/{template_key}")
async def delete_template(
    template_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa mẫu prompt tùy chỉnh
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.user_id == user_id,
            PromptTemplate.template_key == template_key
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail=f"Mẫu {template_key} không tồn tại")

    await db.delete(template)
    await db.commit()
    logger.info(f"Người dùng {user_id} xóa mẫu {template_key}")

    return {"message": "Đã xóa mẫu", "template_key": template_key}


@router.post("/{template_key}/reset")
async def reset_to_default(
    template_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Đặt lại về mẫu mặc định hệ thống (xóa bản tùy chỉnh của người dùng)
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Kiểm tra mẫu mặc định hệ thống có tồn tại không
    system_template = PromptService.get_system_template_info(template_key)
    if not system_template:
        raise HTTPException(status_code=404, detail=f"Mẫu mặc định hệ thống {template_key} không tồn tại")

    # Tìm và xóa mẫu tùy chỉnh của người dùng
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.user_id == user_id,
            PromptTemplate.template_key == template_key
        )
    )
    template = result.scalar_one_or_none()

    if template:
        await db.delete(template)
        await db.commit()
        logger.info(f"Người dùng {user_id} xóa mẫu tùy chỉnh {template_key}, khôi phục về mặc định hệ thống")
        return {"message": "Đã đặt lại về mặc định hệ thống", "template_key": template_key}
    else:
        # Người dùng vốn chưa tùy chỉnh, đã ở trạng thái mặc định hệ thống
        logger.info(f"Mẫu {template_key} của người dùng {user_id} vốn đã là mặc định hệ thống")
        return {"message": "Đã ở trạng thái mặc định hệ thống", "template_key": template_key}


@router.post("/export", response_model=PromptTemplateExport)
async def export_templates(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Xuất tất cả mẫu prompt (gồm tùy chỉnh của người dùng và mặc định hệ thống)
    - Prompt tùy chỉnh của người dùng được đánh dấu is_customized=true
    - Prompt mặc định hệ thống được đánh dấu is_customized=false
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # 1. Truy vấn mẫu tùy chỉnh của người dùng
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.user_id == user_id)
    )
    user_templates = result.scalars().all()

    # 2. Lấy tất cả mẫu mặc định hệ thống
    system_templates = PromptService.get_all_system_templates()

    # 3. Xây dựng tập hợp khóa của các mẫu tùy chỉnh
    user_template_keys = {t.template_key for t in user_templates}

    # 4. Chuẩn bị dữ liệu xuất
    export_items = []
    customized_count = 0
    system_default_count = 0

    # Thêm các mẫu tùy chỉnh của người dùng
    for user_template in user_templates:
        # Lấy mẫu hệ thống tương ứng để tính hash
        system_template = next(
            (t for t in system_templates if t["template_key"] == user_template.template_key),
            None
        )
        system_hash = calculate_content_hash(system_template["content"]) if system_template else None

        export_items.append(PromptTemplateExportItem(
            template_key=user_template.template_key,
            template_name=user_template.template_name,
            template_content=user_template.template_content,
            description=user_template.description,
            category=user_template.category,
            parameters=user_template.parameters,
            is_active=user_template.is_active,
            is_customized=True,
            system_content_hash=system_hash
        ))
        customized_count += 1

    # Thêm các mẫu mặc định hệ thống chưa tùy chỉnh
    for sys_template in system_templates:
        if sys_template['template_key'] not in user_template_keys:
            export_items.append(PromptTemplateExportItem(
                template_key=sys_template['template_key'],
                template_name=sys_template['template_name'],
                template_content=sys_template['content'],
                description=sys_template['description'],
                category=sys_template['category'],
                parameters=json.dumps(sys_template['parameters']),
                is_active=True,
                is_customized=False,
                system_content_hash=calculate_content_hash(sys_template['content'])
            ))
            system_default_count += 1

    statistics = {
        "total": len(export_items),
        "customized": customized_count,
        "system_default": system_default_count
    }

    logger.info(f"Người dùng {user_id} đã xuất {statistics['total']} mẫu "
                f"(tùy chỉnh: {statistics['customized']}, mặc định hệ thống: {statistics['system_default']})")

    return PromptTemplateExport(
        templates=export_items,
        export_time=datetime.now(),
        version="2.0",
        statistics=statistics
    )


@router.post("/import", response_model=PromptTemplateImportResult)
async def import_templates(
    data: PromptTemplateExport,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Nhập mẫu prompt thông minh
    - Nếu nhập là mặc định hệ thống và nội dung chưa sửa → xóa bản ghi tùy chỉnh (dùng mặc định hệ thống)
    - Nếu nhập là mặc định hệ thống nhưng nội dung đã sửa → tạo bản ghi tùy chỉnh
    - Nếu nhập là tùy chỉnh của người dùng → tạo/cập nhật bản ghi tùy chỉnh
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Lấy tất cả mẫu mặc định hệ thống để đối chiếu
    system_templates = PromptService.get_all_system_templates()
    system_template_dict = {t["template_key"]: t for t in system_templates}

    # Thông tin thống kê
    kept_system_default = 0  # Giữ mặc định hệ thống
    created_or_updated = 0   # Tạo hoặc cập nhật tùy chỉnh
    converted_to_custom = 0  # Chuyển từ mặc định hệ thống sang tùy chỉnh
    converted_templates = []  # Danh sách mẫu đã chuyển đổi

    for template_data in data.templates:
        template_key = template_data.template_key
        is_customized = template_data.is_customized
        imported_content = template_data.template_content.strip()

        # Tìm xem người dùng hiện có bản tùy chỉnh của mẫu này không
        result = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.user_id == user_id,
                PromptTemplate.template_key == template_key
            )
        )
        existing = result.scalar_one_or_none()

        # Lấy mẫu mặc định hệ thống
        system_template = system_template_dict.get(template_key)

        if not is_customized:
            # Nội dung nhập được đánh dấu là mặc định hệ thống
            if system_template:
                system_content = system_template["content"].strip()

                # So sánh nội dung có khớp mặc định hệ thống không
                if imported_content == system_content:
                    # Nội dung khớp, xóa bản ghi tùy chỉnh (nếu có)
                    if existing:
                        await db.delete(existing)
                        logger.info(f"Mẫu {template_key} của người dùng {user_id} khôi phục về mặc định hệ thống (xóa tùy chỉnh)")
                    kept_system_default += 1
                else:
                    # Nội dung không khớp, người dùng đã sửa, tạo/cập nhật thành tùy chỉnh
                    if existing:
                        # Cập nhật tùy chỉnh hiện có
                        existing.template_name = template_data.template_name
                        existing.template_content = template_data.template_content
                        existing.description = template_data.description
                        existing.category = template_data.category
                        existing.parameters = template_data.parameters
                        existing.is_active = template_data.is_active
                    else:
                        # Tạo tùy chỉnh mới
                        new_template = PromptTemplate(
                            user_id=user_id,
                            template_key=template_data.template_key,
                            template_name=template_data.template_name,
                            template_content=template_data.template_content,
                            description=template_data.description,
                            category=template_data.category,
                            parameters=template_data.parameters,
                            is_active=template_data.is_active
                        )
                        db.add(new_template)

                    converted_to_custom += 1
                    converted_templates.append({
                        "template_key": template_key,
                        "template_name": template_data.template_name,
                        "reason": "Nội dung không khớp mặc định hệ thống, đã chuyển thành tùy chỉnh"
                    })
                    logger.info(f"Nội dung mẫu {template_key} của người dùng {user_id} đã bị sửa, chuyển thành tùy chỉnh")
            else:
                # Mẫu này không tồn tại trong hệ thống, nhập dưới dạng tùy chỉnh
                if existing:
                    existing.template_name = template_data.template_name
                    existing.template_content = template_data.template_content
                    existing.description = template_data.description
                    existing.category = template_data.category
                    existing.parameters = template_data.parameters
                    existing.is_active = template_data.is_active
                else:
                    new_template = PromptTemplate(
                        user_id=user_id,
                        template_key=template_data.template_key,
                        template_name=template_data.template_name,
                        template_content=template_data.template_content,
                        description=template_data.description,
                        category=template_data.category,
                        parameters=template_data.parameters,
                        is_active=template_data.is_active
                    )
                    db.add(new_template)
                created_or_updated += 1
        else:
            # Nội dung nhập được đánh dấu là tùy chỉnh của người dùng, tạo/cập nhật trực tiếp
            if existing:
                existing.template_name = template_data.template_name
                existing.template_content = template_data.template_content
                existing.description = template_data.description
                existing.category = template_data.category
                existing.parameters = template_data.parameters
                existing.is_active = template_data.is_active
            else:
                new_template = PromptTemplate(
                    user_id=user_id,
                    template_key=template_data.template_key,
                    template_name=template_data.template_name,
                    template_content=template_data.template_content,
                    description=template_data.description,
                    category=template_data.category,
                    parameters=template_data.parameters,
                    is_active=template_data.is_active
                )
                db.add(new_template)
            created_or_updated += 1

    await db.commit()

    statistics = {
        "total": len(data.templates),
        "kept_system_default": kept_system_default,
        "created_or_updated": created_or_updated,
        "converted_to_custom": converted_to_custom
    }

    logger.info(f"Người dùng {user_id} hoàn tất nhập: {statistics}")

    return PromptTemplateImportResult(
        message="Nhập thành công",
        statistics=statistics,
        converted_templates=converted_templates
    )


@router.post("/{template_key}/preview")
async def preview_template(
    template_key: str,
    data: PromptTemplatePreviewRequest,
    request: Request
):
    """
    Xem trước mẫu prompt (render biến)
    """
    # Lấy ID người dùng từ middleware xác thực
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    try:
        # Dùng phương thức format_prompt của PromptService
        rendered = PromptService.format_prompt(
            data.template_content,
            **data.parameters
        )

        return {
            "success": True,
            "rendered_content": rendered,
            "parameters_used": list(data.parameters.keys())
        }
    except KeyError as e:
        return {
            "success": False,
            "error": f"Thiếu tham số bắt buộc: {str(e)}",
            "rendered_content": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Render thất bại: {str(e)}",
            "rendered_content": None
        }
