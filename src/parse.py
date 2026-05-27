"""把简历文件转成纯文字字符串，用于发给 DeepSeek（纯文字模型）。

支持：PDF（有文字层）/ Word / txt / md
不支持：图片简历、扫描件（DeepSeek V3 无多模态，需单独加 OCR 才能处理）
"""

from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXTS = {".txt", ".md"}


def build_content_blocks(file_path: str) -> list:
    """返回单元素列表，内容是纯文字 block，与旧接口保持兼容。"""
    return [{"type": "text", "text": extract_text(file_path)}]


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _pdf_text(path)

    if ext in IMAGE_EXTS:
        raise ValueError(
            f"DeepSeek V3 不支持图片简历（{path.name}）。\n"
            "如需处理图片/扫描件，请先用 OCR 工具（如 pytesseract）转成文字再导入。"
        )

    if ext == ".docx":
        return _docx_text(path)

    if ext in TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"不支持的文件类型: {ext}（支持 pdf/docx/txt/md）")


def _pdf_text(path: Path) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(
            f"{path.name} 是扫描件或图片 PDF，没有文字层，无法直接读取。\n"
            "请先用 OCR 工具转成文字版 PDF 或 txt，再重试。"
        )
    return text


def _docx_text(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)
