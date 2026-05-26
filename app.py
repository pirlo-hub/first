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

tab_new, tab_list = st.tabs(["上传与抽取", "候选人列表"])


with tab_new:
    up = st.file_uploader("上传简历（PDF / Word / 图片 / txt）",
                          type=["pdf", "docx", "png", "jpg", "jpeg", "txt"])

    if up is not None and st.button("开始抽取", type="primary"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(up.name).suffix) as tmp:
            tmp.write(up.getbuffer())
            tmp_path = tmp.name
        try:
            with st.spinner("AI 抽取中…"):
                st.session_state["extracted"] = extract_resume(tmp_path)
                st.session_state["source_file"] = up.name
        except Exception as e:  # noqa: BLE001 - 直接把错误显示给用户
            st.error(f"抽取失败：{e}")

    data = st.session_state.get("extracted")
    if data:
        st.subheader("抽取结果（可核对、可修改后再保存）")
        cand = data.setdefault("candidate", {})
        c1, c2, c3 = st.columns(3)
        cand["age"] = c1.text_input("年龄", value=str(cand.get("age") or ""))
        cand["education"] = c2.text_input("学历", value=cand.get("education") or "")
        cand["total_sales_years"] = c3.text_input("销售总年限(年)",
                                                   value=str(cand.get("total_sales_years") or ""))

        st.markdown("**工作履历 / 经手客户**")
        for i, emp in enumerate(data.get("employments", [])):
            header = f"{emp.get('company', '?')} — {emp.get('title') or ''} [{emp.get('company_type', '未知')}]"
            with st.expander(header, expanded=(i == 0)):
                st.write(f"在职：{emp.get('start', '?')} ~ {emp.get('end', '?')}"
                         f"　|　销售岗：{'是' if emp.get('is_sales') else '否'}")
                deals = emp.get("customer_deals") or []
                if deals:
                    st.table(deals)
                else:
                    st.caption("（简历未提及客户/产品）")

        code = st.text_input("候选人编号（脱敏，建议不要用真实姓名）")
        if st.button("保存到数据库"):
            cid = db.save_extraction(data, st.session_state.get("source_file", ""), code or None)
            st.success(f"已保存，候选人 ID = {cid}")
            st.session_state.pop("extracted", None)


with tab_list:
    rows = db.list_candidates()
    if not rows:
        st.info("还没有数据，先去「上传与抽取」放一份简历。")
    options = ["待定", "录用", "不录用"]
    for r in rows:
        c1, c2, c3, c4 = st.columns([4, 2, 3, 2])
        c1.write(f"**#{r['id']}** {r.get('code') or ''}　学历 {r.get('education') or '-'}"
                 f"　销售年限 {r.get('total_sales_years') or '-'}　来源 {r.get('source_file') or '-'}")
        cur = r.get("decision") or "待定"
        decision = c2.selectbox("决策", options, index=options.index(cur), key=f"dec{r['id']}")
        notes = c3.text_input("备注", value=r.get("notes") or "", key=f"note{r['id']}")
        if c4.button("保存决策", key=f"save{r['id']}"):
            db.set_decision(r["id"], decision, notes)
            st.success("已更新")
