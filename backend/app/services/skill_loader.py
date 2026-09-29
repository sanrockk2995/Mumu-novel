"""Bộ tải prompt Skill

Tải động Skill định dạng oh-story-claudecode từ thư mục backend/app/skills/,
chuyển thành template mặc định của hệ thống tương thích với PromptService.

Cấu trúc thư mục mỗi Skill:
  skills/{skill_name}/
  ├── SKILL.md          # Metadata YAML + chỉ thị workflow đầy đủ
  └── references/       # Kho tri thức tham khảo (tùy chọn)
      ├── xxx.md
      └── ...
"""

import os
import re
from typing import Any, List, Dict, Optional
import yaml
from app.logger import get_logger

logger = get_logger(__name__)

# Đường dẫn thư mục Skills: backend/app/skills/ (file này nằm ở backend/app/services/)
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills")


class _SkillYamlDumper(yaml.SafeDumper):
    pass


class _LiteralString(str):
    pass


def _literal_string_representer(dumper: yaml.SafeDumper, data: _LiteralString):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


_SkillYamlDumper.add_representer(_LiteralString, _literal_string_representer)


def _parse_yaml_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter ở đầu SKILL.md"""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}

    yaml_text = match.group(1)

    try:
        metadata = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Parse YAML frontmatter của Skill thất bại: {e}")
        return {}

    if not isinstance(metadata, dict):
        return {}

    result: Dict[str, Any] = {}
    for key in ("name", "display_name", "category", "description", "triggers"):
        value = metadata.get(key)
        if key == "triggers" and isinstance(value, list):
            result[key] = [str(item).strip() for item in value if str(item).strip()]
        elif value is not None:
            result[key] = str(value).strip()

    return result


def _template_key(name: str) -> str:
    return f"SKILL_{name.upper().replace('-', '_')}"


def _display_name_from_description(description: str, fallback: str) -> str:
    first_line = description.strip().splitlines()[0].strip() if description.strip() else ""
    if "。" in first_line:
        return first_line.split("。")[0].strip() or fallback
    return first_line or fallback


def _infer_category(name: str) -> str:
    if "long" in name:
        return "Skill·Truyện dài"
    if "short" in name:
        return "Skill·Truyện ngắn"
    if "deslop" in name:
        return "Skill·Trau chuốt"
    if "browser" in name:
        return "Skill·Công cụ"
    return "Skill"


def _extract_triggers(name: str, description: str, explicit_triggers: Any = None) -> List[str]:
    """Lấy từ kích hoạt, ưu tiên dùng triggers có cấu trúc, file cũ thì trích tương thích từ mô tả."""
    triggers: List[str] = []

    if isinstance(explicit_triggers, list):
        triggers.extend(str(item).strip() for item in explicit_triggers if str(item).strip())
    elif isinstance(explicit_triggers, str) and explicit_triggers.strip():
        triggers.extend(item.strip() for item in re.split(r'[\n,，、]+', explicit_triggers) if item.strip())

    if not triggers:
        triggers.append(f"/{name}")
        triggers.extend(re.findall(r'「(.+?)」', description))
        triggers.extend(match.group(1) for match in re.finditer(r'(?:^|[\s、，,。；;：:])(/[^\s、，,。；;：:「」]+)', description))

    if f"/{name}" not in triggers:
        triggers.insert(0, f"/{name}")

    return list(dict.fromkeys(triggers))


def _format_skill_frontmatter(metadata: Dict[str, Any]) -> str:
    data = {
        "name": metadata.get("name", ""),
        "display_name": metadata.get("display_name", ""),
        "category": metadata.get("category", "Skill"),
        "description": _LiteralString(metadata.get("description", "")),
        "triggers": metadata.get("triggers", []),
    }
    yaml_text = yaml.dump(
        data,
        Dumper=_SkillYamlDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{yaml_text}\n---"


def _get_skill_body(content: str) -> str:
    """Lấy nội dung sau YAML frontmatter trong SKILL.md (tức chỉ thị workflow)"""
    match = re.match(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
    if match:
        return content[match.end():].strip()
    return content.strip()


def _get_references(skill_dir: str) -> Dict[str, str]:
    """Đọc mọi file .md trong references/ ở thư mục skill"""
    refs_dir = os.path.join(skill_dir, "references")
    references = {}
    
    if not os.path.isdir(refs_dir):
        return references
    
    for filename in sorted(os.listdir(refs_dir)):
        if filename.endswith('.md'):
            filepath = os.path.join(refs_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    ref_name = filename[:-3]  # Bỏ hậu tố .md
                    references[ref_name] = f.read().strip()
            except Exception as e:
                logger.warning(f"Đọc file tham khảo thất bại: {filepath}, lỗi: {e}")
    
    return references


def load_skills() -> List[Dict]:
    """
    Tải mọi Skill từ thư mục skills, trả về danh sách template.
    Định dạng nhất quán với giá trị trả về của PromptService.get_all_system_templates().
    
    Returns:
        List[Dict]: danh sách template Skill, mỗi cái gồm:
            - template_key: tên key template (SKILL_{name})
            - template_name: tên hiển thị
            - category: phân loại ("Skill")
            - description: mô tả
            - parameters: danh sách tham số
            - content: nội dung chỉ thị workflow đầy đủ
            - references: dict kho tri thức tham khảo
            - triggers: danh sách từ kích hoạt
    """
    skills = []
    
    if not os.path.isdir(SKILLS_DIR):
        logger.warning(f"Thư mục Skills không tồn tại: {SKILLS_DIR}")
        return skills
    
    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, skill_name)
        if not os.path.isdir(skill_dir):
            continue
        
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        if not os.path.isfile(skill_md_path):
            continue
        
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            metadata = _parse_yaml_frontmatter(content)
            
            # Lấy chỉ thị workflow (bỏ phần YAML)
            body = _get_skill_body(content)
            
            # Đọc kho tri thức tham khảo
            references = _get_references(skill_dir)
            
            name = metadata.get('name', skill_name)
            desc = metadata.get('description', '')
            display_name = metadata.get('display_name') or _display_name_from_description(desc, name)
            category = metadata.get('category') or _infer_category(name)
            triggers = _extract_triggers(name, desc, metadata.get('triggers'))
            
            # Nối kho tri thức tham khảo vào nội dung (làm phụ lục tải theo nhu cầu)
            if references:
                ref_section = "\n\n---\n\n## Phụ lục: Kho tri thức tài liệu tham khảo\n"
                ref_section += "(Nội dung dưới đây trích dẫn theo nhu cầu người dùng, không cần dùng toàn bộ)\n"
                for ref_name, ref_content in references.items():
                    ref_section += f"\n### Tài liệu tham khảo: {ref_name}\n\n{ref_content}\n"
                full_content = body + ref_section
            else:
                full_content = body
            
            skill_template = {
                "template_key": _template_key(name),
                "name": name,
                "template_name": display_name,
                "display_name": display_name,
                "category": category,
                "description": desc,
                "parameters": ["user_input"],
                "content": full_content,
                "references": references,
                "triggers": triggers,
                "is_skill": True,
            }
            
            skills.append(skill_template)
            logger.info(f"Tải Skill: {name} (Phân loại: {category}, Tham khảo: {len(references)} mục)")
            
        except Exception as e:
            logger.error(f"Tải Skill thất bại: {skill_name}, lỗi: {e}")
    
    return skills


def get_skill_by_trigger(user_input: str) -> Optional[Dict]:
    """
    Khớp Skill tương ứng theo input người dùng
    
    Args:
        user_input: văn bản người dùng nhập
        
    Returns:
        Template Skill khớp được, không khớp trả về None
    """
    skills = load_skills()
    user_input_lower = user_input.lower().strip()
    
    for skill in skills:
        triggers = skill.get('triggers', [])
        for trigger in triggers:
            trigger_lower = trigger.lower()
            # Khớp chính xác từ kích hoạt
            if user_input_lower == trigger_lower:
                return skill
            # Input người dùng bắt đầu bằng từ kích hoạt
            if user_input_lower.startswith(trigger_lower):
                return skill
    
    # Khớp mờ ngôn ngữ tự nhiên
    keyword_map = {
        "viết truyện dài": ["SKILL_STORY_LONG_WRITE"],
        "viết tiểu thuyết dài": ["SKILL_STORY_LONG_WRITE"],
        "giúp tôi mở sách mới": ["SKILL_STORY_LONG_WRITE"],
        "viết dàn ý": ["SKILL_STORY_LONG_WRITE"],
        "viết truyện ngắn": ["SKILL_STORY_SHORT_WRITE"],
        "viết đoản văn": ["SKILL_STORY_SHORT_WRITE"],
        "viết truyện diêm ngôn": ["SKILL_STORY_SHORT_WRITE"],
        "phân tích truyện dài": ["SKILL_STORY_LONG_ANALYZE"],
        "mổ xẻ sách": ["SKILL_STORY_LONG_ANALYZE"],
        "phân tích ba chương vàng": ["SKILL_STORY_LONG_ANALYZE"],
        "phân tích truyện ngắn": ["SKILL_STORY_SHORT_ANALYZE"],
        "phân tích đoản văn": ["SKILL_STORY_SHORT_ANALYZE"],
        "quét bảng xếp hạng truyện dài": ["SKILL_STORY_LONG_SCAN"],
        "truyện dài nào đang hot": ["SKILL_STORY_LONG_SCAN"],
        "bảng xếp hạng Qidian": ["SKILL_STORY_LONG_SCAN"],
        "quét bảng xếp hạng truyện ngắn": ["SKILL_STORY_SHORT_SCAN"],
        "truyện ngắn nào đang hot": ["SKILL_STORY_SHORT_SCAN"],
        "khử mùi AI": ["SKILL_STORY_DESLOP"],
        "khử mùi": ["SKILL_STORY_DESLOP"],
        "quá mùi AI": ["SKILL_STORY_DESLOP"],
        "trau chuốt": ["SKILL_STORY_DESLOP"],
        "trình duyệt": ["SKILL_BROWSER_CDP"],
    }
    
    for keyword, skill_keys in keyword_map.items():
        if keyword in user_input_lower:
            for skill in skills:
                if skill['template_key'] in skill_keys:
                    return skill
    
    return None


# Cache tải trước
_skills_cache = None

def get_all_skills_cached() -> List[Dict]:
    """Lấy mọi Skills (có cache)"""
    global _skills_cache
    if _skills_cache is None:
        _skills_cache = load_skills()
    return _skills_cache

def refresh_skills_cache():
    """Làm mới cache Skills"""
    global _skills_cache
    _skills_cache = load_skills()
    return _skills_cache


def get_skill_detail(skill_key: str) -> Optional[Dict]:
    """Lấy chi tiết đầy đủ của Skill theo template_key (gồm nội dung SKILL.md gốc và references độc lập)"""
    skills = get_all_skills_cached()
    for s in skills:
        if s["template_key"] == skill_key:
            # Tìm thư mục tương ứng
            skill_name = skill_key.replace("SKILL_", "").lower().replace("_", "-")
            skill_dir = os.path.join(SKILLS_DIR, skill_name)
            if not os.path.isdir(skill_dir):
                # Thử lấy từ field name
                for d in os.listdir(SKILLS_DIR):
                    d_path = os.path.join(SKILLS_DIR, d)
                    if os.path.isdir(d_path):
                        md_path = os.path.join(d_path, "SKILL.md")
                        if os.path.isfile(md_path):
                            try:
                                with open(md_path, 'r', encoding='utf-8') as f:
                                    meta = _parse_yaml_frontmatter(f.read())
                                if f"SKILL_{meta.get('name', '').upper().replace('-', '_')}" == skill_key:
                                    skill_dir = d_path
                                    break
                            except:
                                pass

            # Đọc SKILL.md gốc
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            raw_content = ""
            if os.path.isfile(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()

            # Đọc references độc lập (không nối vào content)
            standalone_refs = {}
            refs_dir = os.path.join(skill_dir, "references")
            if os.path.isdir(refs_dir):
                for filename in sorted(os.listdir(refs_dir)):
                    if filename.endswith('.md'):
                        filepath = os.path.join(refs_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                standalone_refs[filename[:-3]] = f.read()
                        except:
                            pass

            return {
                **s,
                "raw_content": raw_content,
                "standalone_references": standalone_refs,
                "skill_dir": skill_dir,
            }
    return None


def _validate_skill_metadata(name: str, display_name: str, category: str, description: str, triggers: List[str], body: str):
    if not name.strip():
        raise ValueError("Định danh nội bộ của Skill không được để trống")
    if not re.fullmatch(r'[a-z0-9][a-z0-9\-]*', name.strip()):
        raise ValueError("Định danh nội bộ của Skill chỉ được chứa chữ thường, số và dấu gạch ngang, và phải bắt đầu bằng chữ cái hoặc số")
    if not display_name.strip():
        raise ValueError("Tên hiển thị không được để trống")
    if not category.strip():
        raise ValueError("Phân loại không được để trống")
    if not description.strip():
        raise ValueError("Mô tả không được để trống")
    if not body.strip():
        raise ValueError("Chỉ thị workflow không được để trống")
    if not triggers:
        raise ValueError("Cần ít nhất một từ kích hoạt")


def create_skill_files(
    name: str,
    description: str,
    body: str,
    references: Optional[Dict[str, str]] = None,
    display_name: Optional[str] = None,
    category: Optional[str] = None,
    triggers: Optional[List[str]] = None,
) -> Dict:
    """Tạo file Skill mới"""
    import re
    name = name.strip().lower().replace("_", "-").replace(" ", "-")
    display_name = (display_name or _display_name_from_description(description, name)).strip()
    category = (category or _infer_category(name)).strip()
    triggers = _extract_triggers(name, description, triggers)
    _validate_skill_metadata(name, display_name, category, description, triggers, body)

    # Tên thư mục: chữ thường + dấu gạch ngang
    dir_name = name
    dir_name = re.sub(r'[^a-z0-9\-]', '', dir_name)
    if not dir_name:
        dir_name = "new-skill"
    
    skill_dir = os.path.join(SKILLS_DIR, dir_name)
    if os.path.exists(skill_dir):
        raise ValueError(f"Thư mục Skill đã tồn tại: {dir_name}")
    
    os.makedirs(skill_dir, exist_ok=True)
    
    frontmatter = _format_skill_frontmatter({
        "name": name,
        "display_name": display_name,
        "category": category,
        "description": description.strip(),
        "triggers": triggers,
    })
    skill_md_content = f"{frontmatter}\n\n{body.strip()}"
    
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, 'w', encoding='utf-8') as f:
        f.write(skill_md_content)
    
    # Tạo references
    if references:
        refs_dir = os.path.join(skill_dir, "references")
        os.makedirs(refs_dir, exist_ok=True)
        for ref_name, ref_content in references.items():
            ref_path = os.path.join(refs_dir, f"{ref_name}.md")
            with open(ref_path, 'w', encoding='utf-8') as f:
                f.write(ref_content)
    
    # Làm mới cache
    refresh_skills_cache()
    
    # Trả về skill mới tạo
    skills = get_all_skills_cached()
    for s in skills:
        if s["template_key"] == _template_key(name):
            return s
    return {"template_key": _template_key(name), "template_name": display_name, "category": category}


def update_skill_files(
    skill_key: str,
    description: Optional[str] = None,
    body: Optional[str] = None,
    references: Optional[Dict[str, str]] = None,
    display_name: Optional[str] = None,
    category: Optional[str] = None,
    triggers: Optional[List[str]] = None,
) -> Dict:
    """Cập nhật file Skill đã có"""
    detail = get_skill_detail(skill_key)
    if not detail:
        raise ValueError(f"Không tìm thấy Skill: {skill_key}")
    
    skill_dir = detail.get("skill_dir", "")
    if not skill_dir or not os.path.isdir(skill_dir):
        raise ValueError(f"Thư mục Skill không tồn tại: {skill_dir}")
    
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    
    # Đọc nội dung hiện có
    with open(skill_md_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    
    # Parse metadata hiện có
    metadata = _parse_yaml_frontmatter(raw)
    name = metadata.get('name', '')
    
    # Cập nhật SKILL.md
    final_desc = description if description is not None else metadata.get('description', '')
    final_body = body if body is not None else _get_skill_body(raw)
    final_display_name = display_name if display_name is not None else metadata.get('display_name') or _display_name_from_description(final_desc, name)
    final_category = category if category is not None else metadata.get('category') or _infer_category(name)
    final_triggers = _extract_triggers(name, final_desc, triggers if triggers is not None else metadata.get('triggers'))
    _validate_skill_metadata(name, final_display_name, final_category, final_desc, final_triggers, final_body)

    frontmatter = _format_skill_frontmatter({
        "name": name,
        "display_name": final_display_name.strip(),
        "category": final_category.strip(),
        "description": final_desc.strip(),
        "triggers": final_triggers,
    })
    new_content = f"{frontmatter}\n\n{final_body.strip()}"
    
    with open(skill_md_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # Cập nhật references
    if references is not None:
        refs_dir = os.path.join(skill_dir, "references")
        # Xóa file reference cũ
        if os.path.isdir(refs_dir):
            for f in os.listdir(refs_dir):
                if f.endswith('.md'):
                    os.remove(os.path.join(refs_dir, f))
        else:
            os.makedirs(refs_dir, exist_ok=True)
        
        # Ghi references mới
        for ref_name, ref_content in references.items():
            if ref_content.strip():  # Chỉ ghi nội dung không rỗng
                ref_path = os.path.join(refs_dir, f"{ref_name}.md")
                with open(ref_path, 'w', encoding='utf-8') as f:
                    f.write(ref_content)
    
    # Làm mới cache
    refresh_skills_cache()
    
    # Trả về chi tiết sau cập nhật
    return get_skill_detail(skill_key) or {}


def delete_skill_files(skill_key: str) -> bool:
    """Xóa thư mục Skill"""
    import shutil
    detail = get_skill_detail(skill_key)
    if not detail:
        raise ValueError(f"Không tìm thấy Skill: {skill_key}")
    
    skill_dir = detail.get("skill_dir", "")
    if not skill_dir or not os.path.isdir(skill_dir):
        raise ValueError(f"Thư mục Skill không tồn tại")
    
    shutil.rmtree(skill_dir)
    refresh_skills_cache()
    return True
