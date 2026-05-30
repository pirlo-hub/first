# 销售简历 AI 抽取与筛选

把应聘销售的简历用 AI 抽成结构化数据，按行业格式展示、入库、导出 Excel。

## 它能做什么

- 上传简历（PDF / Word / 图片 / txt），**支持批量**
- AI 抽取：
  - 个人信息：年龄、学历、销售总年限、**个人业绩简述**
  - 工作履历（按公司分行）：公司、**公司性质**、岗位、就职时间、经手客户、涉及产品品牌/类别/型号、在职情况备注
- 公司性质分 **4 种**，屏幕和 Excel 都有颜色区分：
  - 原厂（白）/ 方案商（黄）/ 贸易商（蓝）/ 代理商（绿）
- 抽取后可逐份核对：
  - 单份 **存入资料库**
  - 单份 **从当前页面删除**
  - **一键全部存入资料库**
  - **导出 Excel（当前抽取结果）**
- 资料库页签：浏览全部已存候选人 / 单独删除 / 导出整个资料库 Excel

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API key
cp .env.example .env      # 编辑 .env，填入 OPENAI_API_KEY 等

# 3. 启动界面
streamlit run app.py
```

## 目录结构

```
prompts/extract_prompt.md   抽取提示词
src/schema.py               抽取的固定字段结构（公司性质 4 选 1）
src/colors.py               公司性质的颜色（屏幕 + Excel 共用）
src/parse.py                文件 → 发给模型的内容块（PDF/图片走多模态）
src/extract.py              调 OpenAI 兼容接口 + 结构化抽取
src/db.py                   SQLite（library.db）建表与读写
src/excel.py                导出带颜色的 Excel
app.py                      Streamlit 界面
samples/                    放脱敏简历（不入库、被 git 忽略）
```

## 关于数据库

数据存在 `library.db`（首次运行自动创建）。如果你以前用过老版本的 `data.db`，新版**不再使用**，可手动删除。

## 注意

- 简历是敏感个人信息：本地 SQLite 存储，调 API 只传必要内容。
- AI 抽取建议人工复核，公司名/职位/时间应核对，业绩简述等可容错。
