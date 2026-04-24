import json
from unittest.mock import MagicMock, patch

from cli_anything.contao.core.backup import backup_create, backup_list, backup_restore
from cli_anything.contao.core.cache import cache_clear, cache_warmup, cache_pool_list, cache_pool_clear
from cli_anything.contao.core.comment import comment_list
from cli_anything.contao.core.content import content_list, content_read, content_create
from cli_anything.contao.core.contao_ops import migrate, maintenance_status, run_sql_table, run_json_or_raw, build_set_args
from cli_anything.contao.core.debug_ops import debug_dca, debug_router, debug_plugins
from cli_anything.contao.core.event import calendar_list, event_list, event_read, event_create
from cli_anything.contao.core.faq import faq_category_list, faq_list, faq_read, faq_create
from cli_anything.contao.core.file import file_list, file_sync, file_process, file_write, file_read, file_meta_update
from cli_anything.contao.core.form import form_list, form_fields
from cli_anything.contao.core.layout import layout_read
from cli_anything.contao.core.listing import listing_module_list, listing_data
from cli_anything.contao.core.mailer import mailer_test
from cli_anything.contao.core.messenger import (
    messenger_stats,
    messenger_failed_show,
    messenger_failed_retry,
    messenger_stop_workers,
    messenger_failed_remove,
    messenger_consume,
)
from cli_anything.contao.core.news import news_archive_list, news_list, news_read, news_create
from cli_anything.contao.core.newsletter import channel_list, newsletter_list, subscriber_list
from cli_anything.contao.core.search import search_reindex, search_index_create, search_index_drop
from cli_anything.contao.core.security import hash_password
from cli_anything.contao.core.template import template_list, template_read, template_write
from cli_anything.contao.core.user import user_list, user_create, user_update, user_delete, user_password
from cli_anything.contao.core.version import version_list, version_read, version_restore, version_create


def make_table(headers, rows):
    rows = [[str(v) for v in row] for row in rows]
    widths = []
    for idx, header in enumerate(headers):
        cell_widths = [len(row[idx]) for row in rows] if rows else [0]
        widths.append(max(len(header), max(cell_widths)))

    def render(values):
        return " ".join(f" {value.ljust(width)} " for value, width in zip(values, widths))

    sep = " ".join("-" * (width + 2) for width in widths)
    lines = [sep, render(headers), sep]
    lines.extend(render(row) for row in rows)
    lines.append(sep)
    return "\n".join(lines)


class _TempFile:
    def __init__(self, name):
        self.name = name
        self.content = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write(self, value):
        self.content += value
        return len(value)


class TestBackup:
    def test_backup_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "created", "returncode": 0}
        result = backup_create(backend)
        assert result == {"status": "created", "output": "created"}
        assert backend.run.call_args[0][0] == "contao:backup:create"

    def test_backup_create_with_name(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "ok", "returncode": 0}
        backup_create(backend, "daily dump")
        assert backend.run.call_args[0][0] == "contao:backup:create 'daily dump'"

    def test_backup_list(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "backup_a\nbackup_b", "returncode": 0}
        result = backup_list(backend)
        assert result == {"output": "backup_a\nbackup_b"}

    def test_backup_restore(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "restored", "returncode": 0}
        result = backup_restore(backend, "nightly.sql")
        assert result["status"] == "restored"
        assert result["backup"] == "nightly.sql"
        assert backend.run.call_args[0][0] == "contao:backup:restore nightly.sql --no-interaction"


class TestCache:
    def test_cache_clear(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "cache cleared", "returncode": 0}
        result = cache_clear(backend)
        assert result["status"] == "cleared"
        assert backend.run.call_args[0][0] == "cache:clear"

    def test_cache_warmup(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "cache warmed", "returncode": 0}
        result = cache_warmup(backend)
        assert result["status"] == "warmed"
        assert backend.run.call_args[0][0] == "cache:warmup"

    def test_cache_pool_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": "Pool Name\ncache.global_clearer\n-\ncache.system\n",
            "returncode": 0,
        }
        result = cache_pool_list(backend)
        assert result["pools"] == ["cache.global_clearer", "cache.system"]

    def test_cache_pool_clear(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "done", "returncode": 0}
        result = cache_pool_clear(backend, "cache.app")
        assert result["pool"] == "cache.app"
        assert backend.run.call_args[0][0] == "cache:pool:clear cache.app"


