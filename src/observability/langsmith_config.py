"""
src/observability/langsmith_config.py
Integración con LangSmith para evaluación continua y evals.
Define datasets y functores de evaluación.
"""
import os
from dotenv import load_dotenv

load_dotenv()

LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "tekyrios-ai-support")


def _is_valid_key(key: str) -> bool:
    """Una key placeholder (lsv2_xxxx) no es válida para tracing real."""
    if not key:
        return False
    return "xxxx" not in key and len(key) > 10


def configure_langsmith():
    """Configura LangSmith para tracing y evals (solo si hay key válida)."""
    if _is_valid_key(LANGSMITH_API_KEY):
        os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
        os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
    else:
        # Sin key válida: desactivar tracing para no romper la ejecución.
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ.pop("LANGSMITH_API_KEY", None)


def is_langsmith_enabled() -> bool:
    return _is_valid_key(LANGSMITH_API_KEY)


def create_evaluation_dataset(client, name: str = "tekyrios-support-evals"):
    """
    Crea (o recupera) un dataset de evaluación en LangSmith.
    Ejemplo de casos de prueba para el agente de soporte.
    """
    if not is_langsmith_enabled():
        return None
    examples = [
        {
            "inputs": {"query": "No puedo conectarme a la VPN de la empresa"},
            "outputs": {"expected_intent": "tech"},
        },
        {
            "inputs": {"query": "Quiero cambiar mi plan de facturación"},
            "outputs": {"expected_intent": "billing"},
        },
        {
            "inputs": {"query": "Cuántos días de vacaciones me quedan"},
            "outputs": {"expected_intent": "hr"},
        },
        {
            "inputs": {"query": "Esto es inaceptable, quiero hablar con un humano ya"},
            "outputs": {"expected_intent": "escalate"},
        },
    ]
    dataset = client.create_dataset(
        dataset_name=name,
        description="Casos de evaluación para agente de soporte Tekyrios",
    )
    client.create_examples(dataset_id=dataset.id, examples=examples)
    return dataset


def correctness_evaluator(run, example) -> dict:
    """
    Evaluador LLM-as-judge: ¿el intent clasificado coincide con el esperado?
    """
    predicted = run.outputs.get("intent", "")
    expected = example.outputs.get("expected_intent", "")
    score = 1.0 if predicted == expected else 0.0
    return {"score": score, "reasoning": f"predicho={predicted}, esperado={expected}"}
