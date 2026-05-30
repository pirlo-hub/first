"""4 种公司性质的颜色定义，屏幕和 Excel 共用同一份。

字体颜色按用户要求：原厂=白、方案商=黄、贸易商=蓝、代理商=绿。
屏幕和 Excel 都给一个深色底色，确保白字看得见。
"""

# 屏幕显示用（CSS 颜色）
SCREEN_COLORS = {
    "原厂":   {"bg": "#2b2b2b", "fg": "#ffffff"},
    "方案商": {"bg": "#2b2b2b", "fg": "#ffd54f"},
    "贸易商": {"bg": "#2b2b2b", "fg": "#4fc3f7"},
    "代理商": {"bg": "#2b2b2b", "fg": "#81c784"},
}

# Excel 用（六位 ARGB 不带 # 号；openpyxl 的格式）
EXCEL_COLORS = {
    "原厂":   {"bg": "FF2B2B2B", "fg": "FFFFFFFF"},
    "方案商": {"bg": "FF2B2B2B", "fg": "FFFFD54F"},
    "贸易商": {"bg": "FF2B2B2B", "fg": "FF4FC3F7"},
    "代理商": {"bg": "FF2B2B2B", "fg": "FF81C784"},
}


def screen_style(company_type: str) -> str:
    """返回内联 CSS 样式串，给 HTML 单元格用。"""
    c = SCREEN_COLORS.get(company_type)
    if not c:
        return ""
    return f"background-color:{c['bg']};color:{c['fg']};font-weight:600;"
