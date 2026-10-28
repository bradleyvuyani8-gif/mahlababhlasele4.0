from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Mahlabahlasele 4.0"
    websocket_route: str = "/ws"
    database_file: str = "data/telemetry.db"


settings = Settings()
