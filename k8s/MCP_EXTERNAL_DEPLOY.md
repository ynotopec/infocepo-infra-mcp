# ============================================================
# Deployment du MCP Server via systemd
# ============================================================
#
# Architecture finale:
#   Machine Host (192.168.1.149)
#     └── systemd service (infocepo-mcp.service)
#          └── Port 8085 (CORS ✅, OpenAPI ✅, SSE ✅)
#
#   Kubernetes Cluster (demo1)
#     ├── EndpointSlice (infocepo-mcp-external) → 192.168.1.149:8085
#     ├── Service (infocepo-mcp-external)
#     └── Ingress (infocepo-mcp-ext-ingress)
#          └── mcp.ailab.infocepo.com → 10.10.0.128
#
# Flow: Client → mcp.ailab.infocepo.com → 10.10.0.128 → 192.168.1.149:8085
# ============================================================
