"""MCP tool definitions for infocepo-infra services."""

from typing import Optional
import base64


def list_tools():
    """Register all MCP tools."""
    return [
        # === Meta/Discovery tools ===
        _tool(
            "infra_list_services",
            "List all infocepo.com infrastructure services with status and endpoints.",
            {
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
            }
        ),
        _tool(
            "infra_refresh_discovery",
            "Re-fetch and re-parse the wiki Main_Page to discover any changes to services/endpoints.",
            {
                "type": "object",
                "properties": {}
            }
        ),
        _tool(
            "infra_read_wiki",
            "Read a page from the infocepo.com wiki. Useful for discovering new services, configurations, or documentation.",
            {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Wiki page title (e.g., 'Main_Page', 'Page_Name')"
                    },
                    "section": {
                        "type": "string",
                        "description": "Optional: extract only this section (e.g., 'Catalogue rapide des services')"
                    }
                },
                "required": ["title"]
            }
        ),
        _tool(
            "infra_parse_wiki",
            "Parse wiki wikitext and return structured sections. Returns list of sections with title and content.",
            {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Wiki page title"
                    }
                },
                "required": ["title"]
            }
        ),

        # === LLM Service ===
        _tool(
            "llm_chat",
            "Chat completions using the infocepo LLM API (OpenAI-compatible). Supports chat, reasoning, code generation.",
            {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name: ai-default, ai-thinking, ai-fast, ai-embedding, ai-stt, ai-tts, ai-image, ai-vision"
                    },
                    "messages": {
                        "type": "array",
                        "description": "Chat messages array: [{role: 'user'|'system'|'assistant', content: 'text'}]",
                        "items": {"type": "object"}
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature (0-2). Default 0.7.",
                        "default": 0.7
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens in response."
                    }
                },
                "required": ["messages"]
            }
        ),
        _tool(
            "llm_vision",
            "Image-to-text / OCR / VLM using the ai-vision model. Send an image (URL or base64) and get a description.",
            {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "Image URL (http://...) or data:image/... base64"
                    },
                    "image_b64": {
                        "type": "string",
                        "description": "Base64-encoded image content (if no image_url)"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Question about the image, e.g. 'Describe this image'",
                        "default": "Décris cette image."
                    }
                },
                "required": []
            }
        ),

        # === STT Service ===
        _tool(
            "stt_transcribe",
            "Transcribe audio to text using Whisper model. Accepts file path, URL, or base64 audio.",
            {
                "type": "object",
                "properties": {
                    "audio_path": {
                        "type": "string",
                        "description": "Local path to audio file (opus, ogg, wav, mp3, m4a)"
                    },
                    "audio_url": {
                        "type": "string",
                        "description": "URL to download audio from"
                    },
                    "audio_b64": {
                        "type": "string",
                        "description": "Base64-encoded audio content"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model name (default: whisper-1)",
                        "default": "whisper-1"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code (e.g., 'fr', 'en'). Auto-detect if omitted."
                    }
                }
            }
        ),

        # === TTS Service ===
        _tool(
            "tts_speech",
            "Text-to-speech synthesis using OmniVoice model. Returns audio in opus/wav format.",
            {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to synthesize"
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice name (e.g., 'coral', 'sage'). Default 'coral'.",
                        "default": "coral"
                    },
                    "response_format": {
                        "type": "string",
                        "description": "Output format: opus, mp3, wav, flac, pcm",
                        "default": "opus"
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Voice direction (e.g., 'Speak in a cheerful tone')"
                    }
                },
                "required": ["text"]
            }
        ),

        # === Text-to-Image Service ===
        _tool(
            "image_generate",
            "Generate images from text prompts using OpenDalle model.",
            {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Image description prompt"
                    },
                    "n": {
                        "type": "integer",
                        "description": "Number of images to generate",
                        "default": 1
                    },
                    "size": {
                        "type": "string",
                        "description": "Image size (e.g., '1024x1024', '1024x768')",
                        "default": "1024x1024"
                    }
                },
                "required": ["prompt"]
            }
        ),

        # === Embeddings Service ===
        _tool(
            "embeddings_create",
            "Generate text embeddings using BGE-M3 model for RAG/search. Returns vector arrays.",
            {
                "type": "object",
                "properties": {
                    "texts": {
                        "type": "array",
                        "description": "List of texts to embed",
                        "items": {"type": "string"}
                    },
                    "model": {
                        "type": "string",
                        "description": "Embedding model (default: bge-m3)",
                        "default": "bge-m3"
                    }
                },
                "required": ["texts"]
            }
        ),

        # === ChromaDB Service ===
        _tool(
            "chromadb_collections",
            "List all ChromaDB collections in the vector database.",
            {
                "type": "object",
                "properties": {
                    "env": {
                        "type": "string",
                        "description": "Environment: prod (default), lab",
                        "enum": ["prod", "lab"]
                    }
                }
            }
        ),
        _tool(
            "chromadb_search",
            "Search ChromaDB collections with semantic/vector similarity search.",
            {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name to search in"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (text, not vector — will be embedded automatically)"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5
                    },
                    "env": {
                        "type": "string",
                        "description": "Environment: prod (default), lab",
                        "enum": ["prod", "lab"]
                    }
                },
                "required": ["collection", "query"]
            }
        ),
        _tool(
            "chromadb_upsert",
            "Upsert documents (with embeddings) into a ChromaDB collection.",
            {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name (created if it doesn't exist)"
                    },
                    "documents": {
                        "type": "array",
                        "description": "List of text documents to store",
                        "items": {"type": "string"}
                    },
                    "metadatas": {
                        "type": "array",
                        "description": "List of metadata dicts for each document",
                        "items": {"type": "object"}
                    },
                    "ids": {
                        "type": "array",
                        "description": "List of unique IDs for each document",
                        "items": {"type": "string"}
                    },
                    "env": {
                        "type": "string",
                        "description": "Environment: prod (default), lab",
                        "enum": ["prod", "lab"]
                    }
                },
                "required": ["collection", "documents", "ids"]
            }
        ),

        # === Summary Service ===
        _tool(
            "summary_text",
            "Summarize long texts using the infocepo summary API.",
            {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to summarize"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Max summary length in characters"
                    }
                },
                "required": ["text"]
            }
        ),

        # === Diarization Service ===
        _tool(
            "diarize_audio",
            "Speaker diarization: identify and separate different speakers in an audio file.",
            {
                "type": "object",
                "properties": {
                    "audio_path": {
                        "type": "string",
                        "description": "Local path to audio file (mp3, wav, etc.)"
                    },
                    "audio_url": {
                        "type": "string",
                        "description": "URL to download audio from"
                    }
                }
            }
        ),

        # === Registry Service ===
        _tool(
            "registry_list",
            "List Docker images from the infocepo private registry.",
            {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of results (for pagination)",
                        "default": 0
                    },
                    "last": {
                        "type": "string",
                        "description": "Name of last entry for pagination"
                    }
                }
            }
        ),

        # === S3 Service ===
        _tool(
            "s3_list",
            "List objects in an S3-compatible storage bucket.",
            {
                "type": "object",
                "properties": {
                    "bucket": {
                        "type": "string",
                        "description": "Bucket name (e.g., 'ORG')"
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Optional prefix/filter"
                    }
                },
                "required": ["bucket"]
            }
        ),
        _tool(
            "s3_upload",
            "Upload a file to S3-compatible storage.",
            {
                "type": "object",
                "properties": {
                    "bucket": {
                        "type": "string",
                        "description": "Bucket name"
                    },
                    "key": {
                        "type": "string",
                        "description": "Object key (path in bucket)"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Local file path to upload"
                    }
                },
                "required": ["bucket", "key", "file_path"]
            }
        ),
        _tool(
            "s3_download",
            "Download a file from S3-compatible storage.",
            {
                "type": "object",
                "properties": {
                    "bucket": {
                        "type": "string",
                        "description": "Bucket name"
                    },
                    "key": {
                        "type": "string",
                        "description": "Object key (path in bucket)"
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Local path to save the file"
                    }
                },
                "required": ["bucket", "key", "save_path"]
            }
        ),
    ]


def _tool(name: str, desc: str, schema: dict) -> dict:
    """Create a tool definition dict."""
    return {
        "name": name,
        "description": desc,
        "inputSchema": schema,
    }
