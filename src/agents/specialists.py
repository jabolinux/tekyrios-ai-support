"""
src/agents/specialists.py
Agentes especializados de soporte para Tekyrios SAS.
Cada uno tiene tools que consultan Floci (S3 RAG, DynamoDB, SQS).
"""
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from src.infra.floci_config import (
    LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL,
    get_boto3_client, SQS_ESCALATION_QUEUE,
)
from src.infra.s3_rag import retrieve_context


def _build_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=temperature,
    )


@tool
def search_knowledge_base(query: str) -> str:
    """Busca en la base de conocimientos de Tekyrios (documentos de la empresa)."""
    results = retrieve_context(query, top_k=3)
    if not results:
        return "No se encontró información relevante en la base de conocimientos."
    return "\n\n".join(
        f"[Fuente: {r['source']}]\n{r['content']}" for r in results
    )


@tool
def create_support_ticket(customer_id: str, issue: str, priority: str = "medium") -> str:
    """Crea un ticket de soporte en el sistema. priority: low|medium|high|critical"""
    client = get_boto3_client("dynamodb")
    ticket_id = f"TK-{abs(hash(customer_id + issue)) % 100000:05d}"
    client.put_item(
        TableName="tekyrios-tickets",
        Item={
            "ticket_id": {"S": ticket_id},
            "customer_id": {"S": customer_id},
            "issue": {"S": issue},
            "priority": {"S": priority},
            "status": {"S": "open"},
        },
    )
    return f"Ticket {ticket_id} creado para cliente {customer_id} (prioridad: {priority})"


@tool
def check_customer_status(customer_id: str) -> str:
    """Consulta el estado de cuenta y tickets abiertos de un cliente."""
    client = get_boto3_client("dynamodb")
    try:
        resp = client.get_item(
            TableName="tekyrios-customers",
            Key={"customer_id": {"S": customer_id}},
        )
        if "Item" in resp:
            item = resp["Item"]
            return f"Cliente {customer_id}: plan={item.get('plan', {}).get('S', 'n/a')}, estado={item.get('status', {}).get('S', 'n/a')}"
        return f"Cliente {customer_id} no encontrado en el sistema."
    except Exception as e:
        return f"Error consultando cliente: {e}"


def build_tech_agent():
    """Agente especialista en soporte técnico de TI."""
    return (
        _build_llm(),
        [
            search_knowledge_base,
            create_support_ticket,
            check_customer_status,
        ],
        "tech_support",
        (
            "Eres el agente de SOPORTE TÉCNICO de Tekyrios SAS. "
            "Ayudas con problemas de infraestructura, redes, software y hardware. "
            "Usa la base de conocimientos para encontrar soluciones documentadas. "
            "Si el problema requiere escalado, crea un ticket."
        ),
    )


def build_billing_agent():
    """Agente especialista en facturación y pagos."""
    return (
        _build_llm(),
        [
            check_customer_status,
            create_support_ticket,
        ],
        "billing_expert",
        (
            "Eres el agente de FACTURACIÓN de Tekyrios SAS. "
            "Manejas consultas sobre pagos, facturas, planes y cargos. "
            "Nunca reveles datos de tarjeta de crédito completos."
        ),
    )


def build_hr_agent():
    """Agente especialista en recursos humanos internos."""
    return (
        _build_llm(),
        [
            search_knowledge_base,
            create_support_ticket,
        ],
        "hr_specialist",
        (
            "Eres el agente de RECURSOS HUMANOS de Tekyrios SAS. "
            "Ayudas con consultas de empleados: vacaciones, nómina, políticas internas. "
            "Usa la base de conocimientos para políticas de la empresa."
        ),
    )
