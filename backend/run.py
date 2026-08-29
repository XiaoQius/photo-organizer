"""PyInstaller 打包入口：照片整理工具单程序启动。"""
import os

if os.environ.get("PHOTO_ORGANIZER_NO_BROWSER") != "1":
    os.environ.setdefault("PHOTO_ORGANIZER_START_BROWSER", "1")

from app.main import app, _find_free_port  # noqa: E402


def main():
    import threading
    import webbrowser

    import uvicorn

    port = _find_free_port(8010)
    url = f"http://127.0.0.1:{port}"
    if os.environ.get("PHOTO_ORGANIZER_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
