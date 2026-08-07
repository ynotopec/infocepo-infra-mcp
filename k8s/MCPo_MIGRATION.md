# =============================================================================
# K8s Deployment — mcpo pour infocepo-infra-mcp
# =============================================================================
#
# mcpo tourne dans un pod K8s et expose OpenAPI auto-généré.
#
# ─── Déploiement ──────────────────────────────────────────────────────────────
#
#   kubectl -n demo1 apply -f k8s/mcpo-deployment.yaml
#   kubectl -n demo1 apply -f k8s/mcpo-service.yaml
#   kubectl -n demo1 apply -f k8s/mcpo-ingress.yaml
#
# ─── Architecture finale ─────────────────────────────────────────────────────
#
#   MCP Server (systemd, host:8085)
#     ↓ SSE
#   mcpo Pod (K8s demo1, ClusterIP:8000)
#     ↓ OpenAPI auto-généré (Swagger OK)
#   Ingress → mcpo.infocepo.com/openapi.json
#     ↓
#   Open WebUI → Settings → Tools → Add OpenAPI Server
#     → URL: https://mcpo.infocepo.com/openapi.json
#
# =============================================================================
