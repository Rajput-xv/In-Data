"""Source-specific parsers.

Each module exposes `parse(content: bytes) -> ParseResult`.
Parsers are dumb on purpose: they tokenize the file into dicts and
collect parse errors. They do not coerce types, look up codes, or
write to the database. That's normalize / validate's job.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
