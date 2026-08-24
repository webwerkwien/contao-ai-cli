"""REPL Skin — Unified terminal interface for the CLI harness.

Lives at:
    contao_ai_cli/utils/repl_skin.py

Usage:
    from contao_ai_cli.utils.repl_skin import ReplSkin

    skin = ReplSkin("contao-ai-cli", version="1.0.0")
    skin.print_banner()  # auto-detects skills/SKILL.md inside the package
    prompt_text = skin.prompt(project_name="my_video.mlt", modified=True)
    skin.success("Project saved")
    skin.error("File not found")
    skin.warning("Unsaved changes")
    skin.info("Processing 24 clips...")
    skin.status("Track 1", "3 clips, 00:02:30")
    skin.table(headers, rows)
    skin.print_goodbye()
"""

import os
import sys

# ── ANSI color codes (no external deps for core styling) ──────────────

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_UNDERLINE = "\033[4m"

# Brand colors
_CYAN = "\033[38;5;80m"       # cli-anything brand cyan
_CYAN_BG = "\033[48;5;80m"
_WHITE = "\033[97m"
_GRAY = "\033[38;5;245m"
_DARK_GRAY = "\033[38;5;240m"
_LIGHT_GRAY = "\033[38;5;250m"

# Software accent colors — each software gets a unique accent
_ACCENT_COLORS = {
    "gimp":        "\033[38;5;214m",   # warm orange
    "blender":     "\033[38;5;208m",   # deep orange
    "inkscape":    "\033[38;5;39m",    # bright blue
    "audacity":    "\033[38;5;33m",    # navy blue
    "libreoffice": "\033[38;5;40m",    # green
    "obs_studio":  "\033[38;5;55m",    # purple
    "kdenlive":    "\033[38;5;69m",    # slate blue
    "shotcut":     "\033[38;5;35m",    # teal green
}
_DEFAULT_ACCENT = "\033[38;5;75m"      # default sky blue

# Status colors
_GREEN = "\033[38;5;78m"
_YELLOW = "\033[38;5;220m"
_RED = "\033[38;5;196m"
_BLUE = "\033[38;5;75m"
_MAGENTA = "\033[38;5;176m"

# ── Glyphs ───────────────────────────────────────────────────────────
#
# Every character this class prints comes from one of these two tables, and the
# choice is made once per instance. Printing a glyph the output encoding cannot
# represent raises UnicodeEncodeError inside print() and takes the whole banner
# with it, so the guard has to be structural rather than one symbol at a time.

_UNICODE_GLYPHS = {
    # brand
    "icon": "◆", "icon_small": "▸", "skill": "◇",
    "arrow": "❯", "mid_dot": "·",
    # status
    "ok": "✓", "err": "✗", "warn": "⚠", "dot": "●",
    # box drawing
    "h": "─", "v": "│", "tl": "╭", "tr": "╮",
    "bl": "╰", "br": "╯",
    "t_down": "┬", "t_up": "┴", "t_right": "├",
    "t_left": "┤", "cross": "┼",
    # progress bar
    "bar_full": "█", "bar_empty": "░",
}

# Status markers follow the [OK] / [ERROR] / [!] convention the rest of the CLI
# already uses. The structural glyphs stay single-width so nothing reflows.
_ASCII_GLYPHS = {
    "icon": "*", "icon_small": ">", "skill": "*", "arrow": ">", "mid_dot": "-",
    "ok": "[OK]", "err": "[X]", "warn": "[!]", "dot": "[i]",
    "h": "-", "v": "|", "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "t_down": "+", "t_up": "+", "t_right": "+", "t_left": "+", "cross": "+",
    "bar_full": "#", "bar_empty": ".",
}


