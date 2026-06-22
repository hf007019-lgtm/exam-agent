import os

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _env_float(name: str, default: float, minimum: float) -> float:
    try:
        value = float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


class Settings:
    """项目配置。

    第一版只读取必要配置，避免引入额外配置框架。
    """

    def __init__(self) -> None:
        """从环境变量读取配置，没有配置时使用默认值。"""
        self.APP_NAME = os.getenv("APP_NAME", "Exam Agent")
        self.RAG_ENABLED = _env_bool("RAG_ENABLED", True)
        self.RAG_BASE_URL = (
            os.getenv("RAG_BASE_URL")
            or os.getenv("RAG_BUILDER_BASE_URL")
            or "http://127.0.0.1:18000"
        )
        self.RAG_ASK_PATH = os.getenv("RAG_ASK_PATH") or "/api/v1/search/ask"
        self.RAG_TIMEOUT_SECONDS = _env_float("RAG_TIMEOUT_SECONDS", 20.0, 0.1)
        self.RAG_TOP_K = _env_int("RAG_TOP_K", 5, 1, 20)
        self.RAG_BUILDER_BASE_URL = self.RAG_BASE_URL
        self.LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.LLM_API_KEY = os.getenv("LLM_API_KEY", "")
        self.LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "sqlite:///data/exam_agent.db",
        )
        self.AUTH_ENABLED = _env_bool("AUTH_ENABLED", False)
        self.JWT_SECRET_KEY = os.getenv(
            "JWT_SECRET_KEY",
            "dev-secret-change-me",
        )
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRE_MINUTES = _env_int(
            "JWT_EXPIRE_MINUTES",
            10080,
            5,
            525600,
        )
        self.DEV_LOGIN_ENABLED = _env_bool("DEV_LOGIN_ENABLED", True)
        self.DEFAULT_DEV_USERNAME = os.getenv(
            "DEFAULT_DEV_USERNAME",
            "anonymous_dev",
        )
        self.API_RESULT_LIMIT = _env_int("API_RESULT_LIMIT", 100, 1, 500)
        self.OBSERVABILITY_TEXT_LIMIT = _env_int(
            "OBSERVABILITY_TEXT_LIMIT",
            2000,
            200,
            20000,
        )


settings = Settings()
