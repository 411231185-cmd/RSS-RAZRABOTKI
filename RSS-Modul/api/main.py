import logging
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from skills.tasks_registry import run_task, TASK_MAP

logger = logging.getLogger(__name__)
app = FastAPI(title="RSS-Modul API", version="1.0.0")


class RunTaskRequest(BaseModel):
    task_id: str
    params: Optional[Dict[str, Any]] = {}


class RunTaskResponse(BaseModel):
    task_id: str
    status: str
    result: Dict[str, Any]


@app.get("/api/health")
def health():
    return {"status": "ok", "available_tasks": list(TASK_MAP.keys())}


@app.post("/api/run-task", response_model=RunTaskResponse)
def api_run_task(request: RunTaskRequest):
    try:
        result = run_task(request.task_id, **(request.params or {}))
        return RunTaskResponse(task_id=request.task_id, status="success", result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Task failed: {request.task_id}")
        raise HTTPException(status_code=500, detail=f"Task failed: {e}")