def _supports_unicode(stream=None) -> bool:
    """Whether the stream's encoding can represent the full Unicode glyph set.

    On Windows this is not a question of "console or not". Python resolves
    sys.stdout.encoding to UTF-8 when a console at code page 65001 is attached
    and to the locale encoding (typically cp1252) otherwise, so redirected
    output, CI, cron and any agent harness capturing stdout land on cp1252 and
    cannot print box drawing.
    """
    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False
    try:
        "".join(_UNICODE_GLYPHS.values()).encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes for length calculation."""
    import re
    return re.sub(r"\033\[[^m]*m", "", text)


def _visible_len(text: str) -> int:
    """Get visible length of text (excluding ANSI codes)."""
    return len(_strip_ansi(text))


class ReplSkin:
    """Unified REPL skin for cli-anything CLIs.

    Provides consistent branding, prompts, and message formatting
    across all CLI harnesses built with the cli-anything methodology.
    """

    def __init__(self, software: str, version: str = "1.0.0",
                 history_file: str | None = None, skill_path: str | None = None,
                 ascii_only: bool | None = None):
        """Initialize the REPL skin.

        Args:
            software: Software name (e.g., "gimp", "shotcut", "blender").
            version: CLI version string.
            history_file: Path for persistent command history.
                         Defaults to ~/.cli-anything-<software>/history
            skill_path: Path to the SKILL.md file for agent discovery.
                        Auto-detected from the package's skills/ directory if not provided.
                        Displayed in banner for AI agents to know where to read skill info.
            ascii_only: Force the ASCII glyph set. Defaults to auto-detection
                        from the stdout encoding, overridable by setting the
                        CONTAO_AI_CLI_ASCII environment variable.
        """
        self.software = software.lower().replace("-", "_")
        self.display_name = software.replace("_", " ").title()
        self.version = version

        # Auto-detect skill path from package layout:
        #   contao_ai_cli/utils/repl_skin.py  (this file)
        #   contao_ai_cli/skills/SKILL.md     (target)
        if skill_path is None:
            from pathlib import Path
            _auto = Path(__file__).resolve().parent.parent / "skills" / "SKILL.md"
            if _auto.is_file():
                skill_path = str(_auto)
        self.skill_path = skill_path
        self.accent = _ACCENT_COLORS.get(self.software, _DEFAULT_ACCENT)

        # History file
        if history_file is None:
            from pathlib import Path
            hist_dir = Path.home() / f".cli-anything-{self.software}"
            hist_dir.mkdir(parents=True, exist_ok=True)
            self.history_file = str(hist_dir / "history")
        else:
            self.history_file = history_file

        # Detect terminal capabilities
        self._color = self._detect_color_support()
        if ascii_only is None:
            ascii_only = (bool(os.environ.get("CONTAO_AI_CLI_ASCII"))
                          or not _supports_unicode())
        self._g = _ASCII_GLYPHS if ascii_only else _UNICODE_GLYPHS

    def _detect_color_support(self) -> bool:
        """Check if terminal supports color."""
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("CLI_ANYTHING_NO_COLOR"):
            return False
        if not hasattr(sys.stdout, "isatty"):
            return False
        return sys.stdout.isatty()

    def _c(self, code: str, text: str) -> str:
        """Apply color code if colors are supported."""
        if not self._color:
            return text
        return f"{code}{text}{_RESET}"

    # ── Banner ────────────────────────────────────────────────────────

    def print_banner(self):
        """Print the startup banner with branding."""
        inner = 54

        def _box_line(content: str) -> str:
            """Wrap content in box drawing, padding to inner width."""
            pad = inner - _visible_len(content)
            vl = self._c(_DARK_GRAY, self._g["v"])
            return f"{vl}{content}{' ' * max(0, pad)}{vl}"

        g = self._g
        top = self._c(_DARK_GRAY, f"{g['tl']}{g['h'] * inner}{g['tr']}")
        bot = self._c(_DARK_GRAY, f"{g['bl']}{g['h'] * inner}{g['br']}")

        # Title:  ◆  cli-anything · Shotcut
        icon = self._c(_CYAN + _BOLD, g["icon"])
        brand = self._c(_CYAN + _BOLD, "cli-anything")
        dot = self._c(_DARK_GRAY, g["mid_dot"])
        name = self._c(self.accent + _BOLD, self.display_name)
        title = f" {icon}  {brand} {dot} {name}"

        ver = f" {self._c(_DARK_GRAY, f'   v{self.version}')}"
        tip = f" {self._c(_DARK_GRAY, '   Type help for commands, quit to exit')}"
        empty = ""

        # Skill path for agent discovery
        skill_line = None
        if self.skill_path:
            skill_icon = self._c(_MAGENTA, g["skill"])
            skill_label = self._c(_DARK_GRAY, "   Skill:")
            skill_path_display = self._c(_LIGHT_GRAY, self.skill_path)
            skill_line = f" {skill_icon} {skill_label} {skill_path_display}"

        print(top)
        print(_box_line(title))
        print(_box_line(ver))
        if skill_line:
            print(_box_line(skill_line))
        print(_box_line(empty))
        print(_box_line(tip))
        print(bot)
        print()

    # ── Prompt ────────────────────────────────────────────────────────

    def prompt(self, project_name: str = "", modified: bool = False,
               context: str = "") -> str:
        """Build a styled prompt string for prompt_toolkit or input().

        Args:
            project_name: Current project name (empty if none open).
            modified: Whether the project has unsaved changes.
            context: Optional extra context to show in prompt.

        Returns:
            Formatted prompt string.
        """
        parts = []

        # Icon
        if self._color:
            parts.append(f"{_CYAN}{self._g['icon']}{_RESET} ")
        else:
            parts.append("> ")

        # Software name
        parts.append(self._c(self.accent + _BOLD, self.software))

        # Project context
        if project_name or context:
            ctx = context or project_name
            mod = "*" if modified else ""
            parts.append(f" {self._c(_DARK_GRAY, '[')}")
            parts.append(self._c(_LIGHT_GRAY, f"{ctx}{mod}"))
            parts.append(self._c(_DARK_GRAY, ']'))

        parts.append(self._c(_GRAY, f" {self._g['arrow']} "))

        return "".join(parts)

    def prompt_tokens(self, project_name: str = "", modified: bool = False,
                      context: str = ""):
        """Build prompt_toolkit formatted text tokens for the prompt.

        Use with prompt_toolkit's FormattedText for proper ANSI handling.

        Returns:
            list of (style, text) tuples for prompt_toolkit.
        """
        accent_hex = _ANSI_256_TO_HEX.get(self.accent, "#5fafff")
        tokens = []

        tokens.append(("class:icon", f"{self._g['icon']} "))
        tokens.append(("class:software", self.software))

        if project_name or context:
            ctx = context or project_name
            mod = "*" if modified else ""
            tokens.append(("class:bracket", " ["))
            tokens.append(("class:context", f"{ctx}{mod}"))
            tokens.append(("class:bracket", "]"))

        tokens.append(("class:arrow", f" {self._g['arrow']} "))

        return tokens

    def get_prompt_style(self):
        """Get a prompt_toolkit Style object matching the skin.

        Returns:
            prompt_toolkit.styles.Style
        """
        try:
            from prompt_toolkit.styles import Style
        except ImportError:
            return None

        accent_hex = _ANSI_256_TO_HEX.get(self.accent, "#5fafff")

        return Style.from_dict({
            "icon": "#5fdfdf bold",     # cyan brand color
            "software": f"{accent_hex} bold",
            "bracket": "#585858",
            "context": "#bcbcbc",
            "arrow": "#808080",
            # Completion menu
            "completion-menu.completion": "bg:#303030 #bcbcbc",
            "completion-menu.completion.current": f"bg:{accent_hex} #000000",
            "completion-menu.meta.completion": "bg:#303030 #808080",
            "completion-menu.meta.completion.current": f"bg:{accent_hex} #000000",
            # Auto-suggest
            "auto-suggest": "#585858",
            # Bottom toolbar
            "bottom-toolbar": "bg:#1c1c1c #808080",
            "bottom-toolbar.text": "#808080",
        })

    # ── Messages ──────────────────────────────────────────────────────

    def success(self, message: str):
        """Print a success message with green checkmark."""
        icon = self._c(_GREEN + _BOLD, self._g["ok"])
        print(f"  {icon} {self._c(_GREEN, message)}")

    def error(self, message: str):
        """Print an error message with red cross."""
        icon = self._c(_RED + _BOLD, self._g["err"])
        print(f"  {icon} {self._c(_RED, message)}", file=sys.stderr)

    def warning(self, message: str):
        """Print a warning message with yellow triangle."""
        icon = self._c(_YELLOW + _BOLD, self._g["warn"])
        print(f"  {icon} {self._c(_YELLOW, message)}")

    def info(self, message: str):
        """Print an info message with blue dot."""
        icon = self._c(_BLUE, self._g["dot"])
        print(f"  {icon} {self._c(_LIGHT_GRAY, message)}")

    def hint(self, message: str):
        """Print a subtle hint message."""
        print(f"  {self._c(_DARK_GRAY, message)}")

    def section(self, title: str):
        """Print a section header."""
        print()
        print(f"  {self._c(self.accent + _BOLD, title)}")
        print(f"  {self._c(_DARK_GRAY, self._g['h'] * len(title))}")

    # ── Status display ────────────────────────────────────────────────

    def status(self, label: str, value: str):
        """Print a key-value status line."""
        lbl = self._c(_GRAY, f"  {label}:")
        val = self._c(_WHITE, f" {value}")
        print(f"{lbl}{val}")

    def status_block(self, items: dict[str, str], title: str = ""):
        """Print a block of status key-value pairs.

        Args:
            items: Dict of label -> value pairs.
            title: Optional title for the block.
        """
        if title:
            self.section(title)

        max_key = max(len(k) for k in items) if items else 0
        for label, value in items.items():
            lbl = self._c(_GRAY, f"  {label:<{max_key}}")
            val = self._c(_WHITE, f"  {value}")
            print(f"{lbl}{val}")

    def progress(self, current: int, total: int, label: str = ""):
        """Print a simple progress indicator.

        Args:
            current: Current step number.
            total: Total number of steps.
            label: Optional label for the progress.
        """
        pct = int(current / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = (self._g["bar_full"] * filled
               + self._g["bar_empty"] * (bar_width - filled))
        text = f"  {self._c(_CYAN, bar)} {self._c(_GRAY, f'{pct:3d}%')}"
        if label:
            text += f" {self._c(_LIGHT_GRAY, label)}"
        print(text)

    # ── Table display ─────────────────────────────────────────────────

    def table(self, headers: list[str], rows: list[list[str]],
              max_col_width: int = 40):
        """Print a formatted table with box-drawing characters.

        Args:
            headers: Column header strings.
            rows: List of rows, each a list of cell strings.
            max_col_width: Maximum column width before truncation.
        """
        if not headers:
            return

        # Calculate column widths
        col_widths = [min(len(h), max_col_width) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = min(
                        max(col_widths[i], len(str(cell))), max_col_width
                    )

        def pad(text: str, width: int) -> str:
            t = str(text)[:width]
            return t + " " * (width - len(t))

        # Header
        header_cells = [
            self._c(_CYAN + _BOLD, pad(h, col_widths[i]))
            for i, h in enumerate(headers)
        ]
        sep = self._c(_DARK_GRAY, f" {self._g['v']} ")
        header_line = f"  {sep.join(header_cells)}"
        print(header_line)

        # Separator
        sep_parts = [self._c(_DARK_GRAY, self._g["h"] * w) for w in col_widths]
        _h = self._g["h"]
        sep_line = self._c(_DARK_GRAY, f"  {(_h * 3).join([_h * w for w in col_widths])}")
        print(sep_line)

        # Rows
        for row in rows:
            cells = []
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    cells.append(self._c(_LIGHT_GRAY, pad(str(cell), col_widths[i])))
            row_sep = self._c(_DARK_GRAY, f" {self._g['v']} ")
            print(f"  {row_sep.join(cells)}")

    # ── Help display ──────────────────────────────────────────────────

    def help(self, commands: dict[str, str]):
        """Print a formatted help listing.

        Args:
            commands: Dict of command -> description pairs.
        """
        self.section("Commands")
        max_cmd = max(len(c) for c in commands) if commands else 0
        for cmd, desc in commands.items():
            cmd_styled = self._c(self.accent, f"  {cmd:<{max_cmd}}")
            desc_styled = self._c(_GRAY, f"  {desc}")
            print(f"{cmd_styled}{desc_styled}")
        print()

    # ── Goodbye ───────────────────────────────────────────────────────

    def print_goodbye(self):
        """Print a styled goodbye message."""
        icon = self._c(_CYAN, self._g["icon_small"])
        print(f"\n  {icon} {self._c(_GRAY, 'Goodbye!')}\n")

    # ── Prompt toolkit session factory ────────────────────────────────

    def create_prompt_session(self):
        """Create a prompt_toolkit PromptSession with skin styling.

        Returns:
            A configured PromptSession, or None if prompt_toolkit unavailable.
        """
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory
            from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
            from prompt_toolkit.formatted_text import FormattedText

            style = self.get_prompt_style()

            session = PromptSession(
                history=FileHistory(self.history_file),
                auto_suggest=AutoSuggestFromHistory(),
                style=style,
                enable_history_search=True,
            )
            return session
        except ImportError:
            return None

    def get_input(self, pt_session, project_name: str = "",
                  modified: bool = False, context: str = "") -> str:
        """Get input from user using prompt_toolkit or fallback.

        Args:
            pt_session: A prompt_toolkit PromptSession (or None).
            project_name: Current project name.
            modified: Whether project has unsaved changes.
            context: Optional context string.

        Returns:
            User input string (stripped).
        """
        if pt_session is not None:
            from prompt_toolkit.formatted_text import FormattedText
            tokens = self.prompt_tokens(project_name, modified, context)
            return pt_session.prompt(FormattedText(tokens)).strip()
        else:
            raw_prompt = self.prompt(project_name, modified, context)
            return input(raw_prompt).strip()

    # ── Toolbar builder ───────────────────────────────────────────────

    def bottom_toolbar(self, items: dict[str, str]):
        """Create a bottom toolbar callback for prompt_toolkit.

        Args:
            items: Dict of label -> value pairs to show in toolbar.

        Returns:
            A callable that returns FormattedText for the toolbar.
        """
        def toolbar():
            from prompt_toolkit.formatted_text import FormattedText
            parts = []
            for i, (k, v) in enumerate(items.items()):
                if i > 0:
                    parts.append(("class:bottom-toolbar.text",
                                  f"  {self._g['v']}  "))
                parts.append(("class:bottom-toolbar.text", f" {k}: "))
                parts.append(("class:bottom-toolbar", v))
            return FormattedText(parts)
        return toolbar


# ── ANSI 256-color to hex mapping (for prompt_toolkit styles) ─────────

_ANSI_256_TO_HEX = {
    "\033[38;5;33m":  "#0087ff",  # audacity navy blue
    "\033[38;5;35m":  "#00af5f",  # shotcut teal
    "\033[38;5;39m":  "#00afff",  # inkscape bright blue
    "\033[38;5;40m":  "#00d700",  # libreoffice green
    "\033[38;5;55m":  "#5f00af",  # obs purple
    "\033[38;5;69m":  "#5f87ff",  # kdenlive slate blue
    "\033[38;5;75m":  "#5fafff",  # default sky blue
    "\033[38;5;80m":  "#5fd7d7",  # brand cyan
    "\033[38;5;208m": "#ff8700",  # blender deep orange
    "\033[38;5;214m": "#ffaf00",  # gimp warm orange
}
