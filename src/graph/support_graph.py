"""
src/graph/support_graph.py
Grafo principal de soporte multi-agente con LangGraph.
Supervisor clasifica intento → enruta a agente especializado → escala si necesario.
Estado persistente vía DynamoDB (Floci).
"""
from typing import TypedDict, Literal, Optional, Annotated
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from src.agents.specialists import build_tech_agent, build_billing_agent, build_hr_agent
from src.agents.escalation import build_escalation_agent
from src.infra.floci_config import LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from src.infra.dynamodb_state import get_dynamodb_checkpointer


# ---------- Estado compartido ----------
class SupportState(MessagesState):
    intent: Optional[str]
    customer_id: Optional[str]
    escalated: bool


# ---------- Clasificador (Router) ----------
def classify_node(state: SupportState) -> dict:
    """Clasifica la intención del usuario y decide el agente."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0,
    )
    last_msg = state["messages"][-1].content if state["messages"] else ""
    prompt = (
        "Clasifica el mensaje en uno de estos intents: "
        "tech (soporte técnico TI), billing (facturación/pagos), "
        "hr (recursos humanos), escalate (escalar a humano), general. "
        "Responde SOLO la palabra del intent. Mensaje: " + last_msg
    )
    resp = llm.invoke([HumanMessage(content=prompt)])
    intent = resp.content.strip().lower()
    valid = {"tech", "billing", "hr", "escalate", "general"}
    if intent not in valid:
        intent = "general"
    return {"intent": intent}


def route_by_intent(state: SupportState) -> str:
    """Enruta al agente especializado según el intent clasificado."""
    intent = state.get("intent", "general")
    mapping = {
        "tech": "tech_agent",
        "billing": "billing_agent",
        "hr": "hr_agent",
        "escalate": "escalate_agent",
        "general": "general_agent",
    }
    return mapping.get(intent, "general_agent")


# ---------- Agentes como nodos ----------
def _make_agent_node(builder_fn, node_name: str):
    """Crea un nodo que ejecuta un ReAct agent especializado."""
    llm, tools, name, prompt = builder_fn()
    agent = create_react_agent(llm, tools, prompt=prompt, name=name)

    def node(state: SupportState) -> dict:
        result = agent.invoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    return node


def general_agent_node(state: SupportState) -> dict:
    """Agente general de fallback."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        temperature=0.3,
    )
    result = llm.invoke(state["messages"])
    return {"messages": [AIMessage(content=result.content)]}


def escalate_node(state: SupportState) -> dict:
    """Nodo de escalado humano con interrupt (Human-in-the-Loop)."""
    from langgraph.types import interrupt
    query = state["messages"][-1].content if state["messages"] else ""
    # Pausa el grafo esperando aprobación/respuesta humana
    human_response = interrupt(
        {"action": "escalate", "query": query, "message": "Requiere revisión humana"}
    )
    return {"messages": [AIMessage(content=f"[Humano] {human_response}")], "escalated": True}


# ---------- Construcción del grafo ----------
def build_support_graph():
    """Ensambla el grafo de soporte multi-agente."""
    graph = StateGraph(SupportState)

    # Nodos
    graph.add_node("classify", classify_node)
    graph.add_node("tech_agent", _make_agent_node(build_tech_agent, "tech_agent"))
    graph.add_node("billing_agent", _make_agent_node(build_billing_agent, "billing_agent"))
    graph.add_node("hr_agent", _make_agent_node(build_hr_agent, "hr_agent"))
    graph.add_node("general_agent", general_agent_node)
    graph.add_node("escalate_agent", _make_agent_node(build_escalation_agent, "escalate_agent"))
    graph.add_node("escalate_human", escalate_node)

    # Flujo: START → classify → (route) → agente → END
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "tech_agent": "tech_agent",
            "billing_agent": "billing_agent",
            "hr_agent": "hr_agent",
            "escalate_agent": "escalate_agent",
            "general_agent": "general_agent",
        },
    )

    # Los agentes automatizados terminan el flujo
    graph.add_edge("tech_agent", END)
    graph.add_edge("billing_agent", END)
    graph.add_edge("hr_agent", END)
    graph.add_edge("general_agent", END)

    # El agente de escalado envía a cola y pausa para humano
    graph.add_edge("escalate_agent", "escalate_human")
    graph.add_edge("escalate_human", END)

    # Checkpointer en DynamoDB (Floci) para persistencia y HITL
    checkpointer = get_dynamodb_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


if __name__ == "__main__":
    g = build_support_graph()
    print("Grafo de soporte compilado exitosamente ✅")
    print("Nodos:", list(g.get_graph().nodes.keys()))
