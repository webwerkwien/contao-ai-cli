"""
DCA schema sync for contao-cli-agent.

Fetches field definitions from the live Contao server via debug:dca,
extracts field metadata (mandatory, inputType, options, label),
and stores them as a local JSON schema per session.

Schema files are stored at:
  ~/.contao-cli-agent/schemas/<session-name>/<table>.json

Usage:
  schema = sync_table(backend, 'tl_user', session_path)
  fields = mandatory_fields('tl_user', session_path)
"""
import json
import os
import shlex
from datetime import datetime
from typing import Optional

from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.utils.vardump_parser import parse_vardump
from cli_anything.contao.utils.table_parser import parse_table

# Fallback tables used when the server DCA cache is not reachable
FALLBACK_TABLES = [
    'tl_user',
    'tl_page',
    'tl_article',
    'tl_content',
    'tl_member',
]

# Path to the compiled DCA cache relative to contao_root
_DCA_CACHE_PATH = 'var/cache/prod/contao/dca'

# Static options for PHP-function-based callbacks (Contao core, rarely changes)
# ISO 639-1 language codes supported by Contao 5
STATIC_OPTIONS: dict[tuple, dict] = {
    ('tl_user', 'language'): {
        'ar': 'Arabic', 'be': 'Belarusian', 'bg': 'Bulgarian', 'bs': 'Bosnian',
        'ca': 'Catalan', 'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish',
        'de': 'German', 'el': 'Greek', 'en': 'English', 'es': 'Spanish',
        'et': 'Estonian', 'eu': 'Basque', 'fa': 'Persian', 'fi': 'Finnish',
        'fr': 'French', 'gl': 'Galician', 'he': 'Hebrew', 'hr': 'Croatian',
        'hu': 'Hungarian', 'hy': 'Armenian', 'id': 'Indonesian', 'it': 'Italian',
        'ja': 'Japanese', 'ka': 'Georgian', 'ko': 'Korean', 'lt': 'Lithuanian',
        'lv': 'Latvian', 'mk': 'Macedonian', 'ms': 'Malay', 'nl': 'Dutch',
        'nn': 'Norwegian Nynorsk', 'no': 'Norwegian', 'pl': 'Polish',
        'pt': 'Portuguese', 'rm': 'Romansh', 'ro': 'Romanian', 'ru': 'Russian',
        'sk': 'Slovak', 'sl': 'Slovenian', 'sq': 'Albanian', 'sr': 'Serbian',
        'sv': 'Swedish', 'sw': 'Swahili', 'th': 'Thai', 'tr': 'Turkish',
        'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese', 'zh': 'Chinese',
    },
    ('tl_member', 'language'): {
        'ar': 'Arabic', 'de': 'German', 'en': 'English', 'es': 'Spanish',
        'fr': 'French', 'it': 'Italian', 'nl': 'Dutch', 'pl': 'Polish',
        'pt': 'Portuguese', 'ru': 'Russian', 'tr': 'Turkish', 'zh': 'Chinese',
    },
    # Contao 5 core page types (extensions may register additional types)
    ('tl_page', 'type'): {
        'regular': 'Regular page', 'forward': 'Forward', 'redirect': 'Redirect',
        'root': 'Root page', 'error_401': 'Error 401', 'error_403': 'Error 403',
        'error_404': 'Error 404', 'error_410': 'Error 410', 'error_503': 'Error 503',
        'logout': 'Logout',
    },
}

# SQL queries to resolve table-based option callbacks
# Returns rows with 'id' and 'name' columns
TABLE_OPTION_QUERIES: dict[tuple, str] = {
    ('tl_user',   'groups'):         'SELECT id, name FROM tl_user_group ORDER BY name',
    ('tl_member', 'groups'):         'SELECT id, name FROM tl_member_group ORDER BY name',
    ('tl_page',   'groups'):         'SELECT id, name FROM tl_member_group ORDER BY name',
    ('tl_page',   'layout'):         'SELECT id, name FROM tl_layout ORDER BY name',
    ('tl_page',   'subpageLayout'):  'SELECT id, name FROM tl_layout ORDER BY name',
    ('tl_page',   'newsArchives'):   'SELECT id, title AS name FROM tl_news_archive ORDER BY title',
    ('tl_page',   'eventCalendars'): 'SELECT id, title AS name FROM tl_calendar ORDER BY title',
    ('tl_page',   'imgSize'):        'SELECT id, name FROM tl_image_size ORDER BY name',
    ('tl_member', 'newsletter'):     'SELECT id, title AS name FROM tl_newsletter_channel ORDER BY title',
}


