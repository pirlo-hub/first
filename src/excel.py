"""Claude 风格的 Excel 导出：暖中性色 + 珊瑚橘 accent + 极简边框。

布局：
- 每段履历一行；同一候选人的 候选人ID/姓名/年龄/学历/销售年限/业绩简述 跨行合并
- 公司性质用 4 色字体
- 表头暖米底 + 珊瑚橘 accent 下划线；候选人间用中灰线分隔
- 自动筛选 + 冻结表头
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .colors import EXCEL_COLORS

# 表头：(名称, 列宽)
_HEADERS = [
    ("候选人ID", 10),
    ("姓名", 11),
    ("年龄", 7),
    ("学历", 9),
    ("销售年限", 9),
    ("业绩简述", 30),
    ("公司", 30),
    ("公司性质", 16),
    ("岗位", 15),
    ("就职时间", 18),
    ("经手客户", 26),
    ("涉及产品品牌", 20),
    ("涉及产品类别", 22),
    ("涉及产品型号", 20),
    ("在职情况备注", 26),
]

# 候选人级字段所在列（1-based），多段履历合并这些列
_CAND_COLS = [1, 2, 3, 4, 5, 6]
# 公司性质列
_CTYPE_COL = 8
# 居中对齐的短字段列
_CENTER_COLS = {1, 2, 3, 4, 5, 8, 10}

_FONT_CN = "微软雅黑"

# Claude 风格调色板：暖中性 + 珊瑚橘 accent
_HEADER_BG   = "FFFFFF00"   # Excel 标准色：黄
_HEADER_FG   = "FF2C2A23"   # 暖深棕
_ACCENT      = "FFC96442"   # Claude 珊瑚橘
_BORDER_LITE = "FFE5E1D8"   # 暖浅灰（数据格网线）
_BORDER_MED  = "FFB8B4AB"   # 暖中灰（候选人分隔）
_ZEBRA_BG    = "FFFBF9F5"   # 极淡暖白（奇数候选人）


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


def _data_border(bottom_strong: bool) -> Border:
    """数据格边框：四周 hair 暖浅线；候选人末行的下边框升级为 medium 暖中灰。"""
    lite = Side(style="hair", color=_BORDER_LITE)
    bottom = Side(style="medium", color=_BORDER_MED) if bottom_strong else lite
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
        top=Side(style="thin", color=_HEADER_BG),
        bottom=Side(style="medium", color=_ACCENT),  # 珊瑚橘 accent
    )
    for col_idx, (name, width) in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = header_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(_HEADERS))}1"

    # ── 数据 ──
    data_font = Font(name=_FONT_CN, size=10, color=_HEADER_FG)
    cand_font = Font(name=_FONT_CN, size=10, bold=True, color=_HEADER_FG)

    row = 2
    for cand_idx, c in enumerate(candidates):
        emps = c.get("employments") or [{}]  # 至少一行
        n = len(emps)
        start_row = row
        zebra = PatternFill("solid", fgColor=_ZEBRA_BG) if cand_idx % 2 == 1 else None

        for i, emp in enumerate(emps):
            is_last = (i == n - 1)

            # 候选人级字段：只在首行写
            # 关键：合并区只看"左上角"的样式 → 候选人末尾的粗底线必须设在 i==0 这行
            if i == 0:
                cand_values = [
                    c.get("id") or c.get("_temp_id") or "",
                    c.get("name") or "",
                    c.get("age") or "",
                    c.get("education") or "",
                    c.get("total_sales_years") or "",
                    c.get("business_summary") or "",
                ]
                cand_border = _data_border(True)  # 合并区或单行，bottom 都用粗线
                for col_idx, val in enumerate(cand_values, start=1):
                    cell = ws.cell(row=row, column=col_idx, value=val)
                    # 业绩简述（第 6 列）是长文本，不要加粗
                    cell.font = data_font if col_idx == 6 else cand_font
                    horiz = "center" if col_idx in _CENTER_COLS else "left"
                    cell.alignment = Alignment(horizontal=horiz, vertical="center", wrap_text=True)
                    cell.border = cand_border
                    if zebra:
                        cell.fill = zebra

            # 履历级字段：每行都写
            emp_border = _data_border(is_last)
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
                cell.border = emp_border
                if zebra:
                    cell.fill = zebra

            # 公司性质：覆盖为 4 色加粗字体
            ctype = emp.get("company_type")
            color = EXCEL_COLORS.get(ctype)
            if color:
                ctype_cell = ws.cell(row=row, column=_CTYPE_COL)
                ctype_cell.font = Font(name=_FONT_CN, bold=True, color=color["fg"], size=10)

            row += 1

        # 合并候选人级字段
        if n > 1:
            for col in _CAND_COLS:
                ws.merge_cells(start_row=start_row, end_row=row - 1,
                               start_column=col, end_column=col)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
