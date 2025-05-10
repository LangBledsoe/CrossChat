#!/bin/bash

set -e

PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
REGION="us-central1"
TIMEZONE="America/Los_Angeles"
SECRET_NAME="mysecrets-json"
SECRET_FILE="mysecrets.json"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "🛠 Using project: $PROJECT_ID"

# Enable necessary APIs
echo "🔧 Enabling required APIs..."
gcloud services enable \
  --quiet \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  iam.googleapis.com

# Ensure secret file exists
if [[ ! -f "$SECRET_FILE" ]]; then
  echo "❌ Missing $SECRET_FILE. Please add it to the root of the cloned repo."
  exit 1
fi

# Grant Cloud Build required roles
echo "🔐 Granting Cloud Build service account permissions..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/run.admin" \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/storage.admin" \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null

# Grant logging permission to the compute service account
echo "📝 Granting logging permissions to compute service account..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/logging.logWriter" \
  --quiet >/dev/null

# Grant secret access to the Cloud Run service account
echo "🔐 Granting Secret Accessor permission to Cloud Run service account..."
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# Create secret
echo "🔐 Creating secret..."
gcloud secrets create "$SECRET_NAME" --data-file="$SECRET_FILE" --quiet || echo "✅ Secret already exists, skipping."

# Submit Cloud Build
echo "🚀 Deploying webhook-app to Cloud Run..."
gcloud builds submit --tag "gcr.io/$PROJECT_ID/webhook-app" --quiet

gcloud run deploy webhook-app \
  --image "gcr.io/$PROJECT_ID/webhook-app" \
  --region "$REGION" \
  --allow-unauthenticated \
  --platform managed \
  --set-secrets "/etc/secrets/mysecrets.json=$SECRET_NAME:latest" \
  --quiet

# Deploy Python Cloud Function
echo "🐍 Deploying refresh-instagram-token Cloud Function..."
# cd into the directory containing the function code
cd key_refresh

gcloud functions deploy refresh-instagram-token \
  --runtime python312 \
  --trigger-http \
  --entry-point refresh_instagram_token \
  --region "$REGION" \
  --set-env-vars "GCP_PROJECT=$PROJECT_ID" \
  --service-account "$SERVICE_ACCOUNT" \
  --source . \
  --quiet

# cd back to the root directory
cd ..

# Create Cloud Scheduler Job
echo "⏰ Checking if Cloud Scheduler job already exists..."
if gcloud scheduler jobs describe refresh-instagram-token-job --location="$REGION" --quiet > /dev/null 2>&1; then
  echo "✅ Cloud Scheduler job 'refresh-instagram-token-job' already exists. Skipping creation."
else
  echo "⏰ Creating Cloud Scheduler job..."
  gcloud scheduler jobs create http refresh-instagram-token-job \
    --schedule="0 0 1 * *" \
    --time-zone="$TIMEZONE" \
    --http-method=GET \
    --uri="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/refresh-instagram-token" \
    --oidc-service-account-email="$SERVICE_ACCOUNT" \
    --location "$REGION" \
    --quiet
fi

# Deploy Go Cloud Function
echo "🐹 Deploying discord-handler Cloud Function..."
# cd into the directory containing the discord handler code
cd discord_handler_go

gcloud functions deploy discord-handler \
  --runtime go122 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point=DiscordHandler \
  --region="$REGION" \
  --set-secrets "/etc/secrets/mysecrets.json=$SECRET_NAME:latest" \
  --source . \
  --quiet

# cd back to the root directory
cd ..

# Load secrets from environment variables
DISCORD_BOT_TOKEN=$(jq -r '.DISCORD_BOT_TOKEN' < mysecrets.json)
DISCORD_APP_ID=$(jq -r '.DISCORD_APP_ID' < mysecrets.json)

# Register Discord Slash Command
echo "🔧 Registering Discord Slash Command..."
curl -X POST "https://discord.com/api/v10/applications/$DISCORD_APP_ID/commands" \
-H "Authorization: Bot $DISCORD_BOT_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "name": "Send Instagram DM",
  "type": 3
}'

echo "✅ Discord Slash Command registered successfully!"

echo "✅ All done! Your project is now set up."
