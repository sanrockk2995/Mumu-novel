"""API trò chuyện Skill

Cung cấp chức năng truy vấn danh sách Skill và trò chuyện streaming dựa trên Skill.
Sau khi người dùng chọn một Skill, lệnh workflow của Skill đó sẽ được dùng làm system prompt để trò chuyện.
"""
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict

from app.database import get_db
from app.user_manager import User
from app.api.settings import require_login
from app.services.skill_loader import get_all_skills_cached, get_skill_by_trigger, get_skill_detail, create_skill_files, update_skill_files, delete_skill_files, refresh_skills_cache, _get_skill_body
from app.services.ai_service import AIService, create_user_ai_service
from app.utils.sse_response import SSEResponse, create_sse_response, wrap_stream_with_heartbeat, HEARTBEAT
from app.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/skills", tags=["Skills"])


class SkillChatRequest(BaseModel):
    """Yêu cầu trò chuyện Skill"""
    skill_key: str  # ví dụ SKILL_STORY_LONG_WRITE
    message: str    # Tin nhắn người dùng
    history: Optional[List[dict]] = None  # Lịch sử trò chuyện [{"role": "user/assistant", "content": "..."}]


class SkillCreateRequest(BaseModel):
    """Yêu cầu tạo Skill"""
    name: str           # Tên Skill (tiếng Anh, ví dụ my-new-skill)
    display_name: str   # Tên hiển thị trên UI
    category: str       # Phân loại Skill
    description: str    # Mô tả Skill
    triggers: List[str] # Danh sách từ kích hoạt
    body: str           # Lệnh workflow (nội dung Markdown)
    references: Optional[Dict[str, str]] = None  # Kho kiến thức tham khảo {"tên file": "nội dung"}


class SkillUpdateRequest(BaseModel):
    """Yêu cầu cập nhật Skill"""
    display_name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    triggers: Optional[List[str]] = None
    body: Optional[str] = None
    references: Optional[Dict[str, str]] = None


@router.get("/list")
async def list_skills(user: User = Depends(require_login)):
    """Lấy danh sách tất cả Skill khả dụng"""
    skills = get_all_skills_cached()
    return [
        {
            "template_key": s["template_key"],
            "name": s.get("name", ""),
            "template_name": s["template_name"],
            "display_name": s.get("display_name", s["template_name"]),
            "category": s["category"],
            "description": s["description"],
            "triggers": s.get("triggers", []),
        }
        for s in skills
    ]


@router.post("/match")
async def match_skill(request: Request, user: User = Depends(require_login)):
    """Khớp Skill phù hợp nhất dựa trên nội dung người dùng nhập"""
    body = await request.json()
    user_input = body.get("user_input", "")

    if not user_input:
        return {"matched": False}

    skill = get_skill_by_trigger(user_input)
    if skill:
        return {
            "matched": True,
            "skill": {
                "template_key": skill["template_key"],
                "template_name": skill["template_name"],
                "category": skill["category"],
                "description": skill["description"],
            }
        }
    return {"matched": False}


