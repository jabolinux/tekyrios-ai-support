#!/usr/bin/env bash
# ============================================================
# floci/init.sh — Inicializa recursos AWS en Floci (local)
# Requisitos: Floci corriendo en localhost:4566, aws cli v2
# Uso: ./floci/init.sh
# ============================================================
set -euo pipefail

# --- Apuntar AWS CLI a Floci (emulador local) ---
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

S3_KB_BUCKET="${S3_KB_BUCKET:-tekyrios-kb}"
DYNAMODB_TABLE="${DYNAMODB_TABLE:-tekyrios-conversations}"
SQS_QUEUE="${SQS_ESCALATION_QUEUE:-tekyrios-escalations}"

echo "==> Verificando Floci en $AWS_ENDPOINT_URL"
aws --version
curl -s "$AWS_ENDPOINT_URL/health" >/dev/null || { echo "ERROR: Floci no responde"; exit 1; }

echo "==> Creando bucket S3: $S3_KB_BUCKET (Knowledge Base RAG)"
aws s3 mb "s3://$S3_KB_BUCKET" 2>/dev/null || echo "    (ya existe)"

echo "==> Creando tabla DynamoDB (Checkpointer LangGraph: tabla única PK/SK)"
# langgraph-checkpoint-aws usa una sola tabla con PK (HASH) y SK (RANGE).
aws dynamodb create-table \
  --table-name "$DYNAMODB_TABLE" \
  --attribute-definitions AttributeName=PK,AttributeType=S AttributeName=SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST 2>/dev/null || echo "    (ya existe: $DYNAMODB_TABLE)"

echo "==> Creando cola SQS: $SQS_QUEUE (Escalado humano)"
aws sqs create-queue \
  --queue-name "$SQS_QUEUE" 2>/dev/null || echo "    (ya existe)"

echo "==> Subiendo documentos de ejemplo al bucket S3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOC_DIR="$SCRIPT_DIR/../docs"
for f in "$DOC_DIR"/*.md; do
  [ -f "$f" ] && aws s3 cp "$f" "s3://$S3_KB_BUCKET/kb/" && echo "    subido: $(basename "$f")"
done

echo ""
echo "✅ Recursos Floci listos:"
echo "   S3:        s3://$S3_KB_BUCKET"
echo "   DynamoDB:  $DYNAMODB_TABLE"
echo "   SQS:       $SQS_QUEUE"
echo ""
echo "Para self-host LangFuse: docker compose up -d"
