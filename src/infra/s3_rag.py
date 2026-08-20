"""
src/infra/s3_rag.py
Knowledge Base RAG cargada desde S3 en Floci.
Los documentos de la empresa viven en s3://tekyrios-kb/kb/
"""
import os
from typing import List, Dict, Any
from src.infra.floci_config import get_boto3_client, S3_KB_BUCKET, FLOCI_ENDPOINT


def upload_documents(local_dir: str = "docs") -> int:
    """Sube documentos .md de un directorio local al bucket S3 (Floci)."""
    client = get_boto3_client("s3")
    count = 0
    for fname in os.listdir(local_dir):
        if fname.endswith((".md", ".txt", ".pdf")):
            path = os.path.join(local_dir, fname)
            client.upload_file(path, S3_KB_BUCKET, f"kb/{fname}")
            count += 1
            print(f"  subido: {fname}")
    return count


def list_kb_documents() -> List[str]:
    """Lista documentos en el bucket KB de Floci."""
    client = get_boto3_client("s3")
    resp = client.list_objects_v2(Bucket=S3_KB_BUCKET, Prefix="kb/")
    return [o["Key"] for o in resp.get("Contents", [])]


def retrieve_context(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Búsqueda semántica simple (placeholder).
    En producción: usar Bedrock Titan Embeddings + OpenSearch en Floci.
    Por ahora: filtrado por palabras clave sobre contenido descargado.
    """
    client = get_boto3_client("s3")
    docs = list_kb_documents()
    results = []
    q_tokens = set(query.lower().split())

    for key in docs:
        obj = client.get_object(Bucket=S3_KB_BUCKET, Key=key)
        content = obj["Body"].read().decode("utf-8", errors="ignore")
        score = sum(1 for t in q_tokens if t in content.lower())
        if score > 0:
            results.append({
                "source": key,
                "content": content[:500],
                "score": score,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    print("Documentos en KB:", list_kb_documents())
