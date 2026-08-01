"""JSON-in/JSON-out CLI so skill step instructions can call the trust guard
via the stock `shell` tool, same pattern as ../tax_engine/ and ../rendering/.

Usage:
    echo '{"content": "...", "source": "transaction_memo"}' | python3 -m trust evaluate
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from trust.guard import evaluate


def _cmd_evaluate(a: dict) -> dict:
    result = evaluate(a["content"], a["source"])
    payload = asdict(result)
    payload["detection"] = asdict(result.detection)
    return payload


COMMANDS = {"evaluate": _cmd_evaluate}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python3 -m trust <{'|'.join(COMMANDS)}> < args.json", file=sys.stderr)
        return 2

    args = json.loads(sys.stdin.read())
    try:
        result = COMMANDS[argv[0]](args)
    except (KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
