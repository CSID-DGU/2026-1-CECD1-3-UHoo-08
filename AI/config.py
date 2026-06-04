from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DASHSCOPE_API_KEY: str = ""
    QWEN_VL_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_VL_MODEL: str = "qwen3-vl-flash"
    # LLM agent (Ollama self-hosted)
    EXAONE_BASE_URL: str = "http://localhost:11434/v1"
    EXAONE_MODEL: str = "qwen2.5:7b"
    EXAONE_API_KEY: str = "ollama"

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_USE_FP16: bool = False
    HF_HOME: str = "/app/.cache/huggingface"

    # Vector search
    VECTOR_SEARCH_EF_SEARCH: int = 40

    # Monitoring - LangSmith
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "capstone-ai"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()