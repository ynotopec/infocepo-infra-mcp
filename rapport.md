# Rapport : MCP Server infocepo-infra

## Objectif

Construire un MCP server qui permet à un agent IA d'exploiter l'infrastructure infocepo.com documentée dans le wiki (Main_Page). Le wiki n'est pas un simple catalogue de documentation — c'est un **registre de services fonctionnels** que le MCP expose comme outils.

---

## Analyse de l'infrastructure

Le wiki Main_Page documente **12 services API distincts** :

| # | Service | Endpoint | Modèle/Engine | Catégorie |
|---|---------|----------|---------------|-----------|
| 1 | **LLM** | `api-nothink.ailab.infocepo.com/v1` | qwen3.6, bge-m3, whisper, OmniVoice, OpenDalle | Gen, RAG, OCR |
| 2 | **STT** | `api-audio2txt.ailab.infocepo.com/v1` | whisper-1 | Transcription |
| 3 | **TTS** | `api-tts-omnivoice.ailab.infocepo.com/v1` | gpt-4o-mini-tts | Synthèse vocale |
| 4 | **Text-to-Image** | `api-txt2image.ailab.infocepo.com/v1` | OpenDalle | Génération images |
| 5 | **Image-to-Text** | `api-nothink.ailab.infocepo.com/v1` (model=ai-vision) | VLM | OCR/Vision |
| 6 | **Embeddings** | `api-embedding.ailab.infocepo.com/v1` | bge-m3 | RAG vector |
| 7 | **ChromaDB** | `chromadb.ailab.infocepo.com` / `chromadb.c1.ailab.infocepo.com` | ChromaDB | Base vecteurs |
| 8 | **Summary** | `api-summary.ailab.infocepo.com:wait-2026-12` | — | Résumé texte |
| 9 | **Diarization** | `api-diarization.ailab.infocepo.com` | — | Segmentation locuteurs |
| 10 | **Realtime AI** | `api-realtime-ai.ailab.infocepo.com:wait-2026-12/v1` | — | WebSocket/WebRTC |
| 11 | **Registry** | `registry.ailab.infocepo.com:wait-2026-09` | Docker Registry | Images container |
| 12 | **S3 Storage** | `s3.ailab.infocepo.com:wait-2026-09` | S3-compatible | Stockage objets |

Observabilité : Grafana, Uptime-Kuma, Web-Stat, LLM-Stat.

Environnements :
- **PROD** : endpoints publics `*.ailab.infocepo.com`
- **LAB** : `chromadb.c1.ailab.infocepo.com`, `datalab.ailab.infocepo.com`

---

## Architecture du MCP Server

### Design

