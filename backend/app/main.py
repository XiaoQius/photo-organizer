import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import ai, db, duplicates, jobs, media, organize, scan, settings, stats, watch
from app.database import init_db

app = FastAPI(title="照片视频整理工具", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/api/scan", tags=["扫描"])
app.include_router(media.router, prefix="/api/media", tags=["媒体库"])
app.include_router(organize.router, prefix="/api/organize", tags=["整理"])
app.include_router(duplicates.router, prefix="/api/duplicates", tags=["重复检测"])
app.include_router(stats.router, prefix="/api/stats", tags=["统计"])
app.include_router(settings.router, prefix="/api/settings", tags=["设置"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI 打标"])
app.include_router(watch.router, prefix="/api/watch", tags=["文件夹监控"])
app.include_router(db.router, prefix="/api/db", tags=["数据库备份"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["后台任务"])

# 托管前端构建产物（开发：frontend/dist；打包：随程序内置）
import sys as _sys
if getattr(_sys, "frozen", False):
    frontend_dist = Path(_sys._MEIPASS) / "frontend_dist"
else:
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    # SPA 回退：非 API 路径 404 时返回 index.html，支持前端路由刷新
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(frontend_dist / "index.html")
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.on_event("startup")
def on_startup():
    init_db()
    from app.services import watcher
    watcher.restart_if_enabled()


def _find_free_port(start: int = 8010) -> int:
    import socket
    port = start
    while port < start + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return start


if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    port = _find_free_port(8010)
    url = f"http://127.0.0.1:{port}"

    def _open_browser():
        webbrowser.open(url)

    if os.environ.get("PHOTO_ORGANIZER_NO_BROWSER") != "1":
        threading.Timer(1.5, _open_browser).start()

    if getattr(_sys, "frozen", False):
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    else:
        uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
