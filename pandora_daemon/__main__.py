import uvicorn
from pathlib import Path
from pandora_daemon.config import load_config

def main():
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    from pandora_daemon.app import create_app
    app = create_app()
    uvicorn.run(app, host=config.server.host, port=config.server.port)

if __name__ == "__main__":
    main()
