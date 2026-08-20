"""
src/observability/langfuse_config.py
Integración con LangFuse para trazabilidad y observabilidad.
Captura cada paso del grafo LangGraph como spans.
"""
import os
from dotenv import load_dotenv

load_dotenv()

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


def configure_langfuse():
    """Configura las variables de entorno para LangFuse SDK."""
    os.environ["LANGFUSE_PUBLIC_KEY"] = LANGFUSE_PUBLIC_KEY or ""
    os.environ["LANGFUSE_SECRET_KEY"] = LANGFUSE_SECRET_KEY or ""
    os.environ["LANGFUSE_HOST"] = LANGFUSE_HOST
    # El SDK de LangChain/LangGraph lee estas vars automáticamente
    os.environ["LANGFUSE_TRACING"] = "true" if LANGFUSE_PUBLIC_KEY else "false"


def get_langfuse_callback_handler(session_id: str = "default"):
    """
    Retorna el callback handler de LangFuse para pasar a LangGraph.
    Requiere: from langfuse.langchain import LangfuseCallbackHandler
    """
    if not LANGFUSE_PUBLIC_KEY:
        return None
    from langfuse.langchain import LangfuseCallbackHandler
    return LangfuseCallbackHandler(
        session_id=session_id,
        metadata={"project": "tekyrios-ai-support"},
    )


def is_langfuse_enabled() -> bool:
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
