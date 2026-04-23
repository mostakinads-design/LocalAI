# Laravel 12 + Filament 4 CMS (Modular Integration)

This repository includes an optional CMS stack designed to stay decoupled from the LocalAI core.

## What is included

- `docker-compose.cms.yaml`:
  - `cms`: Bootstraps Laravel 12 and installs Filament 4 on first run.
  - `python-llm-bridge` (optional profile): App connector for task tracking, prompt creation, and model options.
  - `greswitch-bridge` (optional profile): Greswitch app connector profile.
  - `api` (optional profile): LocalAI service for a full local AI-powered setup.

## Start CMS only

```bash
docker compose -f docker-compose.cms.yaml up -d cms
```

CMS URL: `http://localhost:8090`

## Start CMS + app connectors

```bash
docker compose -f docker-compose.cms.yaml --profile python-llm --profile greswitch up -d
```

## Start CMS + LocalAI + connectors

```bash
docker compose -f docker-compose.cms.yaml --profile with-localai --profile python-llm --profile greswitch up -d
```

## Connector API endpoints

Each bridge service exposes the following endpoints:

| Method | Endpoint          | Description                                      |
|--------|-------------------|--------------------------------------------------|
| GET    | `/health`         | Service health check                             |
| GET    | `/config`         | View current loaded configuration                |
| POST   | `/config/reload`  | Hot-reload `config.json` **without restarting**  |
| GET    | `/tasks`          | List all tracked task processes and their status |
| GET    | `/tasks/<id>`     | Get detail of a specific task by ID              |
| POST   | `/tasks/update`   | Create or update a task with status tracking     |
| POST   | `/prompts/create` | Create a named prompt                            |
| GET    | `/models/options` | List AI model options from config *(python-llm bridge only)* |
| GET    | `/capabilities`   | List connector capabilities *(greswitch only)*   |

## Dynamic config loading

Edit `cms/apps/python-llm-bridge/config.json` or `cms/apps/greswitch-bridge/config.json`
then hot-reload without restarting:

```bash
curl -X POST http://localhost:8010/config/reload
```

## Viewing task processes

```bash
# List all tasks
curl http://localhost:8010/tasks

# View a specific task
curl http://localhost:8010/tasks/task-1
```

## Example: create a task, advance status, then read it

```bash
# Start a task
curl -X POST http://localhost:8010/tasks/update \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"job-42","status":"running","model":"qwen3","prompt":"Summarise this"}'

# Mark it done
curl -X POST http://localhost:8010/tasks/update \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"job-42","status":"done","result":"Summary text here"}'

# View it
curl http://localhost:8010/tasks/job-42
```

---

## laravel-ai-cms integration

