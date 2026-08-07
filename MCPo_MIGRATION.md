# =============================================================================
# Infocepo MCP — mcpo Migration
# =============================================================================
#
# Migration de l'architecture custom SSE → mcpo (open-webui/mcpo)
#
# ─── Architecture ──────────────────────────────────────────────────────────────
#
#   MCP Server (systemd, port 8085)
#     ↓ SSE (mcp.ailab.infocepo.com/sse)
#   mcpo (proxy, port 8000)
#     ↓ OpenAPI (mcpo:8000) + docs Swagger à /docs
#   Open WebUI → Settings → Tools → Add OpenAPI Server
#     → URL: http://mcpo:8000 (ou https://mcpo.internal/openapi.json)
#
# ─── Pourquoi mcpo ? ─────────────────────────────────────────────────────────
#
#   • Officiellement recommandé par Open WebUI (GitHub open-webui/mcpo, 4.3k⭐)
#   • Expose l'OpenAPI spec auto-générée (compat OWUI natif)
#   • Support SSE, stdio, streamable-http
#   • --api-key pour auth, --hot-reload pour config, multi-MCP servers
#   • Docker image officielle: ghcr.io/open-webui/mcpo:main
#   • License MIT, communauté active, 15 tags/stable releases
#
# ─── Avant (custom) ──────────────────────────────────────────────────────────
#
#   MCP Server → custom SSE → openapi.json manuel → CORS manual → OPTIONS bug
#   OWUI ne connectait pas car il attendait de l'OpenAPI, pas du MCP SSE
#
# ─── Après (mcpo) ────────────────────────────────────────────────────────────
#
#   MCP Server → mcpo (proxy officiel) → OpenAPI auto-généré → OWUI OK ✅
#
# =============================================================================
