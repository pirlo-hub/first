# 销售简历 AI 抽取与筛选（第一版）

把应聘销售的简历用 AI 抽成结构化数据，辅助招聘筛选。这是整个产品构想的**第一步地基**：
先把「简历 → 结构化字段」这条管道跑通、验证抽取质量，后续再做销售线索挖掘、客户分级等。

## 它能做什么（v1）

- 上传简历（PDF / Word / 图片 / txt），AI 自动抽取：
  - 应聘人：年龄、学历、销售从业总年限
  - 每段履历：企业名称、职位、起止时间、是否销售岗、企业性质
  - 每段履历下经手过的客户与产品（类别 / 型号 / 品牌 / 营收）
- 人工核对、修改字段后入库（SQLite）
- 记录录用决策（录用 / 不录用 / 待定）——为将来的「自动筛选」积累训练数据

> 暂不做：公司性质联网分类、客户注册资金分级、交叉印证、模型微调（见下方「路线图」）。

## 快速开始

```bash
# 1. 安装依赖（建议先建虚拟环境）
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env      # 然后编辑 .env，填入 ANTHROPIC_API_KEY

# 3a. 命令行验证单份简历的抽取效果（阶段 0）
python -m src.extract samples/某份简历.pdf
python -m src.extract samples/某份简历.pdf --save --code C001   # 顺便入库

# 3b. 启动可视化界面（阶段 1）
streamlit run app.py
```

## 目录结构

```
prompts/extract_prompt.md   抽取提示词（想调效果先改这里）
src/schema.py               抽取的固定字段结构（JSON schema）
src/parse.py                文件 → 发给模型的内容块（PDF/图片走多模态）
src/extract.py              调 Claude 抽取 + 命令行入口
src/db.py                   SQLite 建表与读写
app.py                      Streamlit 界面
samples/                    放脱敏简历（不入库、被 git 忽略）
```

## 路线图

- **阶段 0（先做）**：验证抽取质量——拿 5~10 份脱敏简历跑 `src.extract`，人工对照打分。不达标先调 `prompts/extract_prompt.md` 和 `src/schema.py`。
- **阶段 1（先做）**：Streamlit 招聘筛选工具（本仓库当前内容）。
- **阶段 2**：联网补全公司性质 / 客户注册资金分级 → 销售线索视图 → 交叉印证、竞调。
- **阶段 3**：用攒下的「决策 + 入职表现」数据，评估是否需要专用打分模型。

## 注意

- 简历是敏感个人信息：用编号脱敏，本地 SQLite 存储，调 API 只传必要内容。
- AI 抽取需人工复核，公司名/职位/时间要求准，营收/品牌可容错。
