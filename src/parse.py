"""把简历文件转成可发给 Claude 的 content block 列表。

PDF / 图片直接走多模态（含扫描件），省去单独装 OCR。
Word / 纯文本抽成文字块。
"""

import base64
import mimetypes
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXTS = {".txt", ".md"}


def build_content_blocks(file_path: str) -> list:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return [{
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }]

    if ext in IMAGE_EXTS:
        media = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return [{
            "type": "image",
            "source": {"type": "base64", "media_type": media, "data": data},
        }]

    if ext == ".docx":
        return [{"type": "text", "text": _docx_text(path)}]

    if ext in TEXT_EXTS:
        return [{"type": "text", "text": path.read_text(encoding="utf-8", errors="ignore")}]

    raise ValueError(f"不支持的文件类型: {ext}（支持 pdf/docx/txt/md 及常见图片）")


def _docx_text(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)