class TestComment:
    def test_comment_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(
                ["id", "source", "parent", "date", "name", "email", "comment", "published"],
                [["1", "tl_news", "2", "1711", "Jane", "j@example.com", "Hello", "1"]],
            ),
            "returncode": 0,
        }
        result = comment_list(backend)
        assert len(result) == 1
        assert result[0]["source"] == "tl_news"

    def test_comment_list_with_source(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        comment_list(backend, source="tl_news")
        assert "tl_news" in backend.run.call_args[0][0]

    def test_comment_list_with_parent(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        comment_list(backend, parent_id=5)
        assert "parent = 5" in backend.run.call_args[0][0]


class TestContent:
    def test_content_list_parses_headline(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(
                ["id", "pid", "type", "headline", "invisible", "ptable"],
                [["1", "2", "text", 'a:2:{s:5:"value";s:4:"Hero";}', "", "tl_article"]],
            ),
            "returncode": 0,
        }
        result = content_list(backend)
        assert result[0]["headline"] == "Hero"

    def test_content_list_with_article_id(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        content_list(backend, article_id=9)
        assert "WHERE pid = 9" in backend.run.call_args[0][0]

    def test_content_read(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"id": 7, "type": "text"}), "returncode": 0}
        result = content_read(backend, 7)
        assert result == {"id": 7, "type": "text"}

    def test_content_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "created"}), "returncode": 0}
        result = content_create(backend, "text", 4, fields={"headline": "Hero"})
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "created"
        assert "contao:content:create --type=text --pid=4 --ptable=tl_article --no-interaction" in cmd
        assert "--set headline=Hero" in cmd


class TestContaoOps:
    def test_migrate_dry_run(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "ok", "returncode": 0}
        result = migrate(backend, dry_run=True)
        assert result["dry_run"] is True
        assert backend.run.call_args[0][0] == "contao:migrate --no-interaction --dry-run"

    def test_maintenance_status_enabled(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "Maintenance mode enabled", "returncode": 0}
        result = maintenance_status(backend)
        assert result["enabled"] is True

    def test_run_sql_table(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "Home"]]),
            "returncode": 0,
        }
        result = run_sql_table(backend, "SELECT id, title FROM tl_page")
        assert result == [{"id": "1", "title": "Home"}]
        assert "doctrine:query:sql" in backend.run.call_args[0][0]

    def test_run_json_or_raw_and_build_set_args(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "not-json", "returncode": 0}
        result = run_json_or_raw(backend, "contao:test")
        assert result == {"raw": "not-json"}
        args = build_set_args({"title": "Home", "alias": "index"})
        assert "--set title=Home" in args
        assert "--set alias=index" in args


class TestDebugOps:
    def test_debug_dca(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "fields", "returncode": 0}
        result = debug_dca(backend, "tl_page")
        assert result["table"] == "tl_page"
        assert backend.run.call_args[0][0] == "debug:dca tl_page"

    def test_debug_router_default(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "router dump", "returncode": 0}
        result = debug_router(backend)
        assert result == {"output": "router dump"}
        assert backend.run.call_args[0][0] == "debug:router"

    def test_debug_router_with_path(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "matched", "returncode": 0}
        debug_router(backend, "/news/test")
        assert backend.run.call_args[0][0] == "router:match /news/test"

    def test_debug_plugins(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "plugins", "returncode": 0}
        result = debug_plugins(backend)
        assert result == {"output": "plugins"}


class TestEvent:
    def test_calendar_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "Main Calendar"]]),
            "returncode": 0,
        }
        result = calendar_list(backend)
        assert result[0]["title"] == "Main Calendar"

    def test_event_list_with_calendar_id(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        event_list(backend, calendar_id=3)
        assert "WHERE pid = 3" in backend.run.call_args[0][0]

    def test_event_read(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"id": 5, "title": "Launch"}), "returncode": 0}
        assert event_read(backend, 5)["title"] == "Launch"

    def test_event_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "created"}), "returncode": 0}
        result = event_create(
            backend,
            "Launch Party",
            2,
            start_date="2026-05-01",
            end_date="2026-05-02",
            fields={"alias": "launch"},
        )
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "created"
        assert "--title='Launch Party'" in cmd
        assert "--startDate=2026-05-01" in cmd
        assert "--endDate=2026-05-02" in cmd
        assert "--set alias=launch" in cmd


