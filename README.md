# Multi-Agent RAG Assistant System

An AI-powered customer support and internal support API built with FastAPI, LangGraph, Ollama, Qdrant, Redis, and PostgreSQL.

The project implements a role-aware assistant that can answer customer product questions, support employees with internal process knowledge, keep conversation history, validate inputs and outputs with guardrails, and ingest documents into separate vector knowledge bases.

## What This Project Does

This backend exposes a secured chat API backed by a multi-agent workflow:

1. A user authenticates with JWT.
2. The chat request loads thread history from hybrid memory.
3. An input guardrail validates the user message.
4. An orchestrator chooses the right route.
5. The assistant answers with either RAG or general conversation.
6. An output guardrail checks response quality and can trigger regeneration.
7. New messages and route analytics are saved to Redis and PostgreSQL.

The system is designed around two main user groups:

- `customer`: routed to the customer knowledge base for product, pricing, warranty, return, and support questions.
- `employee` and `admin`: can use the internal process knowledge base, customer knowledge base, and a non-RAG conversation agent.

## Core Features

- FastAPI application with OpenAPI docs at `/docs`.
- JWT authentication with `admin`, `employee`, and `customer` roles.
- Role-based access control for chat, health, ingestion, vector, and database administration routes.
- LangGraph workflow for multi-agent routing and response validation.
- RAG over Qdrant vector collections.
- Dual knowledge bases:
  - `customer_kb` for customer-facing product and support content.
  - `process_kb` for internal HR, IT, policy, and process content.
- Ollama integration for local chat, routing, guardrail, and embedding models.
- Document ingestion pipeline for `.txt`, `.json`, `.csv`, `.pdf`, and `.docx`.
- Upload-time collection targeting with required `.meta` files.
- Automatic, manual, and paused ingestion modes.
- Background ingestion worker with configurable scan interval.
- Hybrid conversation memory:
  - Redis for fast recent-history cache.
  - PostgreSQL for durable conversation, message, user, and analytics storage.
- Input guardrails with rule-based checks, rate limiting, spam detection, prompt-injection checks, and LLM validation.
- Output guardrails for completeness, confidence, hallucination risk, and optional regeneration.
- Health checks for Redis, PostgreSQL, Ollama, Qdrant, and the controller.

## Architecture

```text
Client
  |
  v
FastAPI Controllers
  |
  |-- Auth Service -> PostgreSQL users + JWT
  |-- Chat Service -> LangGraph workflow
  |-- Ingestion Service -> files, chunks, embeddings, Qdrant
  |-- Health Service -> dependency checks
  |
  v
LangGraph Chat Workflow
  |
  |-- Input Guardrail
  |-- Orchestrator
  |     |-- RAG Agent -> Ollama embeddings -> Qdrant -> Ollama chat
  |     |-- Conversation Agent -> Ollama chat
  |-- Output Guardrail
  |
  v
Hybrid Memory
  |
  |-- Redis recent message cache
  |-- PostgreSQL durable history and analytics
```

## Main Tech Stack

- Python 3.12
- FastAPI and Uvicorn
- LangGraph
- Ollama
- Qdrant
- Redis
- PostgreSQL with SQLAlchemy async and asyncpg
- Pydantic and pydantic-settings
- Argon2 password hashing
- JWT authentication

## Project Structure

```text
apps/
  main.py                         FastAPI app entrypoint
  controllers/                    HTTP route handlers
  services/                       Business logic for chat, auth, ingestion, health
  core/
    agents/                       LangGraph agent nodes
    workflow/                     Graph and shared state
    guardrails/                   Input and output validation
    retrieval/                    Embedding search orchestration
    vector_store/                 Qdrant client wrapper
    embeddings/                   Ollama embedding client
    llm/                          Ollama chat client
  ingestion/                      Document loading, chunking, job tracking
  repository/                     Redis, PostgreSQL, user, and memory managers
  models/                         DTOs, entities, validation, ingestion models
  config/                         YAML-backed settings loaded from environment
  prompts/                        Prompt templates for agents and guardrails
data/
  pending/                        Files waiting for ingestion
requirements.txt                  Python dependencies
docker-compose.yml                Redis, PostgreSQL, Ollama, and Qdrant services
Dockerfile                        API image definition
```

## Runtime Dependencies

The API expects these services to be available:

