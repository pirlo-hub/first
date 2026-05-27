"""核心：把一份简历文件喂给 DeepSeek，拿回结构化 dict。

用 OpenAI 兼容接口 + function calling 强制返回固定 JSON。

命令行用法：
    python -m src.extract <简历文件路径> [--save] [--code 编号] [--model 模型名]
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .parse import extract_text
from .schema import DEFAULT_MODEL, EXTRACT_TOOL

load_dotenv()

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_prompt.md"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_openai_tool() -> dict:
    """把 EXTRACT_TOOL 转成 OpenAI function calling 格式。"""
    return {
        "type": "function",
        "function": {
            "name": EXTRACT_TOOL["name"],
            "description": EXTRACT_TOOL["description"],
            "parameters": EXTRACT_TOOL["input_schema"],
        },
    }


def extract_resume(file_path: str, model: str = DEFAULT_MODEL) -> dict:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填入 key")

    client = OpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)

    resume_text = extract_text(file_path)
    system_prompt = _load_prompt()

    resp = client.chat.completions.create(
        model=model,
        tools=[_build_openai_tool()],
        tool_choice={"type": "function", "function": {"name": EXTRACT_TOOL["name"]}},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": resume_text},
        ],
    )

    for choice in resp.choices:
        msg = choice.message
        if msg.tool_calls:
            for call in msg.tool_calls:
                if call.function.name == EXTRACT_TOOL["name"]:
                    return json.loads(call.function.arguments)

    raise RuntimeError("模型未通过工具返回结构化结果")


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="从简历抽取结构化信息（DeepSeek）")
    ap.add_argument("file", help="简历文件路径（pdf/docx/txt）")
    ap.add_argument("--save", action="store_true", help="同时写入 SQLite")
    ap.add_argument("--code", default=None, help="候选人脱敏编号")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="模型名")
    args = ap.parse_args()

    data = extract_resume(args.file, model=args.model)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.save:
        from . import db

        cid = db.save_extraction(data, Path(args.file).name, args.code)
        print(f"\n已写入数据库，candidate id = {cid}")


if __name__ == "__main__":
    _main()