class TestFaq:
    def test_faq_category_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "General"]]),
            "returncode": 0,
        }
        result = faq_category_list(backend)
        assert result[0]["title"] == "General"

    def test_faq_list_with_category(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        faq_list(backend, category_id=4)
        assert "WHERE pid = 4" in backend.run.call_args[0][0]

    def test_faq_read(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"id": 1, "question": "What now?"}), "returncode": 0}
        assert faq_read(backend, 1)["question"] == "What now?"

    def test_faq_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "created"}), "returncode": 0}
        result = faq_create(backend, "What now?", 2, answer="Proceed", fields={"alias": "what-now"})
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "created"
        assert "--question='What now?'" in cmd
        assert "--answer=Proceed" in cmd
        assert "--set alias=what-now" in cmd


class TestFile:
    def test_file_list_with_filters(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        file_list(backend, path="files/images", type_filter="file")
        cmd = backend.run.call_args[0][0]
        assert "files/images" in cmd
        assert "file" in cmd

    def test_file_sync(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": " synced \n", "returncode": 0}
        result = file_sync(backend)
        assert result == {"status": "ok", "output": "synced"}

    def test_file_process(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "ok"}), "returncode": 0}
        result = file_process(
            backend,
            "files/test.jpg",
            allowed_types="jpg,png",
            max_width=100,
            max_height=200,
            max_file_size=1234,
        )
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "ok"
        assert "contao:file:process --path files/test.jpg" in cmd
        assert "--allowed-types jpg,png" in cmd
        assert "--max-width 100" in cmd
        assert "--max-height 200" in cmd
        assert "--max-file-size 1234" in cmd

    def test_file_read(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"content": "hello"}), "returncode": 0}
        result = file_read(backend, "files/demo.txt")
        assert result == {"content": "hello"}

    def test_file_meta_update(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "updated"}), "returncode": 0}
        result = file_meta_update(backend, "files/demo.txt", {"title": "Hero"}, lang="de")
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "updated"
        assert "--path files/demo.txt" in cmd
        assert "--lang de" in cmd
        assert "--set title=Hero" in cmd

    def test_file_write(self):
        backend = MagicMock()
        backend.scp_upload.return_value = {"returncode": 0}
        backend.run.return_value = {"stdout": json.dumps({"status": "written"}), "returncode": 0}
        tmp = _TempFile("C:/tmp/write.tmp")
        with patch("tempfile.NamedTemporaryFile", return_value=tmp), patch("os.unlink") as unlink:
            result = file_write(backend, "files/demo.txt", "hello")
        assert result["status"] == "written"
        assert tmp.content == "hello"
        backend.scp_upload.assert_called_once_with("C:/tmp/write.tmp", "/tmp/contao_write_write.tmp")
        assert "contao:file:write --path files/demo.txt --source /tmp/contao_write_write.tmp" in backend.run.call_args[0][0]
        unlink.assert_called_once_with("C:/tmp/write.tmp")


class TestForm:
    def test_form_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(
                ["id", "title", "alias", "method", "formID", "recipient", "subject", "storeValues", "targetTable", "sendViaEmail"],
                [["1", "Contact", "contact", "POST", "contact", "mail@example.com", "Hi", "1", "", "1"]],
            ),
            "returncode": 0,
        }
        result = form_list(backend)
        assert result[0]["title"] == "Contact"

    def test_form_fields(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(
                ["id", "type", "name", "label", "mandatory", "invisible", "rgxp", "placeholder", "value", "sorting"],
                [["1", "text", "email", "Email", "1", "", "email", "", "", "128"]],
            ),
            "returncode": 0,
        }
        result = form_fields(backend, 8)
        assert result[0]["name"] == "email"
        assert "WHERE pid = 8" in backend.run.call_args[0][0]

    def test_form_list_raw_fallback(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "not a table", "returncode": 0}
        result = form_list(backend)
        assert result == {"raw": "not a table"}


class TestLayout:
    def test_layout_read_json(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"id": 1, "name": "Main"}), "returncode": 0}
        result = layout_read(backend, 1)
        assert result["name"] == "Main"

    def test_layout_read_raw_fallback(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "plain text", "returncode": 0}
        result = layout_read(backend, 1)
        assert result == {"raw": "plain text"}


