from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from garminview.core.config import get_config
from garminview.core.logging import configure_logging
from garminview.core.database import get_session_factory
from garminview.api import deps


def create_app(engine: Engine | None = None) -> FastAPI:
    config = get_config()
    configure_logging(config.log_level)

    if engine is None:
        from garminview.core.database import create_db_engine
        engine = create_db_engine(config)

    app = FastAPI(title="GarminView API", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from garminview.api.routes import health_check, activities, training, body, admin, sync, assessments, export, nutrition

    app.include_router(health_check.router, prefix="/health", tags=["health"])
    app.include_router(activities.router, prefix="/activities", tags=["activities"])
    app.include_router(training.router, prefix="/training", tags=["training"])
    app.include_router(body.router, prefix="/body", tags=["body"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    app.include_router(sync.router, prefix="/sync", tags=["sync"])
    app.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
    app.include_router(export.router)
    app.include_router(nutrition.router, prefix="/nutrition", tags=["nutrition"])

    from garminview.api.routes import actalog as actalog_routes
    app.include_router(actalog_routes.router, prefix="/actalog", tags=["actalog"])
    app.include_router(actalog_routes.admin_router, prefix="/admin/actalog", tags=["actalog-admin"])

    # Wire real DB session factory via dependency_overrides
    factory = get_session_factory(engine)

    def get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[deps.get_db] = get_db

    @app.get("/")
    def root():
        return {"status": "ok", "version": "0.3.0"}

    return app
