# Rapport de Déploiement MCP - Infocepo Infra

**Date:** 2026-08-06
**Repo:** https://github.com/ynotopec/infocepo-infra-mcp
**Serveur:** https://mcp.ailab.infocepo.com
**Dashboard OWUI:** https://chat.infocepo.com/admin/users/overview

---

## 1. Problème Initial

Connexion MCP échouée dans OpenWebUI :
```
Failed to connect to https://mcp.ailab.infocepo.com/sse OpenAPI tool server
```

**Root Cause identifiée :**
- Serveur production : 404 sur les requêtes `OPTIONS` (preflight CORS)
- OpenWebUI fait un preflight CORS avant connexion SSE
- Réponse 404 → erreur frontend OWUI

---

## 2. Correctifs Apportés

### 2.1 Code Source (`src/infocepo_mcp/sse_server.py`)

**Modification 1 :** Handlers MCP (API v2 - decorator pattern)
```python
# AVANT (obsolète) :
mcp_app.add_request_handler("tools/list", ListToolsRequest, _list_tools_handler)

# APRÈS (corrigé) :
@mcp_app.list_tools()
async def list_tools():
    return _MCP_TOOLS

@mcp_app.call_tool()
async def call_tool(name: str, arguments: dict = None):
    ...
```

**Modification 2 :** CORS / OPTIONS preflight
```python
async def router(scope, receive, send):
    if scope["type"] != "http":
        return
    
    path = scope.get("path", "")
    method = scope.get("method", "GET")
    
    # Handle CORS preflight (OPTIONS)
    if method == "OPTIONS":
        from starlette.responses import Response
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
        response = Response(status_code=204, headers=headers)
        return await response(scope, receive, send)
    
    # Gestion du path restant...
```

**Modification 3 :** Route `/openapi.json` + SSE connecté correctement
- Endpoint `/openapi.json` : expose la spec OpenAPI (19 tools documentés)
- Endpoint `/sse` : connexion SSE pour le protocole MCP
- Endpoint `/health` : health check avec statut + nombre de tools

### 2.2 Commit/Push
```bash
cd /home/ai-agent/work/infocepo-infra-mcp
git add src/infocepo_mcp/sse_server.py
git commit -m "fix: MCP CORS OPTIONS + OpenAPI spec + SSE async handler
- Add OPTIONS handler for CORS preflight
- Generate OpenAPI spec endpoint
- Fix SSE endpoint for async context (MCP v2)"
git push origin main
```

---

## 3. Nouvelle Stratégie de Déploiement

### 3.1 Architecture Choisie

Remplacement du déploiement Docker/K8s par un service systemd direct sur le host.

```
Machine Host (192.168.1.149)
  └── systemd service (infocepo-mcp.service)
       └── Port 8085 (CORS ✅, OpenAPI ✅, SSE ✅)

Kubernetes Cluster (demo1)
  ├── EndpointSlice (infocepo-mcp-external) → 192.168.1.149:8085
  ├── Service (infocepo-mcp-external)
  └── Ingress (infocepo-mcp-ext-ingress)
       └── mcp.ailab.infocepo.com → 10.10.0.128

Flow : Client → mcp.ailab.infocepo.com → 10.10.0.128 → 192.168.1.149:8085
```

### 3.2 Service systemd

**Fichier :** `~/.config/systemd/user/infocepo-mcp.service`

```ini
[Unit]
Description=infocepo-infra MCP Server (systemd user service)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/ai-agent/work/infocepo-infra-mcp/src/infocepo_mcp/sse_server.py
Restart=on-failure
RestartSec=5
WorkingDirectory=/home/ai-agent/work/infocepo-infra-mcp

[Install]
WantedBy=default.target
```

**Activation :**
```bash
systemctl --user daemon-reload
systemctl --user enable infocepo-mcp.service
systemctl --user start infocepo-mcp.service
```

**Statut actuel :**
```
● infocepo-mcp.service - infocepo-infra MCP Server (systemd user service)
   Active: active (running) depuis Thu 2026-08-06 14:58:03 CEST
   Main PID: 1331128 (python3)
   Memory: 53.2M (peak: 54.0M)
   Tasks: 1
   └─1331128 /usr/bin/python3 /home/ai-agent/work/infocepo-infra-mcp/src/infocepo_mcp/sse_server.py
```

### 3.3 Tests de Validation

