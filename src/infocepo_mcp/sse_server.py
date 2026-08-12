#!/usr/bin/env python3
"""SSE MCP server for infocepo-infra — MCP v2 API (add_request_handler pattern)."""

import json
import sys
import os
import signal
import asyncio
import hmac
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import (
    Tool, TextContent, ErrorData,
    # Request types
    ListToolsRequest, CallToolRequest,
    CallToolRequestParams,
)

from infocepo_mcp.services import (
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
from infocepo_mcp.wiki_fetcher import WikiFetcher
from infocepo_mcp.config import Config

# Global state
config = Config()
wiki_fetcher = WikiFetcher()

# ============================================================================
# Tool definitions (static)
# ============================================================================

_MCP_TOOLS: list[Tool] = [
    Tool(
        name="infra_list_services",
        description="List all infocepo.com infrastructure services with status and endpoints.",
        inputSchema={
            "type": "object",
            "properties": {
                "include_status": {
                    "type": "boolean",
                    "description": "Include health check status (requires HTTP call)"
                },
                "env": {
                    "type": "string",
                    "description": "Environment to show endpoints for: prod, lab, dev",
                    "enum": ["prod", "lab", "dev"],
                    "default": "prod"
                }
            }
        },
    ),
    Tool(
        name="infra_refresh_discovery",
        description="Re-fetch and re-parse the wiki Main_Page to discover any changes to services/endpoints.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="infra_read_wiki",
        description="Read a page from the infocepo.com wiki. Useful for discovering new services, configurations, or documentation.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Wiki page title (e.g., 'Main_Page', 'Page_Name')"},
                "section": {"type": "string", "description": "Optional: extract only this section (e.g., 'Catalogue rapide des services')"}
            },
            "required": ["title"]
        },
    ),
    Tool(
        name="infra_parse_wiki",
        description="Parse wiki wikitext and return structured sections. Returns list of sections with title and content.",
        inputSchema={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Wiki page title"}},
            "required": ["title"]
        },
    ),
    Tool(
        name="llm_chat",
        description="Chat completions using the infocepo LLM API (OpenAI-compatible). Supports chat, reasoning, code generation.",
        inputSchema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Model name: ai-default, ai-thinking, ai-fast, ai-embedding, ai-stt, ai-tts, ai-image, ai-vision"},
                "messages": {"type": "array", "description": "Chat messages array: [{role: 'user'|'system'|'assistant', content: 'text'}]"},
                "temperature": {"type": "number", "description": "Sampling temperature (0-2). Default 0.7.", "default": 0.7},
                "max_tokens": {"type": "integer", "description": "Max tokens in response."}
            },
            "required": ["messages"]
        },
    ),
    Tool(
        name="llm_vision",
        description="Image-to-text / OCR / VLM using the ai-vision model. Send an image (URL or base64) and get a description.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "Image URL (http://...) or data:image/... base64"},
                "image_b64": {"type": "string", "description": "Base64-encoded image content (if no image_url)"},
                "prompt": {"type": "string", "description": "Question about the image, e.g. 'Describe this image'", "default": "Décris cette image."}
            },
            "required": []
        },
    ),
    Tool(
        name="stt_transcribe",
        description="Transcribe audio to text using Whisper model. Accepts file path, URL, or base64 audio.",
        inputSchema={
            "type": "object",
            "properties": {
                "audio_path": {"type": "string", "description": "Local path to audio file (opus, ogg, wav, mp3, m4a)"},
                "audio_url": {"type": "string", "description": "URL to download audio from"},
                "audio_b64": {"type": "string", "description": "Base64-encoded audio content"},
                "model": {"type": "string", "description": "Model name (default: whisper-1)", "default": "whisper-1"},
                "language": {"type": "string", "description": "Language code (e.g., 'fr', 'en'). Auto-detect if omitted."}
            }
        },
    ),
    Tool(
        name="tts_speech",
        description="Text-to-speech synthesis using OmniVoice model. Returns audio in opus/wav format.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to synthesize"},
                "voice": {"type": "string", "description": "Voice name (e.g., 'coral', 'sage'). Default 'coral'.", "default": "coral"},
                "response_format": {"type": "string", "description": "Output format: opus, mp3, wav, flac, pcm", "default": "opus"},
                "instructions": {"type": "string", "description": "Voice direction (e.g., 'Speak in a cheerful tone')"}
            },
            "required": ["text"]
        },
    ),
    Tool(
        name="image_generate",
        description="Generate images from text prompts using OpenDalle model.",
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image description prompt"},
                "n": {"type": "integer", "description": "Number of images to generate", "default": 1},
                "size": {"type": "string", "description": "Image size (e.g., '1024x1024', '1024x768')", "default": "1024x1024"}
            },
            "required": ["prompt"]
        },
    ),
    Tool(
        name="embeddings_create",
        description="Generate text embeddings using BGE-M3 model for RAG/search. Returns vector arrays.",
        inputSchema={
            "type": "object",
            "properties": {
                "texts": {"type": "array", "description": "List of texts to embed", "items": {"type": "string"}},
                "model": {"type": "string", "description": "Embedding model (default: bge-m3)", "default": "bge-m3"}
            },
            "required": ["texts"]
        },
    ),
    Tool(
        name="chromadb_collections",
        description="List all ChromaDB collections in the vector database.",
        inputSchema={
            "type": "object",
            "properties": {
                "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
            }
        },
    ),
    Tool(
        name="chromadb_search",
        description="Search ChromaDB collections with semantic/vector similarity search.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Collection name to search in"},
                "query": {"type": "string", "description": "Search query (text, not vector — will be embedded automatically)"},
                "n_results": {"type": "integer", "description": "Number of results to return", "default": 5},
                "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
            },
            "required": ["collection", "query"]
        },
    ),
    Tool(
        name="chromadb_upsert",
        description="Upsert documents (with embeddings) into a ChromaDB collection.",
        inputSchema={
            "type": "object",
            "properties": {
                "collection": {"type": "string", "description": "Collection name (created if it doesn't exist)"},
                "documents": {"type": "array", "description": "List of text documents to store", "items": {"type": "string"}},
                "metadatas": {"type": "array", "description": "List of metadata dicts for each document", "items": {"type": "object"}},
                "ids": {"type": "array", "description": "List of unique IDs for each document", "items": {"type": "string"}},
                "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
            },
            "required": ["collection", "documents", "ids"]
        },
    ),
    Tool(
        name="summary_text",
        description="Summarize long texts using the infocepo summary API.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to summarize"},
                "max_length": {"type": "integer", "description": "Max summary length in characters"}
            },
            "required": ["text"]
        },
    ),
    Tool(
        name="diarize_audio",
        description="Speaker diarization: identify and separate different speakers in an audio file.",
        inputSchema={
            "type": "object",
            "properties": {
                "audio_path": {"type": "string", "description": "Local path to audio file (mp3, wav, etc.)"},
                "audio_url": {"type": "string", "description": "URL to download audio from"}
            }
        },
    ),
    Tool(
        name="registry_list",
        description="List Docker images from the infocepo private registry.",
        inputSchema={
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number of results (for pagination)", "default": 0},
                "last": {"type": "string", "description": "Name of last entry for pagination"}
            }
        },
    ),
    Tool(
        name="s3_list",
        description="List objects in an S3-compatible storage bucket.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "Bucket name (e.g., 'ORG')"},
                "prefix": {"type": "string", "description": "Optional prefix/filter"}
            },
            "required": ["bucket"]
        },
    ),
    Tool(
        name="s3_upload",
        description="Upload a file to S3-compatible storage.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "Bucket name"},
                "key": {"type": "string", "description": "Object key (path in bucket)"},
                "file_path": {"type": "string", "description": "Local file path to upload"}
            },
            "required": ["bucket", "key", "file_path"]
        },
    ),
    Tool(
        name="s3_download",
        description="Download a file from S3-compatible storage.",
        inputSchema={
            "type": "object",
            "properties": {
                "bucket": {"type": "string", "description": "Bucket name"},
                "key": {"type": "string", "description": "Object key (path in bucket)"},
                "save_path": {"type": "string", "description": "Local path to save the file"}
            },
            "required": ["bucket", "key", "save_path"]
        },
    ),
]

# OpenAPI-compatible schemas (MCP SDK v2 overwrites Tool.inputSchema to None)
_TOOL_SCHEMAS = {
    "infra_list_services": {
        "type": "object",
        "properties": {
            "include_status": {
                "type": "boolean",
                "description": "Include health check status (requires HTTP call)"
            },
            "env": {
                "type": "string",
                "description": "Environment to show endpoints for: prod, lab, dev",
                "enum": ["prod", "lab", "dev"],
                "default": "prod"
            }
        }
    },
    "infra_refresh_discovery": {"type": "object", "properties": {}},
    "infra_read_wiki": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Wiki page title (e.g., 'Main_Page', 'Page_Name')"},
            "section": {"type": "string", "description": "Optional: extract only this section"}
        },
        "required": ["title"]
    },
    "infra_parse_wiki": {
        "type": "object",
        "properties": {"title": {"type": "string", "description": "Wiki page title"}},
        "required": ["title"]
    },
    "llm_chat": {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Model name: ai-default, ai-thinking, ai-fast, ai-embedding, ai-stt, ai-tts, ai-image, ai-vision"},
            "messages": {"type": "array", "description": "Chat messages array: [{role: 'user'|'system'|'assistant', content: 'text'}]"},
            "temperature": {"type": "number", "description": "Sampling temperature (0-2). Default 0.7.", "default": 0.7},
            "max_tokens": {"type": "integer", "description": "Max tokens in response."}
        },
        "required": ["messages"]
    },
    "llm_vision": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string", "description": "Image URL (http://...) or data:image/... base64"},
            "image_b64": {"type": "string", "description": "Base64-encoded image content (if no image_url)"},
            "prompt": {"type": "string", "description": "Question about the image, e.g. 'Describe this image'", "default": "Décris cette image."}
        },
        "required": []
    },
    "stt_transcribe": {
        "type": "object",
        "properties": {
            "audio_path": {"type": "string", "description": "Local path to audio file (opus, ogg, wav, mp3, m4a)"},
            "audio_url": {"type": "string", "description": "URL to download audio from"},
            "audio_b64": {"type": "string", "description": "Base64-encoded audio content"},
            "model": {"type": "string", "description": "Model name (default: whisper-1)", "default": "whisper-1"},
            "language": {"type": "string", "description": "Language code (e.g., 'fr', 'en'). Auto-detect if omitted."}
        }
    },
    "tts_speech": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize"},
            "voice": {"type": "string", "description": "Voice name (e.g., 'coral', 'sage'). Default 'coral'.", "default": "coral"},
            "response_format": {"type": "string", "description": "Output format: opus, mp3, wav, flac, pcm", "default": "opus"},
            "instructions": {"type": "string", "description": "Voice direction (e.g., 'Speak in a cheerful tone')"}
        },
        "required": ["text"]
    },
    "image_generate": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Image description prompt"},
            "n": {"type": "integer", "description": "Number of images to generate", "default": 1},
            "size": {"type": "string", "description": "Image size (e.g., '1024x1024', '1024x768')", "default": "1024x1024"}
        },
        "required": ["prompt"]
    },
    "embeddings_create": {
        "type": "object",
        "properties": {
            "texts": {"type": "array", "description": "List of texts to embed", "items": {"type": "string"}},
            "model": {"type": "string", "description": "Embedding model (default: bge-m3)", "default": "bge-m3"}
        },
        "required": ["texts"]
    },
    "chromadb_collections": {
        "type": "object",
        "properties": {
            "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
        }
    },
    "chromadb_search": {
        "type": "object",
        "properties": {
            "collection": {"type": "string", "description": "Collection name to search in"},
            "query": {"type": "string", "description": "Search query (text, not vector — will be embedded automatically)"},
            "n_results": {"type": "integer", "description": "Number of results to return", "default": 5},
            "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
        },
        "required": ["collection", "query"]
    },
    "chromadb_upsert": {
        "type": "object",
        "properties": {
            "collection": {"type": "string", "description": "Collection name (created if it doesn't exist)"},
            "documents": {"type": "array", "description": "List of text documents to store", "items": {"type": "string"}},
            "metadatas": {"type": "array", "description": "List of metadata dicts for each document", "items": {"type": "object"}},
            "ids": {"type": "array", "description": "List of unique IDs for each document", "items": {"type": "string"}},
            "env": {"type": "string", "description": "Environment: prod (default), lab", "enum": ["prod", "lab"]}
        },
        "required": ["collection", "documents", "ids"]
    },
    "summary_text": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to summarize"},
            "max_length": {"type": "integer", "description": "Max summary length in characters"}
        },
        "required": ["text"]
    },
    "diarize_audio": {
        "type": "object",
        "properties": {
            "audio_path": {"type": "string", "description": "Local path to audio file (mp3, wav, etc.)"},
            "audio_url": {"type": "string", "description": "URL to download audio from"}
        }
    },
    "registry_list": {
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Number of results (for pagination)", "default": 0},
            "last": {"type": "string", "description": "Name of last entry for pagination"}
        }
    },
    "s3_list": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "Bucket name (e.g., 'ORG')"},
            "prefix": {"type": "string", "description": "Optional prefix/filter"}
        },
        "required": ["bucket"]
    },
    "s3_upload": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "Bucket name"},
            "key": {"type": "string", "description": "Object key (path in bucket)"},
            "file_path": {"type": "string", "description": "Local file path to upload"}
        },
        "required": ["bucket", "key", "file_path"]
    },
    "s3_download": {
        "type": "object",
        "properties": {
            "bucket": {"type": "string", "description": "Bucket name"},
            "key": {"type": "string", "description": "Object key (path in bucket)"},
            "save_path": {"type": "string", "description": "Local path to save the file"}
        },
        "required": ["bucket", "key", "save_path"]
    },
}

# ============================================================================
# Tool handler dispatch
# ============================================================================

async def _handle_tool_call(name: str, arguments: dict) -> str:
    """Handle a tool call and return JSON string."""
    try:
        if name == "infra_list_services":
            result = wiki_fetcher.parse_main_page()
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif name == "infra_refresh_discovery":
            wiki_fetcher.cache_dir.mkdir(parents=True, exist_ok=True)
            import time
            for f in wiki_fetcher.cache_dir.glob("*.txt"):
                f.unlink()
            result = wiki_fetcher.parse_main_page()
            if "error" in result:
                return json.dumps(result, indent=2, ensure_ascii=False)
            return json.dumps({"status": "ok", "services": len(result.get("services", [])), "urls": len(result.get("urls", []))}, indent=2)
        elif name == "infra_read_wiki":
            title = arguments.get("title", "Main_Page")
            section = arguments.get("section")
            content = wiki_fetcher.get_page(title)
            if not content:
                return json.dumps({
                    "error": f"Unable to read wiki page '{title}'",
                    "upstream": wiki_fetcher.last_error,
                }, indent=2, ensure_ascii=False)
            if section:
                content = wiki_fetcher.get_section(title, section) or content
            return content
        elif name == "infra_parse_wiki":
            title = arguments.get("title", "Main_Page")
            sections = wiki_fetcher.parse_sections(title)
            if wiki_fetcher.last_error:
                return json.dumps({
                    "error": f"Unable to parse wiki page '{title}'",
                    "upstream": wiki_fetcher.last_error,
                }, indent=2, ensure_ascii=False)
            return json.dumps(sections, indent=2, ensure_ascii=False)
        elif name == "llm_chat":
            return handle_llm_chat(arguments)
        elif name == "llm_vision":
            return handle_llm_vision(arguments)
        elif name == "stt_transcribe":
            return handle_stt_transcribe(arguments)
        elif name == "tts_speech":
            result_raw = handle_tts_speech(arguments)
            return result_raw
        elif name == "image_generate":
            result_raw = handle_image_generate(arguments)
            return result_raw
        elif name == "embeddings_create":
            return handle_embeddings_create(arguments)
        elif name == "chromadb_collections":
            return handle_chromadb_collections(arguments)
        elif name == "chromadb_search":
            return handle_chromadb_search(arguments)
        elif name == "chromadb_upsert":
            return handle_chromadb_upsert(arguments)
        elif name == "summary_text":
            return handle_summary_text(arguments)
        elif name == "diarize_audio":
            return handle_diarize_audio(arguments)
        elif name == "registry_list":
            return handle_registry_list(arguments)
        elif name == "s3_list":
            return handle_s3_list(arguments)
        elif name == "s3_upload":
            return handle_s3_upload(arguments)
        elif name == "s3_download":
            return handle_s3_download(arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        import traceback
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()[:2000]})


# ============================================================================
# MCP handler registration (decorator pattern, MCP v2)
# ============================================================================

async def list_tools(context, params):
    """Return the list of available MCP tools."""
    from mcp.types import ListToolsResult
    return ListToolsResult(tools=_MCP_TOOLS)


async def call_tool(context, params):
    """Handle a tool call."""
    import traceback as tb_module
    try:
        args = params.arguments or {}
        result_text = await _handle_tool_call(params.name, args)
        from mcp.types import CallToolResult, TextContent
        return CallToolResult(content=[TextContent(type="text", text=str(result_text))])
    except Exception as e:
        from mcp.types import CallToolResult, TextContent
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": str(e), "traceback": tb_module.format_exc()[:2000]}))],
            isError=True
        )


# ============================================================================
# OpenAPI endpoint for OpenWebUI External Tool Servers
# ============================================================================

async def openapi_handler(scope, receive, send):
    from starlette.responses import JSONResponse
    
    openapi_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "infocepo-infra MCP Server",
            "version": "0.1.0",
            "description": "MCP tools for infocepo infrastructure"
        },
        "paths": {}
    }
    
    for tool in _MCP_TOOLS:
        tool_name = tool.name
        schema = _TOOL_SCHEMAS.get(tool_name, {"type": "object", "properties": {}})
        openapi_spec["paths"][f"/tools/{tool_name}"] = {
            "post": {
                "operationId": f"call_{tool_name}",
                "summary": tool.description,
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": schema.get("type", "object"),
                                "properties": schema.get("properties", {}),
                                "required": schema.get("required", []),
                                "additionalProperties": True
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Tool execution result"
                    }
                }
            }
        }
    
    resp = JSONResponse(openapi_spec)
    await resp(scope, receive, send)


# OpenAPI endpoint that also responds to /sse/openapi.json (OpenWebUI probe)
async def openapi_probe_handler(scope, receive, send):
    from starlette.responses import RedirectResponse
    resp = RedirectResponse(url="/openapi.json", status_code=307)
    await resp(scope, receive, send)


async def tool_http_handler(scope, receive, send, tool_name: str):
    """Invoke a tool through the route advertised by the OpenAPI document."""
    from starlette.responses import JSONResponse

    if tool_name not in _TOOL_SCHEMAS:
        response = JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=404)
        await response(scope, receive, send)
        return

    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break

    try:
        arguments = json.loads(body or b"{}")
    except (TypeError, ValueError):
        response = JSONResponse({"error": "Request body must be valid JSON."}, status_code=400)
        await response(scope, receive, send)
        return

    if not isinstance(arguments, dict):
        response = JSONResponse({"error": "Request body must be a JSON object."}, status_code=400)
        await response(scope, receive, send)
        return

    result = await _handle_tool_call(tool_name, arguments)
    response = JSONResponse({"content": result})
    await response(scope, receive, send)


# ============================================================================
# ASGI Routing
# ============================================================================

mcp_app: Server = Server(
    "infocepo-infra",
    version="0.1.0",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
)

sse = SseServerTransport("/messages")

# Streamable HTTP is the current MCP HTTP transport and is used by
# api-mcp-openai.  Stateless JSON responses are particularly useful for an API
# gateway: requests do not depend on a sticky session and regular JSON-RPC
# responses do not require the gateway to consume an SSE stream.
streamable_http = StreamableHTTPSessionManager(
    app=mcp_app,
    stateless=True,
    json_response=True,
)


async def sse_handler(scope, receive, send):
    if scope["type"] != "http":
        return
    async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await mcp_app.run(read_stream, write_stream, mcp_app.create_initialization_options())


async def messages_handler(scope, receive, send):
    return await sse.handle_post_message(scope=scope, receive=receive, send=send)


