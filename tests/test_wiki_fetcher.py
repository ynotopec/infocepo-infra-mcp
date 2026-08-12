"""Tests for wiki fetcher module."""

import pytest
import hashlib
import os
import time
import httpx
from pathlib import Path

from infocepo_mcp.wiki_fetcher import WikiFetcher


class TestWikiFetcher:
    def test_init(self):
        wf = WikiFetcher()
        assert wf.wiki_base == "https://infocepo.com/wiki/api.php"

    def test_init_custom_base(self):
        wf = WikiFetcher(wiki_base="https://example.com/wiki/api.php")
        assert wf.wiki_base == "https://example.com/wiki/api.php"

    def test_default_cache_is_scoped_to_current_user(self, monkeypatch, tmp_path):
        monkeypatch.delenv("INFOCEPO_WIKI_CACHE_DIR", raising=False)
        monkeypatch.setattr("infocepo_mcp.wiki_fetcher.tempfile.gettempdir", lambda: str(tmp_path))
        wf = WikiFetcher()

        assert wf.cache_dir.name.startswith("infocepo-wiki-cache-")

    def test_cache_read_permission_error_falls_back_to_upstream(self, tmp_path, monkeypatch):
        wf = WikiFetcher(cache_dir=str(tmp_path))
        cache_key = hashlib.md5(f"{wf.wiki_base}:Main_Page".encode()).hexdigest()
        (tmp_path / f"{cache_key}.txt").write_text("stale")
        original_read_text = Path.read_text

        def fail_cache_read(path, *args, **kwargs):
            if path.parent == tmp_path:
                raise PermissionError("not readable")
            return original_read_text(path, *args, **kwargs)

        def respond(request):
            return httpx.Response(200, request=request, json={"query": {"pages": {"1": {"revisions": [{"*": "fresh"}]}}}})

        real_client = httpx.Client
        monkeypatch.setattr("pathlib.Path.read_text", fail_cache_read)
        monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(respond)))

        assert wf.get_page("Main_Page") == "fresh"

    def test_clear_cache_reports_unremovable_entry(self, tmp_path, monkeypatch):
        wf = WikiFetcher(cache_dir=str(tmp_path))
        cache_file = tmp_path / "entry.txt"
        cache_file.write_text("cached")
        monkeypatch.setattr("pathlib.Path.unlink", lambda self: (_ for _ in ()).throw(PermissionError("owned elsewhere")))

        assert wf.clear_cache() == [str(cache_file)]

    def test_clean_url(self):
        wf = WikiFetcher()
        assert wf.clean_url("test.ailab.infocepo.com:wait-2026-12") == "test.ailab.infocepo.com"
        assert wf.clean_url("normal.ailab.infocepo.com") == "normal.ailab.infocepo.com"
        assert wf.clean_url("") == ""

    def test_parse_sections_empty_content(self):
        wf = WikiFetcher()
        # Mock get_page to return empty string
        wf.get_page = lambda title: ""
        sections = wf.parse_sections("Test")
        assert sections == []

    def test_parse_sections_single_section(self):
        wf = WikiFetcher()
        content = "== Title ==\nSome content\n== Next ==\nMore content"
        wf.get_page = lambda title: content
        sections = wf.parse_sections("Test")
        assert len(sections) == 2
        assert sections[0]["title"] == "Title"
        assert sections[0]["content"] == "Some content"

    def test_parse_sections_no_sections(self):
        wf = WikiFetcher()
        content = "No sections here\nJust plain text"
        wf.get_page = lambda title: content
        sections = wf.parse_sections("Test")
        assert sections == []

    def test_get_section_not_found(self):
        wf = WikiFetcher()
        wf.get_page = lambda title: "== Title ==\nContent"
        result = wf.get_section("Test", "Nonexistent")
        assert result is None

    def test_get_page_preserves_upstream_http_error(self, tmp_path, monkeypatch):
        def respond(request):
            return httpx.Response(404, request=request)

        real_client = httpx.Client
        monkeypatch.setattr(
            httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(respond)),
        )
        wf = WikiFetcher(cache_dir=str(tmp_path))

        assert wf.get_page("Main_Page") is None
        assert wf.last_error["kind"] == "upstream_http_error"
        assert wf.last_error["status_code"] == 404

    def test_parse_main_page_includes_failure_details(self):
        wf = WikiFetcher()
        wf.last_error = {"kind": "upstream_http_error", "status_code": 404}
        wf.get_page = lambda title: None

        result = wf.parse_main_page()

        assert result["error"] == "Failed to fetch Main_Page"
        assert result["upstream"]["status_code"] == 404


class TestWikiFetcherLive:
    """Live wiki tests — require network."""

    @pytest.mark.skipif(
        os.environ.get("TEST_LIVE") != "1",
        reason="Set TEST_LIVE=1 to run live wiki tests"
    )
    def test_fetch_main_page(self):
        wf = WikiFetcher()
        content = wf.get_page("Main_Page")
        assert content is not None
        assert len(content) > 100
        assert "infocepo.com" in content

    @pytest.mark.skipif(
        os.environ.get("TEST_LIVE") != "1",
        reason="Set TEST_LIVE=1 to run live wiki tests"
    )
    def test_parse_main_page(self):
        wf = WikiFetcher()
        result = wf.parse_main_page()
        assert "error" not in result
        assert "sections" in result
        assert "services" in result
        assert "urls" in result
        assert "Catalogue rapide des services" in result["sections"]
