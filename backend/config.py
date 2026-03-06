from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HUBSPOT_TOKEN: str
    HUBSPOT_ACCOUNT_ID: str = "5454671"
    AIRCALL_API_ID: str
    AIRCALL_API_TOKEN: str
    ANTHROPIC_API_KEY: str
    DATABASE_URL: str  # postgresql://user:pass@host:5432/dbname (set by Railway automatically)

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()
