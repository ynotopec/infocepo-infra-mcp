# Plan: Déployer infocepo-infra-mcp sur Open WebUI

## Étape 1: Activer le service systemd user
1. `systemctl --user daemon-reload`
2. `systemctl --user enable infocepo-infra-mcp.service`
3. `systemctl --user start infocepo-infra-mcp.service`
4. Vérifier: `systemctl --user status infocepo-infra-mcp.service`

## Étape 2: Vérifier le serveur MCP
1. Health: `curl http://localhost:8085/health`
2. Logs: `journalctl --user -u infocepo-infra-mcp -n 20`
3. Attendre 200 OK avec 19 outils

## Étape 3: Configurer Open WebUI
1. Accéder à https://chat.infocepo.com
2. Settings → MCP Configuration
3. Ajouter serveur:
   - Name: `infocepo-infra`
   - URL: `http://localhost:8085/sse`
   - Transport: `SSE`
4. Sauvegarder

## Étape 4: Vérifier les outils
1. Ouvrir une conversation OWUI
2. Vérifier les 19 outils disponibles
3. Tester `infra_list_services` ou `registry_list`
4. Valider la réponse

## Étape 5: Résoudre les problèmes
1. `curl http://localhost:8085/health`
2. `journalctl --user -u infocepo-infra-mcp -f`
3. `systemctl --user restart infocepo-infra-mcp`
