"""
Module quản lý người dùng - lưu trữ bằng database
"""
import asyncio
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from pydantic import BaseModel
from app.config import settings


class User(BaseModel):
    """Đối tượng truyền dữ liệu người dùng"""
    user_id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    trust_level: int = 0
    is_admin: bool = False
    linuxdo_id: str
    created_at: str
    last_login: str


class UserManager:
    """Trình quản lý người dùng - lưu trữ bằng database (thư viện dùng chung PostgreSQL)"""
    
    def __init__(self):
        """Khởi tạo trình quản lý người dùng"""
        pass
    
    async def _get_session(self) -> AsyncSession:
        """Lấy session database - dùng engine PostgreSQL dùng chung"""
        from app.database import get_engine
        
        # Dùng engine PostgreSQL dùng chung (user_id dùng định danh đặc biệt)
        engine = await get_engine("_global_users_")
        
        session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        return session_maker()
    
    async def create_or_update_from_linuxdo(
        self,
        linuxdo_id: str,
        username: str,
        display_name: str,
        avatar_url: Optional[str],
        trust_level: int
    ) -> User:
        """
        Tạo hoặc cập nhật người dùng từ thông tin người dùng LinuxDO

        Args:
            linuxdo_id: ID người dùng LinuxDO (người dùng cục bộ có định dạng local_xxx)
            username: Tên đăng nhập
            display_name: Tên hiển thị
            avatar_url: URL ảnh đại diện
            trust_level: Cấp độ tin cậy

        Returns:
            Đối tượng người dùng
        """
        from app.models.user import User as UserModel
        
        # Sinh user_id
        if linuxdo_id.startswith("local_"):
            user_id = linuxdo_id
        else:
            user_id = f"linuxdo_{linuxdo_id}"
        
        async with await self._get_session() as session:
            # Truy vấn xem người dùng đã tồn tại chưa
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # Kiểm tra có phải quản trị viên ban đầu hoặc người dùng cục bộ không
            initial_admin_id = settings.INITIAL_ADMIN_LINUXDO_ID
            is_initial_admin = (initial_admin_id and linuxdo_id == initial_admin_id)
            is_local_user = user_id.startswith("local_")
            is_admin = is_initial_admin or is_local_user
            
            if user:
                # Cập nhật người dùng hiện có
                user.username = username
                user.display_name = display_name
                user.avatar_url = avatar_url
                user.trust_level = trust_level
                user.last_login = datetime.now()
                
                # Cập nhật trạng thái quản trị viên
                if is_admin and not user.is_admin:
                    user.is_admin = True
            else:
                # Tạo người dùng mới
                user = UserModel(
                    user_id=user_id,
                    username=username,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    trust_level=trust_level,
                    is_admin=is_admin,
                    linuxdo_id=linuxdo_id,
                    created_at=datetime.now(),
                    last_login=datetime.now()
                )
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            
            return User(**user.to_dict())
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Lấy người dùng"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                return User(**user.to_dict())
            return None
    
    async def get_all_users(self) -> List[User]:
        """Lấy tất cả người dùng"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(select(UserModel))
            users = result.scalars().all()
            
            return [User(**user.to_dict()) for user in users]
    
    async def set_admin(self, user_id: str, is_admin: bool) -> bool:
        """
        Đặt quyền quản trị viên cho người dùng

        Args:
            user_id: ID người dùng
            is_admin: Có phải quản trị viên hay không

        Returns:
            Có thành công hay không
        """
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            if not is_admin:
                # Khi thu hồi quyền quản trị viên, đảm bảo giữ lại ít nhất một quản trị viên
                admin_result = await session.execute(
                    select(UserModel).where(UserModel.is_admin == True)
                )
                admin_count = len(admin_result.scalars().all())
                
                if admin_count <= 1:
                    return False
            
            user.is_admin = is_admin
            await session.commit()
            
            return True
    
    async def delete_user(self, user_id: str) -> bool:
        """
        Xóa người dùng

        Args:
            user_id: ID người dùng

        Returns:
            Có thành công hay không
        """
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            # Không thể xóa quản trị viên
            if user.is_admin:
                return False
            
            await session.delete(user)
            await session.commit()
            
            return True
    
    async def is_admin(self, user_id: str) -> bool:
        """Kiểm tra người dùng có phải quản trị viên hay không"""
        from app.models.user import User as UserModel
        
        async with await self._get_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.user_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            return user.is_admin if user else False


# Instance trình quản lý người dùng toàn cục
user_manager = UserManager()