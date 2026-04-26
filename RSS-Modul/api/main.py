"""
RSS-Modul HTTP API на FastAPI.

Запуск:
    uvicorn api.main:app --reload --port 8000

Универсальный endpoint:
    POST /api/run-task { "task_id": "...", "params": {...} }

Шорткаты:
    POST /api/collect
    POST /api/generate
    POST /api/validate
    POST /api/export
    GET  /api/health
    GET  /api/stats
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipelines.collect_raw_pipeline import collect_raw_from_source
from pipelines.generate_descriptions_pipeline import generate_descriptions
from pipelines.validate_pipeline import validate_descriptions, fetch_invalid
from pipelines.export_pipeline import export_promportal
from storage.db import init_db, get_connection

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RSS-Modul API",
    version="1.0.0",
    description="Backend для каталога запчастей ТД РУССтанкоСбыт",
)


# ---------- Модели запросов / ответов ---------------------------------------

class CollectParams(BaseModel):
    source: str = "promportal_export"
    code_prefix: Optional[str] = None
    file_path: Optional[str] = None


class GenerateParams(BaseModel):
    model_id: str = "claude-sonnet"
    code_prefix: Optional[str] = None
    add_services_block: bool = False


class ValidateParams(BaseModel):
    text_type: str = "newdescriptiontop"
    code_prefix: Optional[str] = None


class ExportParams(BaseModel):
    template_path: Optional[str] = None
    output_path: Optional[str] = None
    code_prefix: Optional[str] = None
    add_services_block: bool = False
    text_type: str = "newdescriptiontop"


class RunTaskRequest(BaseModel):
    task_id: str = Field(..., description="collect | generate | validate | export")
    params: Dict[str, Any] = {}


class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Dict[str, Any]


# ---------- Реестр задач для универсального /api/run-task --------------------

def _task_collect(params: dict) -> Dict[str, Any]:
    p = CollectParams(**params)
    return collect_raw_from_source(
        source=p.source,
        code_prefix=p.code_prefix,
        file_path=p.file_path,
    )


def _task_generate(params: dict) -> Dict[str, Any]:
    p = GenerateParams(**params)
    return generate_descriptions(
        model_id=p.model_id,
        code_prefix=p.code_prefix,
        add_services_block=p.add_services_block,
    )


def _task_validate(params: dict) -> Dict[str, Any]:
    p = ValidateParams(**params)
    return validate_descriptions(
        text_type=p.text_type,
        code_prefix=p.code_prefix,
    )


def _task_export(params: dict) -> Dict[str, Any]:
    p = ExportParams(**params)
    return export_promportal(
        template_path=Path(p.template_path) if p.template_path else None,
        output_path=Path(p.output_path) if p.output_path else None,
        code_prefix=p.code_prefix,
        add_services_block=p.add_services_block,
        text_type=p.text_type,
    )


TASK_REGISTRY = {
    "collect":  _task_collect,
    "generate": _task_generate,
    "validate": _task_validate,
    "export":   _task_export,
}


# ---------- Endpoints --------------------------------------------------------

@app.get("/api/health")
def health():
    """Проверка работоспособности и список задач."""
    return {
        "status": "ok",
        "available_tasks": list(TASK_REGISTRY.keys()),
        "version": app.version,
    }


@app.get("/api/stats")
def stats():
    """Сводная статистика по БД (без долгих операций)."""
    init_db()
    with get_connection() as conn:
        products = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
        descs = conn.execute("SELECT COUNT(*) AS n FROM source_descriptions").fetchone()["n"]
        gen = conn.execute("SELECT COUNT(*) AS n FROM generated_texts").fetchone()["n"]
        try:
            valid = conn.execute(
                "SELECT COUNT(*) AS n FROM validation_results WHERE is_valid = 1"
            ).fetchone()["n"]
            invalid = conn.execute(
                "SELECT COUNT(*) AS n FROM validation_results WHERE is_valid = 0"
            ).fetchone()["n"]
        except Exception:
            valid = invalid = None
    return {
        "products": products,
        "source_descriptions": descs,
        "generated_texts": gen,
        "validation": {"valid": valid, "invalid": invalid},
    }


@app.post("/api/run-task", response_model=TaskResponse)
def run_task(req: RunTaskRequest):
    """Универсальный endpoint для запуска любой задачи."""
    if req.task_id not in TASK_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id '{req.task_id}'. Available: {list(TASK_REGISTRY.keys())}",
        )
    try:
        result = TASK_REGISTRY[req.task_id](req.params)
        return TaskResponse(task_id=req.task_id, status="success", result=result)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Task failed: %s", req.task_id)
        raise HTTPException(status_code=500, detail=f"Task failed: {e}")


# ---------- Шорткаты с типизированными моделями ------------------------------

@app.post("/api/collect")
def api_collect(params: CollectParams):
    try:
        return {"status": "success", "result": _task_collect(params.dict())}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("collect failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
def api_generate(params: GenerateParams):
    try:
        return {"status": "success", "result": _task_generate(params.dict())}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("generate failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validate")
def api_validate(params: ValidateParams):
    try:
        return {"status": "success", "result": _task_validate(params.dict())}
    except Exception as e:
        logger.exception("validate failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/validate/invalid")
def api_validate_invalid(text_type: str = "newdescriptiontop", code_prefix: Optional[str] = None):
    """Получить список невалидных записей с детализацией ошибок."""
    try:
        items = fetch_invalid(text_type, code_prefix)
        return {"status": "success", "count": len(items), "items": items}
    except Exception as e:
        logger.exception("fetch_invalid failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export")
def api_export(params: ExportParams):
    try:
        return {"status": "success", "result": _task_export(params.dict())}
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("export failed")
        raise HTTPException(status_code=500, detail=str(e))