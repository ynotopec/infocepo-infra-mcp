"""Tests for tool definitions and service result handling."""

import base64
import json
from unittest.mock import patch

from infocepo_mcp.server import handle_tool_call
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


def test_tts_content_uses_base64_and_preserves_format(tmp_path):
    audio = b"\x00\x01opus-data"
    audio_path = tmp_path / "speech.opus"
    audio_path.write_bytes(audio)

    with patch(
        "infocepo_mcp.server.handle_tts_speech",
        return_value=json.dumps({"audio_path": str(audio_path), "format": "opus"}),
    ):
        content = handle_tool_call("tts_speech", {"text": "hello"})

    resource = content[0].resource
    assert resource.blob == base64.b64encode(audio).decode("ascii")
    assert resource.mime_type == "audio/opus"


def test_image_content_uses_base64(tmp_path):
    image = b"\x89PNG\r\n\x1a\nimage-data"
    image_path = tmp_path / "image.png"
    image_path.write_bytes(image)

    with patch(
        "infocepo_mcp.server.handle_image_generate",
        return_value=json.dumps({"data": [{"saved_to": str(image_path)}]}),
    ):
        content = handle_tool_call("image_generate", {"prompt": "test"})

    assert content[1].data == base64.b64encode(image).decode("ascii")
