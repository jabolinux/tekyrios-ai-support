#!/usr/bin/env bash
# ============================================================
# floci/deploy.sh — Despliega el agente en Floci como Lambda + API Gateway
# Requisitos: Floci corriendo, aws cli v2, zip instalado
# Uso: ./floci/deploy.sh
# ============================================================
set -euo pipefail

export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

LAMBDA_NAME="${LAMBDA_FUNCTION_NAME:-tekyrios-support}"
API_NAME="${API_GATEWAY_NAME:-tekyrios-support-api}"
ROLE_NAME="tekyrios-lambda-role"
PROJECT_ROOT="$(cd .. && pwd)"

echo "==> Empaquetando código Lambda"
cd "$PROJECT_ROOT"
rm -f lambda.zip
zip -r lambda.zip src/ requirements.txt -x "*.pyc" "__pycache__/*" || {
  echo "ERROR: no se pudo crear lambda.zip. Instala 'zip'."
  exit 1
}

echo "==> Creando rol IAM (Floci)"
aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || echo "    (rol ya existe)"

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

echo "==> Creando función Lambda: $LAMBDA_NAME"
aws lambda create-function \
  --function-name "$LAMBDA_NAME" \
  --runtime python3.11 \
  --handler "src.infra.lambda_handler:handler" \
  --role "$ROLE_ARN" \
  --zip-file "fileb://lambda.zip" \
  --environment "Variables={AWS_ENDPOINT_URL=$AWS_ENDPOINT_URL,AWS_ACCESS_KEY_ID=test,AWS_SECRET_ACCESS_KEY=test,AWS_DEFAULT_REGION=us-east-1,OPENAI_API_KEY=${OPENAI_API_KEY:-sk-test},OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://api.openai.com/v1},LLM_MODEL=${LLM_MODEL:-gpt-4o-mini},LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-},LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY:-},LANGFUSE_HOST=${LANGFUSE_HOST:-https://cloud.langfuse.com},LANGSMITH_API_KEY=${LANGSMITH_API_KEY:-},LANGSMITH_TRACING=${LANGSMITH_TRACING:-false},LANGSMITH_PROJECT=${LANGSMITH_PROJECT:-tekyrios-ai-support},S3_KB_BUCKET=${S3_KB_BUCKET:-tekyrios-kb},DYNAMODB_TABLE=${DYNAMODB_TABLE:-tekyrios-conversations},SQS_ESCALATION_QUEUE=${SQS_ESCALATION_QUEUE:-tekyrios-escalations}" \
  2>/dev/null || {
    echo "    (función existe, actualizando código)"
    aws lambda update-function-code \
      --function-name "$LAMBDA_NAME" \
      --zip-file "fileb://lambda.zip" >/dev/null
  }

echo "==> Creando API Gateway REST: $API_NAME"
API_ID=$(aws apigateway create-rest-api --name "$API_NAME" --query 'id' --output text)
ROOT_ID=$(aws apigateway get-resources --rest-api-id "$API_ID" --query 'items[0].id' --output text)

# Recurso /support
RES_ID=$(aws apigateway create-resource --rest-api-id "$API_ID" --parent-id "$ROOT_ID" --path-part "support" --query 'id' --output text)

# Método POST → Lambda proxy
aws apigateway put-method --rest-api-id "$API_ID" --resource-id "$RES_ID" --http-method POST --authorization-type NONE >/dev/null
aws apigateway put-integration \
  --rest-api-id "$API_ID" --resource-id "$RES_ID" --http-method POST \
  --type AWS_PROXY --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:000000000000:function:$LAMBDA_NAME/invocations" >/dev/null

# Permiso Lambda
aws lambda add-permission \
  --function-name "$LAMBDA_NAME" \
  --statement-id apigateway \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:000000000000:$API_ID/*/*/support" 2>/dev/null || true

# Deploy
aws apigateway create-deployment --rest-api-id "$API_ID" --stage-name prod >/dev/null

echo ""
echo "✅ Despliegue completo en Floci:"
echo "   API URL: http://localhost:4566/restapis/$API_ID/prod/_user_request_/support"
echo "   Lambda:  $LAMBDA_NAME"
echo ""
echo "Prueba: curl -X POST http://localhost:4566/restapis/$API_ID/prod/_user_request_/support \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\":\"No puedo conectarme a la VPN\",\"customer_id\":\"C001\"}'"
