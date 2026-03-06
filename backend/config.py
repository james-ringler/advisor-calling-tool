from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HUBSPOT_TOKEN: str
    HUBSPOT_ACCOUNT_ID: str = "5454671"
    AIRCALL_API_ID: str
    AIRCALL_API_TOKEN: str
    ANTHROPIC_API_KEY: str
    DATABASE_URL: str  # postgresql://user:pass@host:5432/dbname (set by Railway automatically)

    # Google Calendar OAuth — set in Railway dashboard when enabling calendar feature
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


settings = Settings()
