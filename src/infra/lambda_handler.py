"""
src/infra/lambda_handler.py
Handler para desplegar el agente como Lambda en Floci.
Floci ejecuta Lambda en contenedores Docker reales (fidelidad total).
"""
import json
from src.api.main import graph, get_langfuse_callback_handler, is_langfuse_enabled


def handler(event, context):
    """
    Lambda handler compatible con Floci (API Gateway proxy).
    event: { "body": '{"query": "...", "customer_id": "...", "thread_id": "..."}' }
    """
    try:
        body = json.loads(event.get("body", "{}"))
        query = body.get("query", "")
        customer_id = body.get("customer_id", "anonymous")
        thread_id = body.get("thread_id", "default")

        config = {"configurable": {"thread_id": thread_id}}
        callbacks = []
        if is_langfuse_enabled():
            cb = get_langfuse_callback_handler(session_id=thread_id)
            if cb:
                callbacks.append(cb)

        result = graph.invoke(
            {"messages": [{"role": "user", "content": query}],
             "customer_id": customer_id},
            config=config,
        )

        ai_messages = [m for m in result["messages"] if m.__class__.__name__ == "AIMessage"]
        final_text = ai_messages[-1].content if ai_messages else "Sin respuesta"

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "response": final_text,
                "intent": result.get("intent", "unknown"),
                "escalated": result.get("escalated", False),
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
