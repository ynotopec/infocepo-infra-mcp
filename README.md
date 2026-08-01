# infocepo-infra-mcp

MCP server qui expose l'infrastructure infocepo.com comme outils MCP standard.

## Installation

```bash
cd infocepo-infra-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Créer `~/.infocepo-credentials` (format JSON) :

```json
{
  "api_key": "sk-...",
  "chroma_token": "CHROMA_TOKEN",
  "s3_access_key": "AKIA...",
  "s3_secret_key": "secret_key_here",
  "registry_user": "user",
  "registry_password": "REG_PASSWORD"
}
```

Variables d'environnement (alternative au fichier) :

```bash
export INFOCEPO_API_KEY=sk-...
export INFOCEPO_CHROMA_TOKEN=...
export INFOCEPO_S3_ACCESS_KEY=AKIA...
export INFOCEPO_S3_SECRET_KEY=...
export INFOCEPO_REGISTRY_PASSWORD=...
export INFOCEPO_CREDENTIALS_FILE=/path/to/credentials.json
```

## Configuration MCP client

Pour Hermes (config.yaml), utiliser le wrapper `run-server.sh` :

```yaml
mcp_servers:
  infocepo-infra:
    command: /path/to/infocepo-infra-mcp/run-server.sh
    env: {}
    timeout: 60
```

Le script lit la clé API depuis `~/.infocepo-credentials` puis via la variable `INFOCEPO_API_KEY`.

## Outils disponibles

### Services API

| Tool | Description |
|------|-------------|
| `llm_chat` | Chat completions OpenAI-compatible (ai-default, ai-thinking, ai-fast, etc.) |
| `llm_vision` | OCR / VLM — image (URL ou base64) → description |
| `stt_transcribe` | Transcription audio → texte (whisper-1) |
| `tts_speech` | Synthèse vocale texte → audio (opus/wav/mp3) |
| `image_generate` | Génération d'images (OpenDalle) |
| `embeddings_create` | Text embeddings (bge-m3) pour RAG/search |
| `summary_text` | Résumé de longs textes |
| `diarize_audio` | Segmentation locuteurs audio |

### ChromaDB

| Tool | Description |
|------|-------------|
| `chromadb_collections` | Lister collections |
| `chromadb_search` | Recherche vectorielle (auto-embed) |
| `chromadb_upsert` | Ajouter des documents vectorisés |

### Registry & S3

| Tool | Description |
|------|-------------|
| `registry_list` | Lister images Docker du registry privé |
| `s3_list` | Lister objets dans un bucket S3 |
| `s3_upload` | Upload fichier vers S3 |
| `s3_download` | Download fichier depuis S3 |

### Discovery (auto-wiki)

| Tool | Description |
|------|-------------|
| `infra_list_services` | Lister tous les services découverts |
| `infra_refresh_discovery` | Re-fetch wiki et redécouvrir |
| `infra_read_wiki` | Lire une page wiki |
| `infra_parse_wiki` | Parser une page wiki en sections structurées |

## Test

```bash
python -m pytest tests/ -v        # Tests unitaires
TEST_LIVE=1 python -m pytest tests/ -v  # Tests live (nécessite réseau)
```
