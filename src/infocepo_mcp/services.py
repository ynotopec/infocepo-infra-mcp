"""Service handlers: call infocepo.com APIs for each tool."""

import json
import os
import tempfile
import base64
from typing import Optional
import httpx
import boto3
from botocore.config import Config

from .config import Config as AppConfig


def _get_config() -> AppConfig:
    return AppConfig()


def _make_llm_request(endpoint: str, data: dict) -> dict:
    """Make a request to any infocepo API endpoint."""
    config = _get_config()
    key = config.get_llm_api_key()
    base_url = config.services.clean_url(endpoint)

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            base_url,
            json=data,
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]}
        return resp.json()


def handle_llm_chat(args: dict) -> str:
    """Chat completions handler."""
    config = _get_config()
    model = args.get("model", "ai-default")
    messages = args["messages"]
    data = {
        "model": model,
        "messages": messages,
        "temperature": args.get("temperature", 0.7),
    }
    if args.get("max_tokens"):
        data["max_tokens"] = args["max_tokens"]
    result = _make_llm_request(config.services.llm_base + "/chat/completions", data)
    return json.dumps(result, indent=2, ensure_ascii=False)


def handle_llm_vision(args: dict) -> str:
    """Vision / OCR handler."""
    config = _get_config()
    content = []

    if args.get("image_url"):
        content.append({
            "type": "image_url",
            "image_url": {"url": args["image_url"]},
        })
    elif args.get("image_b64"):
        img_data = args["image_b64"]
        if img_data.startswith("data:"):
            content.append({"type": "image_url", "image_url": {"url": img_data}})
        else:
            # Assume raw base64, prepend data URI
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}})

    prompt = args.get("prompt", "Décris cette image.")
    content.append({"type": "text", "text": prompt})

    data = {
        "model": "ai-vision",
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
    }
    result = _make_llm_request(config.services.llm_base + "/chat/completions", data)
    return json.dumps(result, indent=2, ensure_ascii=False)