# ── storage helpers ──────────────────────────────────────────────────────────

def _schema_dir(session_path: str) -> str:
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    base = os.path.dirname(session_path)
    return os.path.join(base, 'schemas', session_name)


def _schema_path(table: str, session_path: str) -> str:
    return os.path.join(_schema_dir(session_path), f'{table}.json')


# ── extraction helpers ───────────────────────────────────────────────────────

def _extract_label(raw_label) -> Optional[str]:
    """Extract human-readable label from DCA label value."""
    if isinstance(raw_label, dict):
        return raw_label.get(0) or raw_label.get('0')
    if isinstance(raw_label, list):
        return raw_label[0] if raw_label else None
    if isinstance(raw_label, str):
        return raw_label
    return None


def _extract_options(fdef: dict) -> Optional[object]:
    """Extract allowed options, or '__callback__' if dynamic."""
    opts = fdef.get('options')
    if opts in ('__closure__', '__callback__') or callable(opts):
        return '__callback__'
    if isinstance(opts, str) and opts.startswith('__identifier__:'):
        return '__callback__'

    cb = fdef.get('options_callback') or fdef.get('options_wizard')
    if cb is not None:
        return '__callback__'

    if isinstance(opts, dict):
        # Convert integer keys back to a list if sequential
        if all(isinstance(k, int) for k in opts):
            return [opts[k] for k in sorted(opts)]
        return opts
    return opts


def _build_field_entry(fname: str, fdef: dict) -> dict:
    """Build a clean schema entry for one field."""
    if not isinstance(fdef, dict):
        return {'label': None, 'inputType': None, 'mandatory': False}

    ev = fdef.get('eval') or {}
    if not isinstance(ev, dict):
        ev = {}

    return {
        'label':      _extract_label(fdef.get('label')),
        'inputType':  fdef.get('inputType'),
        'mandatory':  bool(ev.get('mandatory', False)),
        'unique':     bool(ev.get('unique', False)),
        'maxlength':  ev.get('maxlength'),
        'rgxp':       ev.get('rgxp'),
        'options':    _extract_options(fdef),
    }


# ── public API ───────────────────────────────────────────────────────────────

