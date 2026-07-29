"""Tests for tools module."""

import pytest
from infocepo_mcp.tools import list_tools


class TestTools:
    def test_list_tools_returns_list(self):
        tools = list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tools_have_required_fields(self):
        tools = list_tools()
        for tool in tools:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "inputSchema" in tool, f"Tool missing 'inputSchema': {tool}"
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)

    def test_has_llm_tool(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        assert "llm_chat" in names
        assert "llm_vision" in names

    def test_has_audio_tools(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        assert "stt_transcribe" in names
        assert "tts_speech" in names

    def test_has_chromadb_tools(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        assert "chromadb_collections" in names
        assert "chromadb_search" in names
        assert "chromadb_upsert" in names

    def test_has_meta_tools(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        assert "infra_list_services" in names
        assert "infra_refresh_discovery" in names
        assert "infra_read_wiki" in names
        assert "infra_parse_wiki" in names

    def test_total_tool_count(self):
        tools = list_tools()
        # We have 19 tools now (will grow with real-time + RAG tools)
        assert len(tools) >= 19

    def test_tool_schema_structure(self):
        tools = list_tools()
        for tool in tools:
            schema = tool["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema
