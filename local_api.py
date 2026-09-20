import os,sys,time,threading,importlib.util
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
import requests
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field

OTRACE=os.getenv("OTRACE_URL","http://127.0.0.1:8080").rstrip("/")
ROOT=Path(__file__).resolve().parent

def find_pipeline():
    env=os.getenv("OTRACE_FL_PIPELINE")
    candidates=[Path(env)] if env else []
    candidates += [ROOT.parent/"otrace-fl-prototype"/"otrace-fl-prototype"/"fl-pipeline",ROOT.parent/"fl-pipeline"]
    for p in candidates:
        if p and (p/"run_traced_experiment.py").exists(): return p.resolve()
    return None
PIPELINE=find_pipeline()
app=FastAPI(title="OTrace Local Dashboard API")
app.add_middleware(CORSMiddleware,allow_origins=["http://127.0.0.1:5173","http://localhost:5173"],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["Content-Type","Accept"])
lock=threading.Lock(); last_summary:dict[str,Any]={}
class RunRequest(BaseModel):
    consent_sample:int=Field(60,ge=1)
    seed:int=Field(42,ge=0)
def otr_available():
    try:return requests.get(OTRACE+"/docs",timeout=2).status_code<500
    except requests.RequestException:return False
def load_runner():
    if PIPELINE is None: raise RuntimeError("FL pipeline not found. Set OTRACE_FL_PIPELINE to the fl-pipeline folder.")
    if str(PIPELINE) not in sys.path:sys.path.insert(0,str(PIPELINE))
    old=os.getcwd();os.chdir(PIPELINE)
    try:
        spec=importlib.util.spec_from_file_location("otrace_run_traced_experiment",PIPELINE/"run_traced_experiment.py")
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        return mod.run_experiment
    finally:os.chdir(old)
def normalize(result):
    if isinstance(result,dict):
        if isinstance(result.get("summary"),dict):return result["summary"]
        return result
    return {}
@app.get("/health")
def health():return {"ok":True,"otrace":otr_available(),"pipeline":str(PIPELINE) if PIPELINE else None}
@app.get("/ui/api/summary")
def summary():
    base={"meta":{"source":"local backend"},"capabilities":{"run":PIPELINE is not None and otr_available()}}
    base.update(last_summary);return base
@app.post("/ui/api/experiment/run")
def run(body:RunRequest):
    global last_summary
    if not otr_available():raise HTTPException(503,"OTrace service unavailable on "+OTRACE)
    if PIPELINE is None:raise HTTPException(500,"FL pipeline not found. Set OTRACE_FL_PIPELINE.")
    if not lock.acquire(blocking=False):raise HTTPException(409,"A run is already in progress")
    started=datetime.now(timezone.utc);t=time.perf_counter()
    try:
        runner=load_runner();old=os.getcwd();os.chdir(PIPELINE)
        try:result=runner(consent_sample=body.consent_sample,seed=body.seed)
        finally:os.chdir(old)
        last_summary=normalize(result);finished=datetime.now(timezone.utc)
        return {"status":"completed","started_at":started.isoformat(),"finished_at":finished.isoformat(),"duration_sec":round(time.perf_counter()-t,3),"summary":last_summary}
    except HTTPException:raise
    except Exception as e:raise HTTPException(500,str(e))
    finally:lock.release()