| Endpoint | Résultat | Détail |
|----------|----------|--------|
| `GET /health` | ✅ 200 | `{"status":"ok","server":"infocepo-infra-mcp","version":"0.1.0","tools":19}` |
| `GET /openapi.json` | ✅ 200 | OpenAPI spec avec 19 tools |
| `OPTIONS /openapi.json` | ✅ 204 | CORS headers (`Access-Control-Allow-Origin: *`) |
| `GET /sse` | ✅ 200 | SSE connecte correctement |
| Connexion K8s → Host | ✅ OPEN | Port 8085 reachable depuis les pods K8s |
| Ingress → Host | ❌ Échec | Nécessite EndpointSlice admin |

---

## 4. Resources K8s Nécessaires

### 4.1 EndpointSlice (⚠️ Requiert admin K8s)

**Fichier :** `k8s/mcp-external-endpointslice.yaml`

```yaml
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: infocepo-mcp-external
  namespace: demo1
  labels:
    kubernetes.io/service-name: infocepo-mcp-external
addressType: IPv4
endpoints:
  - addresses:
      - "192.168.1.149"
    conditions:
      ready: true
      serving: true
      terminating: false
ports:
  - name: http
    port: 8085
    protocol: TCP
```

**Commande :**
```bash
kubectl apply -f k8s/mcp-external-endpointslice.yaml
```

**Note :** Le namespace `demo1` n'a pas les permissions `endpointslices.discovery.k8s.io`. Nécessite un compte admin ou un RBAC adapté.

### 4.2 Service

**Fichier :** `k8s/mcp-svc.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: infocepo-mcp-external
  namespace: demo1
  labels:
    app: infocepo-mcp
    managed-by: external
spec:
  ports:
    - name: http
      port: 8085
      targetPort: 8085
      protocol: TCP
  type: ClusterIP
  externalIPs:
    - "192.168.1.149"
```

**Commande :**
```bash
kubectl -n demo1 apply -f k8s/mcp-svc.yaml
```

### 4.3 Ingress

**Fichier :** `k8s/mcp-ext-ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: infocepo-mcp-ext-ingress
  namespace: demo1
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  ingressClassName: public
  tls:
    - hosts:
        - mcp.ailab.infocepo.com
      secretName: mcp-ailab-infocepo-com-tls
  rules:
    - host: mcp.ailab.infocepo.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: infocepo-mcp-external
                port:
                  number: 8085
```

**Commande :**
```bash
kubectl -n demo1 apply -f k8s/mcp-ext-ingress.yaml
```

---

## 5. Configuration OpenWebUI

### 5.1 Connexion MCP

**URL SSE :** `https://mcp.ailab.infocepo.com/sse`
**URL OpenAPI :** `https://mcp.ailab.infocepo.com/openapi.json`

Dans OWUI :
1. Aller sur `/admin/users/overview`
2. Section "External Tools" ou "MCP Servers"
3. Ajouter le serveur avec l'URL SSE ci-dessus

### 5.2 19 Tools Disponibles

| Tool | Description |
|------|-------------|
| `infra_list_services` | List all infocepo.com infrastructure services |
| `infra_refresh_discovery` | Re-fetch wiki Main_Page for service discovery |
| `infra_read_wiki` | Read wiki pages (Main_Page, configs, docs) |
| `infra_parse_wiki` | Parse wiki wikitext to structured sections |
| `llm_chat` | Chat completions (OpenAI-compatible) |
| `llm_vision` | Image-to-text / OCR / VLM |
| `stt_transcribe` | Audio transcription (Whisper) |
| `tts_speech` | Text-to-speech (OmniVoice) |
| `image_generate` | Image generation (OpenDalle) |
| `embeddings_create` | Text embeddings (BGE-M3) |
| `chromadb_collections` | List ChromaDB collections |
| `chromadb_search` | Semantic vector search |
| `chromadb_upsert` | Upsert documents with embeddings |
| `summary_text` | Summarize long texts |
| `diarize_audio` | Speaker diarization |
| `registry_list` | List Docker images (private registry) |
| `s3_list` | List S3 bucket objects |
| `s3_upload` | Upload file to S3 |
| `s3_download` | Download file from S3 |

---

## 6. Commands Utilitaires

