# Tekyrios AI Support — Architecture

> Multi-agent customer-support assistant for **Tekyrios SAS**, built with
> **LangGraph** (orchestration), **LangFuse** + **LangSmith** (observability),
> and **Floci** (a local AWS emulator providing S3 / DynamoDB / SQS / Lambda).

All diagrams in this document are written in **Mermaid** so they render on
GitHub, in VS Code, and in any Markdown viewer.

---

## 1. System Overview

Tekyrios AI Support routes an incoming support message through a LangGraph
state graph. A classifier node detects the customer intent (`tech`, `billing`,
`hr`, `escalate`, `general`) and a conditional router dispatches the request to
the matching specialist ReAct agent. Specialists consult a Retrieval-Augmented
Generation (RAG) knowledge base stored in S3 and can create tickets / inspect
customer state in DynamoDB. When a case exceeds automation, an escalation agent
publishes the query to an SQS queue and the graph pauses via a LangGraph
`interrupt` for Human-in-the-Loop (HITL) review.

All AWS services run locally inside **Floci** (`http://localhost:4566`), so the
whole stack is reproducible without a cloud account. An OpenAI-compatible LLM
endpoint (e.g. a local `qwen` model served at `http://192.168.1.10:8081/v1`) is
used through `langchain-openai`.

---

## 2. Four-Layer Architecture

The system is decomposed into four logical layers. Cross-cutting observability
(LangFuse + LangSmith) instruments every layer.

```mermaid
flowchart TB
    subgraph L1["Layer 1 — Presentation / Channels"]
        direction LR
        UI["Streamlit Chat UI<br/>:8501"]
        API["FastAPI REST API<br/>:8000 /support"]
        GW["API Gateway + Lambda<br/>(Floci deploy)"]
    end

    subgraph L2["Layer 2 — Agent Orchestration (LangGraph)"]
        direction TB
        GRAPH["Support Graph (StateGraph)"]
        CLS["classify_node<br/>(intent router)"]
        RT["route_by_intent<br/>(conditional)"]
        TA["tech_agent"]
        BA["billing_agent"]
        HA["hr_agent"]
        GA["general_agent"]
        EA["escalate_agent"]
        EH["escalate_human<br/>(interrupt / HITL)"]
        GRAPH --> CLS --> RT
        RT -->|tech| TA
        RT -->|billing| BA
        RT -->|hr| HA
        RT -->|general| GA
        RT -->|escalate| EA
        EA --> EH
    end

    subgraph L3["Layer 3 — Knowledge & State"]
        direction LR
        RAG["RAG Retriever<br/>keyword over S3 docs"]
        CPT["Conversation Checkpointer<br/>DynamoDB"]
        TKT["Tickets / Customers<br/>DynamoDB"]
        QUE["Escalation Queue<br/>SQS"]
    end

    subgraph L4["Layer 4 — Platform / Infrastructure (Floci @ :4566)"]
        direction LR
        S3["S3<br/>tekyrios-kb"]
        DDB["DynamoDB<br/>tekyrios-conversations<br/>tekyrios-tickets<br/>tekyrios-customers"]
        SQS["SQS<br/>tekyrios-escalations"]
        LAM["Lambda + API Gateway"]
    end

    subgraph OBS["Cross-cutting — Observability"]
        LF["LangFuse (traces)"]
        LS["LangSmith (evals)"]
    end

    L1 --> L2
    TA --> RAG
    HA --> RAG
    EA --> QUE
    GRAPH --> CPT
    TA --> TKT
    BA --> TKT
    HA --> TKT

    RAG --> S3
    CPT --> DDB
    TKT --> DDB
    QUE --> SQS
    GW --> LAM
    LAM --> L2

    L2 -. traces .-> LF
    L2 -. evals .-> LS
```

### Layer responsibilities

| Layer | Responsibility | Key components |
|-------|----------------|----------------|
| **1. Presentation** | Capture user input and render agent answers across channels. | Streamlit UI, FastAPI `/support`, API Gateway + Lambda |
| **2. Orchestration** | Classify intent, route, run specialist ReAct agents, handle HITL. | LangGraph `SupportState` graph, classifier, 5 specialist nodes |
| **3. Knowledge & State** | Provide grounded answers (RAG), persist conversations, queue escalations. | S3 RAG retriever, DynamoDB checkpointer, SQS escalation |
| **4. Platform** | Emulated AWS services backing the whole stack locally. | Floci: S3, DynamoDB, SQS, Lambda |

---

## 3. Component & Deployment Diagram

```mermaid
flowchart LR
    User([Support Agent / Customer]) -->|browser| UI[Streamlit :8501]
    User -->|HTTP POST| APIGW[(API Gateway)]
    APIGW --> LAMBDA[Lambda: tek-support]
    LAMBDA --> GRAPH[Support Graph]
    UI --> GRAPH
    GRAPH --> LLM{{"LLM (OpenAI-compatible)<br/>qwen @ :8081/v1"}}
    GRAPH --> S3[(S3 tekyrios-kb)]
    GRAPH --> DDB[(DynamoDB tekyrios-conversations)]
    GRAPH --> SQS[(SQS tekyrios-escalations)]
    GRAPH --> DDBT[(DynamoDB tickets/customers)]
    GRAPH -.-> LF[LangFuse :3000]
    GRAPH -.-> LS[LangSmith Cloud]
```

---

## 4. UML Sequence Diagrams

### 4.1 Standard support flow (technical intent)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as Streamlit / API
    participant G as Support Graph
    participant C as classify_node
    participant T as tech_agent (ReAct)
    participant R as RAG (S3)
    participant D as DynamoDB

    U->>UI: "No puedo conectarme a la VPN"
    UI->>G: invoke(messages, thread_id)
    G->>C: classify intent
    C-->>G: intent = "tech"
    G->>T: route_by_intent -> tech_agent
    T->>R: search_knowledge_base("VPN")
    R->>D: getObjects(s3://tekyrios-kb/kb/*)
    D-->>R: VPN guide content
    R-->>T: retrieved context
    T->>LLM: answer with grounding
    T-->>G: AIMessage
    G->>D: put checkpoint (PK/SK)
    G-->>UI: {intent, response}
    UI-->>U: rendered answer + "[Intent: tech]"
```

### 4.2 Human escalation flow (HITL)

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant G as Support Graph
    participant E as escalate_agent
    participant Q as SQS (tekyrios-escalations)
    participant H as Human Reviewer
    participant G2 as escalate_human (interrupt)

    U->>G: "Esto es inaceptable, quiero hablar con un humano"
    G->>E: route -> escalate_agent
    E->>Q: send_to_human_queue(query)
    Q-->>E: accepted
    E-->>G: transfer message
    G->>G2: escalate_human
    G2-->>G: interrupt({"action":"escalate","query":...})
    Note over G: Graph PAUSED (awaiting human)
    H->>Q: consume message, draft reply
    H->>G: Command(resume={"reply": "..."})
    G2-->>G: AIMessage("[Humano] ...")
    G-->>U: final human-backed answer
```

---

## 5. State Model

The graph uses a `MessagesState` extension:

```mermaid
classDiagram
    class SupportState {
        +list~BaseMessage~ messages
        +str intent
        +str customer_id
        +bool escalated
    }
```

- `intent` — set by `classify_node`; one of `tech|billing|hr|escalate|general`.
- `customer_id` — passed by the channel; used by tools to look up state.
- `escalated` — set `True` once the human flow resolves.

---

## 6. Data Stores

| Store | Name | Schema | Purpose |
|-------|------|--------|---------|
| S3 | `tekyrios-kb` (`/kb/*`) | object blobs (`.md`) | RAG knowledge base |
| DynamoDB | `tekyrios-conversations` | `PK` (HASH, S), `SK` (RANGE, S) | LangGraph checkpointer (single-table, `langgraph-checkpoint-aws`) |
| DynamoDB | `tekyrios-tickets` | `ticket_id` (HASH) | Support tickets created by agents |
| DynamoDB | `tekyrios-customers` | `customer_id` (HASH) | Customer account status |
| SQS | `tekyrios-escalations` | queue | Pending human reviews |

> Note: `tekyrios-tickets` and `tekyrios-customers` are created on first write
> by the agent tools. `tekyrios-conversations` is provisioned by `floci/init.sh`.

---

## 7. Observability

```mermaid
flowchart LR
    APP[Support Graph] -->|span per node| LF[LangFuse :3000]
    APP -->|eval dataset| LS[LangSmith]
    LF --> UI1[(LangFuse UI)]
    LS --> UI2[(LangSmith UI)]
```

- **LangFuse** captures per-node traces (classify, each agent, RAG retrieval)
  for live debugging. Self-hosted via `docker compose up -d` → `http://localhost:3000`.
- **LangSmith** is used for evaluation datasets / LLM-as-judge correctness of
  intent classification. Tracing is enabled only when a valid `LANGSMITH_API_KEY`
  is present in `.env`.

---

## 8. Technology Stack

| Concern | Technology |
|---------|------------|
| Orchestration | LangGraph 1.x (`StateGraph`, `create_react_agent`, `interrupt`) |
| Agents | `langchain-openai` `ChatOpenAI` (ReAct) |
| LLM | OpenAI-compatible endpoint (local `qwen3.8-27b` at `:8081/v1`) |
| Persistence | `langgraph-checkpoint-aws` DynamoDBSaver (Floci) |
| RAG | S3 documents + keyword retrieval (Bedrock+OpenSearch roadmap) |
| Messaging | SQS (escalation queue) |
| Observability | LangFuse, LangSmith |
| Local cloud | Floci (`localhost:4566`) |
| API | FastAPI + Uvicorn, deployed as Lambda |
| UI | Streamlit |
| Packaging | Python venv, `requirements.txt`, `docker-compose.yml` |
```
