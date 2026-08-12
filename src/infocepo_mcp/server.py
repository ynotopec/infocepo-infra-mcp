#!/usr/bin/env python3
"""MCP server for infocepo.com infrastructure services."""

import sys
import json
import base64
import signal
import os
import asyncio

from mcp.server import Server
from mcp.types import (
    Tool,
    ListToolsResult,
    CallToolResult,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from mcp.server.stdio import stdio_server

from .config import Config as AppConfig
from .services import (
    handle_llm_chat,
    handle_llm_vision,
    handle_stt_transcribe,
    handle_tts_speech,
    handle_image_generate,
    handle_embeddings_create,
    handle_chromadb_collections,
    handle_chromadb_search,
    handle_chromadb_upsert,
    handle_summary_text,
    handle_diarize_audio,
    handle_registry_list,
    handle_s3_list,
    handle_s3_upload,
    handle_s3_download,
)
from .wiki_fetcher import WikiFetcher
from .tools import list_tools


# Global state
config = AppConfig()
wiki_fetcher = WikiFetcher()


def handle_tool_call(name: str, arguments: dict) -> list:
    """Handle a tool call and return content."""
    try:
        # === Meta tools ===
        if name == "infra_list_services":
            result = wiki_fetcher.parse_main_page()
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "infra_refresh_discovery":
            wiki_fetcher.cache_dir.mkdir(parents=True, exist_ok=True)
            import time
            now = time.time()
            for f in wiki_fetcher.cache_dir.glob("*.txt"):
                f.unlink()
            result = wiki_fetcher.parse_main_page()
            return [TextContent(type="text", text=json.dumps({"status": "ok", "services": len(result.get("services", [])), "urls": len(result.get("urls", []))}, indent=2))]

        elif name == "infra_read_wiki":
            title = arguments.get("title", "Main_Page")
            section = arguments.get("section")
            content = wiki_fetcher.get_page(title)
            if not content:
                return [TextContent(type="text", text=json.dumps({"error": f"Page '{title}' not found"}))]
            if section:
                content = wiki_fetcher.get_section(title, section) or content
            return [TextContent(type="text", text=content)]

        elif name == "infra_parse_wiki":
            title = arguments.get("title", "Main_Page")
            sections = wiki_fetcher.parse_sections(title)
            return [TextContent(type="text", text=json.dumps(sections, indent=2, ensure_ascii=False))]

        # === LLM tools ===
        elif name == "llm_chat":
            result = handle_llm_chat(arguments)
            return [TextContent(type="text", text=result)]

        elif name == "llm_vision":
            result = handle_llm_vision(arguments)
            return [TextContent(type="text", text=result)]

        # === STT tools ===
        elif name == "stt_transcribe":
            result = handle_stt_transcribe(arguments)
            return [TextContent(type="text", text=result)]

        # === TTS tools ===
        elif name == "tts_speech":
            result_raw = handle_tts_speech(arguments)
            parsed = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
            if "audio_path" in parsed:
                with open(parsed["audio_path"], "rb") as f:
                    audio_data = f.read()
                audio_format = parsed.get("format", "opus")
                mime_type = {
                    "flac": "audio/flac",
                    "mp3": "audio/mpeg",
                    "opus": "audio/opus",
                    "pcm": "audio/L16",
                    "wav": "audio/wav",
                }.get(audio_format, "application/octet-stream")
                return [
                    EmbeddedResource(
                        type="resource",
                        resource={
                            "mimeType": mime_type,
                            "uri": f"file://{parsed['audio_path']}",
                            "blob": base64.b64encode(audio_data).decode("ascii"),
                        }
                    ),
                    TextContent(type="text", text=result_raw),
                ]
            return [TextContent(type="text", text=result_raw)]

        # === Image tools ===
        elif name == "image_generate":
            result_raw = handle_image_generate(arguments)
            parsed = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
            content_items = [TextContent(type="text", text=result_raw)]
            if "data" in parsed:
                for item in parsed["data"]:
                    if "saved_to" in item:
                        try:
                            with open(item["saved_to"], "rb") as f:
                                img_data = f.read()
                            content_items.append(ImageContent(
                                type="image",
                                data=base64.b64encode(img_data).decode("ascii"),
                                mime_type="image/png",
                            ))
                        except Exception:
                            pass
            return content_items

        # === Embedding tools ===
        elif name == "embeddings_create":
            result = handle_embeddings_create(arguments)
            return [TextContent(type="text", text=result)]

        # === ChromaDB tools ===
        elif name == "chromadb_collections":
            result = handle_chromadb_collections(arguments)
            return [TextContent(type="text", text=result)]

        elif name == "chromadb_search":
            result = handle_chromadb_search(arguments)
            return [TextContent(type="text", text=result)]

        elif name == "chromadb_upsert":
            result = handle_chromadb_upsert(arguments)
            return [TextContent(type="text", text=result)]

        # === Summary tools ===
        elif name == "summary_text":
            result = handle_summary_text(arguments)
            return [TextContent(type="text", text=result)]

        # === Diarization tools ===
        elif name == "diarize_audio":
            result = handle_diarize_audio(arguments)
            return [TextContent(type="text", text=result)]

        # === Registry tools ===
        elif name == "registry_list":
            result = handle_registry_list(arguments)
            return [TextContent(type="text", text=result)]

        # === S3 tools ===
        elif name == "s3_list":
            result = handle_s3_list(arguments)
            return [TextContent(type="text", text=result)]

        elif name == "s3_upload":
            result = handle_s3_upload(arguments)
            return [TextContent(type="text", text=result)]

        elif name == "s3_download":
            result = handle_s3_download(arguments)
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        import traceback
        return [TextContent(type="text", text=json.dumps({"error": str(e), "traceback": traceback.format_exc()[:1000]}))]


async def on_list_tools(context, params):
    """List available tools for MCP."""
    from mcp.types import ListToolsResult
    return ListToolsResult(tools=list_tools())


async def on_call_tool(context, params):
    """Handle a tool call."""
    name = params.name if hasattr(params, 'name') else params.get('name', '')
    arguments = params.arguments if hasattr(params, 'arguments') else params.get('arguments', {})
    content = handle_tool_call(name, arguments)
    return CallToolResult(content=content)


async def run():
    """Main MCP server entrypoint."""
    app = Server(
        "infocepo-infra-mcp",
        version="0.1.0",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )

    async with stdio_server() as (read_stream, write_stream):
        from mcp.server.models import InitializationOptions
        init_opts = InitializationOptions(
            server_name=app.name,
            server_version=app.version,
            capabilities=app.get_capabilities(),
        )
        await app.run(read_stream, write_stream, init_opts)


def main():
    """Entry point."""
    print("infocepo-infra-mcp v0.1.0 starting...", file=sys.stderr)

    def signal_handler(sig, frame):
        print("Shutting down...", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(run())


if __name__ == "__main__":
    main()
