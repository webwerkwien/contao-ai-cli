"""
Parser for Symfony VarDumper output format.
Converts debug:dca output into Python dicts/lists.

Handles:
  - string values: "foo"
  - integer/float values: 42, 3.14
  - booleans: true, false
  - null
  - arrays: array:N [ "key" => value ... ]
  - references: &N value  (first occurrence: define; subsequent: resolve)
  - collapsed arrays: array:2 [&3]  (back-reference, returns stored value)
  - closures: Closure() {#N ... }  (returned as "__closure__")
  - integer keys: 0 => "value"
"""


class VarDumpParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self._refs: dict = {}  # ref-id → value (for back-references)

    # ── whitespace ──────────────────────────────────────────────────────────

    def _ws(self):
        while self.pos < len(self.text) and self.text[self.pos] in ' \t\n\r':
            self.pos += 1

    def _peek(self, n=1) -> str:
        return self.text[self.pos:self.pos + n]

    # ── top-level entry ──────────────────────────────────────────────────────

    def parse(self):
        self._ws()
        return self._value()

    # ── value dispatcher ────────────────────────────────────────────────────

    def _value(self):
        self._ws()

        # &N reference marker
        if self._peek() == '&':
            self.pos += 1
            ref_id = self._digits()
            self._ws()
            # If next char is ] or end → this is a pure back-reference
            if self.pos >= len(self.text) or self._peek() in (']', '\n', ' ', '\t'):
                return self._refs.get(ref_id)
            # Otherwise the value follows — parse and register it
            val = self._value()
            self._refs[ref_id] = val
            return val

        # array
        if self._peek(6) == 'array:':
            return self._array()

        # Closure — skip until matching }
        if self._peek(8) == 'Closure(':
            return self._closure()

        # quoted string
        if self._peek() == '"':
            return self._string()

        # boolean / null  (must precede number check)
        for literal, val in [('true', True), ('false', False), ('null', None)]:
            n = len(literal)
            if self.text[self.pos:self.pos + n] == literal:
                after = self.pos + n
                if after >= len(self.text) or not self.text[after].isalnum():
                    self.pos += n
                    return val

        # number (int or float, possibly negative)
        if self._peek().isdigit() or (
                self._peek() == '-' and self.pos + 1 < len(self.text)
                and self.text[self.pos + 1].isdigit()):
            return self._number()

        # Unquoted identifier / class-based callback (e.g. ClassName::method(): type)
        # May be followed on the same line by a {#N ... } annotation block.
        if self._peek().isalpha() or self._peek() == '\\':
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in ('\n', '\r', '{'):
                self.pos += 1
            identifier = self.text[start:self.pos].strip()
            # Skip {#N ... } block on same line (or following line after ws)
            self._ws()
            if self._peek() == '{':
                self._closure()  # reuse closure skipper
            return '__identifier__:' + identifier

        raise ValueError(
            f"Unexpected '{self._peek()}' at pos {self.pos}: "
            f"…{self.text[max(0, self.pos - 30):self.pos + 30]}…"
        )

    # ── array ────────────────────────────────────────────────────────────────

    def _array(self):
        # skip 'array:N ['
        while self.pos < len(self.text) and self.text[self.pos] != '[':
            self.pos += 1
        self.pos += 1  # skip [

        self._ws()
        # collapsed back-reference: array:N [&M]
        if self._peek() == '&':
            self.pos += 1
            ref_id = self._digits()
            self._ws()
            if self._peek() == ']':
                self.pos += 1
            return self._refs.get(ref_id, {})

        result = {}
        while True:
            self._ws()
            if self.pos >= len(self.text):
                break
            if self._peek() == ']':
                self.pos += 1
                break

            key = self._key()
            self._ws()
            if self._peek(2) == '=>':
                self.pos += 2
            self._ws()
            val = self._value()
            result[key] = val

        return result

    # ── key (string or integer) ──────────────────────────────────────────────

    def _key(self):
        self._ws()
        if self._peek() == '"':
            return self._string()
        if self._peek().isdigit() or (
                self._peek() == '-' and self.pos + 1 < len(self.text)
                and self.text[self.pos + 1].isdigit()):
            return self._number()
        raise ValueError(
            f"Expected key at pos {self.pos}: "
            f"…{self.text[max(0, self.pos - 20):self.pos + 20]}…"
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _digits(self) -> int:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        return int(self.text[start:self.pos]) if self.pos > start else 0

    def _string(self) -> str:
        """
        Parse a quoted string. VarDumper does NOT escape internal double-quotes,
        so we use a lookahead heuristic: a closing `"` is valid when it is
        immediately followed by (optional spaces/tabs then) one of:
          - newline / end-of-text
          - ']'  (end of array)
          - '=>'  (key separator — means this was a key)
        Any other `"` is treated as part of the string content.
        """
        self.pos += 1  # skip opening "
        start = self.pos
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c == '\\':
                # explicit escape — skip next char
                self.pos += 2
                continue
            if c == '"':
                # lookahead: skip spaces/tabs after the candidate close-quote
                after = self.pos + 1
                while after < len(self.text) and self.text[after] in ' \t':
                    after += 1
                # valid end-of-string markers
                if (after >= len(self.text)
                        or self.text[after] in ('\n', '\r', ']')
                        or self.text[after:after + 2] == '=>'):
                    result = self.text[start:self.pos]
                    self.pos += 1  # skip closing "
                    return result
                # otherwise this quote is embedded in the value — keep going
            self.pos += 1
        return self.text[start:self.pos]

    def _number(self):
        start = self.pos
        if self._peek() == '-':
            self.pos += 1
        while self.pos < len(self.text) and (
                self.text[self.pos].isdigit() or self.text[self.pos] == '.'):
            self.pos += 1
        s = self.text[start:self.pos]
        try:
            return int(s)
        except ValueError:
            return float(s)

    def _closure(self) -> str:
        # skip to opening {
        while self.pos < len(self.text) and self.text[self.pos] != '{':
            self.pos += 1
        depth = 0
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
            self.pos += 1
        return '__closure__'


# ── public API ───────────────────────────────────────────────────────────────

def parse_vardump(text: str):
    """Parse Symfony VarDumper output into Python dicts/lists."""
    return VarDumpParser(text).parse()