```
┌─────────────────────────────────────────────────┐
│  MCP Client (Claude, VS Code, WebUI, etc.)      │
│  Tool-use: llm_chat(), stt_transcribe(), tts()  │
└──────────┬──────────────────────────────────────┘
           │ JSON-RPC over stdio
           ▼
┌─────────────────────────────────────────────────┐
│  MCP Server (infocepo_mcp)                       │
│                                                  │
│  ┌─────────────┐  ┌───────────────────────────┐ │
│  │ Wiki Fetcher │  │  Config / Secrets Manager  │ │
│  │ (auto-discover│  │ (env, tokens, credentials) │ │
│  │  endpoints)  │  │                            │ │
│  └─────────────┘  └───────────────────────────┘ │
│                          │                       │
│  ┌──────────────────────┼────────────────────┐  │
│  │      Tool Handlers (per service)          │  │
│  │  ┌────────────┐  ┌────────────────────┐  │  │
│  │  │ LLM Tool   │  │ STT Tool           │  │  │
│  │  │ TTS Tool   │  │ Vision Tool        │  │  │
│  │  │ Embed Tool │  │ ChromaDB Tool      │  │  │
│  │  │ ...        │  │ ...                │  │  │
│  │  └────────────┘  └────────────────────┘  │  │
│  └──────────────────────────────────────────┘  │
│                          │                       │
│  ┌──────────────────────┼────────────────────┐  │
│  │    Cache & Discovery                           │
│  │  - Wiki content cached (TTL 1h)              │
│  │  - Endpoint auto-discovery on startup        │
│  │  - Manual override via config                │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Auto-discovery

Le MCP server lit `Main_Page` via MediaWiki API au démarrage :
1. Parse le tableau "Catalogue rapide des services" → extract endpoints
2. Parse les sections API → extract tokens, models, configs
3. Expose la liste des services comme meta-tool `infra_list_services()`
4. Permet de forcer un refresh via `infra_refresh_discovery()`

### Configuration

- **env** param : `"prod"` (default), `"lab"`, `"dev"` → pointe vers les endpoints appropriés
- **Secrets** : via `INFOCEPO_API_KEY` env var, ou fichier `~/.infocepo-credentials`
- **Override** : `infocepo-config.yaml` pour forcer des endpoints custom

---

## Outils MCP Exposés

| Outil | Service | Description |
|-------|---------|-------------|
| `llm_chat` | LLM | Chat completions (OpenAI-compatible) |
| `llm_chat_stream` | LLM | Streaming chat completions |
| `llm_vision` | Image-to-Text | OCR / VLM via ai-vision model |
| `stt_transcribe` | STT | Transcription audio → texte |
| `tts_speech` | TTS | Texte → audio (opus/wav) |
| `image_generate` | Text-to-Image | Prompt → image |
| `embeddings_create` | Embeddings | Textes → vecteurs bge-m3 |
| `chromadb_collections` | ChromaDB | Lister/rechercher dans collections |
| `chromadb_upsert` | ChromaDB | Ajouter des documents vectorisés |
| `chromadb_search` | ChromaDB | Recherche vectorielle |
| `summary_text` | Summary | Résumé de longs textes |
| `diarize_audio` | Diarization | Segmentation locuteurs audio |
| `registry_list` | Registry | Lister images Docker |
| `registry_pull` | Registry | Pull image from registry |
| `s3_list` | S3 | Lister bucket |
| `s3_upload` | S3 | Upload fichier |
| `s3_download` | S3 | Download fichier |
| `infra_list_services` | Meta | Lister tous les services découverts |
| `infra_refresh_discovery` | Meta | Re-fetch wiki et redécouvrir |
| `infra_read_wiki` | Wiki | Lire/extraire une page wiki |
| `infra_parse_wiki` | Wiki | Parse et structurer le wiki |

---

## Fichiers du Projet

```
infocepo-infra-mcp/
├── rapport.md              # Ce fichier
├── pyproject.toml          # Package config
├── README.md               # Usage doc
├── src/
│   └── infocepo_mcp/
│       ├── __init__.py
│       ├── server.py       # MCP server main
│       ├── wiki_fetcher.py # Auto-discovery from wiki
│       ├── services.py     # Service handlers (LLM, STT, etc.)
│       ├── config.py       # Config management
│       └── tools.py        # MCP tool definitions
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_wiki_fetcher.py
│   └── test_services.py
└── .git/                   # Versionné
```

---

## Défis Identifiés

1. **Tokens masqués** : Le wiki affiche `sk-XXXXX` — les vrais tokens ne sont pas dans le wiki public. Le MCP doit lire depuis un fichier de credentials séparé.

2. **`wait-2026-12` annotations** : Les endpoints contiennent des marqueurs de timeout (`:wait-2026-12`) qui doivent être retirés avant les appels HTTP. C'est un artefact du wiki, pas de l'URL réelle.

3. **Realtime AI = WebSocket** : L'API Realtime utilise WSS, pas HTTP. Le MCP handler doit gérer les connexions WebSocket (via `websockets` library).

4. **ChromaDB auth** : Utilise `chromadb.auth.token.TokenAuthClientProvider` — nécessite un token spécifique, pas l'API key standard.

5. **S3 auth** : Nécessite access_key et secret_key séparés, pas l'API key standard.

6. **Registry auth** : Docker basic auth (`user:XXXXX`), pas Bearer token.

7. **Auto-discovery limitée** : Le wiki est un snapshot. Les endpoints changent. L'auto-discovery est une bonne default mais doit être overrideable.

---

## Roadmap

1. **Phase 1** (ce build) : MCP server avec core tools (LLM, STT, TTS, Vision, Embed, ChromaDB, Summary, Diarization)
2. **Phase 2** : Registry + S3 + Realtime + Wiki tools
3. **Phase 3** : Auto-discovery from wiki (parse Main_Page)
4. **Phase 4** : Multi-env support (prod/lab/dev) with auto-switching
