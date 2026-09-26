# Local OTrace Dashboard

This repository contains the local dashboard exported from the Lovable prototype.

## Local architecture

- Dashboard: http://127.0.0.1:5173
- Local dashboard API: http://127.0.0.1:8090
- Existing OTrace service: http://127.0.0.1:8080
- Existing FL pipeline: ../otrace-fl-prototype/otrace-fl-prototype/fl-pipeline

## First-time setup

Run `setup-local.bat`. This installs the dashboard dependencies and the small local API dependencies. Internet is needed for this first dependency installation if they are not already cached.

## Normal offline demo

1. Start your existing OTrace service on port 8080.
2. Double-click `start-local-dashboard.bat`.
3. Open http://127.0.0.1:5173

The launcher starts the local API bridge on port 8090 and the dashboard on port 5173. The bridge calls the existing `run_experiment()` in the FL pipeline; it does not duplicate the FL/OTrace research logic.
