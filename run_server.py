#!/usr/bin/env python3
"""Entry point for infocepo-mcp server."""
import json, sys, os, signal, asyncio
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ErrorData, ListToolsRequest, CallToolRequest

from services import (
    handle_llm_chat, handle_llm_vision, handle_stt_transcribe,
    handle_tts_speech, handle_image_generate, handle_embeddings_create,
    handle_chromadb_collections, handle_chromadb_search, handle_chromadb_upsert,
    handle_summary_text, handle_diarize_audio,
    handle_registry_list, handle_s3_list, handle_s3_upload, handle_s3_download,
)
from wiki_fetcher import WikiFetcher
from config import Config

config = Config()
wiki_fetcher = WikiFetcher()
mcp_app: Server = Server("infocepo-infra")

_MCP_TOOLS: list[Tool] = [
    Tool(name="infra_list_services",
        description="List all infocepo.com infrastructure services with status and endpoints.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_status": {"type": "boolean", "description": "Include health check status (requires HTTP call)"},
                "env": {"type": "string", "description": "Environment: prod, lab, dev", "enum": ["prod", "lab", "dev"], "default": "prod"},
            }
        },
    ),
    Tool(name="infra_refresh_discovery",
        description="Re-fetch and re-parse the wiki Main_Page to discover changes.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(name="infra_read_wiki",
        description="Read a page from the infocepo.com wiki.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Wiki page title"},
            }
        },
    ),
    Tool(name="infra_parse_wiki",
        description="Parse wiki wikitext and return structured sections.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Wiki page title"},
            }
        },
    ),
    Tool(name="llm_chat",
        description="Chat completions using the infocepo LLM API.",
        inputSchema={
            "type": "object",
            "properties": {
                "messages": {"type": "array", "description": "Chat messages"},
                "model": {"type": "string", "description": "Model name (optional)"},
            }
        },
    ),
    Tool(name="llm_vision",
        description="Image-to-text / OCR / VLM using the ai-vision model.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Image URL"},
                "question": {"type": "string", "description": "Question about the image"},
            }
        },
    ),
    Tool(name="stt_transcribe",
        description="Transcribe audio to text using Whisper model.",
        inputSchema={
            "type": "object",
            "properties": {
                "audio_file": {"type": "string", "description": "Audio file path or URL"},
            }
        },
    ),
    Tool(name="tts_speech",
        description="Text-to-speech synthesis using OmniVoice model.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak"},
            }
        },
    ),
    Tool(name="image_generate",
        description="Generate images from text prompts using OpenDalle model.",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image prompt"},
            }
        },
    ),
    Tool(name="embeddings_create",
        description="Generate text embeddings using BGE-M3 model.",
        inputSchema={
            "type": "object",
            "properties": {
                "texts": {"type": "array", "description": "List of texts to embed"},
            }
        },
    ),
    Tool(name="summary_text",
        description="Summarize long texts.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to summarize"},
            }
        },
    ),
    Tool(name="diarize_audio",
        description="Speaker diarization: identify and separate different speakers.",
        inputSchema={
            "type": "object",
            "properties": {
                "audio_file": {"type": "string", "description": "Audio file path"},
            }
        },
    ),
    Tool(name="chromadb_collections",
        description="List all ChromaDB collections.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(name="chromadb_search",
        description="Search ChromaDB collections with semantic/vector similarity.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Collection name"},
                "query": {"type": "string", "description": "Search query"},
            }
        },
    ),
    Tool(name="chromadb_upsert",
        description="Upsert documents into a ChromaDB collection.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Collection name"},
                "documents": {"type": "array", "description": "Documents to upsert"},
            }
        },
    ),
    Tool(name="registry_list",
        description="List Docker images from the infocepo private registry.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(name="s3_list",
        description="List objects in an S3-compatible storage bucket.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "S3 bucket name"},
            }
        },
    ),
    Tool(name="s3_upload",
        description="Upload a file to S3-compatible storage.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "S3 bucket name"},
                "key": {"type": "string", "description": "Object key"},
            }
        },
    ),
    Tool(name="s3_download",
        description="Download a file from S3-compatible storage.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "S3 bucket name"},
                "key": {"type": "string", "description": "Object key"},
            }
        },
    ),
]

@mcp_app.list_tools()
async def list_tools():
    return _MCP_TOOLS

@mcp_app.call_tool()
async def call_tool(name, arguments):
    handler_map = {
        "llm_chat": handle_llm_chat,
        "llm_vision": handle_llm_vision,
        "stt_transcribe": handle_stt_transcribe,
        "tts_speech": handle_tts_speech,
        "image_generate": handle_image_generate,
        "embeddings_create": handle_embeddings_create,
        "summary_text": handle_summary_text,
        "diarize_audio": handle_diarize_audio,
        "chromadb_collections": handle_chromadb_collections,
        "chromadb_search": handle_chromadb_search,
        "chromadb_upsert": handle_chromadb_upsert,
        "registry_list": handle_registry_list,
        "s3_list": handle_s3_list,
        "s3_upload": handle_s3_upload,
        "s3_download": handle_s3_download,
    }
    
    handler = handler_map.get(name)
    if handler:
        try:
            result = handler(arguments) if arguments else handler()
            if asyncio.iscoroutine(result):
                result = await result
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error calling {name}: {str(e)}")]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def run_sse_server():
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    
    sse = SseServerTransport("/messages/")
    
    async def handle_sse(scope):
        async with sse.connect_sse(
            scope,
            lambda: asyncio.create_task(sse.receive_message()),
            lambda msg: asyncio.create_task(sse.send_message(msg))
        ) as streams:
            await mcp_app.run(
                streams[0],
                streams[1],
                mcp_app.create_initialization_options()
            )
    
    async def health_check(request):
        return {"status": "ok", "server": "infocepo-infra-mcp", "version": "0.1.0", "tools": len(_MCP_TOOLS)}
    
    app = Starlette(
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ],
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages/{path:path}", endpoint=handle_sse),
            Route("/health", endpoint=health_check),
        ],
    )
    
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8085"))
    
    print(f"Starting MCP SSE server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    asyncio.run(run_sse_server())
