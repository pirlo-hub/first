"""4 种公司性质的颜色定义。

屏幕端用深色底 + 彩色字（适配 Streamlit 深色主题）；
Excel 端不上底色，只用加粗的彩色字（白底看得清，原厂用黑色）。
"""

# 屏幕显示用（CSS 颜色，深色底）
SCREEN_COLORS = {
    "原厂":   {"bg": "#2b2b2b", "fg": "#ffffff"},
    "方案商": {"bg": "#2b2b2b", "fg": "#ffd54f"},
    "贸易商": {"bg": "#2b2b2b", "fg": "#4fc3f7"},
    "代理商": {"bg": "#2b2b2b", "fg": "#81c784"},
}

# Excel 用：只给字体上色，无底色（六位 ARGB，openpyxl 格式）
EXCEL_COLORS = {
    "原厂":   {"fg": "FF000000"},  # 黑
    "方案商": {"fg": "FFF57F17"},  # 深黄（白底可见）
    "贸易商": {"fg": "FF1976D2"},  # 深蓝
    "代理商": {"fg": "FF2E7D32"},  # 深绿
}


def screen_style(company_type: str) -> str:
    """返回内联 CSS 样式串，给 HTML 单元格用。"""
    c = SCREEN_COLORS.get(company_type)
    if not c:
        return ""
    return f"background-color:{c['bg']};color:{c['fg']};font-weight:600;"
