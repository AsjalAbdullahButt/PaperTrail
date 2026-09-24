# Deployment Topology

## The four managed services

PaperTrail's production deployment spans four separate managed services, each responsible for one layer of the stack. The frontend is deployed on Vercel, built from the Next.js app under `frontend/`. The backend is deployed on Render as a Docker container built from `backend/Dockerfile`, running behind Render's own load balancing. The database is MySQL hosted on Aiven, which requires TLS for all connections — Aiven rejects plain, unencrypted connections outright. File storage for uploaded documents uses Cloudflare R2, accessed through the same `boto3` S3-compatible client PaperTrail would use for real AWS S3, since R2 exposes an S3-compatible API.

## Config committed to the repository

Rather than configuring each managed service by hand through its dashboard, PaperTrail commits its deployment configuration as code: `render.yaml` at the repository root defines the backend service and its accompanying Redis instance, and `frontend/vercel.json` defines the frontend build. This is described as "infrastructure as code" in the sense that the configuration is committed and repeatable — it does not mean that zero manual dashboard interaction is ever required.

## Manual steps that cannot be avoided

Even with configuration committed to the repository, a few steps still require a one-time manual action in each provider's dashboard. Render Blueprints (the mechanism that reads `render.yaml`) are applied through the Render dashboard's "New → Blueprint" flow, pointing it at the repository — Render does not currently offer a command-line equivalent to Vercel's `vercel deploy`. Every environment variable marked `sync: false` inside `render.yaml` still has to be typed into the Render dashboard once, after the Blueprint has been applied, because a Blueprint defines the structure of the configuration, not the actual secret values that go into it. On the Vercel side, the environment variable reference named `@papertrail_api_url`, used inside `frontend/vercel.json`, must be created once — via `vercel env add papertrail_api_url production`, with the value set to the deployed Render backend's URL — before that reference resolves to anything at all.

## Deploying the backend

From the Render dashboard, deploying the backend and its Redis instance is a matter of choosing "New → Blueprint," selecting the PaperTrail repository, and applying it — after which the operator must still fill in every `sync: false` variable listed in `backend/DEPLOYMENT.md`, with real values sourced from Aiven (database credentials) and Cloudflare (R2 storage credentials).

## Deploying the frontend

Deploying the frontend to Vercel is done from the `frontend/` directory using the Vercel CLI: installing it globally with `npm i -g vercel`, running `vercel link` to associate the local project with a Vercel project, running `vercel env add papertrail_api_url production` to set the backend URL environment reference, and finally running `vercel --prod` to trigger a production deployment.

## A caveat about Render's YAML schema

Because Render's Blueprint YAML schema can change over time, the exact field names used for a Render Key Value (Redis) resource in `render.yaml` — such as the `type: keyvalue` declaration and the `connectionString` property used to wire that instance's connection string into the backend service's environment — should be checked against Render's current Blueprint documentation before deploying, since a schema change upstream could require small key-name corrections to the committed file.
