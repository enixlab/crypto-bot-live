#!/bin/bash
# Déploiement Cloud Run + Cloud Scheduler
# Prérequis : gcloud installé, authentifié, projet enix-crypto-bot créé.
set -e

PROJECT=${GCP_PROJECT:-enix-crypto-bot}
REGION=${GCP_REGION:-europe-west1}
SERVICE=enix-crypto-bot
BUCKET=${GCS_BUCKET:-enix-crypto-bot-state}

echo "→ Création bucket GCS (idempotent)"
gsutil mb -p "$PROJECT" -l "$REGION" "gs://$BUCKET" 2>/dev/null || true
gsutil iam ch allUsers:objectViewer "gs://$BUCKET" || true
gsutil cors set scripts/gcs_cors.json "gs://$BUCKET" || true

echo "→ Build & deploy Cloud Run"
gcloud builds submit --tag "gcr.io/$PROJECT/$SERVICE" --project="$PROJECT"

gcloud run deploy "$SERVICE" \
  --image "gcr.io/$PROJECT/$SERVICE" \
  --region "$REGION" \
  --project "$PROJECT" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 540s \
  --max-instances 1 \
  --set-env-vars "GCS_BUCKET=$BUCKET,BOT_MODE=${BOT_MODE:-paper},HYPERLIQUID_NETWORK=${HYPERLIQUID_NETWORK:-testnet}" \
  --set-secrets "HYPERLIQUID_PRIVATE_KEY=hl-private-key:latest,HYPERLIQUID_ACCOUNT_ADDRESS=hl-account-address:latest,DEEPSEEK_API_KEY=deepseek-key:latest" \
  --no-allow-unauthenticated

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')
echo "→ Service URL : $URL"

echo "→ Création Cloud Scheduler (cycle toutes les 10 min)"
gcloud scheduler jobs create http "$SERVICE-cycle" \
  --schedule "*/10 * * * *" \
  --uri "$URL/cycle" \
  --http-method POST \
  --location "$REGION" \
  --project "$PROJECT" \
  --oidc-service-account-email "$(gcloud iam service-accounts list --project="$PROJECT" --filter='email~scheduler' --format='value(email)' | head -1)" \
  --attempt-deadline 540s 2>/dev/null || \
gcloud scheduler jobs update http "$SERVICE-cycle" \
  --schedule "*/10 * * * *" \
  --uri "$URL/cycle" \
  --location "$REGION" \
  --project "$PROJECT"

echo "✅ Déploiement OK. Bot actif toutes les 10 min."
