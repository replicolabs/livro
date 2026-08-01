"""JSON-in/JSON-out CLI so skill/SOP step instructions can validate a record
BEFORE appending it to the workspace ledger, via the stock `shell` tool --
same pattern as ../tax_engine/, ../rendering/, ../trust/.

Usage:
    echo '{"record_type": "disposition_instruction", "data": {...}}' | python3 -m ledger validate
"""
from __future__ import annotations

import json
import sys

from ledger.serialization import from_dict, to_json_line


def _cmd_validate(a: dict) -> dict:
    """Validate `data` as `record_type`. On success, returns the exact JSONL
    line the caller should append (so validation and serialization can
    never drift apart). On failure, the CLI exits non-zero with the
    validation error -- the caller must not append anything.
    """
    record = from_dict(a["record_type"], a["data"])
    return {"valid": True, "json_line": to_json_line(record)}


COMMANDS = {"validate": _cmd_validate}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python3 -m ledger <{'|'.join(COMMANDS)}> < args.json", file=sys.stderr)
        return 2

    args = json.loads(sys.stdin.read())
    try:
        result = COMMANDS[argv[0]](args)
    except (KeyError, ValueError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
