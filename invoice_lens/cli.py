import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .engine import ask, extract
from .model import FieldModel


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find invoice fields with page-level evidence.")
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("extract", "ask"):
        sub = commands.add_parser(action)
        if action == "ask":
            sub.add_argument("question", help="Ask about the total, due date, supplier or invoice ID.")
        sub.add_argument("files", type=Path, nargs="+", help="One invoice or matching translations.")
        sub.add_argument("--ocr", action="store_true", help="Read images and PDF pages without a text layer.")
        sub.add_argument("--languages", default="kaz+rus+eng", help="Installed Tesseract languages.")
        sub.add_argument("--json", action="store_true", help="Write the complete result as UTF-8 JSON.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        model = FieldModel()
        facts, warnings = extract(args.files, model, args.ocr, args.languages)
        if args.action == "extract":
            result = {"fields": [asdict(fact) for fact in facts]}
        else:
            result = ask(args.question, model, facts, [file.name for file in args.files])
        result["warnings"] = warnings
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.action == "extract":
            for fact in facts:
                print(f"{fact.field} = {fact.value}  [{fact.source}, p. {fact.page}, line {fact.line}]")
                print(f"  {fact.quote}")
            if not facts:
                print("No supported fields found.")
        else:
            print(f"{result['status']} ({result['field'] or 'unknown field'})")
            for answer in result["answers"]:
                print(answer["value"])
                for cite in answer["citations"]:
                    print(f"  {cite['source']}, p. {cite['page']}, line {cite['line']} | {cite['quote']}")
            if result["status"] == "select_one_invoice":
                print("Ask about a single file, or supply copies that share the same invoice number.")
        if not args.json:
            for warning in warnings:
                print(f"Review: {warning}")
        return 0
    except (OSError, ValueError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
