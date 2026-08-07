# Rapport de Déploiement - MCP Server systemd + K8s

**Date:** 2026-08-06  
**Repo:** https://github.com/ynotopec/infocepo-infra-mcp  
**Serveur:** https://mcp.ailab.infocepo.com  
**Dashboard OWUI:** https://chat.infocepo.com

---

## 1. Problème Initial

Erreur de connexion MCP dans OpenWebUI :
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
  ├── EndpointSlice (infocepo-mcp-external) → 10.0.1.1:8085
  ├── Service (infocepo-mcp-external)
  └── Ingress (infocepo-mcp-external-ingress)
       └── mcp.ailab.infocepo.com → 10.10.0.128

Flow : Client → mcp.ailab.infocepo.com → 10.10.0.128 → 10.0.1.1:8085
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
   Active: active (running) since Thu 2026-08-06 19:06:27 CEST
   Main PID: 3022 (python3)
   Memory: ~53M (peak: 54M)
   └─3022 /usr/bin/python3 /home/ai-agent/work/infocepo-infra-mcp/src/infocepo_mcp/sse_server.py
```

### 3.3 Tests de Validation

| Endpoint | Résultat | Détail |
|----------|----------|--------|
| `GET /health` | ✅ 200 | `{"status":"ok","server":"infocepo-infra-mcp","version":"0.1.0","tools":19}` |
| `GET /openapi.json` | ✅ 200 | OpenAPI spec avec 19 tools |
| `OPTIONS /openapi.json` | ✅ 200 | CORS headers (`Access-Control-Allow-Origin: *`) |
| `GET /sse` | ✅ 200 | SSE connecte correctement (`event: endpoint`) |

### 3.4 Connectivité Réseau

| Test | Résultat |
|------|----------|
| Pod K8s → 10.0.1.1:8085 (loopback microk8s) | ✅ 200 OK |
| Pod K8s → 192.168.1.149:8085 (IP externe) | ✅ 200 OK |
| HTTPS mcp.ailab.infocepo.com | ✅ 200 OK |

---

## 4. Resources K8s Déployées

### 4.1 EndpointSlice

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
      - "10.0.1.1"
    conditions:
      ready: true
      serving: true
      terminating: false
ports:
  - name: http
    port: 8085
    protocol: TCP
```

**Commande d'application :**
```bash
kubectl apply -f k8s/mcp-external-endpointslice.yaml
```

**Statut actuel :**
- Adresse : `10.0.1.1` (loopback microk8s - le noeud K8s et le host sont sur la même machine)
- Port : `8085`
- Conditions : ready=true, serving=true

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

**Commande d'application :**
```bash
kubectl -n demo1 apply -f k8s/mcp-svc.yaml
```

**Statut actuel :**
- ClusterIP : `10.152.183.104`
- ExternalIPs : `192.168.1.149`
- Port : `8085/TCP`

### 4.3 Ingress

**Fichier :** `k8s/mcp-ext-ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: infocepo-mcp-external-ingress
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

**Commande d'application :**
```bash
kubectl -n demo1 apply -f k8s/mcp-ext-ingress.yaml
```

**Statut actuel :**
- IngressClass : `public`
- LoadBalancer IP : `10.10.0.128`
- Backend : `infocepo-mcp-external:8085`
- TLS : cert-manager via `letsencrypt-prod`

---

## 5. Configuration OpenWebUI

### 5.1 Connexion MCP

**URL SSE :** `https://mcp.ailab.infocepo.com/sse`  
**URL OpenAPI :** `https://mcp.ailab.infocepo.com/openapi.json`

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
kubectl -n demo1 exec <pod-name> -- ping -c 2 10.0.1.1

# Port test
kubectl -n demo1 exec <pod-name> -- bash -c 'echo > /dev/tcp/10.0.1.1/8085 && echo "OPEN" || echo "CLOSED"'

# HTTP from pod
kubectl -n demo1 exec <pod-name> -- curl -sS http://10.0.1.1:8085/health

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
ip route show 10.0.1.0/24
```

---

## 7. Checklist de Déploiement

- [x] ✅ Code source corrigé (`sse_server.py` - CORS, OpenAPI, SSE, MCP v2)
- [x] ✅ Code commité et pushé sur GitHub
- [x] ✅ Service systemd créé et actif
- [x] ✅ Serveur testé localement (health, openapi, options, sse)
- [x] ✅ EndpointSlice créé et déployé (10.0.1.1:8085)
- [x] ✅ Service créé et déployé (ClusterIP: 10.152.183.104)
- [x] ✅ Ingress créé et déployé (mcp.ailab.infocepo.com → 10.10.0.128)
- [x] ✅ Connectivité Ingress → Service → EndpointSlice → systemd MCP
- [x] ✅ HTTPS fonctionnel avec cert-manager TLS
- [x] ✅ CORS OPTIONS préflight fonctionnel
- [x] ✅ SSE connecte correctement
- [ ] ⏳ OWUI configuré avec URL SSE (à faire manuellement)
- [ ] ⏳ Test de bout en bout : client → OWUI → MCP (à faire manuellement)

---

## 8. Architecture Finale

```
Client HTTPS
    ↓
mcp.ailab.infocepo.com
    ↓
Nginx Ingress (10.10.0.128)
    ↓
Service ClusterIP (10.152.183.104:8085)
    ↓
EndpointSlice (10.0.1.1:8085)
    ↓
systemd MCP (port 8085) → 19 tools disponibles
```

### Points Clés
- Le noeud K8s et le host sont sur la même machine physique (`192.168.1.149`)
- L'EndpointSlice pointe vers `10.0.1.1` (loopback microk8s) pour un accès direct
- Pas de NAT ni de port forwarding nécessaire
- Le service systemd est géré en `--user` (pas de privilèges root pour le déploiement)

---

## 9. Prochaines Étapes

### Priorité 1 : Configuration OWUI
1. Se connecter sur https://chat.infocepo.com/admin/users/overview
2. Section "External Tools" → "MCP Servers"
3. Ajouter : `https://mcp.ailab.infocepo.com/sse`
4. Sauvegarder

### Priorité 2 : Test de bout en bout
1. Ouvrir un chat dans OWUI
2. Taper une commande utilisant un des 19 tools
3. Vérifier la réponse

### Priorité 3 : Monitoring
- Surveiller les logs systemd : `journalctl --user -u infocepo-mcp.service -f`
- Surveiller les logs Ingress : `kubectl -n ingress-nginx logs -l app.kubernetes.io/name=ingress-nginx`
- Surveiller les health checks : `curl -sS https://mcp.ailab.infocepo.com/health`

---

**Fin du rapport**