Integrates [`sanchit237/laravel-ai-cms`](https://github.com/sanchit237/laravel-ai-cms) — a
Laravel 10 article CMS with **AI-generated slugs and summaries** — backed by LocalAI instead of
OpenAI.

### Architecture

```
laravel-ai-cms  ──POST /v1/chat/completions──►  laravel-ai-cms-bridge (port 8012)
                                                         │
                                                  records task +
                                                  forwards to LocalAI
                                                         │
                                                         ▼
                                                  LocalAI api (port 8080)
```

The bridge is an OpenAI-compatible proxy that **records every slug / summary generation as a
tracked task**, visible in real time at `http://localhost:8012/tasks`.

### Quick start

```bash
# 1. Clone the CMS app into the expected path
git clone https://github.com/sanchit237/laravel-ai-cms cms/laravel-ai-cms

# 2. Copy the LocalAI env template (no OpenAI key needed)
cp cms/laravel-ai-cms/.env.localai cms/laravel-ai-cms/.env

# 3. Start everything (CMS app + MySQL + queue worker + bridge + LocalAI)
docker compose -f docker-compose.cms.yaml \
  --profile laravel-ai-cms --profile with-localai up -d
```

| Service | URL |
|---|---|
| Laravel CMS API | http://localhost:8091 |
| Task visibility (bridge) | http://localhost:8012/tasks |
| LocalAI API | http://localhost:8080/v1 |

### Watching AI generation tasks

```bash
# See all slug/summary generation jobs that ran (or are running)
curl http://localhost:8012/tasks

# Detail of one task
curl http://localhost:8012/tasks/<task-id>
```

### Hot-reload model config

Edit `cms/apps/laravel-ai-cms-bridge/config.json` (e.g. to change `override_model`) then:

```bash
curl -X POST http://localhost:8012/config/reload
```

### Default credentials (from laravel-ai-cms seeder)

| Role | Email | Password |
|---|---|---|
| Admin | admin@example.com | password |
| Author | author@example.com | password |

### Key environment variables (`.env.localai`)

| Variable | Value | Purpose |
|---|---|---|
| `OPENAI_BASE_URL` | `http://laravel-ai-cms-bridge:8012/v1` | Routes AI calls through the tracking bridge |
| `OPENAI_API_KEY` | `localai` | Any non-empty value — LocalAI doesn't validate keys |
| `DB_HOST` | `laravel-ai-cms-mysql` | MySQL container name |
| `QUEUE_CONNECTION` | `database` | Async slug/summary jobs use the DB queue |

---

## crm-billing integration (Liberu CRM — billing invoice auto-generation)

Integrates [`mostakinads-design/crm-laravel`](https://github.com/mostakinads-design/crm-laravel)
— a Laravel 12 + Filament 5 CRM with contacts, deals, and billing — with LocalAI for
**AI-powered billing invoice auto-generation**.

When a deal is created or reaches a configured stage, the CRM queue worker calls the bridge's
`/invoices/generate` endpoint. LocalAI receives the deal data, generates a complete, structured
invoice (line items, totals, tax, payment terms), and the result is recorded as a tracked task.

### Architecture

```
Liberu CRM queue worker
        │ POST /invoices/generate   (or POST /v1/chat/completions)
        ▼
crm-billing-bridge (port 8013)  ── records task ──► GET /tasks (task visibility)
        │
        │ POST /v1/chat/completions (structured invoice prompt)
        ▼
LocalAI api (port 8080)
        │
        ▼ structured invoice JSON
crm-billing-bridge
        │ stores result on task
        ▼
CRM receives invoice object → creates invoice record in DB
```

### Quick start

```bash
# 1. Clone the Liberu CRM app into the expected path
git clone https://github.com/mostakinads-design/crm-laravel cms/crm-billing

# 2. Copy the LocalAI env template
cp cms/crm-billing/.env.localai cms/crm-billing/.env

# 3. Start everything (CRM + MySQL + queue worker + bridge + LocalAI)
docker compose -f docker-compose.cms.yaml \
  --profile crm-billing --profile with-localai up -d
```

| Service | URL |
|---|---|
| Liberu CRM | http://localhost:8093 |
| Invoice task visibility | http://localhost:8013/tasks |
| LocalAI API | http://localhost:8080/v1 |

### Invoice auto-generation API

The bridge exposes a dedicated invoice generation endpoint that any service can call:

```bash
curl -X POST http://localhost:8013/invoices/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_name": "Acme Corp",
    "customer_email": "billing@acme.com",
    "company": "Acme Corp",
    "deal_title": "Annual SaaS Subscription",
    "deal_value": 4800,
    "currency": "USD",
    "products": "SaaS platform access (12 months), Priority support",
    "notes": "Renewing from last year"
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-...",
  "invoice": {
    "invoice_number": "INV-2024-0001",
    "issue_date": "2024-04-23",
    "due_date": "2024-05-23",
    "currency": "USD",
    "client": { "name": "Acme Corp", "email": "billing@acme.com" },
    "line_items": [
      { "description": "SaaS platform access (12 months)", "quantity": 1, "unit_price": 4400, "total": 4400 },
      { "description": "Priority support", "quantity": 1, "unit_price": 400, "total": 400 }
    ],
    "subtotal": 4800,
    "tax_rate": 0.1,
    "tax_amount": 480,
    "total": 5280,
    "payment_terms": "Net 30",
    "notes": "Thank you for renewing!"
  }
}
```

### Watching invoice generation tasks

```bash
# List all invoice and AI generation jobs
curl http://localhost:8013/tasks

# Detail of a specific job (includes invoice_number, total, customer, deal)
curl http://localhost:8013/tasks/<task-id>
```

### Hot-reload model / prompt config

Edit `cms/apps/crm-billing-bridge/config.json` then:

```bash
curl -X POST http://localhost:8013/config/reload
```

To use a different model per request without restarting, set `override_model` to `null` in
`config.json` and pass `"model": "mistral"` in your invoice generate request body.

### Calling the bridge from a Laravel queue job

Add this to a Laravel job in the CRM codebase:

```php
$response = Http::post('http://crm-billing-bridge:8013/invoices/generate', [
    'customer_name' => $deal->contact->name,
    'customer_email' => $deal->contact->email,
    'company'       => $deal->contact->company,
    'deal_title'    => $deal->title,
    'deal_value'    => $deal->value,
    'currency'      => $deal->currency ?? 'USD',
    'products'      => $deal->products->pluck('name')->implode(', '),
]);

if ($response->successful()) {
    $invoice = $response->json('invoice');
    Invoice::createFromAI($deal, $invoice);
}
```

### Key environment variables (`.env.localai`)

| Variable | Value | Purpose |
|---|---|---|
| `OPENAI_BASE_URL` | `http://crm-billing-bridge:8013/v1` | Routes CRM AI calls through the tracking bridge |
| `OPENAI_API_KEY` | `localai` | Any non-empty value — LocalAI doesn't validate keys |
| `DB_HOST` | `crm-billing-mysql` | MySQL 8 container |
| `QUEUE_CONNECTION` | `database` | Invoice generation uses DB queue |

---

## Extending to integrate any app

1. Add a new app connector service in `docker-compose.cms.yaml` (or a compose override file).
2. Expose endpoints for:
   - `/tasks/update`
   - `/tasks`
   - `/prompts/create`
   - `/models/options`
   - `/config/reload`
3. Add the connector name to `CMS_APP_CONNECTORS`.
   - Example: `CMS_APP_CONNECTORS=python-llm-bridge,greswitch-bridge`
4. Keep each connector in its own folder under `cms/apps/<connector-name>/` for modular growth.

This keeps the architecture extensible so new applications can be integrated without changing LocalAI core services.
