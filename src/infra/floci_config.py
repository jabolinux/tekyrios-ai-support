"""
src/infra/floci_config.py
Configuración central de AWS apuntando a Floci (emulador local).
Todas las llamadas boto3 usan AWS_ENDPOINT_URL=http://localhost:4566
"""
import os
from dotenv import load_dotenv

load_dotenv()

FLOCI_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

S3_KB_BUCKET = os.getenv("S3_KB_BUCKET", "tekyrios-kb")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "tekyrios-conversations")
SQS_ESCALATION_QUEUE = os.getenv("SQS_ESCALATION_QUEUE", "tekyrios-escalations")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


def get_boto3_client(service: str):
    """Retorna cliente boto3 apuntado a Floci."""
    import boto3
    return boto3.client(
        service,
        endpoint_url=FLOCI_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def get_boto3_resource(service: str):
    """Retorna resource boto3 apuntado a Floci."""
    import boto3
    return boto3.resource(
        service,
        endpoint_url=FLOCI_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )
