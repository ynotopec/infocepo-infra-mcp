"""Tests for config module."""

import pytest
import os
import tempfile
import json
from unittest.mock import patch

from infocepo_mcp.config import ServicesConfig, Credentials, Config


class TestServicesConfig:
    def test_default_env(self):
        config = ServicesConfig()
        assert config.env == "prod"

    def test_clean_url_removes_wait_annotation(self):
        config = ServicesConfig()
        result = config.clean_url("chromadb.ailab.infocepo.com:wait-2026-12")
        assert "wait" not in result
        assert result == "chromadb.ailab.infocepo.com"

    def test_clean_port_removes_wait_annotation(self):
        config = ServicesConfig()
        result = config.clean_port("registry.ailab.infocepo.com:wait-2026-09")
        assert "wait" not in result
        assert result == "registry.ailab.infocepo.com"

    def test_chroma_url_prod(self):
        config = ServicesConfig()
        result = config.chroma_url("prod")
        assert "chromadb.ailab.infocepo.com" in result

    def test_chroma_url_lab(self):
        config = ServicesConfig()
        result = config.chroma_url("lab")
        assert "chromadb.c1.ailab.infocepo.com" in result

    def test_registry_host(self):
        config = ServicesConfig()
        result = config.registry_host()
        assert "wait" not in result
        assert "registry.ailab.infocepo.com" in result

    def test_s3_host(self):
        config = ServicesConfig()
        result = config.s3_host()
        assert "wait" not in result
        assert "s3.ailab.infocepo.com" in result

    def test_s3_endpoint_url(self):
        config = ServicesConfig()
        result = config.s3_endpoint_url()
        assert result.startswith("https://")
        assert "s3.ailab.infocepo.com" in result

    def test_chroma_port(self):
        config = ServicesConfig()
        assert config.chroma_port() == 443


class TestCredentials:
    def test_load_from_env(self):
        with patch.dict(os.environ, {"INFOCEPO_API_KEY": "test-key"}):
            creds = Credentials()
            creds.load()
            assert creds.api_key == "test-key"

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"api_key": "file-key", "chroma_token": "c-token"}, f)
            path = f.name
        try:
            creds = Credentials()
            creds.load(path)
            assert creds.api_key == "file-key"
            assert creds.chroma_token == "c-token"
        finally:
            os.unlink(path)

    def test_registry_user_default(self):
        creds = Credentials()
        creds.load()
        assert creds.registry_user == "user"


class TestConfig:
    def test_singleton(self):
        c1 = Config()
        c2 = Config()
        assert c1 is c2

    def test_get_llm_api_key_raises_without_key(self):
        c = Config()
        c.creds.api_key = None
        with pytest.raises(ValueError, match="INFOCEPO_API_KEY"):
            c.get_llm_api_key()

    def test_get_headers(self):
        c = Config()
        c.creds.api_key = "test-key"
        c.creds.registry_user = "admin"
        c.creds.registry_password = "pass"

        headers = c.get_headers("api")
        assert "accept" in headers
        assert "Bearer test-key" in headers["Authorization"]

        headers = c.get_headers("registry")
        assert "Basic" in headers["Authorization"]
