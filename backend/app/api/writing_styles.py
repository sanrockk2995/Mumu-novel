"""API quản lý phong cách viết"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List

from..database import get_db
from..models.writing_style import WritingStyle
from..models.project import Project
from..models.project_default_style import ProjectDefaultStyle
from..schemas.writing_style import (
    WritingStyleCreate,
    WritingStyleUpdate,
    WritingStyleResponse,
    WritingStyleListResponse,
    SetDefaultStyleRequest
)
from..logger import get_logger

router = APIRouter(prefix="/writing-styles", tags=["writing-styles"])
logger = get_logger(__name__)


def get_current_user_id(request: Request) -> str:
    """Lấy ID người dùng đang đăng nhập"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return user_id


@router.get("/presets/list", response_model=List[dict])
async def get_preset_styles(db: AsyncSession = Depends(get_db)):
    """
    Lấy danh sách tất cả phong cách preset (đọc từ cơ sở dữ liệu)
    
    Định dạng trả về: danh sách phong cách preset dạng mảng
    [
        {"id": 1, "preset_id": "natural", "name": "Tự nhiên trôi chảy", "description": "...", "prompt_content": "..."},
        {"id": 2, "preset_id": "classical", "name": "Cổ điển trang nhã",...}
    ]
    """
    # Lấy phong cách preset toàn cục từ cơ sở dữ liệu (user_id là NULL)
    result = await db.execute(
        select(WritingStyle)
        .where(WritingStyle.user_id.is_(None))
        .order_by(WritingStyle.order_index)
    )
    preset_styles = result.scalars().all()
    
    # Chuyển thành định dạng response
    return [
        {
            "id": style.id,
            "preset_id": style.preset_id,
            "name": style.name,
            "description": style.description,
            "prompt_content": style.prompt_content,
            "style_type": style.style_type,
            "order_index": style.order_index
        }
        for style in preset_styles
    ]


