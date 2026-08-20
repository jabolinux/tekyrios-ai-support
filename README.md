# AI Support flow

A **multi-agent customer-support assistant**, built with
**LangGraph** (agent orchestration), **LangFuse** + **LangSmith** (observability),
and **Floci** (a local AWS emulator: S3 / DynamoDB / SQS / Lambda).

The assistant classifies each support message, routes it to a specialist agent
(technical, billing, HR, or general), grounds answers in a company knowledge
base (RAG), and can escalate to a human via a queue + Human-in-the-Loop pause.

See [`architecture.md`](./architecture.md) for the full 4-layer design and
UML sequence diagrams.

Author: Jaime Alfredo Bonilla Pérez
jaimebp@gmail.com
---

## Features

- **Intent classification & routing** — `tech`, `billing`, `hr`, `escalate`, `general`.
- **Specialist ReAct agents** with tools (knowledge search, ticket creation,
  customer lookup).
- **RAG** over an S3-backed knowledge base (`tekyrios-kb`).
- **Conversational memory** persisted in DynamoDB (resumable threads).
- **Human escalation** via SQS + LangGraph `interrupt` (HITL).
- **Observability** with LangFuse traces and LangSmith evals.
- **100% local** — all AWS services run in Floci (`localhost:4566`); the LLM is
  an OpenAI-compatible endpoint (e.g. a local `qwen` model).

---

## Architecture (summary)

| Layer | What it does |
|-------|--------------|
| **1. Presentation** | Streamlit chat UI (`:8501`) and FastAPI REST API (`:8000`). Deployable via API Gateway + Lambda in Floci. |
| **2. Orchestration** | LangGraph `SupportState` graph: `classify` → conditional router → specialist agents → optional `escalate_human`. |
| **3. Knowledge & State** | S3 RAG retriever, DynamoDB conversation checkpointer, SQS escalation queue. |
| **4. Platform** | Floci emulated AWS (S3, DynamoDB, SQS, Lambda). |

---

## Prerequisites

- **Python 3.11+**
- **Floci** running locally on `http://localhost:4566`
  (Docker image with the AWS emulator; 80+ services, v1.7.0+).
- An **OpenAI-compatible LLM endpoint** (e.g. a local `qwen3.8-27b` served at
  `http://192.168.1.10:8081/v1` with any API key like `local`).
- *(Optional)* **LangFuse** via Docker for live traces (`docker compose up -d`).
- *(Optional)* **LangSmith** account for evals (set a valid `LANGSMITH_API_KEY`).
- *(Optional)* **AWS CLI v2** for `floci/init.sh` resource bootstrap.

---

## Installation

```bash
# 1. Clone
git clone https://github.com/jabolinux/tekyrios-ai-support.git
cd tekyrios-ai-support

# 2. Create & activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
#   Edit .env and set at least:
#   OPENAI_BASE_URL=http://192.168.1.10:8081/v1
#   OPENAI_API_KEY=local
#   LLM_MODEL=qwen3.8-27b

# 5. Start Floci (AWS emulator) — example with Docker
#   (adjust to your Floci launch command)
docker run -d -p 4566:4566 flavorlabs/floci:latest

# 6. Provision local AWS resources (S3 bucket, DynamoDB table, SQS queue)
./floci/init.sh
```

`.env` reference:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | Floci endpoint |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | `test` / `test` | Dummy creds for Floci |
| `S3_KB_BUCKET` | `tekyrios-kb` | RAG knowledge bucket |
| `DYNAMODB_TABLE` | `tekyrios-conversations` | Checkpointer table |
| `SQS_ESCALATION_QUEUE` | `tekyrios-escalations` | HITL escalation queue |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM endpoint |
| `OPENAI_API_KEY` | — | LLM key (`local` for local models) |
| `LLM_MODEL` | `gpt-4o-mini` | Model name (e.g. `qwen3.8-27b`) |
| `LANGFUSE_*` | — | LangFuse host/public/secret keys |
| `LANGSMITH_API_KEY` | — | Only enables LangSmith tracing if valid |

---

## Running

### Streamlit chat UI

```bash
source venv/bin/activate
streamlit run src/frontend/chat.py --server.port 8501
```

Open <http://localhost:8501>. Enter a `Customer ID` and a `Thread ID`
(session) in the sidebar, then chat. Each reply shows the detected intent and
flags escalations.

### REST API (FastAPI)

```bash
source venv/bin/activate
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

```bash
curl -X POST http://localhost:8000/support \
  -H "Content-Type: application/json" \
  -d '{"query":"No puedo conectarme a la VPN","customer_id":"C001","thread_id":"s1"}'
```

Health check: `GET http://localhost:8000/health`.

### Observability (LangFuse)

```bash
docker compose up -d        # starts LangFuse on http://localhost:3000
```

Set `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`; the
UI automatically shows per-node traces.

---

## Usage examples

| You say | Routed to |
|---------|-----------|
| "No puedo conectarme a la VPN" | `tech_agent` (RAG-grounded VPN guide) |
| "Quiero cambiar mi plan de facturación" | `billing_agent` |
| "Cuántos días de vacaciones me quedan" | `hr_agent` |
| "Esto es inaceptable, quiero hablar con un humano" | `escalate_agent` → SQS + HITL pause |

---

## Project structure

```
tekyrios-ai-support/
├── architecture.md            # 4-layer + UML sequence diagrams
├── README.md
├── requirements.txt
├── docker-compose.yml         # LangFuse self-host
├── .env.example
├── floci/
│   ├── init.sh                # provision S3 / DynamoDB / SQS in Floci
│   └── deploy.sh              # deploy Lambda + API Gateway in Floci
├── docs/                      # knowledge-base markdown (uploaded to S3)
├── src/
│   ├── graph/support_graph.py # LangGraph orchestration
│   ├── agents/
│   │   ├── specialists.py     # tech / billing / hr agents + tools
│   │   └── escalation.py      # escalation agent + SQS
│   ├── infra/
│   │   ├── floci_config.py    # AWS + LLM config
│   │   ├── dynamodb_state.py  # DynamoDB checkpointer (langgraph-checkpoint-aws)
│   │   └── s3_rag.py          # S3 RAG retrieval
│   ├── observability/
│   │   ├── langfuse_config.py
│   │   └── langsmith_config.py
│   ├── api/main.py            # FastAPI service
│   ├── frontend/chat.py       # Streamlit UI
│   └── lambda_handler.py      # Lambda entrypoint
└── tests/test_e2e.py
```

---

## Testing

```bash
source venv/bin/activate
pytest tests/ -q
```

`tests/test_e2e.py` verifies that the knowledge-base documents exist in the S3
bucket. Intent-classification tests require a reachable LLM endpoint.

---

## Deployment (Floci Lambda + API Gateway)

```bash
./floci/deploy.sh
```

This packages the app and creates a Lambda function + API Gateway in Floci so
the support graph is reachable via HTTP, exactly like the local FastAPI service.

---

## Roadmap

- Semantic RAG with **Bedrock Titan Embeddings + OpenSearch** (currently keyword).
- Pre-built LangSmith eval datasets for intent accuracy.
- Auth, multi-tenant customer profiles, and a human-review console for SQS items.

---

## License

© Tekyrios SAS. Internal use.
