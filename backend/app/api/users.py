"""
API quản lý người dùng
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.user_manager import user_manager, User
from app.user_password import password_manager

router = APIRouter(prefix="/users", tags=["Quản lý người dùng"])


def require_login(request: Request):
    """Dependency: yêu cầu người dùng đã đăng nhập"""
    if not hasattr(request.state, "user") or not request.state.user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return request.state.user


def require_admin(request: Request):
    """Dependency: yêu cầu người dùng là quản trị viên"""
    user = require_login(request)
    if not request.state.is_admin:
        raise HTTPException(status_code=403, detail="Cần quyền quản trị viên")
    return user


class SetAdminRequest(BaseModel):
    user_id: str
    is_admin: bool


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: Optional[str] = None  # Nếu để trống, hệ thống sẽ tạo mật khẩu tạm thời


@router.get("/current")
async def get_current_user(user: User = Depends(require_login)):
    """Lấy thông tin người dùng đang đăng nhập"""
    return user.dict()


@router.get("", response_model=List[dict])
async def list_users(admin_user: User = Depends(require_admin)):
    """
    Lấy danh sách tất cả người dùng (chỉ quản trị viên)
    """
    users = await user_manager.get_all_users()
    return [user.dict() for user in users]


@router.post("/set-admin")
async def set_admin(
    data: SetAdminRequest,
    request: Request,
    admin_user: User = Depends(require_admin)
):
    """
    Thiết lập quyền quản trị viên cho người dùng (chỉ quản trị viên)
    
    Giới hạn:
    - Không thể thu hồi quyền quản trị viên của chính mình
    - Phải giữ lại ít nhất một quản trị viên
    """
    # Kiểm tra xem có đang cố thu hồi quyền của chính mình không
    if data.user_id == admin_user.user_id and not data.is_admin:
        raise HTTPException(
            status_code=400,
            detail="Không thể thu hồi quyền quản trị viên của chính mình"
        )
    
    # Thử thiết lập quyền quản trị viên
    success = await user_manager.set_admin(data.user_id, data.is_admin)
    
    if not success:
        if not data.is_admin:
            raise HTTPException(
                status_code=400,
                detail="Không thể thu hồi quyền quản trị viên, cần giữ lại ít nhất một quản trị viên"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="Người dùng không tồn tại"
            )
    
    return {
        "message": f"Đã {'cấp' if data.is_admin else 'thu hồi'} quyền quản trị viên",
        "user_id": data.user_id,
        "is_admin": data.is_admin
    }


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: User = Depends(require_admin)
):
    """
    Xóa người dùng (chỉ quản trị viên)
    
    Giới hạn:
    - Không thể xóa người dùng quản trị viên
    """
    success = await user_manager.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa người dùng này (người dùng không tồn tại hoặc là quản trị viên)"
        )
    
    return {
        "message": "Đã xóa người dùng",
        "user_id": user_id
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    admin_user: User = Depends(require_admin)
):
    """Lấy thông tin người dùng đã chỉ định (chỉ quản trị viên)"""
    user = await user_manager.get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    return user.dict()


@router.post("/reset-password")
async def reset_user_password(
    data: ResetPasswordRequest,
    admin_user: User = Depends(require_admin)
):
    """
    Đặt lại mật khẩu người dùng (chỉ quản trị viên)
    
    Nếu cung cấp new_password, đặt thành mật khẩu đã chỉ định
    Nếu không cung cấp new_password, hệ thống sẽ tạo mật khẩu tạm thời
    
    Giới hạn:
    - Không thể đặt lại mật khẩu của chính mình (nên dùng chức năng đổi mật khẩu)
    """
    # Kiểm tra xem có đang cố đặt lại mật khẩu của chính mình không
    if data.user_id == admin_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="Không thể đặt lại mật khẩu của chính mình, vui lòng dùng chức năng đổi mật khẩu"
        )
    
    # Kiểm tra người dùng mục tiêu có tồn tại không
    target_user = await user_manager.get_user(data.user_id)
    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="Người dùng mục tiêu không tồn tại"
        )
    
    # Đặt lại mật khẩu
    try:
        generated_password = data.new_password
        if not generated_password:
            import secrets
            generated_password = secrets.token_urlsafe(12)

        await password_manager.set_password(
            target_user.user_id,
            target_user.username,
            generated_password
        )
        
        # Nếu dùng mật khẩu mặc định, trả về mật khẩu để quản trị viên thông báo cho người dùng
        message = "Đặt lại mật khẩu thành công"
        response_data = {
            "message": message,
            "user_id": data.user_id,
            "username": target_user.username
        }
        
        if not data.new_password:
            response_data["temporary_password"] = generated_password
            response_data["message"] = "Mật khẩu đã được đặt lại thành mật khẩu tạm thời do hệ thống tạo, vui lòng thông báo cho người dùng đổi càng sớm càng tốt"
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Đặt lại mật khẩu thất bại: {str(e)}"
        )
