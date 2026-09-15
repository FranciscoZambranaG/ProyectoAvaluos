from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, appraisals, auth, dashboard, gis, public_config

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(appraisals.router)
app.include_router(gis.router)
app.include_router(admin.router)
app.include_router(public_config.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}