# ============================================================================
# Middleware: CORS headers
# ============================================================================

async def debug_middleware(scope, receive, send):
    if scope["type"] != "http" or not scope.get("path", "").startswith("/messages"):
        return await not_found(scope, receive, send)
    
    import asyncio
    body = b""
    while True:
        try:
            msg = await asyncio.wait_for(receive(), timeout=1.0)
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        except asyncio.TimeoutError:
            break
    
    print(f"[DEBUG RAW] Body: {body.decode()[:1000]}", file=sys.stderr, flush=True)
    
    # Put the body back by wrapping receive
    body_data = body
    async def wrapped_receive():
        nonlocal body_data
        if body_data:
            first = {"type": "http.request", "body": body_data, "more_body": False}
            body_data = b""
            return first
        return await receive()
    
    # Now call the actual handler
    await messages_handler(scope, wrapped_receive, send)


async def health_handler(scope, receive, send):
    from starlette.responses import JSONResponse
    resp = JSONResponse({"status": "ok", "server": "infocepo-infra-mcp", "version": "0.1.0", "tools": len(_MCP_TOOLS)})
    await resp(scope, receive, send)


async def not_found(scope, receive, send):
    from starlette.responses import JSONResponse
    resp = JSONResponse({"error": "not found"}, status_code=404)
    await resp(scope, receive, send)


async def router(scope, receive, send):
    if scope["type"] == "lifespan":
        async with streamable_http.run():
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        return

    if scope["type"] != "http":
        return
    
    path = scope.get("path", "")
    method = scope.get("method", "GET")

    # Protect every API endpoint except the health probe.  Leaving API_TOKEN
    # unset keeps local development backwards-compatible.
    api_token = os.getenv("API_TOKEN", "")
    if api_token and path != "/health" and method != "OPTIONS":
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        supplied_token = (
            authorization[7:]
            if authorization.lower().startswith("bearer ")
            else headers.get("x-api-key", "")
        )
        if not hmac.compare_digest(supplied_token, api_token):
            from starlette.responses import JSONResponse
            response = JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
    
    # Handle CORS preflight (OPTIONS) - respond with CORS headers immediately
    if method == "OPTIONS":
        from starlette.responses import Response
        resp = Response(status_code=204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "*"
        await resp(scope, receive, send)
        return
    
    if path in ("/mcp", "/mcp/") and method in ("GET", "POST", "DELETE"):
        await streamable_http.handle_request(scope, receive, send)
    elif method == "GET" and path == "/openapi.json":
        await openapi_handler(scope, receive, send)
    elif method == "GET" and path == "/sse/openapi.json":
        await openapi_probe_handler(scope, receive, send)
    elif method == "POST" and path.startswith("/tools/"):
        await tool_http_handler(scope, receive, send, path.removeprefix("/tools/"))
    elif method == "GET" and path == "/sse":
        await sse_handler(scope, receive, send)
    elif method == "POST" and path.startswith("/messages"):
        await debug_middleware(scope, receive, send)
    elif method == "POST" and path == "/debug/body":
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        print(f"[DEBUG RAW] Body: {body.decode()[:1000]}", file=sys.stderr, flush=True)
        from starlette.responses import JSONResponse
        resp = JSONResponse({"captured": body.decode()[:1000], "length": len(body)})
        await resp(scope, receive, send)
    elif method == "GET" and path == "/health":
        await health_handler(scope, receive, send)
    else:
        await not_found(scope, receive, send)


# ============================================================================
# Main entrypoint
# ============================================================================

def main():
    """Run the HTTP server."""
    import uvicorn
    import logging
    logging.getLogger("uvicorn").setLevel(logging.DEBUG)
    logging.getLogger("mcp.server").setLevel(logging.DEBUG)
    logging.getLogger("mcp.shared").setLevel(logging.DEBUG)
    logging.getLogger("sse").setLevel(logging.DEBUG)

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8085"))

    print(f"Starting infocepo-infra MCP SSE server on {host}:{port}", file=sys.stderr)

    # Create app with CORS middleware
    app = CORSMiddleware(app=router, allow_origins=["*"])
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