class TestListing:
    def test_listing_module_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "name", "list_table", "list_fields", "list_where"], [["1", "Demo", "tl_demo", "id,title", "published=1"]]),
            "returncode": 0,
        }
        result = listing_module_list(backend)
        assert result[0]["name"] == "Demo"

    def test_listing_data_with_cfg(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "Entry"]]),
            "returncode": 0,
        }
        result = listing_data(backend, 1, cfg={"list_table": "tl_demo", "list_fields": "id, title", "list_where": 'type = "news"'})
        assert result == [{"id": "1", "title": "Entry"}]
        assert "tl_demo" in backend.run.call_args[0][0]

    def test_listing_data_missing_module(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        result = listing_data(backend, 99)
        assert result == {"error": "Module 99 not found or not a listing module"}

    def test_listing_data_missing_config(self):
        backend = MagicMock()
        result = listing_data(backend, 5, cfg={"list_table": "", "list_fields": ""})
        assert result == {"error": "Module 5 has no list_table or list_fields configured"}


class TestMailer:
    def test_mailer_test(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "sent", "returncode": 0}
        result = mailer_test(backend, "user@example.com")
        assert result == {"status": "ok", "to": "user@example.com", "output": "sent"}

    def test_mailer_test_command(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "sent", "returncode": 0}
        mailer_test(backend, "user@example.com")
        assert backend.run.call_args[0][0] == "mailer:test --to=user@example.com --no-interaction"


class TestMessenger:
    def test_messenger_stats(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "stats", "returncode": 0}
        assert messenger_stats(backend) == {"output": "stats"}

    def test_messenger_failed_show(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "failed messages", "returncode": 0}
        assert messenger_failed_show(backend) == {"output": "failed messages"}

    def test_messenger_failed_retry(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "retried", "returncode": 0}
        result = messenger_failed_retry(backend, "42")
        assert result["status"] == "retried"
        assert backend.run.call_args[0][0] == "messenger:failed:retry --no-interaction 42"

    def test_messenger_stop_workers(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "stopping", "returncode": 0}
        result = messenger_stop_workers(backend)
        assert result == {"status": "stopping", "output": "stopping"}

    def test_messenger_failed_remove(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "removed", "returncode": 0}
        result = messenger_failed_remove(backend, "17")
        assert result["message_id"] == "17"
        assert backend.run.call_args[0][0] == "messenger:failed:remove 17 --no-interaction"

    def test_messenger_consume(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "done", "returncode": 0}
        result = messenger_consume(backend, transport="async", limit=10, time_limit=30)
        assert result["status"] == "ok"
        assert backend.run.call_args[0][0] == "messenger:consume --no-interaction async --limit=10 --time-limit=30"


class TestNews:
    def test_news_archive_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "News"]]),
            "returncode": 0,
        }
        result = news_archive_list(backend)
        assert result[0]["title"] == "News"

    def test_news_list_with_archive(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        news_list(backend, archive_id=2)
        assert "WHERE pid = 2" in backend.run.call_args[0][0]

    def test_news_read(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"id": 1, "headline": "Test News"}), "returncode": 0}
        assert news_read(backend, 1)["headline"] == "Test News"

    def test_news_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "created"}), "returncode": 0}
        result = news_create(backend, "Test News", 4, date="2026-04-24", fields={"alias": "test-news"})
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "created"
        assert "--headline='Test News'" in cmd
        assert "--date=2026-04-24" in cmd
        assert "--set alias=test-news" in cmd


class TestNewsletter:
    def test_channel_list(self):
        backend = MagicMock()
        backend.run.return_value = {
            "stdout": make_table(["id", "title"], [["1", "Weekly"]]),
            "returncode": 0,
        }
        result = channel_list(backend)
        assert result[0]["title"] == "Weekly"

    def test_newsletter_list_with_channel(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        newsletter_list(backend, channel_id=3)
        assert "WHERE pid = 3" in backend.run.call_args[0][0]

    def test_subscriber_list_with_channel(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "", "returncode": 0}
        subscriber_list(backend, channel_id=5)
        assert "WHERE pid = 5" in backend.run.call_args[0][0]


class TestSearch:
    def test_search_reindex(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "ok", "returncode": 0}
        result = search_reindex(backend, "news")
        assert result["status"] == "ok"
        assert backend.run.call_args[0][0] == "cmsig:seal:reindex --no-interaction --index=news"

    def test_search_index_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "ok", "returncode": 0}
        search_index_create(backend)
        assert backend.run.call_args[0][0] == "cmsig:seal:index-create --no-interaction"

    def test_search_index_drop(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "ok", "returncode": 0}
        search_index_drop(backend, "news")
        assert backend.run.call_args[0][0] == "cmsig:seal:index-drop --no-interaction --index=news"


