# Plan: Déployer infocepo-infra-mcp sur Open WebUI en mode systemd

## Objectif
Installer le serveur MCP `infocepo-infra-mcp` sur Open WebUI (chat.infocepo.com) en mode systemd user avec un port libre (8085).

## Étape 1: Activer le service systemd
- `systemctl --user daemon-reload`
- `systemctl --user enable infocepo-infra-mcp.service`
- `systemctl --user start infocepo-infra-mcp.service`
- Vérifier: `systemctl --user status infocepo-infra-mcp.service`

## Étape 2: Vérifier le serveur MCP
- Tester le health endpoint: `curl http://localhost:8085/health`
- Vérifier les logs: `journalctl --user -u infocepo-infra-mcp -n 20`

## Étape 3: Configurer Open WebUI
- Accéder à l'interface OWUI
- Aller dans Settings → MCP Configuration
- Ajouter un nouveau serveur MCP avec:
  - Name: `infocepo-infra`
  - URL: `http://localhost:8085` (ou l'IP du serveur)
  - Transport: SSE
- Sauvegarder et vérifier que les outils apparaissent

## Étape 4: Tester l'intégration
- Dans OWUI, vérifier que les 19 outils MCP sont visibles
- Tester un appel simple (ex: `infra_list_services`)
- Valider la réponse

## Risques et vérifications
- S'assurer que le port 8085 est libre avant de démarrer
- Vérifier que OWUI peut joindre le MCP server (même machine)
- Vérifier les logs si échec de connexion OWUI → MCP
