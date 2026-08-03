# InfoCEPO MCP Server — Logs d'Avancement

**Déploiement** : K8s cluster `demo1` (demo1.ailab.infocepo.com)  
**Version** : 0.1.0  
**Dernière MAJ** : 2026-08-03

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         Nginx Ingress Controller (82.66.194.251)    │
│  Wildcard *.ailab.infocepo.com → Route vers K8s     │
└────────────────────────┬────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────┐
│              Kubernetes (demo1 ns)                  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Ingress: infocepo-mcp-ingress              │    │
│  │  Host: mcp.ailab.infocepo.com               │    │
│  │  Path: / (Prefix)                           │    │
│  │  TLS: mcp-ailab-tls (cert-manager)          │    │
│  └──────────────┬──────────────────────────────┘    │
│                 │                                   │
│  ┌──────────────▼──────────────────────────────┐    │
│  │  Service: infocepo-mcp-service              │    │
│  │  Port: 8085 → 8085                          │    │
│  │  Type: ClusterIP                            │    │
│  └──────────────┬──────────────────────────────┘    │
│                 │                                   │
│  ┌──────────────▼──────────────────────────────┐    │
│  │  Pod: infocepo-mcp-85b47665b9-zs5zm         │    │
│  │  SSE Server: :8085                           │    │
│  │  Tools: 19 (llm_chat, chromadb_search, ...)  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## Chronologie des Décisions

### 2026-08-03

**1. Initialisation du projet**
- Création du serveur MCP Python avec SSE transport
- 19 outils implémentés (llm_chat, chromadb_search, s3_upload, etc.)
- Serveur accessible en localhost:8085 ✅

**2. Déploiement K8s initial**
- Tentative de déploiement avec PVC → échoué (pas de StorageClass par défaut)
- Décision : utiliser ConfigMap + script `start.sh` (git clone + pip install au boot)
- Service ClusterIP créé (port 8085)

**3. Erreur SDK v2 -32602**
- Cause : incompatibilité de validation Pydantic dans `mcp/server/runner.py`
- Fix : patch injected via `start.sh` (exécuté après `pip install`)
- Fichier : `src/infocepo_mcp/_debug_patch.py`

**4. Bug SSE path**
- Cause : le path `/messages/` (avec slash) ne matchait pas le client SDK
- Fix : changement vers `/messages` (sans slash)
- Fichier modifié : `src/infocepo_mcp/sse_server.py`

**5. Bug wiki_fetcher**
- Cause : `TypeError: unhashable type: 'dict'` dans la déduplication des endpoints
- Fix : passage à une déduplication sur la clé URL string
- Fichier modifié : `src/infocepo_mcp/wiki_fetcher.py`

**6. Configuration Ingress**
- Décision initiale : paths séparés `/sse` et `/messages`
- Problème : le Nginx Ingress Controller à 82.66.194.251 rejetait les requêtes
- Décision de pivot : changer le path en `/` (Prefix) pour laisser le pod MCP faire le routage interne
- Résultat : ✅ SSE et POST sur `/messages` fonctionnent via l'URL publique

**7. Configuration OpenWebUI**
- Tentative de configuration via API REST `/api/v1/configs/tool_servers`
- Blocage : "Server storage is not writable"
- OpenWebUI hébergé hors-cluster (IP 82.66.194.251)
- Décision : configuration manuelle nécessaire (admin OpenWebUI)

---

## Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `src/infocepo_mcp/sse_server.py` | Serveur MCP principal (SSE transport, routing, tools) |
| `src/infocepo_mcp/wiki_fetcher.py` | Fetcher wiki MediaWiki (dépub+endpoints) |
| `src/infocepo_mcp/_debug_patch.py` | Patch SDK v2 pour compatibilité Pydantic |
| `start.sh` | Script de boot (git clone, pip install, apply patch, start server) |
| `src/infocepo_mcp/tools/` | Tous les outils MCP (19 fichiers) |

## Manifestes K8s (dans /tmp/ à la volée)

| Fichier | Description |
|---------|-------------|
| `infocepo-mcp-deploy.yaml` | Deployment avec ConfigMap + start.sh |
| `infocepo-mcp-service.yaml` | Service ClusterIP port 8085 |
| `infocepo-mcp-ingress-v7.yaml` | Ingress avec path `/` (state actuelle) |
| `infocepo-mcp-secrets.yaml` | Secrets (ChromaDB, etc.) |

---

## Statut Actuel

| Composant | État | Notes |
|-----------|------|-------|
| Pod K8s | ✅ Running | 1/1, code patché actif |
| Service | ✅ ClusterIP:8085 | Endpoints: 10.1.31.128 |
| Ingress | ✅ Path `/` Prefix | Nginx Ingress Controller external |
| TLS | ✅ Ready | cert-manager, Let's Encrypt |
| SSE endpoint | ✅ Fonctionnel | Retourne session_id |
| POST /messages | ✅ Fonctionnel | session_id nécessaire |
| 19 Outils MCP | ✅ Listés | health check OK |
| OpenWebUI MCP config | ❌ Bloqué | "Server storage not writable" |
| chromadb_search | ⚠️ Partiel | INFOCEPO_CHROMA_TOKEN manquant |

---

## Procédures de Dépannage

### SSE ne retourne pas de session_id
1. Vérifier que le pod tourne : `kubectl get pods -n demo1 -l app=infocepo-mcp`
2. Vérifier les logs : `kubectl logs -n demo1 deployment/infocepo-mcp --tail=50`
3. Tester en interne : `kubectl exec ... -- curl localhost:8085/sse`

### POST /messages renvoie "Invalid session ID"
- Le session_id doit venir de la réponse SSE (`event: endpoint`)
- Il est passé en query string : `POST /messages?session_id=XXX`
- Le serveur doit être initialisé (`initialize` method) avant tout call

### Ingress 404 depuis l'extérieur
- Vérifier que le Nginx Ingress Controller connaît le VirtualHost
- Tester avec curl `-k -m 5 -D - https://mcp.ailab.infocepo.com/sse`
- Vérifier les logs Nginx si accès admin

### Erreur -32602 (validation Pydantic)
- Le patch `_debug_patch.py` est appliqué automatiquement via `start.sh`
- Si le pod redémarre, le patch se réapplique
- Vérifier : `kubectl exec ... -- python3 -c "import mcp.server.runner"`

---

## Conventions

- **Nommage K8s** : `infocepo-mcp-*` (deployment, service, ingress, secret)
- **Namespace** : `demo1` (cluster demo1.ailab.infocepo.com)
- **IngressClass** : `public` (Nginx Ingress Controller à 82.66.194.251)
- **TLS** : cert-manager avec issuer `letsencrypt-prod`
- **Health check** : endpoint interne `/health` (pas standard MCP)
- **SSE transport** : spec MCP SSE standard (session_id dans query string)
