"""API chế độ cảm hứng - tạo dự án thông qua đối thoại dẫn dắt"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import json

from app.database import get_db
from app.services.ai_service import AIService
from app.services.json_helper import loads_json
from app.api.settings import get_user_ai_service
from app.services.prompt_service import PromptService
from app.logger import get_logger

router = APIRouter(prefix="/inspiration", tags=["Chế độ cảm hứng"])
logger = get_logger(__name__)


# Cài đặt temperature cho từng giai đoạn (giảm dần để giữ tính nhất quán)
TEMPERATURE_SETTINGS = {
    "title": 0.8,        # Giai đoạn tên sách có thể sáng tạo hơn
    "description": 0.65, # Giới thiệu cần bám sát tên sách và ý tưởng ban đầu
    "theme": 0.55,       # Chủ đề cần bám sát hơn nữa
    "genre": 0.45        # Thể loại nên rõ ràng
}


def validate_options_response(result: Dict[str, Any], step: str, max_retries: int = 3) -> tuple[bool, str]:
    """
    Kiểm tra định dạng các lựa chọn mà AI trả về có đúng không

    Returns:
        (is_valid, error_message)
    """
    # Kiểm tra các trường bắt buộc
    if "options" not in result:
        return False, "Thiếu trường options"

    options = result.get("options", [])

    # Kiểm tra options có phải mảng không
    if not isinstance(options, list):
        return False, "options phải là mảng"

    # Kiểm tra độ dài mảng
    if len(options) < 3:
        return False, f"Số lựa chọn không đủ, cần ít nhất 3, hiện chỉ có {len(options)}"

    if len(options) > 10:
        return False, f"Số lựa chọn quá nhiều, tối đa 10, hiện có {len(options)}"

    # Kiểm tra mỗi lựa chọn có phải chuỗi không rỗng không
    for i, option in enumerate(options):
        if not isinstance(option, str):
            return False, f"Lựa chọn thứ {i+1} không phải kiểu chuỗi"
        if not option.strip():
            return False, f"Lựa chọn thứ {i+1} trống"
        if len(option) > 500:
            return False, f"Lựa chọn thứ {i+1} quá dài (vượt quá 500 ký tự)"

    # Kiểm tra đặc thù theo từng bước
    if step == "genre":
        # Nhãn thể loại nên ngắn
        for i, option in enumerate(options):
            if len(option) > 10:
                return False, f"Nhãn thể loại [{option}] quá dài, nên trong khoảng 2-10 ký tự"

    return True, ""


@router.post("/generate-options")
async def generate_options(
    data: Dict[str, Any],
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_user_ai_service)
) -> Dict[str, Any]:
    """
    Tạo gợi ý lựa chọn cho bước tiếp theo dựa trên thông tin đã thu thập (kèm tự động thử lại)

    Request:
        {
            "step": "title",  // title/description/theme/genre
            "context": {
                "title": "...",
                "description": "...",
                "theme": "..."
            }
        }

    Response:
        {
            "prompt": "Câu dẫn dắt",
            "options": ["Lựa chọn 1", "Lựa chọn 2", ...]
        }
    """
    max_retries = 3

    for attempt in range(max_retries):
        try:
            step = data.get("step", "title")
            context = data.get("context", {})

            logger.info(f"Chế độ cảm hứng: tạo lựa chọn cho giai đoạn {step} (lần thử thứ {attempt + 1})")

            # Lấy ID người dùng
            user_id = getattr(http_request.state, 'user_id', None)

            # Lấy template prompt tương ứng (xác định key template theo step)
            # Cấu trúc mới: mỗi bước có template SYSTEM và USER riêng
            template_key_map = {
                "title": ("INSPIRATION_TITLE_SYSTEM", "INSPIRATION_TITLE_USER"),
                "description": ("INSPIRATION_DESCRIPTION_SYSTEM", "INSPIRATION_DESCRIPTION_USER"),
                "theme": ("INSPIRATION_THEME_SYSTEM", "INSPIRATION_THEME_USER"),
                "genre": ("INSPIRATION_GENRE_SYSTEM", "INSPIRATION_GENRE_USER")
            }
            template_keys = template_key_map.get(step)

            if not template_keys:
                return {
                    "error": f"Bước không được hỗ trợ: {step}",
                    "prompt": "",
                    "options": []
                }

            system_key, user_key = template_keys

            # Lấy template prompt tùy chỉnh (lần lượt lấy system và user)
            system_template = await PromptService.get_template(system_key, user_id, db)
            user_template = await PromptService.get_template(user_key, user_id, db)

            # Chuẩn bị tham số định dạng
            format_params = {
                "initial_idea": context.get("initial_idea", context.get("description", "")),
                "title": context.get("title", ""),
                "description": context.get("description", ""),
                "theme": context.get("theme", "")
            }

            # Định dạng prompt
            system_prompt = system_template.format(**format_params)
            user_prompt = user_template.format(**format_params)

            # Nếu thử lại, nhấn mạnh yêu cầu định dạng trong prompt
            if attempt > 0:
                system_prompt += f"\n\nCảnh báo: đây là lần tạo thứ {attempt + 1}, hãy tuân thủ nghiêm ngặt định dạng JSON trả về, đảm bảo mảng options chứa 6 lựa chọn hợp lệ!"

            # Gọi AI tạo lựa chọn
            # Cải tiến quan trọng: dùng temperature giảm dần để giữ tính nhất quán của các giai đoạn sau với phần trước
            temperature = TEMPERATURE_SETTINGS.get(step, 0.7)
            logger.info(f"Gọi AI tạo lựa chọn {step}... (temperature={temperature})")

            # Tạo stream và tích lũy text
            accumulated_text = ""
            async for chunk in ai_service.generate_text_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature
            ):
                accumulated_text += chunk

            response = {"content": accumulated_text}
            content = accumulated_text
            logger.info(f"Độ dài nội dung AI trả về: {len(content)}")

            # Phân tích JSON (dùng phương pháp làm sạch JSON thống nhất)
            try:
                # Dùng phương pháp làm sạch JSON thống nhất
                cleaned_content = ai_service._clean_json_response(content)

                result = loads_json(cleaned_content)

                # Kiểm tra định dạng trả về
                is_valid, error_msg = validate_options_response(result, step)

                if not is_valid:
                    logger.warning(f"Cảnh báo: lần tạo thứ {attempt + 1} kiểm tra định dạng thất bại: {error_msg}")
                    if attempt < max_retries - 1:
                        logger.info("Chuẩn bị thử lại...")
                        continue  # Thử lại
                    else:
                        # Lần thử cuối cùng cũng thất bại
                        return {
                            "prompt": f"Vui lòng cung cấp nội dung cho [{step}]:",
                            "options": ["Để AI tạo lại", "Tự nhập"],
                            "error": f"Định dạng AI tạo sai ({error_msg}), đã tự động thử lại {max_retries} lần, vui lòng thử lại thủ công hoặc tự nhập"
                        }

                logger.info(f"Thành công: lần thứ {attempt + 1} đã tạo {len(result.get('options', []))} lựa chọn hợp lệ")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Lần thứ {attempt + 1} phân tích JSON thất bại: {e}")

                if attempt < max_retries - 1:
                    logger.info("Phân tích JSON thất bại, chuẩn bị thử lại...")
                    continue  # Thử lại
                else:
                    # Lần thử cuối cùng cũng thất bại
                    return {
                        "prompt": f"Vui lòng cung cấp nội dung cho [{step}]:",
                        "options": ["Để AI tạo lại", "Tự nhập"],
                        "error": f"Định dạng AI trả về sai, đã tự động thử lại {max_retries} lần, vui lòng thử lại thủ công hoặc tự nhập"
                    }

        except Exception as e:
            logger.error(f"Lần tạo thứ {attempt + 1} thất bại: {e}", exc_info=True)
            if attempt < max_retries - 1:
                logger.info("Gặp ngoại lệ, chuẩn bị thử lại...")
                continue
            else:
                return {
                    "error": str(e),
                    "prompt": "Tạo thất bại, vui lòng thử lại",
                    "options": ["Tạo lại", "Tự nhập"]
                }

    # Về lý thuyết không bao giờ đến đây
    return {
        "error": "Tạo thất bại",
        "prompt": "Vui lòng thử lại",
        "options": []
    }


@router.post("/refine-options")
async def refine_options(
    data: Dict[str, Any],
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_user_ai_service)
) -> Dict[str, Any]:
    """
    Tạo lại lựa chọn dựa trên phản hồi của người dùng (hỗ trợ đối thoại nhiều vòng)

    Request:
        {
            "step": "title",  // Bước hiện tại
            "context": {
                "initial_idea": "...",
                "title": "...",
                "description": "...",
                "theme": "..."
            },
            "feedback": "Tôi muốn chủ đề bi thương hơn",  // Phản hồi của người dùng
            "previous_options": ["Lựa chọn 1", "Lựa chọn 2", ...]  // Các lựa chọn trước (tùy chọn)
        }

    Response:
        {
            "prompt": "Câu dẫn dắt",
            "options": ["Lựa chọn mới 1", "Lựa chọn mới 2", ...]
        }
    """
    max_retries = 3

    for attempt in range(max_retries):
        try:
            step = data.get("step", "title")
            context = data.get("context", {})
            feedback = data.get("feedback", "")
            previous_options = data.get("previous_options", [])

            logger.info(f"Chế độ cảm hứng: tạo lại lựa chọn giai đoạn {step} theo phản hồi (lần thử thứ {attempt + 1})")
            logger.info(f"Phản hồi người dùng: {feedback}")

            # Lấy ID người dùng
            user_id = getattr(http_request.state, 'user_id', None)

            # Lấy template prompt tương ứng
            template_key_map = {
                "title": ("INSPIRATION_TITLE_SYSTEM", "INSPIRATION_TITLE_USER"),
                "description": ("INSPIRATION_DESCRIPTION_SYSTEM", "INSPIRATION_DESCRIPTION_USER"),
                "theme": ("INSPIRATION_THEME_SYSTEM", "INSPIRATION_THEME_USER"),
                "genre": ("INSPIRATION_GENRE_SYSTEM", "INSPIRATION_GENRE_USER")
            }
            template_keys = template_key_map.get(step)

            if not template_keys:
                return {
                    "error": f"Bước không được hỗ trợ: {step}",
                    "prompt": "",
                    "options": []
                }

            system_key, user_key = template_keys

            # Lấy template prompt tùy chỉnh
            system_template = await PromptService.get_template(system_key, user_id, db)
            user_template = await PromptService.get_template(user_key, user_id, db)

            # Chuẩn bị tham số định dạng
            format_params = {
                "initial_idea": context.get("initial_idea", context.get("description", "")),
                "title": context.get("title", ""),
                "description": context.get("description", ""),
                "theme": context.get("theme", "")
            }

            # Định dạng prompt
            system_prompt = system_template.format(**format_params)
            user_prompt = user_template.format(**format_params)

            # Thêm thông tin phản hồi vào prompt
            feedback_instruction = f"""

