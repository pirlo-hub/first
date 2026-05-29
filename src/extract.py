"""核心：把一份简历文件喂给 OpenAI，拿回结构化 dict。

用 function calling 强制返回固定 JSON，支持图片/PDF 多模态输入。

命令行用法：
    python -m src.extract <简历文件路径> [--save] [--code 编号] [--model 模型名]
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .parse import build_content_blocks
from .schema import DEFAULT_MODEL, EXTRACT_TOOL

load_dotenv()

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_prompt.md"


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


def _parse_tool_args(raw: str) -> dict:
    """容忍尾部多余内容地解析 function call 的 arguments。

    模型偶尔会在合法 JSON 后多吐字符（重复输出/附加说明），导致 json.loads
    报 "Extra data" 错。用 raw_decode 只取第一个合法对象，丢弃后面的。
    """
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        obj, _ = json.JSONDecoder().raw_decode(raw)
        return obj


def extract_resume(file_path: str, model: str = DEFAULT_MODEL, max_retries: int = 1) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY，请复制 .env.example 为 .env 并填入 key")

    # 支持自定义 base URL（用于 OpenAI 兼容的第三方代理）；不设则走官方
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    client = OpenAI(api_key=api_key, base_url=base_url)

    # content blocks：图片简历是 image_url 列表，文字简历是单个 text block
    content_blocks = build_content_blocks(file_path)
    content_blocks = content_blocks + [{"type": "text", "text": _load_prompt()}]
    messages = [{"role": "user", "content": content_blocks}]

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                tools=[_build_openai_tool()],
                tool_choice={"type": "function", "function": {"name": EXTRACT_TOOL["name"]}},
                messages=messages,
            )
            for choice in resp.choices:
                msg = choice.message
                if msg.tool_calls:
                    for call in msg.tool_calls:
                        if call.function.name == EXTRACT_TOOL["name"]:
                            return _parse_tool_args(call.function.arguments)
            raise RuntimeError("模型未通过工具返回结构化结果")
        except (json.JSONDecodeError, RuntimeError) as e:
            last_err = e
            if attempt >= max_retries:
                break
            # 否则进入下一轮重试

    raise RuntimeError(f"抽取失败（已重试 {max_retries} 次）: {last_err}")


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="从简历抽取结构化信息（OpenAI）")
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
