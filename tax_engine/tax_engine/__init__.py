"""Pure, independently-testable tax arithmetic for Livro.

No network I/O lives in this package. Every function takes plain data in
(dicts, Decimals, dated table objects) and returns plain data out, so it can
be unit-tested without a live BACEN/Solana/Etherfuse connection, and so the
same engine can be invoked from a skill or SOP step via the `shell` tool
without dragging chat/agent glue into the calculation.
"""
