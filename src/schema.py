"""抽取用的固定结构。用 tool use 强制模型返回这个形状的 JSON。"""

DEFAULT_MODEL = "gpt-5.5"  # 支持多模态（图片 + 文字）

# 4 种公司性质（带颜色规则，颜色定义在 src/colors.py）
COMPANY_TYPES = ["原厂", "方案商", "贸易商", "代理商"]

EXTRACT_TOOL = {
    "name": "record_resume",
    "description": (
        "记录从一份销售简历中抽取出的结构化信息。"
        "所有字段尽量如实抽取；简历里没有的信息一律留空（null 或空数组），不要编造或推测。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "candidate": {
                "type": "object",
                "properties": {
                    "age": {"type": ["integer", "null"], "description": "年龄；简历未提供则 null"},
                    "education": {"type": ["string", "null"], "description": "最高学历，如 本科/硕士/大专"},
                    "total_sales_years": {
                        "type": ["number", "null"],
                        "description": "销售从业总年限（单位：年），可由销售岗履历累加推算",
                    },
                    "business_summary": {
                        "type": ["string", "null"],
                        "description": "个人业绩简述：用 1-3 句话概括他的销售业绩、主要成就、擅长领域。简历未明确提供时填 null",
                    },
                },
                "required": ["age", "education", "total_sales_years", "business_summary"],
            },
            "employments": {
                "type": "array",
                "description": "全部工作履历，按时间倒序",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string", "description": "企业名称"},
                        "company_type": {
                            "type": "string",
                            "enum": COMPANY_TYPES,
                            "description": "公司性质，必须从 4 种里选一种：原厂/方案商/贸易商/代理商；按简历内容做最佳判断",
                        },
                        "title": {"type": ["string", "null"], "description": "职位/岗位"},
                        "start": {"type": ["string", "null"], "description": "入职时间，YYYY-MM 或 YYYY"},
                        "end": {"type": ["string", "null"], "description": "离职时间，至今填 present"},
                        "is_sales": {"type": "boolean", "description": "是否销售岗位"},
                        "customers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "在该公司经手过的客户名称列表；无则空数组",
                        },
                        "product_brands": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "涉及的产品品牌列表",
                        },
                        "product_categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "涉及的产品类别列表（如 MCU、电源管理芯片、MOS 等）",
                        },
                        "product_models": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "涉及的产品具体型号列表",
                        },
                        "notes": {
                            "type": ["string", "null"],
                            "description": "在职情况备注：简历中提到的业绩、离职原因、特殊情况等",
                        },
                    },
                    "required": [
                        "company", "company_type", "title", "start", "end",
                        "is_sales", "customers", "product_brands",
                        "product_categories", "product_models", "notes",
                    ],
                },
            },
        },
        "required": ["candidate", "employments"],
    },
}
