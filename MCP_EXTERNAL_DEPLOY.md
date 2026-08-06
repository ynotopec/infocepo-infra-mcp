# Infocepo MCP Server - Hosted via systemd on the host machine
# This replaces the previous K8s Deployment approach
#
# Architecture:
#   1. MCP server runs as a systemd user service on the host (192.168.1.149)
#   2. K8s Ingress routes mcp.ailab.infocepo.com -> host:8085
#   3. CORS OPTIONS are handled properly for OpenWebUI External Tools

## Files:
# - src/infocepo_mcp/sse_server.py        → MCP server with CORS + OpenAPI + SSE
# - k8s/mcp-ext-ingress.yaml              → Ingress pointing to external service
# - .config/systemd/user/infocepo-mcp.service  → systemd user service
