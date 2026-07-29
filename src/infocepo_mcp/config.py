"""Configuration management for infocepo-infra-mcp."""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServicesConfig:
    """Endpoints for all infocepo.com services."""
    env: str = "prod"  # prod, lab, dev

    # Core endpoints (without port/timeout annotations)
    llm_base: str = "https://api-nothink.ailab.infocepo.com/v1"
    stt_base: str = "https://api-audio2txt.ailab.infocepo.com/v1"
    tts_base: str = "https://api-tts-omnivoice.ailab.infocepo.com/v1"
    txt2image_base: str = "https://api-txt2image.ailab.infocepo.com/v1"
    embedding_base: str = "https://api-embedding.ailab.infocepo.com/v1"
    summary_base: str = "https://api-summary.ailab.infocepo.com:wait-2026-12"
    diarization_base: str = "https://api-diarization.ailab.infocepo.com"
    realtime_base: str = "wss://api-realtime-ai.ailab.infocepo.com:wait-2026-12/v1"
    registry_base: str = "registry.ailab.infocepo.com:wait-2026-09"
    s3_endpoint: str = "s3.ailab.infocepo.com:wait-2026-09"
    chroma_prod: str = "chromadb.ailab.infocepo.com:wait-2026-12"
    chroma_lab: str = "chromadb.c1.ailab.infocepo.com:wait-2026-12"
    wiki_base: str = "https://infocepo.com/wiki/api.php"
    grafana_base: str = "https://grafana.ailab.infocepo.com:wait-2026-12"
    uptime_base: str = "https://uptime-kuma.ailab.infocepo.com:wait-2026-12/status/ai"

    def clean_url(self, url: str) -> str:
        """Strip :wait-YYYY-MM annotations from wiki URLs."""
        if not url:
            return url
        import re
        return re.sub(r':wait-\d{4}-\d{2}', '', url)

    def clean_port(self, host: str) -> str:
        """Strip :wait-YYYY-MM from host strings."""
        import re
        return re.sub(r':wait-\d{4}-\d{2}', '', host)

    def chroma_url(self, env: Optional[str] = None) -> str:
        """Return ChromaDB URL based on environment."""
        env = env or self.env
        if env == "lab":
            return self.clean_url(self.chroma_lab)
        return self.clean_url(self.chroma_prod)

    def chroma_port(self) -> int:
        return 443

    def registry_host(self) -> str:
        return self.clean_port(self.registry_base)

    def s3_host(self) -> str:
        return self.clean_port(self.s3_endpoint)

    def s3_endpoint_url(self) -> str:
        return f"https://{self.s3_host()}"


@dataclass
class Credentials:
    """Service credentials (loaded from file or env)."""
    api_key: Optional[str] = None
    chroma_token: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    registry_user: Optional[str] = None
    registry_password: Optional[str] = None

    def load(self, config_path: Optional[str] = None):
        """Load credentials from env vars and optional config file."""
        self.api_key = self.api_key or os.getenv("INFOCEPO_API_KEY")
        self.chroma_token = self.chroma_token or os.getenv("INFOCEPO_CHROMA_TOKEN")
        self.s3_access_key = self.s3_access_key or os.getenv("INFOCEPO_S3_ACCESS_KEY")
        self.s3_secret_key = self.s3_secret_key or os.getenv("INFOCEPO_S3_SECRET_KEY")
        self.registry_user = self.registry_user or os.getenv("INFOCEPO_REGISTRY_USER", "user")
        self.registry_password = self.registry_password or os.getenv("INFOCEPO_REGISTRY_PASSWORD")

        if config_path and Path(config_path).exists():
            data = json.loads(Path(config_path).read_text())
            if isinstance(data, dict):
                self.api_key = data.get("api_key", self.api_key)
                self.chroma_token = data.get("chroma_token", self.chroma_token)
                self.s3_access_key = data.get("s3_access_key", self.s3_access_key)
                self.s3_secret_key = data.get("s3_secret_key", self.s3_secret_key)
                self.registry_user = data.get("registry_user", self.registry_user)
                self.registry_password = data.get("registry_password", self.registry_password)


class Config:
    """Singleton config combining services and credentials."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.services = ServicesConfig()
        self.creds = Credentials()
        self.creds.load(os.getenv("INFOCEPO_CREDENTIALS_FILE"))

    def get_llm_api_key(self) -> str:
        if not self.creds.api_key:
            raise ValueError("INFOCEPO_API_KEY not set")
        return self.creds.api_key

    def get_headers(self, service: str = "api") -> dict:
        headers = {"accept": "application/json"}
        key = self.get_llm_api_key()
        if service == "registry":
            import base64
            credentials = f"{self.creds.registry_user}:{self.creds.registry_password}"
            headers["Authorization"] = f"Basic {base64.b64encode(credentials.encode()).decode()}"
        else:
            headers["Authorization"] = f"Bearer {key}"
        return headers
