"""Streamlit 界面：上传简历 → AI 抽取 → 人工核对 → 记录录用决策。

运行： streamlit run app.py
"""

import tempfile
from pathlib import Path

import streamlit as st

from src import db
from src.extract import extract_resume

st.set_page_config(page_title="销售简历抽取与筛选", layout="wide")
st.title("销售简历 AI 抽取与筛选")

# 客户交易表头中文映射
_DEAL_COLUMNS = {
    "customer_name": "客户名称",
    "product_category": "产品类别",
    "product_model": "产品型号",
    "product_brand": "产品品牌",
    "revenue": "营收/规模",
}

tab_new, tab_list = st.tabs(["上传与抽取", "候选人列表"])


# ── 上传与抽取 ────────────────────────────────────────────
with tab_new:
    uploaded = st.file_uploader(
        "上传简历（PDF / Word / 图片 / txt），支持同时选多个文件",
        type=["pdf", "docx", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
    )

    if uploaded and st.button("开始抽取", type="primary"):
        results = []  # list of (filename, data | Exception)
        progress = st.progress(0, text="准备中…")
        for i, up in enumerate(uploaded):
            progress.progress((i) / len(uploaded), text=f"正在抽取：{up.name}  ({i+1}/{len(uploaded)})")
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(up.name).suffix) as tmp:
                tmp.write(up.getbuffer())
                tmp_path = tmp.name
            try:
                data = extract_resume(tmp_path)
                results.append((up.name, data))
            except Exception as e:  # noqa: BLE001
                results.append((up.name, e))
        progress.progress(1.0, text="抽取完成")
        st.session_state["results"] = results

    results = st.session_state.get("results", [])
    if results:
        st.markdown(f"**共 {len(results)} 份，展示结果如下：**")
        for filename, data in results:
            with st.expander(f"📄 {filename}", expanded=True):
                if isinstance(data, Exception):
                    st.error(f"抽取失败：{data}")
                    continue

                cand = data.setdefault("candidate", {})
                c1, c2, c3 = st.columns(3)
                cand["age"] = c1.text_input("年龄", value=str(cand.get("age") or ""),
                                            key=f"age_{filename}")
                cand["education"] = c2.text_input("学历", value=cand.get("education") or "",
                                                  key=f"edu_{filename}")
                cand["total_sales_years"] = c3.text_input(
                    "销售总年限(年)", value=str(cand.get("total_sales_years") or ""),
                    key=f"yrs_{filename}")

                st.markdown("**工作履历 / 经手客户**")
                for i, emp in enumerate(data.get("employments", [])):
                    header = (f"{emp.get('company', '?')} — {emp.get('title') or ''} "
                              f"[{emp.get('company_type', '未知')}]")
                    with st.expander(header, expanded=(i == 0)):
                        st.write(
                            f"在职：{emp.get('start', '?')} ~ {emp.get('end', '?')}"
                            f"　|　销售岗：{'是' if emp.get('is_sales') else '否'}"
                        )
                        deals = emp.get("customer_deals") or []
                        if deals:
                            # 字段名替换为中文
                            renamed = [
                                {_DEAL_COLUMNS.get(k, k): v for k, v in d.items()}
                                for d in deals
                            ]
                            st.table(renamed)
                        else:
                            st.caption("（简历未提及客户/产品）")

                code = st.text_input("候选人编号（脱敏，建议不用真实姓名）",
                                     key=f"code_{filename}")
                if st.button("保存到数据库", key=f"save_{filename}"):
                    cid = db.save_extraction(data, filename, code or None)
                    st.success(f"已保存，候选人 ID = {cid}")


# ── 候选人列表 ────────────────────────────────────────────
with tab_list:
    rows = db.list_candidates()
    if not rows:
        st.info("还没有数据，先去「上传与抽取」放一份简历。")
    options = ["待定", "录用", "不录用"]
    for r in rows:
        c1, c2, c3, c4 = st.columns([4, 2, 3, 2])
        c1.write(
            f"**#{r['id']}** {r.get('code') or ''}　"
            f"学历 {r.get('education') or '-'}　"
            f"销售年限 {r.get('total_sales_years') or '-'}　"
            f"来源 {r.get('source_file') or '-'}"
        )
        cur = r.get("decision") or "待定"
        decision = c2.selectbox("决策", options, index=options.index(cur), key=f"dec{r['id']}")
        notes = c3.text_input("备注", value=r.get("notes") or "", key=f"note{r['id']}")
        if c4.button("保存决策", key=f"save{r['id']}"):
            db.set_decision(r["id"], decision, notes)
            st.success("已更新")
