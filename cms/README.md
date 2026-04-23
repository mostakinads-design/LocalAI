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
