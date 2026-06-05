"""把简历文件转成可发给 OpenAI 多模态接口的 content block 列表。

支持：
  - PDF（有文字层）→ pymupdf 抽文字 + 重复行水印过滤
  - PDF（扫描件/图片层）→ pymupdf 转图片后以 image_url 发送
  - 图片（jpg/png/webp 等）→ base64 image_url
  - Word / txt / md → 纯文字
"""

import base64
import mimetypes
from collections import Counter
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


def summarize_blocks(blocks: list) -> dict:
    """概括一组 content block，供界面核对"模型到底读到了什么"。

    返回 {"text": 拼接的文字, "n_images": 图片数量, "kind": "text"/"image"/"mixed"}。
    """
    texts = [b["text"] for b in blocks if b.get("type") == "text"]
    n_images = sum(1 for b in blocks if b.get("type") == "image_url")
    text = "\n".join(texts).strip()
    if text and n_images:
        kind = "mixed"
    elif n_images:
        kind = "image"
    else:
        kind = "text"
    return {"text": text, "n_images": n_images, "kind": kind}


# 文字层太短就认定为扫描件（按字符数）；中文简历正常都远超这个量
_MIN_PDF_TEXT_CHARS = 40


# ── 内部工具 ─────────────────────────────────────────────


def _image_block(path: Path) -> dict:
    media = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media};base64,{data}"},
    }


def _pdf_blocks(path: Path) -> list:
    """用 pymupdf 抽文字（顺序比 pdfplumber 稳很多），并过滤重复行水印。

    扫描件 / 文字层残缺时退化为整页转图片。
    """
    text = _extract_pdf_text(path)
    cleaned = _strip_watermarks(text)
    # 文字层够多才走文字；太短（残缺/只有页眉页脚）就当扫描件转图片，
    # 避免模型拿到半截内容后"脑补"剩下的。
    if len(cleaned) >= _MIN_PDF_TEXT_CHARS:
        return [{"type": "text", "text": cleaned}]
    return _pdf_as_images(path)


def _extract_pdf_text(path: Path) -> str:
    """pymupdf 按阅读顺序抽文字。"""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise RuntimeError("需要 pymupdf：pip install pymupdf")
    pages = []
    doc = fitz.open(str(path))
    try:
        for page in doc:
            t = page.get_text("text") or ""
            if t.strip():
                pages.append(t)
    finally:
        doc.close()
    return "\n".join(pages)


def _strip_watermarks(text: str) -> str:
    """过滤"重复行水印"：

    PDF 水印（如"公司名 ID：xxxx 日期"）在 pymupdf 抽取里通常是反复出现的整行，
    且这种水印**重复次数远高于简历正文里的标题**。

    规则：一行如果同时满足
      - 去空白后**长度 ≥ 8**（避免误杀短标题如"销售经理"/"工作业绩"）
      - 在全文出现 **≥ 5 次**
    就认定为水印行，删掉；并连带删掉它的子串（截断的水印片段）。

    安全网：过滤后若剩余 < 原文 20%，认为可能误伤，回退原文。
    （之前用过 50% 阈值，但有些 PDF 水印实在太多，正文反而占少数。）
    """
    if not text:
        return ""

    raw_lines = text.splitlines()
    stripped = [ln.strip() for ln in raw_lines]
    counts = Counter(ln for ln in stripped if ln)

    watermarks = {ln for ln, n in counts.items() if n >= 5 and len(ln) >= 8}
    if not watermarks:
        return text.strip()

    def _is_watermark_fragment(ln: str) -> bool:
        if not ln:
            return False
        if ln in watermarks:
            return True
        # 子串：截断的水印片段（"杭州百" 是 "杭州百隆电子有限公司" 的前缀）
        for w in watermarks:
            if len(ln) < len(w) and ln in w:
                return True
        return False

    kept = [orig for orig, s in zip(raw_lines, stripped) if not _is_watermark_fragment(s)]
    cleaned = "\n".join(kept).strip()

    original = text.strip()
    if original and len(cleaned) < len(original) * 0.2:
        return original  # 过滤过头，回退
    return cleaned


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
        pix = page.get_pixmap(dpi=200)  # 中文小字识别更稳，避免看不清而脑补
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
