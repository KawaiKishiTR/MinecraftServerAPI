from pathlib import Path
import uvicorn
import os



if __name__ == "__main__":
    os.environ["APP_ROOT_DIR"] = str(Path(__file__).parent)

    from app.config import load_config
    cfg = load_config("config.yml")


    from app.logger import setup_logging
    setup_logging()

    from app.app import fastapi
    uvicorn.run("app.app:fastapi", host=cfg.server.host, port=cfg.server.port, reload=cfg.server.debug)