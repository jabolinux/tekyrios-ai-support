"""
tests/test_e2e.py
Pruebas end-to-end del agente de soporte contra Floci local.
Ejecutar: pytest tests/test_e2e.py -v
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.support_graph import build_support_graph
from src.infra.dynamodb_state import create_table_if_not_exists
from src.infra.s3_rag import upload_documents, list_kb_documents


@pytest.fixture(scope="module")
def graph():
    create_table_if_not_exists()
    return build_support_graph()


def test_classify_tech_intent(graph):
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "No puedo conectarme a la VPN"}]},
        config={"configurable": {"thread_id": "test-tech"}},
    )
    assert result.get("intent") in ["tech", "general"]


def test_classify_billing_intent(graph):
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Quiero cambiar mi plan de facturación"}]},
        config={"configurable": {"thread_id": "test-billing"}},
    )
    assert result.get("intent") in ["billing", "general"]


def test_classify_hr_intent(graph):
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Cuántos días de vacaciones tengo"}]},
        config={"configurable": {"thread_id": "test-hr"}},
    )
    assert result.get("intent") in ["hr", "general"]


def test_classify_escalate_intent(graph):
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Quiero hablar con un humano ya mismo"}]},
        config={"configurable": {"thread_id": "test-escalate"}},
    )
    assert result.get("intent") in ["escalate", "general"]


def test_kb_documents_exist():
    """Verifica que los docs de ejemplo estén en S3 (Floci)."""
    # Subir si no existen
    upload_documents(os.path.join(os.path.dirname(__file__), "..", "docs"))
    docs = list_kb_documents()
    assert any("tekyrios" in d for d in docs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
