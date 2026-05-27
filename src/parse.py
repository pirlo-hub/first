"""把简历文件转成可发给 DeepSeek V4-Pro 的 content block 列表。

支持：
  - PDF（有文字层）→ pdfplumber 抽文字（快、省 token）
  - PDF（扫描件/图片层）→ pymupdf 转图片后以 image_url 发送
  - 图片（jpg/png/webp 等）→ base64 image_url
  - Word / txt / md → 纯文字
"""

import base64
import mimetypes
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TEXT_EXTS = {".txt", ".md"}


def build_content_blocks(file_path: str) -> list:
    """返回 OpenAI vision 格式的 content block 列表。"""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _pdf_blocks(path)

    if ext in IMAGE_EXTS:
        return [_image_block(path)]

    if ext == ".docx":
        return [{"type": "text", "text": _docx_text(path)}]

    if ext in TEXT_EXTS:
        return [{"type": "text", "text": path.read_text(encoding="utf-8", errors="ignore")}]

    raise ValueError(f"不支持的文件类型: {ext}（支持 pdf/docx/txt/md 及常见图片）")


def extract_text(file_path: str) -> str:
    """兼容旧调用：返回纯文字（仅 PDF/docx/txt 有意义）。"""
    blocks = build_content_blocks(file_path)
    texts = [b["text"] for b in blocks if b.get("type") == "text"]
    return "\n".join(texts)


# ── 内部工具 ─────────────────────────────────────────────


def _image_block(path: Path) -> dict:
    media = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media};base64,{data}"},
    }


def _pdf_blocks(path: Path) -> list:
    """先尝试 pdfplumber 抽文字；如果是扫描件（无文字层），改用 pymupdf 转图片。"""
    import pdfplumber

    pages_text = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())

    if pages_text:
        return [{"type": "text", "text": "\n\n".join(pages_text)}]

    # 扫描件：逐页转图片
    return _pdf_as_images(path)


def _pdf_as_images(path: Path) -> list:
    """用 pymupdf 把 PDF 每页渲染成 PNG，打包成 image_url block 列表。"""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise RuntimeError(
            "处理图片 PDF 需要 pymupdf，请运行：pip install pymupdf"
        )

    blocks = []
    doc = fitz.open(str(path))
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        data = base64.standard_b64encode(png_bytes).decode()
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{data}"},
        })
    doc.close()
    return blocks


def _docx_text(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)
