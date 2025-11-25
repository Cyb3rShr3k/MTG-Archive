# core/sql_utils.py
from __future__ import annotations
from typing import List, Tuple, Any


def _unescape_sql_string(s: str) -> str:
    # Handle standard SQL single-quoted string with '' as escaped '
    return s.replace("''", "'")


def parse_sql_values_tuple(values_src: str) -> List[Any]:
    """
    Parse a single SQL VALUES tuple body (without surrounding parentheses),
    splitting into Python values. Supports:
    - Single-quoted strings with '' escapes
    - NULL -> None
    - Numeric ints/floats
    - Otherwise returns raw string
    """
    out: List[Any] = []  # type: ignore
    i = 0
    n = len(values_src)
    buf = []
    in_str = False
    while i < n:
        ch = values_src[i]
        if in_str:
            if ch == "'":
                # Peek escape
                if i + 1 < n and values_src[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                else:
                    in_str = False
                    i += 1
                    continue
            else:
                buf.append(ch)
                i += 1
                continue
        else:
            if ch == "'":
                in_str = True
                i += 1
                continue
            elif ch == ',':
                token = ''.join(buf).strip()
                out.append(_convert_sql_literal(token))
                buf = []
                i += 1
                continue
            else:
                buf.append(ch)
                i += 1
                continue
    # last token
    token = ''.join(buf).strip()
    out.append(_convert_sql_literal(token))
    return out


def _convert_sql_literal(token: str) -> Any:
    if token.upper() == 'NULL':
        return None
    # Numeric
    try:
        if '.' in token:
            return float(token)
        return int(token)
    except Exception:
        pass
    # Quoted strings are already unescaped by caller; but if still quoted, strip
    if token.startswith("'") and token.endswith("'") and len(token) >= 2:
        return _unescape_sql_string(token[1:-1])
    return token


def split_values_rows(values_section: str) -> List[str]:
    """
    Given a VALUES section content like: (..),(...),(...) possibly with newlines,
    return a list of each tuple body without parentheses.
    Handles parentheses nesting level 1 and strings.
    """
    rows: List[str] = []
    i = 0
    n = len(values_section)
    in_str = False
    depth = 0
    start = -1
    while i < n:
        ch = values_section[i]
        if in_str:
            if ch == "'" and i + 1 < n and values_section[i + 1] == "'":
                i += 2
                continue
            elif ch == "'":
                in_str = False
                i += 1
                continue
            else:
                i += 1
                continue
        else:
            if ch == "'":
                in_str = True
                i += 1
                continue
            if ch == '(':
                if depth == 0:
                    start = i + 1
                depth += 1
                i += 1
                continue
            if ch == ')':
                depth -= 1
                if depth == 0 and start != -1:
                    rows.append(values_section[start:i])
                    start = -1
                i += 1
                continue
            i += 1
    return rows