@router.post("/chat")
async def skill_chat(
    request: SkillChatRequest,
    user: User = Depends(require_login),
    db: AsyncSession = Depends(get_db),
):
    """
    Trò chuyện streaming dựa trên Skill

    Nhận tin nhắn người dùng và định danh Skill, dùng nội dung Skill làm system prompt,
    trả lời streaming thông qua cấu hình AI của người dùng.
    """
    # Tìm Skill
    skills = get_all_skills_cached()
    skill = None
    for s in skills:
        if s["template_key"] == request.skill_key:
            skill = s
            break

    if not skill:
        async def error_gen():
            yield await SSEResponse.send_error(f"Không tìm thấy Skill: {request.skill_key}")
        return create_sse_response(error_gen())

    # Lấy system prompt (nội dung Skill)
    system_prompt = skill["content"]

    # Xây dựng prompt đầy đủ (nối lịch sử tin nhắn vào prompt)
    history_text = ""
    if request.history:
        for msg in request.history[-20:]:
            role_label = "Người dùng" if msg.get("role") == "user" else "Trợ lý"
            history_text += f"\n{role_label}: {msg.get('content', '')}"

    full_prompt = request.message
    if history_text:
        full_prompt = f"Dưới đây là lịch sử trò chuyện trước đó:{history_text}\n\nTin nhắn mới nhất của người dùng: {request.message}"

    # Lấy cấu hình AI của người dùng
    from app.api.settings import get_user_ai_service
    try:
        ai_service = await get_user_ai_service(user=user, db=db)
        # Ghi đè system prompt thành nội dung Skill
        ai_service.default_system_prompt = system_prompt
    except Exception as e:
        logger.error(f"Tạo dịch vụ AI thất bại: {e}")
        async def error_gen():
            yield await SSEResponse.send_error(f"Lỗi cấu hình dịch vụ AI: {str(e)}")
        return create_sse_response(error_gen())

    # Tạo streaming
    async def generate():
        try:
            yield await SSEResponse.send_progress(f"Đang sử dụng {skill['template_name']}...", 10)

            stream = ai_service.generate_text_stream(
                prompt=full_prompt,
                system_prompt=system_prompt,
                auto_mcp=False,  # Trò chuyện Skill không dùng công cụ MCP
            )

            async for item in wrap_stream_with_heartbeat(stream, heartbeat_interval=15.0):
                if item is HEARTBEAT:
                    yield await SSEResponse.send_heartbeat()
                    continue
                yield await SSEResponse.send_chunk(item)

            yield await SSEResponse.send_progress("Hoàn tất trả lời", 100, "success")
            yield await SSEResponse.send_done()

        except Exception as e:
            logger.error(f"Tạo trò chuyện Skill thất bại: {e}")
            yield await SSEResponse.send_error(f"Tạo thất bại: {str(e)}")

    return create_sse_response(generate())


# ==================== API quản trị Skill CRUD ====================

@router.get("/detail/{skill_key:path}")
async def get_skill_detail_api(skill_key: str, user: User = Depends(require_login)):
    """Lấy thông tin chi tiết Skill (gồm nội dung gốc và references)"""
    detail = get_skill_detail(skill_key)
    if not detail:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Không tìm thấy Skill: {skill_key}")

    return {
        "template_key": detail["template_key"],
        "name": detail.get("name", ""),
        "template_name": detail["template_name"],
        "display_name": detail.get("display_name", detail["template_name"]),
        "category": detail["category"],
        "description": detail["description"],
        "triggers": detail.get("triggers", []),
        "body": _get_skill_body(detail.get("raw_content", "")),
        "raw_content": detail.get("raw_content", ""),
        "standalone_references": detail.get("standalone_references", {}),
    }


@router.post("/create")
async def create_skill(request: SkillCreateRequest, user: User = Depends(require_login)):
    """Tạo Skill mới"""
    try:
        result = create_skill_files(
            name=request.name,
            display_name=request.display_name,
            category=request.category,
            description=request.description,
            triggers=request.triggers,
            body=request.body,
            references=request.references,
        )
        return {"success": True, "skill": result}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Tạo Skill thất bại: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Tạo thất bại: {str(e)}")


@router.put("/update/{skill_key:path}")
async def update_skill(skill_key: str, request: SkillUpdateRequest, user: User = Depends(require_login)):
    """Cập nhật Skill"""
    try:
        result = update_skill_files(
            skill_key=skill_key,
            display_name=request.display_name,
            category=request.category,
            description=request.description,
            triggers=request.triggers,
            body=request.body,
            references=request.references,
        )
        return {"success": True, "skill": result}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Cập nhật Skill thất bại: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Cập nhật thất bại: {str(e)}")


@router.delete("/delete/{skill_key:path}")
async def delete_skill(skill_key: str, user: User = Depends(require_login)):
    """Xóa Skill"""
    try:
        delete_skill_files(skill_key)
        return {"success": True, "message": f"Đã xóa Skill: {skill_key}"}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Xóa Skill thất bại: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Xóa thất bại: {str(e)}")


@router.post("/refresh-cache")
async def refresh_cache(user: User = Depends(require_login)):
    """Làm mới cache Skill thủ công"""
    skills = refresh_skills_cache()
    return {"success": True, "count": len(skills)}
