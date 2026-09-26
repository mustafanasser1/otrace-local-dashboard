from fastapi import FastAPI
from routers import introduction, attestation, consent, data_use, data_subject_request, trace, check

app = FastAPI(
    title="Otrace API V1 (Local)",
    description="OTrace v0.5 adapted for local development. SQLite backend, no auth.",
    version="0.5-local",
)

# No authentication for local development.
# All routers are public.
for router in [
    introduction.router,
    attestation.router,
    consent.router,
    data_use.router,
    data_subject_request.router,
    trace.router,
    check.router,
]:
    app.include_router(router)


@app.get("/")
def home():
    return {"message": "Welcome to OTrace V1 (Local SQLite)"}


if __name__ == "__main__":
    import uvicorn

    from config import host, port

    uvicorn.run(app, host=host(), port=port())
