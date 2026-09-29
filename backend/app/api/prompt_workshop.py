"""API Xưởng prompt"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
from datetime import datetime
import uuid

from app.database import get_db
from app.config import settings, INSTANCE_ID, is_workshop_server
from app.models.writing_style import WritingStyle
from app.models.prompt_workshop import PromptWorkshopItem, PromptSubmission, PromptWorkshopLike
from app.schemas.prompt_workshop import (
    ImportRequest, DownloadRequest, PromptSubmissionCreate,
    ReviewRequest, AdminItemCreate, AdminItemUpdate
)
from app.services.workshop_client import workshop_client, WorkshopClientError
from app.constants.prompt_categories import PROMPT_CATEGORIES
from app.logger import get_logger

router = APIRouter(prefix="/prompt-workshop", tags=["prompt-workshop"])
logger = get_logger(__name__)


# ==================== Hàm phụ trợ ====================

def get_current_user_id(request: Request) -> str:
    """Lấy ID người dùng đang đăng nhập"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return user_id


def get_user_identifier(user_id: str) -> str:
    """Tạo định danh người dùng trên đám mây"""
    return f"{INSTANCE_ID}:{user_id}"


def get_user_identifier_from_request(request: Request) -> str:
    """
    Lấy định danh người dùng từ request
    Middleware đã xử lý yêu cầu proxy, lưu định danh người dùng vào request.state.user_id
    - Yêu cầu proxy: user_id có định dạng "instance_id:user_id"
    - Yêu cầu cục bộ: user_id là ID người dùng cục bộ, cần chuyển thành định dạng "instance_id:user_id"
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập hoặc thiếu ID người dùng")

    # Kiểm tra có phải yêu cầu proxy không (user_id đã có định dạng đầy đủ)
    is_proxy = getattr(request.state, 'is_proxy_request', False)
    if is_proxy:
        # Yêu cầu proxy, user_id đã ở định dạng "instance_id:user_id"
        return user_id
    else:
        # Yêu cầu cục bộ, cần thêm tiền tố instance
        return get_user_identifier(user_id)


def get_optional_user_identifier(request: Request) -> Optional[str]:
    """
    Lấy định danh người dùng tùy chọn (dùng cho API công khai, có thể không có người dùng)
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        return None

    # Kiểm tra có phải yêu cầu proxy không
    is_proxy = getattr(request.state, 'is_proxy_request', False)
    if is_proxy:
        return user_id
    else:
        return get_user_identifier(user_id)


def _item_to_dict(item: PromptWorkshopItem, is_liked: bool = False) -> dict:
    """Chuyển model thành dict"""
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "prompt_content": item.prompt_content,
        "category": item.category,
        "tags": item.tags,
        "author_name": item.author_name,
        "is_official": item.is_official,
        "download_count": item.download_count,
        "like_count": item.like_count,
        "is_liked": is_liked,
        "created_at": item.created_at.isoformat() if item.created_at else None
    }


def _submission_to_dict(submission: PromptSubmission) -> dict:
    """Chuyển bản ghi gửi thành dict"""
    return {
        "id": submission.id,
        "name": submission.name,
        "description": submission.description,
        "prompt_content": submission.prompt_content,
        "category": submission.category,
        "tags": submission.tags,
        "author_display_name": submission.author_display_name,
        "is_anonymous": submission.is_anonymous,
        "status": submission.status,
        "review_note": submission.review_note,
        "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "source_instance": submission.source_instance,
        "submitter_name": submission.submitter_name
    }


async def check_workshop_admin(request: Request):
    """Kiểm tra có phải quản trị viên xưởng không (phải là quản trị viên của instance đám mây)"""
    if not is_workshop_server():
        raise HTTPException(status_code=403, detail="Chức năng này chỉ khả dụng trên dịch vụ đám mây")

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Cần quyền quản trị viên")

    return user


# ==================== API công khai ====================

@router.get("/status")
async def get_status():
    """Lấy trạng thái dịch vụ"""
    result = {
        "mode": settings.WORKSHOP_MODE,
        "instance_id": INSTANCE_ID
    }

    if not is_workshop_server():
        result["cloud_url"] = settings.WORKSHOP_CLOUD_URL
        try:
            result["cloud_connected"] = await workshop_client.check_connection()
        except Exception:
            result["cloud_connected"] = False

    return result


