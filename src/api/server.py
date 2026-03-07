from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import deps
from src.api.routes import strategy, experiments


def create_app(db_path: str = "data/trading_agent.duckdb",
               strategies_dir: str = "strategies") -> FastAPI:
    deps.configure(db_path, strategies_dir)

    app = FastAPI(title="Quant Autoresearch API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(strategy.router)
    app.include_router(experiments.router)
    return app


app = create_app()