Cảnh báo: người dùng chưa hài lòng với các lựa chọn trước và đã đưa ra phản hồi sau:
「{feedback}」

Các lựa chọn đã tạo trước đó:
{chr(10).join([f"- {opt}" for opt in previous_options]) if previous_options else "(không có)"}

Hãy điều chỉnh chiến lược tạo theo phản hồi của người dùng, cung cấp các lựa chọn mới phù hợp hơn với mong đợi của người dùng.
Lưu ý:
1. Hiểu kỹ ý định trong phản hồi của người dùng
2. Các lựa chọn mới phải thể hiện rõ hướng điều chỉnh mà người dùng yêu cầu
3. Giữ tính nhất quán với ngữ cảnh hiện có
4. Đảm bảo trả về 6 lựa chọn hợp lệ
"""

            system_prompt += feedback_instruction

            # Nếu thử lại, nhấn mạnh yêu cầu định dạng
            if attempt > 0:
                system_prompt += f"\n\nCảnh báo: đây là lần tạo thứ {attempt + 1}, hãy tuân thủ nghiêm ngặt định dạng JSON trả về!"

            # Gọi AI tạo lựa chọn
            temperature = TEMPERATURE_SETTINGS.get(step, 0.7)
            # Khi tạo theo phản hồi dùng temperature cao hơn một chút để có kết quả đa dạng hơn
            temperature = min(temperature + 0.1, 0.9)
            logger.info(f"Gọi AI tạo lựa chọn {step} theo phản hồi... (temperature={temperature})")

            # Tạo stream và tích lũy text
            accumulated_text = ""
            async for chunk in ai_service.generate_text_stream(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temperature
            ):
                accumulated_text += chunk

            content = accumulated_text
            logger.info(f"Độ dài nội dung AI trả về: {len(content)}")

            # Phân tích JSON
            try:
                cleaned_content = ai_service._clean_json_response(content)
                result = loads_json(cleaned_content)

                # Kiểm tra định dạng trả về
                is_valid, error_msg = validate_options_response(result, step)

                if not is_valid:
                    logger.warning(f"Cảnh báo: lần tạo thứ {attempt + 1} kiểm tra định dạng thất bại: {error_msg}")
                    if attempt < max_retries - 1:
                        logger.info("Chuẩn bị thử lại...")
                        continue
                    else:
                        return {
                            "prompt": f"Vui lòng cung cấp nội dung cho [{step}]:",
                            "options": ["Để AI tạo lại", "Tự nhập"],
                            "error": f"Định dạng AI tạo sai ({error_msg}), đã tự động thử lại {max_retries} lần"
                        }

                logger.info(f"Thành công: lần thứ {attempt + 1} theo phản hồi đã tạo {len(result.get('options', []))} lựa chọn hợp lệ")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Lần thứ {attempt + 1} phân tích JSON thất bại: {e}")

                if attempt < max_retries - 1:
                    logger.info("Phân tích JSON thất bại, chuẩn bị thử lại...")
                    continue
                else:
                    return {
                        "prompt": f"Vui lòng cung cấp nội dung cho [{step}]:",
                        "options": ["Để AI tạo lại", "Tự nhập"],
                        "error": f"Định dạng AI trả về sai, đã tự động thử lại {max_retries} lần"
                    }

        except Exception as e:
            logger.error(f"Lần thứ {attempt + 1} tạo theo phản hồi thất bại: {e}", exc_info=True)
            if attempt < max_retries - 1:
                logger.info("Gặp ngoại lệ, chuẩn bị thử lại...")
                continue
            else:
                return {
                    "error": str(e),
                    "prompt": "Tạo thất bại, vui lòng thử lại",
                    "options": ["Tạo lại", "Tự nhập"]
                }

    return {
        "error": "Tạo thất bại",
        "prompt": "Vui lòng thử lại",
        "options": []
    }


@router.post("/quick-generate")
async def quick_generate(
    data: Dict[str, Any],
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    ai_service: AIService = Depends(get_user_ai_service)
) -> Dict[str, Any]:
    """
    Tự động hoàn thiện thông minh: dựa trên một phần thông tin người dùng đã cung cấp, AI tự động hoàn thiện các trường còn thiếu

    Request:
        {
            "title": "Tên sách (tùy chọn)",
            "description": "Giới thiệu (tùy chọn)",
            "theme": "Chủ đề (tùy chọn)",
            "genre": ["Thể loại 1", "Thể loại 2"] (tùy chọn)
        }

    Response:
        {
            "title": "Tên sách đã hoàn thiện",
            "description": "Giới thiệu đã hoàn thiện",
            "theme": "Chủ đề đã hoàn thiện",
            "genre": ["Thể loại đã hoàn thiện"]
        }
    """
    try:
        logger.info("Chế độ cảm hứng: tự động hoàn thiện thông minh")

        # Lấy ID người dùng
        user_id = getattr(http_request.state, 'user_id', None)

        # Xây dựng prompt hoàn thiện
        existing_info = []
        if data.get("title"):
            existing_info.append(f"- Tên sách: {data['title']}")
        if data.get("description"):
            existing_info.append(f"- Giới thiệu: {data['description']}")
        if data.get("theme"):
            existing_info.append(f"- Chủ đề: {data['theme']}")
        if data.get("genre"):
            existing_info.append(f"- Thể loại: {', '.join(data['genre'])}")

        existing_text = "\n".join(existing_info) if existing_info else "Chưa có thông tin"

        # Lấy template prompt tùy chỉnh
        system_template = await PromptService.get_template("INSPIRATION_QUICK_COMPLETE", user_id, db)

        # Định dạng prompt
        prompts = {
            "system": PromptService.format_prompt(system_template, existing=existing_text),
            "user": "Vui lòng hoàn thiện thông tin tiểu thuyết"
        }

        # Gọi AI - tạo stream và tích lũy text
        accumulated_text = ""
        async for chunk in ai_service.generate_text_stream(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=0.7
        ):
            accumulated_text += chunk

        response = {"content": accumulated_text}
        content = accumulated_text

        # Phân tích JSON (dùng phương pháp làm sạch JSON thống nhất)
        try:
            # Dùng phương pháp làm sạch JSON thống nhất
            cleaned_content = ai_service._clean_json_response(content)

            result = loads_json(cleaned_content)

            # Gộp thông tin người dùng đã cung cấp (ưu tiên input của người dùng)
            final_result = {
                "title": data.get("title") or result.get("title", ""),
                "description": data.get("description") or result.get("description", ""),
                "theme": data.get("theme") or result.get("theme", ""),
                "genre": data.get("genre") or result.get("genre", [])
            }

            logger.info(f"Thành công: tự động hoàn thiện thông minh")
            return final_result

        except json.JSONDecodeError as e:
            logger.error(f"Phân tích JSON thất bại: {e}")
            raise Exception("Định dạng AI trả về sai, vui lòng thử lại")

    except Exception as e:
        logger.error(f"Tự động hoàn thiện thông minh thất bại: {e}", exc_info=True)
        return {
            "error": str(e)
        }
