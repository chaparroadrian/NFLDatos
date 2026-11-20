import os
from pathlib import Path

def cargar_env():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

cargar_env()

from contextlib import asynccontextmanager
import logging
from typing import Any, Iterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend import analytics, schemas


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dashboard" / "dist"
logger = logging.getLogger(__name__)

_engine: analytics.Engine | None = None


def set_engine(engine: analytics.Engine | None) -> None:
    """Replace the process engine, primarily for isolated application tests."""

    global _engine
    _engine = engine


def get_engine() -> analytics.Engine:
    """Return the engine initialized during application startup."""

    if _engine is None:
        raise HTTPException(status_code=503, detail="El motor analítico no está disponible")
    return _engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Iterator[None]:
    """Load approved source tables once before serving requests."""

    set_engine(analytics.load_engine(DATA_DIR))
    try:
        yield
    finally:
        set_engine(None)


app = FastAPI(title="PocketIQ", lifespan=lifespan)


def _validation_field(error: dict[str, Any]) -> str:
    location = tuple(error.get("loc", ()))
    meaningful = [str(part) for part in location if part not in {"body", "path", "query"}]
    return ".".join(meaningful) if meaningful else "request"


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return field-oriented validation errors without echoing rejected values."""

    detail = [
        {"field": _validation_field(error), "message": str(error.get("msg", "valor inválido"))}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


def _json_model(model_type: type[BaseModel], value: Any) -> JSONResponse:
    model = model_type.model_validate(value)
    return JSONResponse(content=analytics.json_safe(model.model_dump()))


def _analysis_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, analytics.TrackingComputationError):
        detail = "El análisis de tracking del Rival no se pudo completar"
    else:
        detail = "El análisis no se pudo completar"
    return HTTPException(status_code=500, detail=detail)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/filters", response_model=schemas.FiltersResponse)
def filters(
    engine: analytics.Engine = Depends(get_engine),
) -> JSONResponse:
    try:
        return _json_model(schemas.FiltersResponse, engine.filters())
    except Exception as exc:
        logger.exception("No se pudieron obtener los filtros")
        raise _analysis_failure(exc) from exc


@app.post("/api/analysis", response_model=schemas.AnalysisResponse)
def analysis(
    request: schemas.AnalysisRequest,
    engine: analytics.Engine = Depends(get_engine),
) -> JSONResponse:
    try:
        return _json_model(schemas.AnalysisResponse, engine.analyze(request))
    except Exception as exc:
        logger.exception("No se pudo completar el análisis")
        raise _analysis_failure(exc) from exc


@app.get(
    "/api/plays/{game_id}/{play_id}",
    response_model=schemas.PlayDetailResponse,
)
def play_detail(
    game_id: int,
    play_id: int,
    engine: analytics.Engine = Depends(get_engine),
) -> JSONResponse:
    try:
        detail = engine.play_detail(game_id, play_id)
    except Exception as exc:
        logger.exception("No se pudo obtener el detalle de jugada")
        raise _analysis_failure(exc) from exc
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"No existe la jugada gameId={game_id} playId={play_id}",
        )
    try:
        return _json_model(schemas.PlayDetailResponse, detail)
    except Exception as exc:
        logger.exception("No se pudo serializar el detalle de jugada")
        raise _analysis_failure(exc) from exc


@app.get("/api/status/{opponent}", response_model=schemas.StatusResponse)
def opponent_status(
    opponent: str,
    engine: analytics.Engine = Depends(get_engine),
) -> JSONResponse:
    try:
        return _json_model(schemas.StatusResponse, engine.rival_status(opponent))
    except Exception as exc:
        logger.exception("No se pudo obtener el estado del Rival")
        raise _analysis_failure(exc) from exc


@app.api_route(
    "/api/{rest:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
def unknown_api_route(rest: str) -> JSONResponse:
    """Keep unknown API requests from falling through to the SPA."""

    return JSONResponse(status_code=404, content={"detail": "Ruta de API no encontrada"})


@app.get("/{full_path:path}", response_model=None)
def serve_dist(full_path: str) -> FileResponse | JSONResponse:
    """Serve built dashboard assets and use index.html for client-side routes."""

    dist_dir = DIST_DIR.resolve()
    requested = (dist_dir / full_path).resolve()
    if not requested.is_relative_to(dist_dir):
        return JSONResponse(status_code=404, content={"detail": "Ruta no encontrada"})

    if requested.is_file():
        return FileResponse(requested)

    index = dist_dir / "index.html"
    if index.is_file():
        return FileResponse(index)

    return JSONResponse(status_code=404, content={"detail": "Dashboard no compilado"})
