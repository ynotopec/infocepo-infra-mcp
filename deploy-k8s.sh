#!/usr/bin/env bash
# Deploy infocepo-infra-mcp to K8s
# This creates a Deployment + Service + Ingress for the MCP SSE server
# and configures OWUI to connect to it
set -euo pipefail

NAMESPACE="demo1"
MCP_IMAGE="registry.ailab.infocepo.com:wait-2026-09/infocepo-mcp:latest"
MCP_HOST="0.0.0.0"
MCP_PORT="8085"

echo "🚀 Deploying infocepo-infra-mcp to K8s..."
echo "   Namespace: $NAMESPACE"
echo "   Image: $MCP_IMAGE"

# 1. Check if MCP server is already running
echo ""
echo "📋 Checking existing deployment..."
kubectl --insecure-skip-tls-verify -n "$NAMESPACE" get deployment infocepo-mcp-server 2>/dev/null || echo "   No existing deployment found"

# 2. Create the Deployment manifest
cat > /tmp/infocepo-mcp-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: infocepo-mcp-server
  namespace: $NAMESPACE
  labels:
    app: infocepo-mcp
    version: "0.1.0"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: infocepo-mcp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: infocepo-mcp
        version: "0.1.0"
    spec:
      containers:
        - name: mcp-server
          image: ${MCP_IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: ${MCP_PORT}
              name: http-mcp
              protocol: TCP
          env:
            - name: MCP_HOST
              value: "${MCP_HOST}"
            - name: MCP_PORT
              value: "${MCP_PORT}"
            - name: INFOCEPO_API_KEY
              valueFrom:
                secretKeyRef:
                  name: infocepo-mcp-credentials
                  key: INFOCEPO_API_KEY
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          readinessProbe:
            httpGet:
              path: /health
              port: ${MCP_PORT}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: ${MCP_PORT}
            initialDelaySeconds: 10
            periodSeconds: 30
          startupProbe:
            httpGet:
              path: /health
              port: ${MCP_PORT}
            failureThreshold: 30
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: infocepo-mcp-server
  namespace: $NAMESPACE
  labels:
    app: infocepo-mcp
spec:
  selector:
    app: infocepo-mcp
  ports:
    - port: ${MCP_PORT}
      targetPort: ${MCP_PORT}
      name: http-mcp
      protocol: TCP
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: infocepo-mcp-ingress
  namespace: $NAMESPACE
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: public
  tls:
    - hosts:
        - mcp.infocepo.com
      secretName: mcp-infocepo-com-tls
  rules:
    - host: mcp.infocepo.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: infocepo-mcp-server
                port:
                  number: ${MCP_PORT}
EOF

echo ""
echo "📝 Creating K8s resources..."
kubectl --insecure-skip-tls-verify apply -f /tmp/infocepo-mcp-deployment.yaml --namespace "$NAMESPACE"

echo ""
echo "⏳ Waiting for deployment to stabilize..."
kubectl --insecure-skip-tls-verify rollout status deployment/infocepo-mcp-server -n "$NAMESPACE" --timeout=120s

echo ""
echo "📋 Checking deployment status..."
kubectl --insecure-skip-tls-verify get pods -l app=infocepo-mcp -n "$NAMESPACE"

echo ""
echo "🌐 Testing health endpoint..."
# Wait for service to be ready
sleep 5
# Use kubectl port-forward to test
kubectl --insecure-skip-tls-verify -n "$NAMESPACE" port-forward service/infocepo-mcp-server 8085:8085 &
PORTFORWARD_PID=$!
sleep 3

curl -s http://localhost:8085/health | python3 -m json.tool

# Clean up port-forward
kill $PORTFORWARD_PID 2>/dev/null || true

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Resources created:"
kubectl --insecure-skip-tls-verify get all -l app=infocepo-mcp -n "$NAMESPACE"
