"""
src/frontend/chat.py
Frontend de chat (Streamlit) para Tekyrios AI Support.
Invoca el grafo LangGraph directamente y muestra trazas en LangFuse.
Ejecutar: streamlit run src/frontend/chat.py
"""
import os
import sys
import streamlit as st

# Asegurar que src/ esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

from src.graph.support_graph import build_support_graph
from src.observability.langfuse_config import (
    get_langfuse_callback_handler, is_langfuse_enabled, configure_langfuse
)
from src.observability.langsmith_config import configure_langsmith, is_langsmith_enabled

configure_langfuse()
configure_langsmith()

st.set_page_config(page_title="Tekyrios AI Support", page_icon="🤖", layout="wide")

st.title("🤖 Tekyrios AI Support")
st.caption("Agente de soporte multi-agente (LangGraph + LangFuse + LangSmith sobre Floci)")

# Sidebar: estado
with st.sidebar:
    st.header("Configuración")
    customer_id = st.text_input("Customer ID", value="C001")
    thread_id = st.text_input("Thread ID (sesión)", value="session-1")
    st.divider()
    st.write("**Observabilidad:**")
    st.write(f"🔍 LangFuse: {'✅' if is_langfuse_enabled() else '❌'}")
    st.write(f"📊 LangSmith: {'✅' if is_langsmith_enabled() else '❌'}")
    st.write(f"☁️ Floci: http://localhost:4566")
    if st.button("🗑️ Limpiar chat"):
        st.session_state.messages = []
        st.rerun()

# Inicializar grafo (cache)
@st.cache_resource
def get_graph():
    return build_support_graph()

graph = get_graph()

# Estado de mensajes
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "meta" in msg:
            st.caption(msg["meta"])

# Input del usuario
if prompt := st.chat_input("Escribe tu consulta de soporte..."):
    # Mostrar mensaje usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Invocar grafo
    with st.chat_message("assistant"):
        with st.spinner("Agente procesando..."):
            config = {"configurable": {"thread_id": thread_id}}
            callbacks = []
            if is_langfuse_enabled():
                cb = get_langfuse_callback_handler(session_id=thread_id)
                if cb:
                    callbacks.append(cb)

            try:
                result = graph.invoke(
                    {"messages": [{"role": "user", "content": prompt}],
                     "customer_id": customer_id},
                    config=config,
                )
                ai_messages = [m for m in result["messages"]
                               if m.__class__.__name__ == "AIMessage"]
                final_text = ai_messages[-1].content if ai_messages else "Sin respuesta"
                intent = result.get("intent", "unknown")
                escalated = result.get("escalated", False)

                st.write(final_text)
                meta = f"Intent: `{intent}`" + (" · 🚨 Escalado a humano" if escalated else "")
                st.caption(meta)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_text,
                    "meta": meta,
                })
            except Exception as e:
                err = f"❌ Error: {e}"
                st.error(err)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err,
                })

# Footer
st.divider()
st.caption("Tekyrios SAS · Powered by LangGraph + Floci local")
