"""Streamlit 界面：上传简历 → AI 抽取 → 核对 → 存入资料库 / 导出 Excel。

运行： streamlit run app.py
"""

import html
import tempfile
from pathlib import Path

import streamlit as st

from src import db
from src.colors import screen_style
from src.excel import candidates_to_xlsx
from src.extract import extract_resume

st.set_page_config(page_title="销售简历抽取与筛选", layout="wide")
st.title("销售简历 AI 抽取与筛选")


# ── 工具：把一份候选人数据渲染成带颜色的 HTML 表格 ─────────────
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


_TABLE_HEADERS = [
    "公司", "公司性质", "岗位", "就职时间",
    "经手客户", "涉及产品品牌", "涉及产品类别", "涉及产品型号",
    "在职情况备注",
]


def _norm(s: str) -> str:
    """归一化用于子串匹配：去掉所有空白（pdfplumber 偶尔会插空格）。"""
    return "".join(str(s).split())


def _in_source(item: str, source_norm: str) -> bool:
    """item 是否在简历原文（归一化后）中出现。"""
    if not source_norm or not item:
        return True  # 没有原文（图片简历）或空值，跳过判定
    return _norm(item) in source_norm


_SUSPECT_STYLE = (
    "background:#5c2b2b;color:#ffb4b4;padding:1px 6px;"
    "border-radius:3px;border:1px solid #a04040;"
)


def _wrap_suspect(text: str) -> str:
    return f'<span style="{_SUSPECT_STYLE}" title="原文中未找到，疑似 AI 虚构">⚠ {html.escape(text)}</span>'


def _join_verified(arr, source_norm: str) -> str:
    """渲染数组字段；每个元素若不在原文则加红色 ⚠ 标记。"""
    if not arr:
        return ""
    parts = []
    for x in arr:
        if not x:
            continue
        x = str(x)
        if _in_source(x, source_norm):
            parts.append(html.escape(x))
        else:
            parts.append(_wrap_suspect(x))
    return "、".join(parts)


def _cell_verified(value: str, source_norm: str) -> str:
    """渲染单值字段（如公司名）；不在原文则加红色 ⚠ 标记。"""
    if not value:
        return ""
    if _in_source(value, source_norm):
        return html.escape(value)
    return _wrap_suspect(value)


def find_suspects(data: dict, source_text: str) -> list[tuple[str, str]]:
    """返回 [(字段标签, 值), ...]，列出所有"原文没找到"的可疑项。"""
    if not source_text:
        return []
    src = _norm(source_text)
    out = []
    for emp in data.get("employments") or []:
        for label, val in [("公司", emp.get("company")), ("岗位", emp.get("title"))]:
            if val and not _in_source(val, src):
                out.append((label, val))
        for label, key in [("客户", "customers"), ("品牌", "product_brands"),
                           ("类别", "product_categories"), ("型号", "product_models")]:
            for item in (emp.get(key) or []):
                if item and not _in_source(item, src):
                    out.append((label, str(item)))
    return out


def render_employment_table(employments: list[dict], source_text: str = "") -> None:
    """渲染履历表格。若给了原文，可疑项（不在原文中的客户/品牌/型号等）会红色高亮。"""
    src = _norm(source_text) if source_text else ""
    rows_html = []
    for emp in employments:
        ctype = emp.get("company_type") or ""
        style = screen_style(ctype)
        cells = [
            _cell_verified(emp.get("company") or "", src),
            f'<span style="{style};padding:2px 8px;border-radius:4px;">{html.escape(ctype)}</span>'
            if style else html.escape(ctype),
            _cell_verified(emp.get("title") or "", src),
            html.escape(_period(emp.get("start"), emp.get("end"))),
            _join_verified(emp.get("customers"), src),
            _join_verified(emp.get("product_brands"), src),
            _join_verified(emp.get("product_categories"), src),
            _join_verified(emp.get("product_models"), src),
            html.escape(emp.get("notes") or ""),
        ]
        tr = "".join(f"<td style='padding:6px 10px;border-bottom:1px solid #444;vertical-align:top;'>{c}</td>" for c in cells)
        rows_html.append(f"<tr>{tr}</tr>")

    thead = "".join(
        f"<th style='padding:8px 10px;border-bottom:2px solid #888;text-align:left;'>{h}</th>"
        for h in _TABLE_HEADERS
    )
    html_str = (
        "<div style='overflow-x:auto;'>"
        "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table></div>"
    )
    st.markdown(html_str, unsafe_allow_html=True)


