#!/usr/bin/env bash
# Deploy Dagster user code to Kubernetes
# Usage: ./deploy.sh [namespace] [release-name]
# Note: make this script executable with: chmod +x deploy.sh

set -euo pipefail

NAMESPACE="${1:-dagster}"
RELEASE="${2:-dagster}"

echo "Deploying to namespace=$NAMESPACE release=$RELEASE"

# Rollout restart the user code deployment
kubectl rollout restart deployment/${RELEASE}-dagster-user-deployments-dagster-user-code \
    -n "$NAMESPACE"

echo "Waiting for rollout..."
kubectl rollout status deployment/${RELEASE}-dagster-user-deployments-dagster-user-code \
    -n "$NAMESPACE" \
    --timeout=120s

echo "Deploy complete. Verify at Dagster UI."
