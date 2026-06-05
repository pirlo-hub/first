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

from .parse import build_content_blocks, summarize_blocks
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


def extract_resume(file_path: str, model: str = DEFAULT_MODEL, max_retries: int = 1,
                   return_debug: bool = False):
    """抽取一份简历。

    return_debug=True 时返回 (data, debug)，debug 含模型实际读到的输入概况
    （识别出的文字 / 图片张数），用于人工核对是否发生"脑补"。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY，请复制 .env.example 为 .env 并填入 key")

    # 支持通过环境变量覆盖模型名，方便切换代理时适配不同模型别名
    model = os.environ.get("OPENAI_MODEL") or model
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    client = OpenAI(api_key=api_key, base_url=base_url)

    # content blocks：图片简历是 image_url 列表，文字简历是单个 text block
    resume_blocks = build_content_blocks(file_path)
    debug = summarize_blocks(resume_blocks)  # 模型实际拿到的简历输入概况
    content_blocks = resume_blocks + [{"type": "text", "text": _load_prompt()}]
    messages = [{"role": "user", "content": content_blocks}]

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                tools=[_build_openai_tool()],
                tool_choice="required",  # 强制调用工具；兼容不支持 tool_choice.function 的旧版代理
                temperature=0,  # 关掉创造性，降低凭空捏造（客户名/品牌/型号等）
                messages=messages,
            )
            for choice in resp.choices:
                msg = choice.message
                if msg.tool_calls:
                    for call in msg.tool_calls:
                        if call.function.name == EXTRACT_TOOL["name"]:
                            data = _parse_tool_args(call.function.arguments)
                            return (data, debug) if return_debug else data
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