def sync_table(backend: ContaoBackend, table: str, session_path: str) -> dict:
    """
    Fetch DCA for *table* from the server and save a local schema JSON.
    Returns the schema dict.
    """
    result = backend.run(f'debug:dca {shlex.quote(table)} fields')
    raw = result['stdout']

    fields_raw = parse_vardump(raw)
    if not isinstance(fields_raw, dict):
        raise ContaoBackendError(f'Unexpected DCA output for {table}')

    fields = {
        fname: _build_field_entry(fname, fdef)
        for fname, fdef in fields_raw.items()
        if isinstance(fname, str)   # skip integer meta-keys
    }

    schema = {
        'table':   table,
        'fetched': datetime.now().isoformat(timespec='seconds'),
        'fields':  fields,
    }

    os.makedirs(_schema_dir(session_path), exist_ok=True)
    with open(_schema_path(table, session_path), 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    return schema


def discover_tables(backend: ContaoBackend) -> list[str]:
    """
    Discover all registered DCA tables by listing the compiled cache directory.
    Returns sorted list of table names (e.g. ['tl_article', 'tl_news', ...]).
    Falls back to FALLBACK_TABLES if the cache directory is not accessible.
    """
    try:
        result = backend.run_raw(f'ls {_DCA_CACHE_PATH}/')
        tables = sorted(
            fname.replace('.php', '')
            for fname in result['stdout'].split()
            if fname.endswith('.php') and fname.startswith('tl_')
        )
        return tables if tables else FALLBACK_TABLES
    except Exception:
        return FALLBACK_TABLES


def sync_all(backend: ContaoBackend, session_path: str,
             tables: Optional[list] = None) -> dict:
    """
    Sync schemas for multiple tables. Returns {table: schema|error}.
    If *tables* is None, discovers all registered tables from the server.
    """
    if tables is None:
        tables = discover_tables(backend)
    results = {}
    for table in tables:
        try:
            results[table] = sync_table(backend, table, session_path)
        except Exception as e:
            results[table] = {'error': str(e)}
    return results


def load_schema(table: str, session_path: str) -> Optional[dict]:
    """Load cached schema for *table*. Returns None if not synced yet."""
    path = _schema_path(table, session_path)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def mandatory_fields(table: str, session_path: str) -> list[str]:
    """Return sorted list of mandatory field names for *table*."""
    schema = load_schema(table, session_path)
    if not schema:
        return []
    return sorted(
        fname for fname, fdef in schema['fields'].items()
        if fdef.get('mandatory')
    )


def validate_fields(table: str, provided: dict, session_path: str) -> list[str]:
    """
    Check *provided* field values against the cached DCA schema for *table*.

    Returns a list of missing mandatory field names. Empty list = all good.

    If no schema is cached yet, returns [] with a warning side-effect
    (validation is skipped rather than blocking the command).

    *provided* is a dict of {field_name: value} where value=None or ""
    counts as missing.
    """
    schema = load_schema(table, session_path)
    if schema is None:
        return []   # no schema → skip validation silently

    missing = []
    for fname, fdef in schema['fields'].items():
        if not fdef.get('mandatory'):
            continue
        val = provided.get(fname)
        # None, empty string, or missing key all count as "not provided"
        if val is None or val == '':
            missing.append(fname)
    return missing


def resolve_callback_options(
    backend: ContaoBackend,
    table: str,
    session_path: str,
    field: Optional[str] = None,
) -> dict:
    """
    Resolve __callback__ options in the cached schema for *table*.

    Tries static lists first, then live SQL queries via doctrine:query:sql.
    Updates the cached schema JSON in-place and returns a result dict:
      {field_name: resolved_options | '__unresolved__'}

    If *field* is given, only that field is processed.
    Raises ValueError if no schema is cached yet.
    """
    schema = load_schema(table, session_path)
    if schema is None:
        raise ValueError(f"No schema for '{table}'. Run: schema sync {table}")

    if field:
        if field not in schema['fields']:
            raise ValueError(f"Field '{field}' not found in schema for '{table}'")
        candidates = [(field, schema['fields'][field])]
    else:
        candidates = [
            (f, d) for f, d in schema['fields'].items()
            if d.get('options') == '__callback__'
        ]

    results = {}
    changed = False

    for fname, fdef in candidates:
        key = (table, fname)

        if key in STATIC_OPTIONS:
            schema['fields'][fname]['options'] = STATIC_OPTIONS[key]
            results[fname] = STATIC_OPTIONS[key]
            changed = True
            continue

        if key in TABLE_OPTION_QUERIES:
            try:
                sql = TABLE_OPTION_QUERIES[key]
                res = backend.run(f'doctrine:query:sql "{sql}"')
                rows = parse_table(res['stdout'])
                if rows and isinstance(rows, list):
                    options = {str(r['id']): r['name'] for r in rows
                               if 'id' in r and 'name' in r}
                    schema['fields'][fname]['options'] = options
                    results[fname] = options
                    changed = True
                    continue
            except Exception:
                pass

        results[fname] = '__unresolved__'

    if changed:
        with open(_schema_path(table, session_path), 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

    return results


def field_summary(table: str, session_path: str) -> list[dict]:
    """
    Return a list of field summaries suitable for display.
    Each entry: {field, label, inputType, mandatory, options}.
    """
    schema = load_schema(table, session_path)
    if not schema:
        return []
    return [
        {
            'field':     fname,
            'label':     fdef.get('label', ''),
            'inputType': fdef.get('inputType', ''),
            'mandatory': fdef.get('mandatory', False),
            'options':   fdef.get('options'),
        }
        for fname, fdef in schema['fields'].items()
    ]