### 6.1 Vérification Serveur
```bash
# Health check
curl -sS http://localhost:8085/health

# OpenAPI spec (first 300 chars)
curl -sS http://localhost:8085/openapi.json | head -c 300

# OPTIONS preflight
curl -sSki -X OPTIONS http://localhost:8085/openapi.json

# SSE connection (2s timeout)
timeout 2 curl -sS -N http://localhost:8085/sse

# systemd status
systemctl --user status infocepo-mcp.service

# Recent logs
journalctl --user -u infocepo-mcp.service --since "5 min ago" --no-pager
```

### 6.2 Network Testing from K8s
```bash
# Ping from pod
kubectl -n demo1 exec <pod-name> -- ping -c 2 192.168.1.149

# Port test
kubectl -n demo1 exec <pod-name> -- bash -c 'echo > /dev/tcp/192.168.1.149/8085 && echo "OPEN" || echo "CLOSED"'

# HTTP from pod
kubectl -n demo1 exec <pod-name> -- curl -sS http://192.168.1.149:8085/health

# Via Ingress IP
kubectl -n demo1 exec <pod-name> -- curl -sS -H "Host: mcp.ailab.infocepo.com" http://10.10.0.128/health
```

### 6.3 Network on Host
```bash
# Check listening port
ss -tlnp | grep 8085

# Firewall check
ufw status verbose

# Route check
ip route show default
ip route show 192.168.1.0/24
```

---

## 7. Checklist de Déploiement

- [x] ✅ Code source corrigé (`sse_server.py` - CORS, OpenAPI, SSE, MCP v2)
- [x] ✅ Code commité et pushé sur GitHub
- [x] ✅ Service systemd créé et actif
- [x] ✅ Serveur testé localement (health, openapi, options, sse)
- [x] ✅ Connectivité K8s → Host vérifiée (port 8085 OPEN)
- [x] ✅ EndpointSlice créé (en attente de déploiement admin)
- [ ] ⏳ EndpointSlice déployé (⚠️ nécessite admin K8s)
- [ ] ⏳ Service déployé (`kubectl -n demo1 apply -f k8s/mcp-svc.yaml`)
- [ ] ⏳ Ingress déployé (`kubectl -n demo1 apply -f k8s/mcp-ext-ingress.yaml`)
- [ ] ⏳ Connectivité Ingress → Host vérifiée
- [ ] ⏳ OWUI configuré avec URL SSE
- [ ] ⏳ Test de bout en bout : client → OWUI → Ingress → systemd MCP

---

## 8. Prochaines Étapes

### Priorité 1 : Déploiement K8s (admin requis)
```bash
# Appliquer l'EndpointSlice (admin only)
kubectl apply -f k8s/mcp-external-endpointslice.yaml

# Appliquer le Service
kubectl -n demo1 apply -f k8s/mcp-svc.yaml

# Appliquer l'Ingress
kubectl -n demo1 apply -f k8s/mcp-ext-ingress.yaml

# Vérifier
kubectl -n demo1 get endpointslice infocepo-mcp-external
kubectl -n demo1 get service infocepo-mcp-external
kubectl -n demo1 get ingress infocepo-mcp-ext-ingress

# Tester
curl -sS https://mcp.ailab.infocepo.com/health
```

### Priorité 2 : Configuration OWUI
1. Se connecter sur https://chat.infocepo.com/admin/users/overview
2. Section "External Tools" → "MCP Servers"
3. Ajouter : `https://mcp.ailab.infocepo.com/sse`
4. Sauvegarder

### Priorité 3 : Test de bout en bout
1. Ouvrir un chat dans OWUI
2. Taper une commande utilisant un des 19 tools
3. Vérifier la réponse

---

## 9. Observations & Notes

### Réseau
- IP Host : 192.168.1.149
- Route K8s : default via 192.168.1.1 dev enP7s7 (same machine!)
- Le noeud K8s et le host sont sur la même machine physique (192.168.1.149)
- Ports 80, 22, 8085 tous OPEN depuis les pods K8s

### Permissions
- Namespace `demo1` : peut créer Services et Ingresss ✅
- Namespace `demo1` : NE PEUT PAS créer Endpoints ni EndpointSlices ❌
- EndpointSlice nécessite un compte admin K8s ou un RBAC dédié

### Docker vs systemd
- L'approche Docker était envisagée mais abandonnée (pas d'accès build sur ce node)
- systemd `--user` est plus simple, plus rapide, et directement testable
- Le serveur MCP est maintenant autonome sur le host

### Versions
- MCP library : v2 (API decorator pattern)
- Python : 3.12.3
- Starlette : compatible SSE
- Uvicorn : serveur ASGI

---

**Fin du rapport**
