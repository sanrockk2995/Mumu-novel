"""API làm sạch văn phong AI - tính năng nổi bật cốt lõi"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.generation_history import GenerationHistory
from app.schemas.polish import PolishRequest, PolishResponse
from app.services.ai_service import AIService
from app.services.prompt_service import prompt_service, PromptService
from app.logger import get_logger
from app.api.settings import get_user_ai_service

router = APIRouter(prefix="/polish", tags=["Làm sạch văn phong AI"])
logger = get_logger(__name__)


@router.post("", response_model=PolishResponse, summary="Làm sạch văn phong AI")
async def polish_text(
    request: PolishRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Làm sạch văn phong AI - viết lại văn bản do AI tạo sao cho giống văn phong của tác giả con người hơn

    Chức năng cốt lõi:
    - Xóa dấu vết AI (cấu trúc liệt kê quá trau chuốt, biện pháp tu từ lặp lại, tổng kết máy móc)
    - Tăng tính con người (lời văn gần gũi, chi tiết không hoàn hảo, cảm xúc chân thật)
    - Tối ưu lối kể (nhịp điệu tự nhiên, từ vựng đơn giản, cảm giác thư thả)
    - Làm hội thoại gần gũi với đời sống hơn

    Đây là tính năng đặc sắc cốt lõi của dự án này!
    """
    try:
        # Lấy ID người dùng
        user_id = getattr(http_request.state, 'user_id', None)

        # Lấy mẫu prompt tùy chỉnh
        template = await PromptService.get_template("AI_DENOISING", user_id, db)
        # Định dạng prompt
        prompt = PromptService.format_prompt(
            template,
            original_text=request.original_text
        )

        logger.info(f"Bắt đầu xử lý làm sạch văn phong AI, độ dài văn bản gốc: {len(request.original_text)}")

        # Gọi AI để xử lý làm sạch
        polished_text = await user_ai_service.generate_text(
            prompt=prompt,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=len(request.original_text) * 2  # Dự phòng đủ token
        )

        # Tính số ký tự
        word_count_before = len(request.original_text)
        word_count_after = len(polished_text)

        logger.info(f"Hoàn tất làm sạch văn phong AI, độ dài sau xử lý: {word_count_after}")

        # Nếu có ID dự án, ghi vào lịch sử
        if request.project_id:
            history = GenerationHistory(
                project_id=request.project_id,
                generation_type="polish",
                prompt=f"Văn bản gốc: {request.original_text[:100]}...",
                result=polished_text,
                provider=request.provider or "default",
                model=request.model or "default"
            )
            db.add(history)
            await db.commit()

        return PolishResponse(
            original_text=request.original_text,
            polished_text=polished_text,
            word_count_before=word_count_before,
            word_count_after=word_count_after
        )

    except Exception as e:
        logger.error(f"Làm sạch văn phong AI thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Làm sạch văn phong AI thất bại: {str(e)}")


@router.post("/batch", summary="Làm sạch văn phong AI hàng loạt")
async def polish_batch(
    texts: list[str],
    project_id: int = None,
    provider: str = None,
    model: str = None,
    http_request: Request = None,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    Xử lý làm sạch văn phong AI cho nhiều văn bản

    Phù hợp khi xử lý một lần nhiều chương hoặc đoạn văn
    """
    try:
        # Lấy ID người dùng
        user_id = getattr(http_request.state, 'user_id', None) if http_request else None

        results = []

        for idx, text in enumerate(texts):
            logger.info(f"Đang xử lý văn bản thứ {idx+1}/{len(texts)}")

            # Lấy mẫu prompt tùy chỉnh
            template = await PromptService.get_template("AI_DENOISING", user_id, db)
            # Định dạng prompt
            prompt = PromptService.format_prompt(template, original_text=text)

            polished_text = await user_ai_service.generate_text(
                prompt=prompt,
                provider=provider,
                model=model
            )

            results.append({
                "index": idx,
                "original": text,
                "polished": polished_text,
                "word_count_before": len(text),
                "word_count_after": len(polished_text)
            })

        logger.info(f"Hoàn tất làm sạch văn phong AI hàng loạt, đã xử lý {len(results)} văn bản")

        return {
            "total": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Làm sạch văn phong AI hàng loạt thất bại: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Làm sạch văn phong AI hàng loạt thất bại: {str(e)}")