def handle_stt_transcribe(args: dict) -> str:
    """STT transcription handler."""
    config = _get_config()
    base_url = config.services.clean_url(config.services.stt_base + "/audio/transcriptions")
    key = config.get_llm_api_key()

    audio_data = None
    filename = None
    content_type = "audio/opus"

    if args.get("audio_path"):
        with open(args["audio_path"], "rb") as f:
            audio_data = f.read()
        filename = os.path.basename(args["audio_path"])
        content_type = _guess_content_type(filename)
    elif args.get("audio_url"):
        with httpx.Client(timeout=30) as client:
            resp = client.get(args["audio_url"])
            audio_data = resp.content
            filename = "audio.ogg"
    elif args.get("audio_b64"):
        audio_data = base64.b64decode(args["audio_b64"])
        filename = "audio.ogg"
    else:
        return json.dumps({"error": "No audio source provided. Use audio_path, audio_url, or audio_b64."})

    with httpx.Client(timeout=120) as client:
        files = {
            "file": (filename, audio_data, content_type),
            "model": (None, args.get("model", "whisper-1")),
        }
        params = {"language": args.get("language")} if args.get("language") else {}
        resp = client.post(
            base_url,
            files=files,
            params=params,
            headers={"Authorization": f"Bearer {key}"},
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        return json.dumps(resp.json(), indent=2, ensure_ascii=False)


def handle_tts_speech(args: dict) -> str:
    """TTS synthesis handler."""
    config = _get_config()
    base_url = config.services.clean_url(config.services.tts_base + "/audio/speech")
    key = config.get_llm_api_key()

    data = {
        "model": "gpt-4o-mini-tts",
        "input": args["text"],
        "voice": args.get("voice", "coral"),
        "response_format": args.get("response_format", "opus"),
    }
    if args.get("instructions"):
        data["instructions"] = args["instructions"]

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            base_url,
            json=data,
            headers={
                "accept": "audio/opus",
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        # Save audio to temp file, return path
        output_format = data.get("response_format", "opus")
        fmt = ".opus" if output_format == "opus" else f".{output_format}"
        tmp_path = tempfile.mktemp(suffix=fmt)
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        return json.dumps({"audio_path": tmp_path, "format": output_format, "voice": data.get("voice")})


def handle_image_generate(args: dict) -> str:
    """Text-to-image generation handler."""
    config = _get_config()
    base_url = config.services.clean_url(config.services.txt2image_base + "/images/generations")
    key = config.get_llm_api_key()

    data = {
        "prompt": args["prompt"],
        "n": args.get("n", 1),
        "size": args.get("size", "1024x1024"),
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            base_url,
            json=data,
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        result = resp.json()
        # Return image URLs or data URIs
        if "data" in result:
            for item in result["data"]:
                if "url" in item:
                    item["saved_to"] = tempfile.mktemp(suffix=".png")
                    with httpx.Client(timeout=30) as img_client:
                        img_resp = img_client.get(item["url"])
                        with open(item["saved_to"], "wb") as f:
                            f.write(img_resp.content)
                elif "b64_json" in item:
                    import base64 as b64mod
                    img_data = b64mod.b64decode(item["b64_json"])
                    item["saved_to"] = tempfile.mktemp(suffix=".png")
                    with open(item["saved_to"], "wb") as f:
                        f.write(img_data)
        return json.dumps(result, indent=2, ensure_ascii=False)


def handle_embeddings_create(args: dict) -> str:
    """Embeddings generation handler."""
    config = _get_config()
    base_url = config.services.clean_url(config.services.embedding_base + "/embeddings")

    data = {
        "model": args.get("model", "bge-m3"),
        "input": args["texts"],
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            base_url,
            json=data,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        result = resp.json()
        return json.dumps(result, indent=2, ensure_ascii=False)


def handle_chromadb_collections(args: dict) -> str:
    """List ChromaDB collections."""
    config = _get_config()
    from .config import ServicesConfig
    chroma_url = config.services.chroma_url(args.get("env"))
    token = config.creds.chroma_token

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.HttpClient(
            host=chroma_url,
            port=443,
            ssl=True,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=token,
            ) if token else Settings()
        )
        collections = client.list_collections()
        return json.dumps([c.name for c in collections], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_chromadb_search(args: dict) -> str:
    """Search ChromaDB collection."""
    config = _get_config()
    chroma_url = config.services.chroma_url(args.get("env"))
    token = config.creds.chroma_token

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.HttpClient(
            host=chroma_url,
            port=443,
            ssl=True,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=token,
            ) if token else Settings()
        )
        collection = client.get_or_create_collection(args["collection"])

        # Auto-embed the query
        query = args["query"]
        embedding_config = _get_config()
        emb_base = embedding_config.services.clean_url(embedding_config.services.embedding_base) + "/embeddings"

        with httpx.Client(timeout=30) as emb_client:
            emb_resp = emb_client.post(
                emb_base,
                json={"model": "bge-m3", "input": [query]},
                headers={"Content-Type": "application/json"},
            )
            if emb_resp.status_code == 200:
                vectors = [emb_resp.json()["data"][0]["embedding"]]
            else:
                vectors = None

        result = collection.query(
            query_texts=[query] if not vectors else None,
            query_embeddings=vectors,
            n_results=args.get("n_results", 5),
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_chromadb_upsert(args: dict) -> str:
    """Upsert documents to ChromaDB collection."""
    config = _get_config()
    chroma_url = config.services.chroma_url(args.get("env"))
    token = config.creds.chroma_token

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.HttpClient(
            host=chroma_url,
            port=443,
            ssl=True,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token.TokenAuthClientProvider",
                chroma_client_auth_credentials=token,
            ) if token else Settings()
        )
        collection = client.get_or_create_collection(args["collection"])

        collection.add(
            documents=args["documents"],
            metadatas=args.get("metadatas"),
            ids=args["ids"],
        )
        return json.dumps({"status": "ok", "added": len(args["ids"]), "collection": args["collection"]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_summary_text(args: dict) -> str:
    """Summary API handler."""
    config = _get_config()
    base_url = config.services.clean_url(config.services.summary_base) + "/summary/"

    data = {"text": args["text"]}
    if args.get("max_length"):
        data["max_length"] = args["max_length"]

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            base_url,
            json=data,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        return json.dumps(resp.json(), indent=2, ensure_ascii=False)


def handle_diarize_audio(args: dict) -> str:
    """Diarization API handler."""
    config = _get_config()
    base_url = f"{config.services.clean_url(config.services.diarization_base)}/upload-audio/"
    key = config.get_llm_api_key()

    audio_data = None
    filename = None

    if args.get("audio_path"):
        with open(args["audio_path"], "rb") as f:
            audio_data = f.read()
        filename = os.path.basename(args["audio_path"])
    elif args.get("audio_url"):
        with httpx.Client(timeout=30) as client:
            resp = client.get(args["audio_url"])
            audio_data = resp.content
            filename = "audio.mp3"
    else:
        return json.dumps({"error": "No audio source provided."})

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            base_url,
            files={"file": (filename, audio_data)},
            headers={"Authorization": f"Bearer {key}"},
        )
        if resp.status_code not in (200, 201, 202):
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        return json.dumps(resp.json(), indent=2, ensure_ascii=False)


def handle_registry_list(args: dict) -> str:
    """Docker registry list handler."""
    config = _get_config()
    host = config.services.registry_host() + ":443"

    credentials = f"{config.creds.registry_user}:{config.creds.registry_password}"
    auth_header = base64.b64encode(credentials.encode()).decode()

    with httpx.Client(timeout=30) as client:
        params = {"n": args.get("n", 0)}
        if args.get("last"):
            params["last"] = args["last"]

        resp = client.get(
            f"https://{host}/v2/_catalog",
            params=params,
            headers={"Authorization": f"Basic {auth_header}"},
            verify=True,
        )
        if resp.status_code != 200:
            return json.dumps({"error": f"HTTP {resp.status_code}", "detail": resp.text[:500]})
        return json.dumps(resp.json(), indent=2, ensure_ascii=False)


def handle_s3_list(args: dict) -> str:
    """S3 list handler."""
    config = _get_config()

    s3 = boto3.client(
        "s3",
        endpoint_url=config.services.s3_endpoint_url(),
        aws_access_key_id=config.creds.s3_access_key,
        aws_secret_access_key=config.creds.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )
    params = {"Bucket": args["bucket"]}
    if args.get("prefix"):
        params["Prefix"] = args["prefix"]

    try:
        resp = s3.list_objects_v2(**params)
        return json.dumps({
            "bucket": args["bucket"],
            "count": len(resp.get("Contents", [])),
            "objects": [{"key": o["Key"], "size": o["Size"], "last_modified": str(o["LastModified"])} for o in resp.get("Contents", [])],
        }, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_s3_upload(args: dict) -> str:
    """S3 upload handler."""
    config = _get_config()

    s3 = boto3.client(
        "s3",
        endpoint_url=config.services.s3_endpoint_url(),
        aws_access_key_id=config.creds.s3_access_key,
        aws_secret_access_key=config.creds.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )
    try:
        s3.upload_file(args["file_path"], args["bucket"], args["key"])
        return json.dumps({"status": "ok", "bucket": args["bucket"], "key": args["key"]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_s3_download(args: dict) -> str:
    """S3 download handler."""
    config = _get_config()

    s3 = boto3.client(
        "s3",
        endpoint_url=config.services.s3_endpoint_url(),
        aws_access_key_id=config.creds.s3_access_key,
        aws_secret_access_key=config.creds.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )
    try:
        s3.download_file(args["bucket"], args["key"], args["save_path"])
        return json.dumps({"status": "ok", "path": args["save_path"]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _guess_content_type(filename: str) -> str:
    """Guess content type from filename."""
    import mimetypes
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
