# FastAPI integration reference — `POST /ui/api/experiment/run`

This file specifies the exact contract the frontend expects. The Python source
lives outside this repository; nothing here is implemented or mocked in the
frontend.

## Requirements

- The endpoint MUST call the existing
  `run_experiment(consent_sample: int = 60, seed: int = 42) -> dict`
  in `fl-pipeline/run_traced_experiment.py`. Do NOT duplicate or reimplement the
  FL / OTrace logic in the API layer.
- The OTrace service must be running; if it is not, return an error response
  (see below) rather than a partial or simulated result.
- No result may be invented: the response must reflect the run that just
  executed.

## Request

```
POST /ui/api/experiment/run
Content-Type: application/json

{
  "consent_sample": 60,   // optional, integer, defaults to 60
  "seed": 42              // optional, integer, defaults to 42
}
```

Both fields are optional; an empty body `{}` must be accepted and use the
Python defaults.

## Success response — `200`

```json
{
  "status": "completed",
  "started_at": "2026-09-01T19:30:00Z",
  "finished_at": "2026-09-01T19:30:07Z",
  "duration_sec": 6.19,
  "summary": { "...": "same shape as GET /ui/api/summary" }
}
```

- `status` MUST be the literal `"completed"`; the frontend rejects anything else.
- `summary` is optional but recommended: it should be the summary produced by
  this run. Either way, the frontend refetches `GET /ui/api/summary` after a
  successful run, so that endpoint must already reflect the new run.

## Error responses

| Situation | Status | Body |
| --- | --- | --- |
| Endpoint not implemented / wrong method | `404` / `405` | any | 
| OTrace service unavailable | `503` | `{ "detail": "OTrace service unavailable" }` |
| Invalid `consent_sample` / `seed` | `422` | FastAPI validation body |
| Run raised an exception | `500` | `{ "detail": "<error message>" }` |

The frontend treats `404`/`405`/unreachable as **"Run endpoint unavailable"**
and keeps showing the verified fallback data separately. Any other non-2xx is
shown as a failed run with the `detail` text.

## Capability advertisement

`GET /ui/api/summary` SHOULD include:

```json
{ "capabilities": { "run": true } }
```

The **Run Experiment** button stays disabled until the live backend advertises
`capabilities.run === true`. When the field is absent (or the backend is
offline), the frontend assumes no run capability.

## Timeouts and CORS

- The frontend allows up to 600 s for a run to complete.
- For local development the UI is pointed at FastAPI with
  `VITE_OTRACE_API_BASE=http://127.0.0.1:8080` (the default when the variable
  is unset); the service must allow CORS for
  the frontend origin (`POST` and `Content-Type: application/json`).