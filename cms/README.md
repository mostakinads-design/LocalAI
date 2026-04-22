# Laravel 12 + Filament 4 CMS (Modular Integration)

This repository includes an optional CMS stack designed to stay decoupled from the LocalAI core.

## What is included

- `docker-compose.cms.yaml`:
  - `cms`: Bootstraps Laravel 12 and installs Filament 4 on first run.
  - `python-llm-bridge` (optional profile): Example app integration for task updates, prompt creation, and model options.
  - `greswitch-bridge` (optional profile): Example app connector profile.
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

## Extending to integrate any app

1. Add a new app connector service in `docker-compose.cms.yaml` (or a compose override file).
2. Expose endpoints for:
   - `/tasks/update`
   - `/prompts/create`
   - `/models/options`
3. Add the connector name to `CMS_APP_CONNECTORS`.
   - Example: `CMS_APP_CONNECTORS=python-llm-bridge,greswitch-bridge`
4. Keep each connector in its own folder under `cms/apps/<connector-name>/` for modular growth.

This keeps the architecture extensible so new applications can be integrated without changing LocalAI core services.
