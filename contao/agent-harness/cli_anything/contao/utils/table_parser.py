"""
Parser for Symfony Console Table output format.
Converts ASCII table output (e.g. from doctrine:query:sql, contao:user:list)
into a list of dicts for structured access by AI agents.

Example input:
 ---- ----------- --------------------- -----------
  id   username    email                 firstname
 ---- ----------- --------------------- -----------
  1    j.smith     j.smith@example.com   John
  2    d.evans     d.evans@example.com   Donna
 ---- ----------- --------------------- -----------
"""
import re


def parse_table(text: str) -> list[dict]:
    """
    Parse Symfony Console Table output into a list of dicts.
    Returns [] if the text does not look like a table.
    Each row becomes a dict keyed by the column headers.
    """
    lines = text.splitlines()

    # Find separator lines (lines consisting of dashes and spaces, e.g. " ---- -------- ")
    sep_pattern = re.compile(r'^\s*[-\s]+$')
    sep_indices = [i for i, line in enumerate(lines) if sep_pattern.match(line) and '-' in line]

    if len(sep_indices) < 2:
        return []

    # Determine column boundaries from the first separator line
    sep_line = lines[sep_indices[0]]
    col_spans = _column_spans(sep_line)

    # Header row is between first and second separator
    header_idx = sep_indices[0] + 1
    if header_idx >= sep_indices[1]:
        return []
    headers = [_cell(lines[header_idx], start, end) for start, end in col_spans]

    # Data rows are after the second separator, up to the last separator
    data_start = sep_indices[1] + 1
    data_end = sep_indices[-1] if sep_indices[-1] > sep_indices[1] else len(lines)

    rows = []
    for line in lines[data_start:data_end]:
        if sep_pattern.match(line) and '-' in line:
            continue
        if not line.strip():
            continue
        values = [_cell(line, start, end) for start, end in col_spans]
        rows.append(dict(zip(headers, values)))

    return rows


def _column_spans(sep_line: str) -> list[tuple[int, int]]:
    """
    Extract (start, end) character positions for each column
    from a separator line like ' ---- ----------- ----- '.
    """
    spans = []
    in_dashes = False
    start = 0
    for i, ch in enumerate(sep_line):
        if ch == '-' and not in_dashes:
            in_dashes = True
            start = i
        elif ch != '-' and in_dashes:
            in_dashes = False
            spans.append((start, i))
    if in_dashes:
        spans.append((start, len(sep_line)))
    return spans


def _cell(line: str, start: int, end: int) -> str:
    """Extract and strip cell value from a line using column boundaries."""
    segment = line[start:end] if end <= len(line) else line[start:]
    return segment.strip()
