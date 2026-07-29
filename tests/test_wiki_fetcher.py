"""Tests for wiki fetcher module."""

import pytest
import os
import time

from infocepo_mcp.wiki_fetcher import WikiFetcher


class TestWikiFetcher:
    def test_init(self):
        wf = WikiFetcher()
        assert wf.wiki_base == "https://infocepo.com/wiki/api.php"

    def test_init_custom_base(self):
        wf = WikiFetcher(wiki_base="https://example.com/wiki/api.php")
        assert wf.wiki_base == "https://example.com/wiki/api.php"

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
