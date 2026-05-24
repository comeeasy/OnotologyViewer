from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    fuseki_base_url: str = "http://localhost:3030"
    fuseki_admin_user: str = "admin"
    fuseki_admin_password: str = "admin"

    model_config = {"env_file": ".env"}


settings = Settings()
