"""把候选人列表导出为带颜色的 Excel。

每段履历一行，公司性质单元格按 4 种类型上色（字体颜色 + 深色底色）。
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .colors import EXCEL_COLORS

# 表头与列宽
_HEADERS = [
    ("候选人ID", 10),
    ("年龄", 8),
    ("学历", 10),
    ("销售年限", 10),
    ("业绩简述", 40),
    ("公司", 28),
    ("公司性质", 12),
    ("岗位", 16),
    ("就职时间", 18),
    ("经手客户", 30),
    ("涉及产品品牌", 25),
    ("涉及产品类别", 25),
    ("涉及产品型号", 25),
    ("在职情况备注", 30),
]


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


def candidates_to_xlsx(candidates: list[dict]) -> bytes:
    """传入 db.list_candidates() 的结果（或抽取页临时数据），返回 xlsx 字节。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "简历库"

    # 表头
    header_font = Font(bold=True, color="FFFFFFFF")
    header_fill = PatternFill("solid", fgColor="FF1F4E78")
    for col_idx, (name, width) in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = "A2"

    row = 2
    for c in candidates:
        emps = c.get("employments") or [{}]  # 至少一行，保证候选人能露面
        for emp in emps:
            values = [
                c.get("id") or c.get("_temp_id") or "",
                c.get("age") or "",
                c.get("education") or "",
                c.get("total_sales_years") or "",
                c.get("business_summary") or "",
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
            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                cell.alignment = Alignment(wrap_text=True, vertical="top")

            # 给"公司性质"单元格上色（第 7 列）
            ctype = emp.get("company_type")
            color = EXCEL_COLORS.get(ctype)
            if color:
                ctype_cell = ws.cell(row=row, column=7)
                ctype_cell.font = Font(bold=True, color=color["fg"])
                ctype_cell.fill = PatternFill("solid", fgColor=color["bg"])
                ctype_cell.alignment = Alignment(horizontal="center", vertical="center")
            row += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
