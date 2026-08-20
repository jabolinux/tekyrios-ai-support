"""
src/infra/dynamodb_state.py
Checkpointer de LangGraph usando DynamoDB en Floci (persistencia local).
Permite reanudar conversaciones y human-in-the-loop.
Usa el saver oficial langgraph-checkpoint-aws (tabla única PK/SK).
"""
import boto3
try:
    from langgraph.checkpoint.dynamodb import DynamoDBSaver  # placeholder
except ImportError:
    DynamoDBSaver = None
if DynamoDBSaver is None:
    from langgraph_checkpoint_aws import DynamoDBSaver

from src.infra.floci_config import (
    DYNAMODB_TABLE, FLOCI_ENDPOINT, AWS_REGION,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
)

CHECKPOINTS_TABLE = DYNAMODB_TABLE  # tabla única (checkpoints + writes)


def _client_config() -> dict:
    """Configuración de cliente boto3 apuntada a Floci."""
    return {
        "endpoint_url": FLOCI_ENDPOINT,
        "region_name": AWS_REGION,
        "aws_access_key_id": AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
    }


def get_dynamodb_checkpointer():
    """
    Retorna un DynamoDBSaver (langgraph-checkpoint-aws) configurado contra Floci.
    Requiere que la tabla exista (ver create_table_if_not_exists / floci/init.sh).
    """
    saver = DynamoDBSaver(
        table_name=CHECKPOINTS_TABLE,
        endpoint_url=FLOCI_ENDPOINT,
        region_name=AWS_REGION,
    )
    return saver


def create_table_if_not_exists():
    """Crea la tabla de checkpoints/writes en Floci si no existe.

    Esquema esperado por langgraph-checkpoint-aws:
      PK (HASH, S), SK (RANGE, S).
    """
    client = boto3.client(
        "dynamodb",
        endpoint_url=FLOCI_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    try:
        client.create_table(
            TableName=CHECKPOINTS_TABLE,
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Tabla {CHECKPOINTS_TABLE} creada en Floci")
    except client.exceptions.ResourceInUseException:
        print(f"Tabla {CHECKPOINTS_TABLE} ya existe")