- PostgreSQL on the configured host and port.
- Redis on the configured host and port.
- Qdrant on the configured host and port.
- Ollama with:
  - chat model, for example `gemma3:4b`
  - embedding model, for example `nomic-embed-text`

The provided `docker-compose.yml` starts Redis, PostgreSQL, Ollama, and Qdrant. The API service is currently commented out, so the common local workflow is to run infrastructure with Docker and run FastAPI from the host machine.

## Environment Configuration

Configuration is read from `.env` through YAML files in `apps/config/`.

Important environment groups:

- API: `API_HOST`, `API_PORT`, `CONTROLLER_TIMEOUT`
- PostgreSQL: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_IP`, `POSTGRES_PORT`, `POSTGRES_DATABASE`
- Redis: `REDIS_IP`, `REDIS_PORT`, `REDIS_INDEX_DATABASE`
- Ollama: `LLM_IP`, `LLM_PORT`, `LLM_MODEL`, `LLM_EMBEDDING_MODEL`, temperature and token settings
- Qdrant: `QDRANT_IP`, `QDRANT_PORT`, `QDRANT_CUSTOMER_COLLECTION`, `QDRANT_PROCESS_COLLECTION`, vector and retrieval settings
- Memory: `MEMORY_STRATEGY`, Redis TTL, PostgreSQL pool settings, cache warming
- Ingestion: pending, processing, completed, and failed directories, supported extensions, batch size, scan interval
- Validation: text length, rate limits, spam detection, strategy, guardrail thresholds
- Auth: `AUTH_SECRET_KEY`, `AUTH_ALGORITHM`, `AUTH_MIN_TO_EXPIRE`

Do not commit real secrets. Use a local `.env` for development and inject secrets through your deployment environment in production.

## Quick Start

Start the backing services:

```bash
docker compose up -d redis postgres ollama qdrant
```

Create and activate a Python environment:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn apps.main:app --host localhost --port 8000 --reload
```

Open the API docs:

```text
http://localhost:8000/docs
```

The root URL `/` redirects to `/docs`.

## First-Run Flow

1. Start Redis, PostgreSQL, Ollama, and Qdrant.
2. Start the FastAPI app.
3. Register an admin user with `POST /auth/register`.
4. Use the returned bearer token in Swagger or your HTTP client.
5. Initialize or verify the database with `POST /db/init`.
6. Create vector collections with `POST /vector/collection-create`.
7. Upload or place documents into the pending ingestion directory.
8. Start ingestion with `POST /ingestion/start`.
9. Chat through `POST /chat`.

## Authentication and Roles

Supported roles:

- `admin`: full access to admin routes, ingestion controls, vector collection management, database administration, and chat.
- `employee`: authenticated chat access and employee/admin health access. Employee chat can route to internal process RAG, customer RAG, or conversation.
- `customer`: authenticated chat access to customer-facing RAG.

