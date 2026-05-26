"""抽取用的固定结构。用 tool use 强制模型返回这个形状的 JSON。"""

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODEL = "claude-opus-4-7"  # 难解析的简历再升级用

COMPANY_TYPES = ["原厂", "方案商", "贸易商", "未知"]

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
                },
                "required": ["age", "education", "total_sales_years"],
            },
            "employments": {
                "type": "array",
                "description": "全部工作履历，按时间倒序",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string", "description": "企业名称"},
                        "title": {"type": ["string", "null"], "description": "职位"},
                        "start": {"type": ["string", "null"], "description": "入职时间，YYYY-MM 或 YYYY"},
                        "end": {"type": ["string", "null"], "description": "离职时间，至今填 present"},
                        "duration_months": {"type": ["integer", "null"], "description": "在职时长（月）"},
                        "is_sales": {"type": "boolean", "description": "是否销售岗位"},
                        "company_type": {
                            "type": "string",
                            "enum": COMPANY_TYPES,
                            "description": "企业性质；仅凭简历无法判断时填 未知（后续阶段再联网补全）",
                        },
                        "customer_deals": {
                            "type": "array",
                            "description": "在该公司经手过的客户与产品；简历未提及则空数组",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "customer_name": {"type": "string", "description": "客户名称"},
                                    "product_category": {"type": ["string", "null"], "description": "产品类别"},
                                    "product_model": {"type": ["string", "null"], "description": "产品型号"},
                                    "product_brand": {"type": ["string", "null"], "description": "产品品牌"},
                                    "revenue": {"type": ["string", "null"], "description": "营收/规模，按简历原文表述"},
                                },
                                "required": ["customer_name"],
                            },
                        },
                    },
                    "required": ["company", "is_sales", "company_type", "customer_deals"],
                },
            },
        },
        "required": ["candidate", "employments"],
    },
}
