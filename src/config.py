"""Configuration management for the AI News LinkedIn Agent."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # NewsAPI Configuration
    NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
    NEWSAPI_BASE_URL = "https://newsapi.org/v2"
    
    # LinkedIn Credentials
    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_API_VERSION = os.getenv("LINKEDIN_API_VERSION", "202603")
    LINKEDIN_AUTHOR_URN = os.getenv("LINKEDIN_AUTHOR_URN", "").strip()
    LINKEDIN_PAGE_URN = os.getenv("LINKEDIN_PAGE_URN", "").strip()
    LINKEDIN_PAGE_ID = os.getenv("LINKEDIN_PAGE_ID", "").strip()
    LINKEDIN_DRY_RUN = os.getenv("LINKEDIN_DRY_RUN", "true").strip().lower() in {
        "1", "true", "yes", "on"
    }
    
    # News Keywords
    NEWS_KEYWORDS = os.getenv("NEWS_KEYWORDS", "artificial intelligence,machine learning")
    
    # Scheduling
    SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")
    SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "24"))
    
    @staticmethod
    def validate():
        """Validate that all required configuration is set."""
        if not (Config.LINKEDIN_EMAIL and Config.LINKEDIN_PASSWORD) and not Config.LINKEDIN_ACCESS_TOKEN:
            raise ValueError(
                "Set LINKEDIN_ACCESS_TOKEN for official posting, or LINKEDIN_EMAIL and "
                "LINKEDIN_PASSWORD for the credential-based fallback"
            )

    @staticmethod
    def resolve_linkedin_author_urn() -> str:
        """Return the configured LinkedIn author URN when provided."""
        if Config.LINKEDIN_AUTHOR_URN:
            return Config.LINKEDIN_AUTHOR_URN
        if Config.LINKEDIN_PAGE_URN:
            return Config.LINKEDIN_PAGE_URN
        if Config.LINKEDIN_PAGE_ID:
            return f"urn:li:organization:{Config.LINKEDIN_PAGE_ID}"
        return ""