@router.get("/items")
async def get_items(
    request: Request,
    category: Optional[str] = None,
    search: Optional[str] = None,
    tags: Optional[str] = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách prompt (giao diện công khai, không cần đăng nhập)"""
    user_identifier = get_optional_user_identifier(request)

    if is_workshop_server():
        # Chế độ server: truy vấn trực tiếp cơ sở dữ liệu cục bộ
        return await _get_items_local(db, category, search, tags, sort, page, limit, user_identifier)
    else:
        # Chế độ client: proxy lên đám mây
        try:
            return await workshop_client.get_items(
                category=category, search=search, tags=tags,
                sort=sort, page=page, limit=limit,
                user_identifier=user_identifier
            )
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


async def _get_items_local(
    db: AsyncSession,
    category: Optional[str],
    search: Optional[str],
    tags: Optional[str],
    sort: str,
    page: int,
    limit: int,
    user_identifier: Optional[str]
) -> dict:
    """Truy vấn danh sách prompt cục bộ"""
    # Xây dựng truy vấn
    query = select(PromptWorkshopItem).where(PromptWorkshopItem.status == "active")
    count_query = select(func.count(PromptWorkshopItem.id)).where(PromptWorkshopItem.status == "active")

    if category:
        query = query.where(PromptWorkshopItem.category == category)
        count_query = count_query.where(PromptWorkshopItem.category == category)

    if search:
        search_filter = or_(
            PromptWorkshopItem.name.ilike(f"%{search}%"),
            PromptWorkshopItem.description.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Sắp xếp
    if sort == "popular":
        query = query.order_by(PromptWorkshopItem.like_count.desc())
    elif sort == "downloads":
        query = query.order_by(PromptWorkshopItem.download_count.desc())
    else:  # newest
        query = query.order_by(PromptWorkshopItem.created_at.desc())

    # Đếm
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Phân trang
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    # Lấy trạng thái thích của người dùng
    liked_ids = set()
    if user_identifier:
        like_result = await db.execute(
            select(PromptWorkshopLike.workshop_item_id).where(
                PromptWorkshopLike.user_identifier == user_identifier
            )
        )
        liked_ids = {row[0] for row in like_result.fetchall()}

    # Lấy thống kê phân loại
    cat_result = await db.execute(
        select(
            PromptWorkshopItem.category,
            func.count(PromptWorkshopItem.id)
        ).where(PromptWorkshopItem.status == "active")
        .group_by(PromptWorkshopItem.category)
    )
    categories = [
        {"id": cat, "name": PROMPT_CATEGORIES.get(cat, cat), "count": count}
        for cat, count in cat_result.fetchall()
    ]

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "limit": limit,
            "items": [
                _item_to_dict(item, is_liked=item.id in liked_ids)
                for item in items
            ],
            "categories": categories
        }
    }


@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Lấy chi tiết một prompt"""
    user_identifier = get_optional_user_identifier(request)

    if is_workshop_server():
        result = await db.execute(
            select(PromptWorkshopItem).where(
                PromptWorkshopItem.id == item_id,
                PromptWorkshopItem.status == "active"
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Prompt không tồn tại")
        return {"success": True, "data": _item_to_dict(item)}
    else:
        try:
            return await workshop_client.get_item(item_id, user_identifier=user_identifier)
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


@router.post("/items/{item_id}/import")
async def import_item(
    item_id: str,
    data: ImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Nhập prompt vào phong cách viết cục bộ"""
    user_id = get_current_user_id(request)
    user_identifier = get_user_identifier(user_id)

    # Lấy chi tiết prompt
    if is_workshop_server():
        result = await db.execute(
            select(PromptWorkshopItem).where(PromptWorkshopItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Prompt không tồn tại")
        item_data = _item_to_dict(item)

        # Tăng bộ đếm tải xuống
        item.download_count += 1
        await db.commit()
    else:
        # Lấy từ đám mây
        try:
            result = await workshop_client.get_item(item_id, user_identifier=user_identifier)
            item_data = result.get("data", result)

            # Thông báo đám mây tăng bộ đếm tải xuống
            try:
                await workshop_client.record_download(item_id, user_identifier)
            except Exception as e:
                logger.warning(f"Thông báo đám mây tăng bộ đếm tải xuống thất bại: {e}")
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))

    # Tạo phong cách viết cục bộ
    count_result = await db.execute(
        select(func.count(WritingStyle.id)).where(WritingStyle.user_id == user_id)
    )
    max_order = count_result.scalar_one()

    new_style = WritingStyle(
        user_id=user_id,
        name=data.custom_name or item_data["name"],
        style_type="custom",
        description=f"Nhập từ xưởng prompt: {item_data.get('description', '') or ''}",
        prompt_content=item_data["prompt_content"],
        order_index=max_order + 1
    )
    db.add(new_style)
    await db.commit()
    await db.refresh(new_style)

    return {
        "success": True,
        "message": "Nhập thành công",
        "writing_style": {
            "id": new_style.id,
            "name": new_style.name,
            "style_type": new_style.style_type,
            "prompt_content": new_style.prompt_content
        }
    }


@router.post("/items/{item_id}/like")
async def toggle_like(
    item_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Thích/bỏ thích"""
    user_identifier = get_user_identifier_from_request(request)

    if is_workshop_server():
        # Kiểm tra đã thích chưa
        result = await db.execute(
            select(PromptWorkshopLike).where(
                PromptWorkshopLike.user_identifier == user_identifier,
                PromptWorkshopLike.workshop_item_id == item_id
            )
        )
        existing_like = result.scalar_one_or_none()

        # Lấy prompt
        item_result = await db.execute(
            select(PromptWorkshopItem).where(PromptWorkshopItem.id == item_id)
        )
        item = item_result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Prompt không tồn tại")

        if existing_like:
            # Bỏ thích
            await db.delete(existing_like)
            item.like_count = max(0, item.like_count - 1)
            liked = False
        else:
            # Thêm thích
            new_like = PromptWorkshopLike(
                id=str(uuid.uuid4()),
                user_identifier=user_identifier,
                workshop_item_id=item_id
            )
            db.add(new_like)
            item.like_count += 1
            liked = True

        await db.commit()
        return {"success": True, "liked": liked, "like_count": item.like_count}
    else:
        try:
            return await workshop_client.toggle_like(item_id, user_identifier)
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


@router.post("/items/{item_id}/download")
async def record_download(
    item_id: str,
    data: DownloadRequest,
    db: AsyncSession = Depends(get_db)
):
    """Ghi nhận lượt tải xuống (chỉ instance đám mây dùng)"""
    if not is_workshop_server():
        raise HTTPException(status_code=403, detail="Giao diện này chỉ dành cho instance đám mây")

    result = await db.execute(
        select(PromptWorkshopItem).where(PromptWorkshopItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    item.download_count += 1
    await db.commit()

    return {"success": True, "download_count": item.download_count}


@router.post("/submit")
async def submit_prompt(
    data: PromptSubmissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Gửi prompt"""
    user_identifier = get_user_identifier_from_request(request)

    # Tên tác giả ưu tiên dùng author_display_name do người dùng nhập
    # Nếu người dùng chưa nhập, mới dùng tên người dùng hệ thống lấy được
    submitter_name = data.author_display_name

    if not submitter_name:
        # Người dùng chưa nhập tên tác giả, thử lấy từ hệ thống
        is_proxy = getattr(request.state, 'is_proxy_request', False)

        if is_proxy:
            submitter_name = "Người dùng không xác định"
        else:
            user = getattr(request.state, 'user', None)
            if user:
                submitter_name = user.display_name
            else:
                user_id = getattr(request.state, 'user_id', None)
                if user_id:
                    from app.user_manager import user_manager
                    user = await user_manager.get_user(user_id)
                    submitter_name = user.display_name if user else "Người dùng không xác định"
                else:
                    submitter_name = "Người dùng không xác định"

    if is_workshop_server():
        # Tạo trực tiếp bản ghi gửi
        # Với yêu cầu proxy, source_instance lấy từ Header
        source_instance = request.headers.get("X-Instance-ID") or INSTANCE_ID

        submission = PromptSubmission(
            id=str(uuid.uuid4()),
            submitter_id=user_identifier,
            submitter_name=submitter_name,
            source_instance=source_instance,
            name=data.name,
            description=data.description,
            prompt_content=data.prompt_content,
            category=data.category,
            tags=data.tags,
            author_display_name=data.author_display_name or submitter_name,
            is_anonymous=data.is_anonymous,
            status="pending"
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)

        return {
            "success": True,
            "message": "Gửi thành công, đang chờ quản trị viên kiểm duyệt",
            "submission": {
                "id": submission.id,
                "status": submission.status,
                "created_at": submission.created_at.isoformat() if submission.created_at else None
            }
        }
    else:
        try:
            return await workshop_client.submit(
                user_identifier=user_identifier,
                submitter_name=submitter_name,
                data=data.model_dump()
            )
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


@router.get("/my-submissions")
async def get_my_submissions(
    request: Request,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Lấy bản ghi đã gửi của tôi"""
    user_identifier = get_user_identifier_from_request(request)

    if is_workshop_server():
        query = select(PromptSubmission).where(
            PromptSubmission.submitter_id == user_identifier
        )
        if status:
            query = query.where(PromptSubmission.status == status)
        query = query.order_by(PromptSubmission.created_at.desc())

        result = await db.execute(query)
        submissions = result.scalars().all()

        return {
            "success": True,
            "data": {
                "total": len(submissions),
                "items": [_submission_to_dict(s) for s in submissions]
            }
        }
    else:
        try:
            return await workshop_client.get_submissions(user_identifier, status)
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


@router.delete("/submissions/{submission_id}")
async def withdraw_submission(
    submission_id: str,
    request: Request,
    force: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Xóa bản ghi gửi
    - Bài gửi đang chờ duyệt (pending) có thể rút lại trực tiếp
    - Bài gửi đã duyệt (approved/rejected) cần tham số force=True mới xóa được
    """
    user_identifier = get_user_identifier_from_request(request)

    if is_workshop_server():
        result = await db.execute(
            select(PromptSubmission).where(
                PromptSubmission.id == submission_id,
                PromptSubmission.submitter_id == user_identifier
            )
        )
        submission = result.scalar_one_or_none()

        if not submission:
            raise HTTPException(status_code=404, detail="Bản ghi gửi không tồn tại")

        # Đang chờ duyệt có thể rút lại trực tiếp, đã duyệt cần tham số force
        if submission.status != "pending" and not force:
            raise HTTPException(status_code=400, detail="Chỉ được rút lại bài gửi đang chờ duyệt, muốn xóa bản ghi đã duyệt hãy dùng tham số force")

        await db.delete(submission)
        await db.commit()

        if submission.status == "pending":
            return {"success": True, "message": "Rút lại thành công"}
        else:
            return {"success": True, "message": "Xóa thành công"}
    else:
        try:
            return await workshop_client.withdraw_submission(submission_id, user_identifier, force)
        except WorkshopClientError as e:
            raise HTTPException(status_code=503, detail=str(e))


# ==================== API quản trị (chỉ instance đám mây) ====================

@router.get("/admin/submissions")
async def admin_get_submissions(
    request: Request,
    status: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách chờ duyệt (quản trị viên)"""
    await check_workshop_admin(request)

    query = select(PromptSubmission)
    count_query = select(func.count(PromptSubmission.id))

    if status and status != "all":
        query = query.where(PromptSubmission.status == status)
        count_query = count_query.where(PromptSubmission.status == status)
    if source:
        query = query.where(PromptSubmission.source_instance == source)
        count_query = count_query.where(PromptSubmission.source_instance == source)

    # Đếm
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Số lượng chờ duyệt
    pending_result = await db.execute(
        select(func.count(PromptSubmission.id)).where(PromptSubmission.status == "pending")
    )
    pending_count = pending_result.scalar_one()

    # Truy vấn phân trang
    query = query.order_by(PromptSubmission.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    submissions = result.scalars().all()

    return {
        "success": True,
        "data": {
            "total": total,
            "pending_count": pending_count,
            "page": page,
            "limit": limit,
            "items": [_submission_to_dict(s) for s in submissions]
        }
    }


@router.post("/admin/submissions/{submission_id}/review")
async def admin_review_submission(
    submission_id: str,
    data: ReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Kiểm duyệt bài gửi (quản trị viên)"""
    admin = await check_workshop_admin(request)

    result = await db.execute(
        select(PromptSubmission).where(PromptSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        raise HTTPException(status_code=404, detail="Bản ghi gửi không tồn tại")
    if submission.status != "pending":
        raise HTTPException(status_code=400, detail="Bài gửi này đã được kiểm duyệt")

    admin_user_id = getattr(admin, 'user_id', str(admin))

    if data.action == "approve":
        # Tạo mục xưởng
        new_item = PromptWorkshopItem(
            id=str(uuid.uuid4()),
            name=submission.name,
            description=submission.description,
            prompt_content=submission.prompt_content,
            category=data.category or submission.category,
            tags=data.tags or submission.tags,
            author_id=None if submission.is_anonymous else submission.submitter_id,
            author_name=submission.author_display_name if not submission.is_anonymous else None,
            source_instance=submission.source_instance,
            is_official=False,
            status="active"
        )
        db.add(new_item)

        submission.status = "approved"
        submission.workshop_item_id = new_item.id
        submission.reviewer_id = admin_user_id
        submission.review_note = data.review_note
        submission.reviewed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(new_item)

        return {
            "success": True,
            "message": "Đã duyệt và phát hành",
            "workshop_item": _item_to_dict(new_item)
        }
    else:
        submission.status = "rejected"
        submission.reviewer_id = admin_user_id
        submission.review_note = data.review_note
        submission.reviewed_at = datetime.utcnow()

        await db.commit()
        await db.refresh(submission)

        return {
            "success": True,
            "message": "Đã từ chối",
            "submission": _submission_to_dict(submission)
        }


@router.post("/admin/items")
async def admin_create_item(
    data: AdminItemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Thêm prompt chính thức (quản trị viên)"""
    await check_workshop_admin(request)

    new_item = PromptWorkshopItem(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        prompt_content=data.prompt_content,
        category=data.category,
        tags=data.tags,
        author_name="Chính thức",
        is_official=True,
        status="active"
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)

    return {"success": True, "item": _item_to_dict(new_item)}


@router.put("/admin/items/{item_id}")
async def admin_update_item(
    item_id: str,
    data: AdminItemUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Chỉnh sửa prompt (quản trị viên)"""
    await check_workshop_admin(request)

    result = await db.execute(
        select(PromptWorkshopItem).where(PromptWorkshopItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    await db.commit()
    await db.refresh(item)

    return {"success": True, "item": _item_to_dict(item)}


@router.delete("/admin/items/{item_id}")
async def admin_delete_item(
    item_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Xóa prompt (quản trị viên)"""
    await check_workshop_admin(request)

    result = await db.execute(
        select(PromptWorkshopItem).where(PromptWorkshopItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Prompt không tồn tại")

    await db.delete(item)
    await db.commit()

    return {"success": True, "message": "Xóa thành công"}


@router.get("/admin/stats")
async def admin_get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Lấy dữ liệu thống kê (quản trị viên)"""
    await check_workshop_admin(request)

    # Tổng số prompt
    items_count = await db.execute(
        select(func.count(PromptWorkshopItem.id)).where(PromptWorkshopItem.status == "active")
    )
    total_items = items_count.scalar_one()

    # Số prompt chính thức
    official_count = await db.execute(
        select(func.count(PromptWorkshopItem.id)).where(
            PromptWorkshopItem.status == "active",
            PromptWorkshopItem.is_official == True
        )
    )
    total_official = official_count.scalar_one()

    # Số chờ duyệt
    pending_count = await db.execute(
        select(func.count(PromptSubmission.id)).where(PromptSubmission.status == "pending")
    )
    total_pending = pending_count.scalar_one()

    # Tổng lượt tải xuống
    downloads_sum = await db.execute(
        select(func.sum(PromptWorkshopItem.download_count))
    )
    total_downloads = downloads_sum.scalar_one() or 0

    # Tổng lượt thích
    likes_sum = await db.execute(
        select(func.sum(PromptWorkshopItem.like_count))
    )
    total_likes = likes_sum.scalar_one() or 0

    return {
        "success": True,
        "data": {
            "total_items": total_items,
            "total_official": total_official,
            "total_pending": total_pending,
            "total_downloads": total_downloads,
            "total_likes": total_likes
        }
    }