@router.post("", response_model=WritingStyleResponse, status_code=201)
async def create_writing_style(
    style_data: WritingStyleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Tạo phong cách viết mới (cấp người dùng)
    
    - **Tạo dựa trên preset**: cung cấp preset_id, hệ thống sẽ truy vấn nội dung preset từ cơ sở dữ liệu để tự động điền
    - **Hoàn toàn tùy chỉnh**: không cung cấp preset_id, cần điền thủ công mọi trường
    """
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    # Nếu tạo dựa trên preset, lấy nội dung preset từ cơ sở dữ liệu
    if style_data.preset_id:
        result = await db.execute(
            select(WritingStyle)
            .where(
                WritingStyle.user_id.is_(None),
                WritingStyle.preset_id == style_data.preset_id
            )
        )
        preset = result.scalar_one_or_none()
        
        if not preset:
            raise HTTPException(status_code=400, detail=f"Phong cách preset '{style_data.preset_id}' không tồn tại")
        
        # Dùng nội dung preset để điền (nếu người dùng chưa cung cấp)
        if not style_data.name:
            style_data.name = preset.name
        if not style_data.description:
            style_data.description = preset.description
        if not style_data.prompt_content:
            style_data.prompt_content = preset.prompt_content
    
    # Kiểm tra các trường bắt buộc
    if not style_data.name or not style_data.prompt_content:
        raise HTTPException(
            status_code=400,
            detail="name và prompt_content là các trường bắt buộc"
        )
    
    # Lấy order_index lớn nhất hiện tại của người dùng
    count_result = await db.execute(
        select(func.count(WritingStyle.id))
        .where(WritingStyle.user_id == user_id)
    )
    max_order = count_result.scalar_one()
    
    # Tạo bản ghi phong cách
    new_style = WritingStyle(
        user_id=user_id,
        name=style_data.name,
        style_type=style_data.style_type or ("preset" if style_data.preset_id else "custom"),
        preset_id=style_data.preset_id,
        description=style_data.description,
        prompt_content=style_data.prompt_content,
        order_index=max_order + 1
    )
    
    db.add(new_style)
    await db.commit()
    await db.refresh(new_style)
    
    # Trả về dict có trường is_default (phong cách mới tạo mặc định không phải phong cách mặc định)
    return {
        "id": new_style.id,
        "user_id": new_style.user_id,
        "name": new_style.name,
        "style_type": new_style.style_type,
        "preset_id": new_style.preset_id,
        "description": new_style.description,
        "prompt_content": new_style.prompt_content,
        "order_index": new_style.order_index,
        "created_at": new_style.created_at,
        "updated_at": new_style.updated_at,
        "is_default": False
    }


@router.get("/user", response_model=WritingStyleListResponse)
async def get_user_styles(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả phong cách viết khả dụng của người dùng
    
    Trả về: phong cách preset toàn cục + phong cách tùy chỉnh của người dùng
    Sắp xếp theo order_index
    """
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    # Lấy phong cách preset toàn cục (user_id là NULL)
    result = await db.execute(
        select(WritingStyle)
        .where(WritingStyle.user_id.is_(None))
        .order_by(WritingStyle.order_index)
    )
    preset_styles = list(result.scalars().all())
    
    # Lấy phong cách tùy chỉnh của người dùng
    result = await db.execute(
        select(WritingStyle)
        .where(WritingStyle.user_id == user_id)
        .order_by(WritingStyle.order_index)
    )
    custom_styles = list(result.scalars().all())
    
    # Gộp: phong cách preset + phong cách tùy chỉnh
    all_styles = preset_styles + custom_styles
    
    # Chuyển thành định dạng response
    styles_with_default = []
    for style in all_styles:
        style_dict = {
            "id": style.id,
            "user_id": style.user_id,
            "name": style.name,
            "style_type": style.style_type,
            "preset_id": style.preset_id,
            "description": style.description,
            "prompt_content": style.prompt_content,
            "order_index": style.order_index,
            "created_at": style.created_at,
            "updated_at": style.updated_at,
            "is_default": False # Cấp người dùng không cần cờ phong cách mặc định nữa
        }
        styles_with_default.append(style_dict)
    
    return {"styles": styles_with_default, "total": len(styles_with_default)}


@router.get("/project/{project_id}", response_model=WritingStyleListResponse)
async def get_project_styles(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy tất cả phong cách viết khả dụng của dự án (giữ lại để tương thích ngược)
    
    Trả về: phong cách preset toàn cục + phong cách tùy chỉnh của người dùng
    Sắp xếp theo order_index, và đánh dấu phong cách mặc định hiện tại của dự án
    """
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    # Kiểm tra quyền truy cập dự án
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại hoặc không có quyền truy cập")
    
    # Lấy ID phong cách mặc định của dự án
    result = await db.execute(
        select(ProjectDefaultStyle.style_id)
        .where(ProjectDefaultStyle.project_id == project_id)
    )
    default_style_id = result.scalar_one_or_none()
    
    # Lấy phong cách preset toàn cục (user_id là NULL)
    result = await db.execute(
        select(WritingStyle)
        .where(WritingStyle.user_id.is_(None))
        .order_by(WritingStyle.order_index)
    )
    preset_styles = list(result.scalars().all())
    
    # Lấy phong cách tùy chỉnh của người dùng
    result = await db.execute(
        select(WritingStyle)
        .where(WritingStyle.user_id == user_id)
        .order_by(WritingStyle.order_index)
    )
    custom_styles = list(result.scalars().all())
    
    # Gộp: phong cách preset + phong cách tùy chỉnh
    all_styles = preset_styles + custom_styles
    
    # Thêm cờ is_default cho mỗi phong cách (để frontend hiển thị)
    styles_with_default = []
    for style in all_styles:
        style_dict = {
            "id": style.id,
            "user_id": style.user_id,
            "name": style.name,
            "style_type": style.style_type,
            "preset_id": style.preset_id,
            "description": style.description,
            "prompt_content": style.prompt_content,
            "order_index": style.order_index,
            "created_at": style.created_at,
            "updated_at": style.updated_at,
            "is_default": style.id == default_style_id
        }
        styles_with_default.append(style_dict)
    
    return {"styles": styles_with_default, "total": len(styles_with_default)}


@router.get("/{style_id}", response_model=WritingStyleResponse)
async def get_writing_style(
    style_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy chi tiết một phong cách viết"""
    user_id = get_current_user_id(request)
    result = await db.execute(
        select(WritingStyle).where(WritingStyle.id == style_id)
    )
    style = result.scalar_one_or_none()
    if not style:
        raise HTTPException(status_code=404, detail="Phong cách viết không tồn tại")
    if style.user_id is not None and style.user_id!= user_id:
        raise HTTPException(status_code=404, detail="Phong cách viết không tồn tại")
    
    # Kiểm tra có dự án nào đặt nó làm phong cách mặc định không (một phong cách có thể được nhiều dự án dùng, dùng first() để tránh MultipleResultsFound)
    result = await db.execute(
        select(ProjectDefaultStyle).where(ProjectDefaultStyle.style_id == style_id)
    )
    is_default = result.scalars().first() is not None
    
    # Trả về dict có trường is_default
    return {
        "id": style.id,
        "user_id": style.user_id,
        "name": style.name,
        "style_type": style.style_type,
        "preset_id": style.preset_id,
        "description": style.description,
        "prompt_content": style.prompt_content,
        "order_index": style.order_index,
        "created_at": style.created_at,
        "updated_at": style.updated_at,
        "is_default": is_default
    }


@router.put("/{style_id}", response_model=WritingStyleResponse)
async def update_writing_style(
    style_id: int,
    style_data: WritingStyleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cập nhật phong cách viết
    
    - Chỉ được sửa phong cách tùy chỉnh
    - Không được sửa phong cách preset toàn cục
    """
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    result = await db.execute(
        select(WritingStyle).where(WritingStyle.id == style_id)
    )
    style = result.scalar_one_or_none()
    if not style:
        raise HTTPException(status_code=404, detail="Phong cách viết không tồn tại")
    
    # Kiểm tra có phải phong cách preset toàn cục không (không cho phép sửa)
    if style.user_id is None:
        raise HTTPException(status_code=403, detail="Không được sửa phong cách preset toàn cục, chỉ được sửa phong cách tùy chỉnh")
    
    # Kiểm tra quyền người dùng (chỉ được sửa phong cách của mình)
    if style.user_id!= user_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa phong cách của người dùng khác")
    
    # Cập nhật các trường
    update_data = style_data.model_dump(exclude_unset=True)
    
    # Nếu sửa nội dung, đổi style_type thành custom
    if any(key in update_data for key in ["name", "description", "prompt_content"]):
        update_data["style_type"] = "custom"
    
    for key, value in update_data.items():
        setattr(style, key, value)
    
    await db.commit()
    await db.refresh(style)
    
    # Kiểm tra có dự án nào đặt nó làm phong cách mặc định không (một phong cách có thể được nhiều dự án dùng, dùng first() để tránh MultipleResultsFound)
    result = await db.execute(
        select(ProjectDefaultStyle).where(ProjectDefaultStyle.style_id == style_id)
    )
    is_default = result.scalars().first() is not None
    
    # Trả về dict có trường is_default
    return {
        "id": style.id,
        "user_id": style.user_id,
        "name": style.name,
        "style_type": style.style_type,
        "preset_id": style.preset_id,
        "description": style.description,
        "prompt_content": style.prompt_content,
        "order_index": style.order_index,
        "created_at": style.created_at,
        "updated_at": style.updated_at,
        "is_default": is_default
    }


@router.delete("/{style_id}", status_code=204)
async def delete_writing_style(
    style_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa phong cách viết
    
    Lưu ý:
    - Chỉ được xóa phong cách tùy chỉnh, không được xóa phong cách preset toàn cục
    - Không được xóa phong cách mặc định (phải đặt phong cách khác làm mặc định trước)
    - Xóa rồi không khôi phục được
    """
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    result = await db.execute(
        select(WritingStyle).where(WritingStyle.id == style_id)
    )
    style = result.scalar_one_or_none()
    if not style:
        raise HTTPException(status_code=404, detail="Phong cách viết không tồn tại")
    
    # Kiểm tra có phải phong cách preset toàn cục không (không cho phép xóa)
    if style.user_id is None:
        raise HTTPException(status_code=403, detail="Không được xóa phong cách preset toàn cục, chỉ được xóa phong cách tùy chỉnh")
    
    # Kiểm tra quyền người dùng (chỉ được xóa phong cách của mình)
    if style.user_id!= user_id:
        raise HTTPException(status_code=403, detail="Không có quyền xóa phong cách của người dùng khác")
    
    # Kiểm tra có dự án nào đặt nó làm phong cách mặc định không (một phong cách có thể được nhiều dự án dùng, dùng first() để tránh MultipleResultsFound)
    result = await db.execute(
        select(ProjectDefaultStyle).where(ProjectDefaultStyle.style_id == style_id)
    )
    default_relation = result.scalars().first()
    if default_relation:
        raise HTTPException(
            status_code=400,
            detail="Không được xóa phong cách mặc định, hãy đặt phong cách khác làm mặc định trước"
        )
    
    await db.delete(style)
    await db.commit()
    
    return None


@router.post("/{style_id}/set-default", response_model=dict)
async def set_default_style(
    style_id: int,
    request_data: SetDefaultStyleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Đặt phong cách được chỉ định làm phong cách mặc định của dự án
    
    Dùng bảng project_default_styles để ghi lựa chọn phong cách mặc định của dự án
    Mỗi dự án chỉ có một phong cách mặc định (đảm bảo bằng UniqueConstraint)
    
    Tham số:
    - style_id: ID phong cách cần đặt làm mặc định (tham số đường dẫn)
    - project_id: ID dự án (request body), dùng để xác định đặt mặc định trong ngữ cảnh dự án nào
    """
    project_id = request_data.project_id
    
    # Lấy ID người dùng hiện tại
    user_id = get_current_user_id(request)
    
    # Kiểm tra quyền truy cập dự án
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Dự án không tồn tại hoặc không có quyền truy cập")
    
    # Kiểm tra phong cách có tồn tại không
    result = await db.execute(
        select(WritingStyle).where(WritingStyle.id == style_id)
    )
    style = result.scalar_one_or_none()
    if not style:
        raise HTTPException(status_code=404, detail="Phong cách viết không tồn tại")
    
    # Kiểm tra phong cách có thuộc người dùng này không (phong cách tùy chỉnh) hoặc là phong cách preset toàn cục
    if style.user_id is not None and style.user_id!= user_id:
        raise HTTPException(status_code=403, detail="Không có quyền thao tác phong cách của người dùng khác")
    
    # Dùng logic UPSERT: xóa bản ghi phong cách mặc định cũ của dự án trước, rồi chèn bản mới
    await db.execute(
        delete(ProjectDefaultStyle).where(ProjectDefaultStyle.project_id == project_id)
    )
    
    # Chèn bản ghi phong cách mặc định mới
    new_default = ProjectDefaultStyle(
        project_id=project_id,
        style_id=style_id
    )
    db.add(new_default)
    await db.commit()
    
    return {
        "message": "Đặt phong cách mặc định thành công",
        "project_id": project_id,
        "style_id": style_id,
        "style_name": style.name
    }


@router.post("/project/{project_id}/init-defaults", response_model=WritingStyleListResponse)
async def initialize_default_styles(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    【Đã ngừng dùng】Khởi tạo phong cách mặc định cho dự án
    
    Trong kiến trúc mới, phong cách preset là toàn cục, không cần khởi tạo riêng cho từng dự án
    Giao diện này giữ lại để tương thích, trả về trực tiếp tất cả phong cách khả dụng của dự án
    """
    # Trả về trực tiếp tất cả phong cách khả dụng của dự án (preset toàn cục + tùy chỉnh của người dùng)
    return await get_project_styles(project_id, request, db)
