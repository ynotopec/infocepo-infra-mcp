# infocepo-infra-mcp

MCP server qui expose l'infrastructure infocepo.com comme outils MCP standard.

## Installation

```bash
cd infocepo-infra-mcp
pip install -e .
```

## Configuration

Créer `~/.infocepo-credentials` :

```yaml
api_key: sk-REEL_TOKEN  # Token LLM/STT/TTS/T2I/Embeddings/Summary/Diarization
chroma_token: CHROMA_TOKEN  # Pour ChromaDB (distinct)
s3_access_key: AKIA...  # Pour S3
s3_secret_key: secret_key_here
registry_user: user
registry_password: REG_PASSWORD
```

Variables d'environnement :

```bash
export INFOCEPO_API_KEY=sk-...
export INFOCEPO_ENV=prod  # ou lab, dev
```

## Configuration MCP client

Pour Claude Desktop / Hermes / tout client MCP :

```json
{
  "mcpServers": {
    "infocepo": {
      "command": "python",
      "args": ["-m", "infocepo_mcp.server"],
      "env": {
        "INFOCEPO_API_KEY": "sk-...",
        "INFOCEPO_ENV": "prod"
      }
    }
  }
}
```

## Outils disponibles

| Tool | Description |
|------|-------------|
| `llm_chat` | Chat completions OpenAI-compatible |
| `llm_vision` | OCR / VLM (ai-vision model) |
| `stt_transcribe` | Transcription audio |
| `tts_speech` | Synthèse vocale |
| `image_generate` | Génération d'images |
| `embeddings_create` | Text embeddings (bge-m3) |
| `chromadb_collections` | Lister collections ChromaDB |
| `chromadb_search` | Recherche vectorielle |
| `chromadb_upsert` | Upsert documents |
| `summary_text` | Résumé de textes |
| `diarize_audio` | Segmentation locuteurs |
| `registry_list` | Lister Docker registry |
| `registry_pull` | Pull image |
| `s3_list` | Lister bucket S3 |
| `s3_upload` | Upload S3 |
| `s3_download` | Download S3 |
| `infra_list_services` | Lister services découverts |
| `infra_refresh_discovery` | Re-fetch wiki |
| `infra_read_wiki` | Lire page wiki |
| `infra_parse_wiki` | Parse page wiki |

## Test

```bash
python -m pytest tests/ -v
```
