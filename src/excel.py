"""把候选人列表导出为美观的 Excel。

布局：
- 每段履历一行；同一候选人的 候选人ID/姓名/年龄/学历/销售年限/业绩简述 跨行合并
- 公司性质用 4 色字体（无底色）
- 候选人之间用粗深色线分隔，奇数候选人加浅斑马底色
- 默认开自动筛选 + 冻结表头
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .colors import EXCEL_COLORS

# 表头：(名称, 列宽)
_HEADERS = [
    ("候选人ID", 9),
    ("姓名", 12),
    ("年龄", 7),
    ("学历", 10),
    ("销售年限", 10),
    ("业绩简述", 42),
    ("公司", 26),
    ("公司性质", 11),
    ("岗位", 16),
    ("就职时间", 17),
    ("经手客户", 26),
    ("涉及产品品牌", 20),
    ("涉及产品类别", 20),
    ("涉及产品型号", 20),
    ("在职情况备注", 28),
]

# 候选人级字段所在列（1-based），多段履历合并这些列
_CAND_COLS = [1, 2, 3, 4, 5, 6]
# 公司性质列
_CTYPE_COL = 8
# 居中对齐的短字段列（其余按"长文本"处理：左对齐 + 顶对齐）
_CENTER_COLS = {1, 2, 3, 4, 5, 8, 10}

# 字体（中文优先，无此字体时 Excel 会自动回落）
_FONT_CN = "微软雅黑"

# 调色板
_HEADER_BG   = "FF1F4E78"
_HEADER_FG   = "FFFFFFFF"
_ZEBRA_BG    = "FFF4F7FB"
_BORDER_LITE = "FFCBD3DC"
_BORDER_DARK = "FF7B8794"


def _join(arr) -> str:
    if not arr:
        return ""
    return "、".join(str(x) for x in arr if x)


def _period(start, end) -> str:
    s = start or ""
    e = "至今" if (end == "present") else (end or "")
    if not s and not e:
        return ""
    return f"{s}-{e}"


def _cell_border(is_last_of_cand: bool) -> Border:
    """末行下边框用 medium 深色，其余用 hair 浅色——形成候选人之间的视觉分隔。"""
    lite = Side(style="hair", color=_BORDER_LITE)
    if is_last_of_cand:
        bottom = Side(style="medium", color=_BORDER_DARK)
    else:
        bottom = lite
    return Border(left=lite, right=lite, top=lite, bottom=bottom)


def candidates_to_xlsx(candidates: list[dict]) -> bytes:
    """传入 db.list_candidates() 的结果（或抽取页临时数据），返回 xlsx 字节。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "简历库"

    # ── 表头 ──
    header_font = Font(name=_FONT_CN, bold=True, color=_HEADER_FG, size=11)
    header_fill = PatternFill("solid", fgColor=_HEADER_BG)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    header_border = Border(
        left=Side(style="thin", color=_HEADER_BG),
        right=Side(style="thin", color=_HEADER_BG),
        top=Side(style="medium", color=_BORDER_DARK),
        bottom=Side(style="medium", color=_BORDER_DARK),
    )
    for col_idx, (name, width) in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = header_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(_HEADERS))}1"

    # ── 数据 ──
    data_font = Font(name=_FONT_CN, size=10)
    cand_font = Font(name=_FONT_CN, size=10, bold=True)

    row = 2
    for cand_idx, c in enumerate(candidates):
        emps = c.get("employments") or [{}]  # 至少一行，保证候选人露面
        n = len(emps)
        start_row = row
        # 斑马底：按候选人交替（保证同一人多段履历底色一致）
        zebra = PatternFill("solid", fgColor=_ZEBRA_BG) if cand_idx % 2 == 1 else None

        for i, emp in enumerate(emps):
            is_last = (i == n - 1)

            # 候选人级字段：只在首行写值（其余行留空便于合并）
            if i == 0:
                cand_values = [
                    c.get("id") or c.get("_temp_id") or "",
                    c.get("name") or "",
                    c.get("age") or "",
                    c.get("education") or "",
                    c.get("total_sales_years") or "",
                    c.get("business_summary") or "",
                ]
                for col_idx, val in enumerate(cand_values, start=1):
                    cell = ws.cell(row=row, column=col_idx, value=val)
                    cell.font = cand_font
                    horiz = "center" if col_idx in _CENTER_COLS else "left"
                    cell.alignment = Alignment(horizontal=horiz, vertical="center", wrap_text=True)

            # 履历级字段：每行都写
            emp_values = [
                emp.get("company") or "",
                emp.get("company_type") or "",
                emp.get("title") or "",
                _period(emp.get("start"), emp.get("end")),
                _join(emp.get("customers")),
                _join(emp.get("product_brands")),
                _join(emp.get("product_categories")),
                _join(emp.get("product_models")),
                emp.get("notes") or "",
            ]
            for col_idx, val in enumerate(emp_values, start=7):
                cell = ws.cell(row=row, column=col_idx, value=val)
                cell.font = data_font
                if col_idx in _CENTER_COLS:
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

            # 公司性质：仅字体颜色（覆盖默认 data_font）
            ctype = emp.get("company_type")
            color = EXCEL_COLORS.get(ctype)
            if color:
                ctype_cell = ws.cell(row=row, column=_CTYPE_COL)
                ctype_cell.font = Font(name=_FONT_CN, bold=True, color=color["fg"], size=10)
                ctype_cell.alignment = Alignment(horizontal="center", vertical="center")

            # 整行：斑马底 + 边框
            border = _cell_border(is_last)
            for col in range(1, len(_HEADERS) + 1):
                cell = ws.cell(row=row, column=col)
                if zebra:
                    cell.fill = zebra
                cell.border = border

            row += 1

        # 多段履历则合并候选人级字段
        if n > 1:
            for col in _CAND_COLS:
                ws.merge_cells(start_row=start_row, end_row=row - 1,
                               start_column=col, end_column=col)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