def render_input_preview(debug: dict | None) -> None:
    """显示模型实际读到的简历输入，供核对是否"脑补"。"""
    if not debug:
        return
    kind = debug.get("kind")
    n_img = debug.get("n_images") or 0
    text = (debug.get("text") or "").strip()

    if kind == "image":
        st.warning(
            f"⚠️ 本简历按**图片**方式发送给模型（共 {n_img} 张），靠模型识图。"
            "请重点核对下方抽取结果是否与原图一致——若代理/模型不支持读图，可能会出现凭空捏造的内容。"
        )
        return

    # 文字 / 混合：把识别到的原文亮出来，方便逐字比对
    chars = len(text)
    note = f"识别到约 {chars} 字" + (f"，另有 {n_img} 张图片" if n_img else "")
    if chars < 80:
        st.error(
            f"⚠️ 只从该文件里识别到很少的文字（{note}）。"
            "模型几乎没拿到简历内容，抽取结果很可能是**编的**，请不要采信，换 Word 或更清晰的文件重试。"
        )
    with st.expander(f"🔍 模型实际读到的简历原文（{note}）— 核对用", expanded=False):
        st.text(text or "（空）")


def render_candidate_card(data: dict, key_prefix: str, *, db_id: int | None = None,
                          source_file: str | None = None,
                          source_text: str = "") -> dict:
    """渲染单个候选人卡片（个人信息可编辑 + 履历表）。返回（可能被用户改过的）data。

    若给了 source_text，履历表里"原文中找不到"的项会红字加 ⚠ 标记。
    """
    # 提前列出可疑项，醒目地放在卡片顶部
    suspects = find_suspects(data, source_text) if source_text else []
    if suspects:
        items_html = "".join(
            f"<li><b>[{html.escape(label)}]</b> {html.escape(val)}</li>"
            for label, val in suspects
        )
        st.markdown(
            f"<div style='background:#5c2b2b;color:#ffd0d0;padding:10px 14px;"
            f"border-left:4px solid #ff5555;border-radius:4px;margin-bottom:8px;'>"
            f"⚠️ <b>下列 {len(suspects)} 项在简历原文中未找到，疑似 AI 虚构，请核对后再存入：</b>"
            f"<ul style='margin:6px 0 0 18px;'>{items_html}</ul>"
            f"</div>",
            unsafe_allow_html=True,
        )

    cand = data.setdefault("candidate", {})

    c0, c1, c2, c3 = st.columns([1, 1, 1, 1])
    cand["name"] = c0.text_input("姓名", value=cand.get("name") or "",
                                 key=f"{key_prefix}_name")
    cand["age"] = c1.text_input("年龄", value=str(cand.get("age") or ""),
                                key=f"{key_prefix}_age")
    cand["education"] = c2.text_input("学历", value=cand.get("education") or "",
                                      key=f"{key_prefix}_edu")
    cand["total_sales_years"] = c3.text_input(
        "销售总年限(年)", value=str(cand.get("total_sales_years") or ""),
        key=f"{key_prefix}_yrs")
    cand["business_summary"] = st.text_area(
        "个人业绩简述",
        value=cand.get("business_summary") or "",
        key=f"{key_prefix}_sum",
        height=80,
    )

    employments = data.get("employments") or []
    if employments:
        render_employment_table(employments, source_text=source_text)
    else:
        st.caption("（未抽到工作履历）")

    return data


def ok_results_to_card_list(ok_results: list[dict]) -> list[dict]:
    """把当前抽取页的结果包成 candidates_to_xlsx 能吃的格式（无 db id）。"""
    out = []
    for i, r in enumerate(ok_results, start=1):
        d = r["data"]
        cand = d.get("candidate", {}) or {}
        out.append({
            "_temp_id": f"T{i}",
            "source_file": r["filename"],
            "name": cand.get("name"),
            "age": cand.get("age"),
            "education": cand.get("education"),
            "total_sales_years": cand.get("total_sales_years"),
            "business_summary": cand.get("business_summary"),
            "employments": d.get("employments") or [],
        })
    return out


# ── 页签布局 ───────────────────────────────────────────────
tab_new, tab_lib = st.tabs(["上传与抽取", "资料库"])


