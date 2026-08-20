"""
src/agents/escalation.py
Manejo de escalado a humano (Human-in-the-Loop) con LangGraph interrupt.
Envía la consulta a SQS en Floci y pausa el grafo para revisión humana.
"""
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from src.infra.floci_config import (
    LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL,
    get_boto3_client, SQS_ESCALATION_QUEUE,
)


@tool
def send_to_human_queue(query: str, context: str = "") -> str:
    """Envía la consulta a la cola de escalado humano para revisión manual."""
    client = get_boto3_client("sqs")
    queue_url = client.get_queue_url(QueueName=SQS_ESCALATION_QUEUE)["QueueUrl"]
    import json
    msg = json.dumps({"query": query, "context": context, "timestamp": __import__("time").time()})
    client.send_message(QueueUrl=queue_url, MessageBody=msg)
    return "Consulta enviada a revisión humana. Recibirás respuesta pronto."


def build_escalation_agent():
    """Agente de escalado humano. Pausa con interrupt() para aprobación."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0.1,
    )
    return llm, [send_to_human_queue], "escalation_agent", (
        "Eres el agente de ESCALADO HUMANO de Tekyrios SAS. "
        "Cuando el caso supera la capacidad de los agentes automatizados, "
        "envías la consulta a la cola de revisión humana. "
        "No intentes resolver el problema tú mismo; coordina la transferencia."
    )
