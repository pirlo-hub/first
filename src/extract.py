"""核心：把一份简历文件喂给 Claude，拿回结构化 dict。

命令行用法：
    python -m src.extract <简历文件路径> [--save] [--code 编号] [--model 模型名]
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from .parse import build_content_blocks
from .schema import DEFAULT_MODEL, EXTRACT_TOOL

load_dotenv()

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_prompt.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def extract_resume(file_path: str, model: str = DEFAULT_MODEL) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 ANTHROPIC_API_KEY，请复制 .env.example 为 .env 并填入 key")

    client = Anthropic(api_key=api_key)
    content = build_content_blocks(file_path)
    content.append({"type": "text", "text": _load_prompt()})

    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": EXTRACT_TOOL["name"]},
        messages=[{"role": "user", "content": content}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == EXTRACT_TOOL["name"]:
            return block.input
    raise RuntimeError("模型未通过工具返回结构化结果")


def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="从简历抽取结构化信息")
    ap.add_argument("file", help="简历文件路径（pdf/docx/图片/txt）")
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