Authentication endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/register` | Create a user and return a JWT token |
| `POST` | `/auth/login` | Authenticate and return a JWT token |
| `POST` | `/auth/change-password` | Change the current user's password |
| `GET` | `/auth/me` | Return current token user info |

Use the JWT as a bearer token:

```http
Authorization: Bearer <token>
```

## Chat API

Main endpoint:

```http
POST /chat
```

Example request:

```json
{
  "thread_id": "support-thread-1",
  "message": "What is the warranty policy for this laptop?"
}
```

Example response shape:

```json
{
  "thread_id": "support-thread-1",
  "message": "What is the warranty policy for this laptop?",
  "reply": "The assistant response...",
  "route": "rag",
  "health": {},
  "turn_count": 1,
  "loaded_history": 0
}
```

Conversation endpoints:

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| `POST` | `/chat` | Authenticated | Send a chat message |
| `GET` | `/thread/{thread_id}/history` | Authenticated | Load current user's thread history |
| `GET` | `/threads` | Authenticated | List current user's threads with optional date filters |
| `DELETE` | `/thread/{thread_id}` | Admin | Soft-delete a conversation thread |

## Agent Routing

The chat graph uses this flow:

1. `input_guardrail`: handles greetings, blocks invalid or unsafe input, and applies stricter domain validation for customers.
2. `orchestrator`: routes the message.
3. `rag`: retrieves documents from Qdrant and generates a grounded response.
4. `conversation`: handles employee general conversation without retrieval.
5. `output_guardrail`: validates the answer and may add a disclaimer, regenerate, or return a fallback.

Customer routing:

- Always uses RAG.
- Always targets `customer_kb`.

Employee and admin routing:

- Conversation and memory-related messages can route to the conversation agent.
- Internal HR, IT, helpdesk, payroll, onboarding, and policy messages target `process_kb`.
- Product, pricing, warranty, return, and electronics messages target `customer_kb`.
- If keyword routing is inconclusive, the orchestrator asks the LLM to classify the route.

## Document Ingestion

Supported formats:

- `.txt`
- `.json`
- `.csv`
- `.pdf`
- `.docx`

Uploaded files are placed in the pending directory and receive a `.meta` file that records the target collection. The ingestion service requires every pending file to have valid metadata before processing starts.

Example metadata:

```json
{
  "collection": "customer_kb"
}
```

Ingestion pipeline:

1. Validate that all pending files have valid `.meta` files.
2. Move each file to the processing directory.
3. Extract text with the document loader.
4. Split text into overlapping chunks.
5. Generate embeddings with Ollama.
6. Upsert chunks into the target Qdrant collection.
7. Move files and metadata to completed or failed directories.
8. Track job status and history.

Ingestion endpoints:

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/ingestion/status` | Admin | Get current ingestion status |
| `POST` | `/ingestion/upload?collection=customer_kb` | Admin | Upload files for a target collection |
| `GET` | `/ingestion/files` | Admin | List pending files and target collections |
| `POST` | `/ingestion/start` | Admin | Start processing pending files |
| `POST` | `/ingestion/cancel` | Admin | Cancel the running ingestion job |
| `GET` | `/ingestion/history` | Admin | View ingestion job history |
| `GET` | `/ingestion/mode` | Admin | View pipeline mode and worker status |
| `POST` | `/ingestion/mode/{mode}` | Admin | Set `automatic`, `manual`, or `pause` mode |
| `POST` | `/ingestion/resume` | Admin | Resume from paused mode |
| `POST` | `/ingestion/worker/start` | Admin | Start background worker |
| `POST` | `/ingestion/worker/stop` | Admin | Stop background worker |
| `GET` | `/ingestion/worker/status` | Admin | Get worker status |

## Vector Collections

Vector endpoints:

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| `POST` | `/vector/collection-create` | Admin | Create or recreate an allowed Qdrant collection |
| `GET` | `/vector/collections-list` | Admin | List configured customer and process collections |
| `GET` | `/vector/collection-info` | Admin | Get statistics for one collection |

Only the configured customer and process collections are accepted by the collection creation endpoint.

## Health and Database Administration

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | Employee or admin | Check Redis, PostgreSQL, Ollama, Qdrant, and controller status |
| `POST` | `/db/init` | Admin | Initialize PostgreSQL and create tables |
| `GET` | `/db/status` | Admin | Return database initialization and table status |

## Memory and Persistence

The assistant stores conversation state in two layers:

- Redis keeps recent history fast and has a TTL for inactive threads.
- PostgreSQL stores durable conversations, messages, users, and analytics.

Conversation IDs are user-scoped internally as:

```text
<user_id>:<thread_id>
```

This prevents users from reading or writing each other's thread history.

## Development Notes

- The app initializes PostgreSQL tables during startup when possible.
- If startup database initialization fails, use `POST /db/init` after dependencies are ready.
- The background ingestion worker starts automatically only when `INGESTION_AUTO_SCAN_ENABLED` is true.
- Manual ingestion through `POST /ingestion/start` works when the pipeline is not paused.
- Qdrant collections can be auto-created during ingestion if `INGESTION_CREATE_COLLECTION_IF_NOT_EXISTS` is true.
- The included `data/pending` folder contains sample documents and `.meta` files for ingestion testing.

## Tests and Local Checks

The repository includes exploratory test scripts under `apps/test/`:

```bash
python -m apps.test.test_loaders
python -m apps.test.test_rag_components
```

These scripts depend on the configured environment and running services. The RAG test code may need updates if collection names or Qdrant helper signatures change.

## Known Limitations

- The Docker Compose API service is currently commented out.
- The project relies on local Ollama models, so startup and first run depend on model availability.
- Guardrail and routing behavior depends on prompt templates and model responses.
- There is no migration tool configured; tables are created with SQLAlchemy metadata.
- Some test scripts are closer to manual smoke checks than automated CI tests.