class TestSecurity:
    def test_hash_password(self):
        backend = MagicMock()
        backend.run_raw.return_value = {"stdout": "  $argon2id$v=19$hash  ", "returncode": 0}
        result = hash_password(backend, "secret")
        assert result["output"] == "$argon2id$v=19$hash"
        assert "security:hash-password --no-interaction" in backend.run_raw.call_args[0][0]

    def test_hash_password_with_algorithm(self):
        backend = MagicMock()
        backend.run_raw.return_value = {"stdout": "hash", "returncode": 0}
        hash_password(backend, "secret", algorithm="bcrypt")
        assert "--algorithm=bcrypt" in backend.run_raw.call_args[0][0]


class TestTemplate:
    def test_template_list(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"templates": ["ce_text"]}), "returncode": 0}
        result = template_list(backend, prefix="ce_")
        assert result == {"templates": ["ce_text"]}
        assert backend.run.call_args[0][0] == "contao:template:list --prefix ce_"

    def test_template_read_raw_fallback(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "plain", "returncode": 0}
        result = template_read(backend, "templates/demo.html.twig")
        assert result == {"raw": "plain"}

    def test_template_write(self):
        backend = MagicMock()
        backend.scp_upload.return_value = {"returncode": 0}
        backend.run.return_value = {"stdout": json.dumps({"status": "written"}), "returncode": 0}
        tmp = _TempFile("C:/tmp/template.twig")
        with patch("tempfile.NamedTemporaryFile", return_value=tmp), patch("os.unlink") as unlink:
            result = template_write(backend, "variant", "content_element/text", "{% block content %}{% endblock %}", name="custom")
        assert result["status"] == "written"
        backend.scp_upload.assert_called_once_with("C:/tmp/template.twig", "/tmp/contao_tpl_template.twig")
        cmd = backend.run.call_args[0][0]
        assert "contao:template:write --mode variant --base content_element/text --source /tmp/contao_tpl_template.twig" in cmd
        assert "--name custom" in cmd
        unlink.assert_called_once_with("C:/tmp/template.twig")


class TestUser:
    def test_user_list(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps([{"username": "admin"}]), "returncode": 0}
        result = user_list(backend)
        assert result == [{"username": "admin"}]
        assert backend.run.call_args[0][0] == "contao:user:list --format=json"

    def test_user_create_admin(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "created", "returncode": 0}
        result = user_create(backend, "admin", "secret", "Admin User", "admin@example.com", admin=True)
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "created"
        assert "--username=admin" in cmd
        assert "--password=secret" in cmd
        assert "--name='Admin User'" in cmd
        assert "--admin" in cmd

    def test_user_update(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "updated"}), "returncode": 0}
        result = user_update(backend, "admin", {"name": "Admin User", "language": "de"})
        cmd = backend.run.call_args[0][0]
        assert result["status"] == "updated"
        assert "contao:user:update admin" in cmd
        assert "--set 'name=Admin User'" in cmd
        assert "--set language=de" in cmd

    def test_user_delete(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "deleted"}), "returncode": 0}
        result = user_delete(backend, "admin")
        assert result == {"status": "deleted"}
        assert backend.run.call_args[0][0] == "contao:user:delete admin --no-interaction"

    def test_user_password(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "updated", "returncode": 0}
        result = user_password(backend, "admin", "new-secret")
        cmd = backend.run.call_args[0][0]
        assert result == {"status": "updated", "username": "admin", "output": "updated"}
        assert cmd.endswith(" admin")


class TestVersion:
    def test_version_list(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"versions": [1, 2]}), "returncode": 0}
        result = version_list(backend, "tl_content", 42)
        assert result == {"versions": [1, 2]}

    def test_version_read_raw_fallback(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": "plain", "returncode": 0}
        result = version_read(backend, "tl_content", 42, 3)
        assert result == {"raw": "plain"}

    def test_version_restore(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "restored"}), "returncode": 0}
        result = version_restore(backend, "tl_content", 42, 3)
        assert result == {"status": "restored"}

    def test_version_create(self):
        backend = MagicMock()
        backend.run.return_value = {"stdout": json.dumps({"status": "created"}), "returncode": 0}
        result = version_create(backend, "tl_content", 42)
        assert result == {"status": "created"}
        assert backend.run.call_args[0][0] == "contao:version:create --table tl_content --id 42"

