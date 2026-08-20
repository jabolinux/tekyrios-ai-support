"""
src/api/main.py
API REST para el agente de soporte Tekyrios.
Corre localmente con uvicorn y se despliega en Lambda (Floci).
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.graph.support_graph import build_support_graph
from src.observability.langfuse_config import get_langfuse_callback_handler, configure_langfuse, is_langfuse_enabled
from src.observability.langsmith_config import configure_langsmith, is_langsmith_enabled

# Configurar observabilidad al arrancar
configure_langfuse()
configure_langsmith()

app = FastAPI(
    title="Tekyrios AI Support",
    description="Agente de soporte multi-agente (LangGraph) sobre Floci local",
    version="1.0.0",
)

graph = build_support_graph()


class SupportRequest(BaseModel):
    query: str
    customer_id: str = "anonymous"
    thread_id: str = "default"


class SupportResponse(BaseModel):
    response: str
    intent: str = "unknown"
    escalated: bool = False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "floci_endpoint": "http://localhost:4566",
        "langfuse": is_langfuse_enabled(),
        "langsmith": is_langsmith_enabled(),
    }


@app.post("/support", response_model=SupportResponse)
def support(req: SupportRequest):
    """Procesa una consulta de soporte a través del grafo multi-agente."""
    try:
        config = {"configurable": {"thread_id": req.thread_id}}
        callbacks = []
        if is_langfuse_enabled():
            cb = get_langfuse_callback_handler(session_id=req.thread_id)
            if cb:
                callbacks.append(cb)

        result = graph.invoke(
            {"messages": [{"role": "user", "content": req.query}],
             "customer_id": req.customer_id},
            config=config,
        )

        # Extraer último mensaje del agente
        ai_messages = [m for m in result["messages"] if m.__class__.__name__ == "AIMessage"]
        final_text = ai_messages[-1].content if ai_messages else "Sin respuesta"
        intent = result.get("intent", "unknown")
        escalated = result.get("escalated", False)

        return SupportResponse(response=final_text, intent=intent, escalated=escalated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