# ───────────────── 上传与抽取 ─────────────────
with tab_new:
    uploaded = st.file_uploader(
        "上传简历（PDF / Word / 图片 / txt），支持同时选多个文件",
        type=["pdf", "docx", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
    )

    if uploaded and st.button("开始抽取", type="primary"):
        results = []  # list of dict: {filename, data | error}
        progress = st.progress(0, text="准备中…")
        for i, up in enumerate(uploaded):
            progress.progress(i / len(uploaded),
                              text=f"正在抽取：{up.name}  ({i+1}/{len(uploaded)})")
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(up.name).suffix) as tmp:
                tmp.write(up.getbuffer())
                tmp_path = tmp.name
            try:
                data, debug = extract_resume(tmp_path, return_debug=True)
                results.append({"filename": up.name, "data": data,
                                "debug": debug, "error": None})
            except Exception as e:  # noqa: BLE001
                results.append({"filename": up.name, "data": None,
                                "debug": None, "error": str(e)})
        progress.progress(1.0, text="抽取完成")
        st.session_state["results"] = results

    results = st.session_state.get("results", [])
    if results:
        ok_results = [r for r in results if r["data"] is not None]

        # 顶栏：批量操作
        col_a, col_b, col_c = st.columns([2, 2, 6])
        if col_a.button("📥 一键全部存入资料库", type="primary",
                        disabled=not ok_results):
            saved = 0
            for r in ok_results:
                db.save_extraction(r["data"], r["filename"])
                saved += 1
            st.session_state["results"] = []  # 全部存完清空当前页
            st.success(f"已全部存入资料库（{saved} 份）")
            st.rerun()

        if ok_results:
            xlsx = candidates_to_xlsx(ok_results_to_card_list(ok_results))
            col_b.download_button(
                "📊 导出 Excel（当前抽取）", data=xlsx,
                file_name="抽取结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown(f"**共 {len(results)} 份，逐份核对：**")
        for idx, r in enumerate(list(results)):
            filename = r["filename"]
            with st.expander(f"📄 {filename}", expanded=True):
                if r["error"]:
                    st.error(f"抽取失败：{r['error']}")
                    if st.button("从当前页面删除", key=f"del_err_{idx}"):
                        st.session_state["results"].pop(idx)
                        st.rerun()
                    continue

                render_input_preview(r.get("debug"))
                src_text = (r.get("debug") or {}).get("text") or ""
                data = render_candidate_card(r["data"], key_prefix=f"new_{idx}",
                                             source_file=filename,
                                             source_text=src_text)
                r["data"] = data  # 写回 session

                btn1, btn2, _ = st.columns([1.5, 1.5, 5])
                if btn1.button("✅ 存入资料库", key=f"save_{idx}", type="primary"):
                    db.save_extraction(data, filename)
                    st.session_state["results"].pop(idx)
                    st.success(f"已存入：{filename}")
                    st.rerun()
                if btn2.button("🗑 从当前页面删除", key=f"del_{idx}"):
                    st.session_state["results"].pop(idx)
                    st.rerun()


# ───────────────── 资料库 ─────────────────

with tab_lib:
    candidates = db.list_candidates()
    if not candidates:
        st.info("资料库还没有数据。先去「上传与抽取」处理几份简历再存入。")
    else:
        top1, top2, _ = st.columns([2, 3, 6])
        top1.markdown(f"**共 {len(candidates)} 位候选人**")
        xlsx = candidates_to_xlsx(candidates)
        top2.download_button(
            "📊 导出 Excel（整个资料库）", data=xlsx,
            file_name="简历资料库.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        for c in candidates:
            label = f"#{c['id']}　{c.get('name') or '—'}　{c.get('source_file') or '—'}　学历 {c.get('education') or '-'}　销售年限 {c.get('total_sales_years') or '-'}"
            with st.expander(label, expanded=False):
                # 个人信息（只读展示）
                a, b, cc, dd = st.columns(4)
                a.metric("姓名", c.get("name") or "—")
                b.metric("年龄", c.get("age") or "—")
                cc.metric("学历", c.get("education") or "—")
                dd.metric("销售总年限(年)", c.get("total_sales_years") or "—")
                if c.get("business_summary"):
                    st.markdown(f"**个人业绩简述**：{c['business_summary']}")

                employments = c.get("employments") or []
                if employments:
                    render_employment_table(employments)
                else:
                    st.caption("（无工作履历）")

                if st.button("🗑 从资料库删除", key=f"libdel_{c['id']}"):
                    db.delete_candidate(c["id"])
                    st.success(f"已删除 #{c['id']}")
                    st.rerun()
