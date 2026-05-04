#!/usr/bin/env bash
# One-time cluster bootstrap — run once per fresh cluster before ArgoCD app-of-apps.
# After this, ArgoCD manages everything declaratively.
set -euo pipefail

GITEA_TOKEN="${GITEA_TOKEN:-536e64c76138f3b94eecbfbb23cc38a9d4a513bc}"
GITEA_HOST="git.lupulup.com"

echo "==> Installing ArgoCD"
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.12.6/manifests/install.yaml
kubectl patch deployment argocd-server -n argocd --type strategic --patch \
  '{"spec":{"template":{"spec":{"containers":[{"name":"argocd-server","command":["argocd-server","--insecure"]}]}}}}'

echo "==> Installing ArgoCD Image Updater"
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-image-updater/v0.14.0/manifests/install.yaml

echo "==> Adding Gitea repo credential to ArgoCD"
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: bankoffer-gitea-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://${GITEA_HOST}/admin/BankOfferingAI.git
  username: admin
  password: ${GITEA_TOKEN}
EOF

echo "==> Configuring Image Updater registry credentials"
kubectl patch secret argocd-image-updater-secret -n argocd \
  --type merge \
  -p "{\"stringData\":{\"${GITEA_HOST}\":\"admin:${GITEA_TOKEN}\"}}"

kubectl patch configmap argocd-image-updater-config -n argocd \
  --type merge \
  -p "{\"data\":{\"registries.conf\":\"registries:\\n  - name: Gitea\\n    api_url: https://${GITEA_HOST}\\n    prefix: ${GITEA_HOST}\\n    credentials: secret:argocd/argocd-image-updater-secret#${GITEA_HOST}\\n    defaultns: admin\\n    insecure: false\\n\"}}"

echo "==> Creating Gitea image pull secret in cf-marketing"
kubectl create namespace cf-marketing --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret docker-registry gitea-registry \
  --docker-server=${GITEA_HOST} \
  --docker-username=admin \
  --docker-password=${GITEA_TOKEN} \
  -n cf-marketing \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Creating Gitea image pull secret in cf-demo"
kubectl create namespace cf-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret docker-registry gitea-registry \
  --docker-server=${GITEA_HOST} \
  --docker-username=admin \
  --docker-password=${GITEA_TOKEN} \
  -n cf-demo \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Setting up iptables routes for k3d MetalLB"
PANGOLIN_BR=br-fc0c74747834
K3D_BR=br-501329b585e3
iptables -I FORWARD 1 -i ${PANGOLIN_BR} -o ${K3D_BR} -j ACCEPT 2>/dev/null || true
iptables -I FORWARD 1 -i ${K3D_BR} -o ${PANGOLIN_BR} -j ACCEPT 2>/dev/null || true

echo "==> Applying k3d app-of-apps"
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: k3d-app-of-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://${GITEA_HOST}/admin/BankOfferingAI.git
    targetRevision: HEAD
    path: k8s/argocd
    directory:
      recurse: false
      exclude: app-of-apps.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
EOF

echo ""
echo "Bootstrap complete. ArgoCD will now manage the cluster."
echo "ArgoCD admin password:"
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
echo ""
