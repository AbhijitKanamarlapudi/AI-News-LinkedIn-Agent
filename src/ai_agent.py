"""Main AI News LinkedIn Agent orchestrator."""

from apscheduler.schedulers.background import BackgroundScheduler
from src.news_fetcher import NewsFetcher
from src.linkedin_poster import LinkedInPoster
from src.config import Config
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AINewsLinkedInAgent:
    """Main agent that coordinates news fetching and LinkedIn posting."""
    
    def __init__(self):
        """Initialize the agent with fetcher and poster."""
        self.news_fetcher = NewsFetcher()
        self.linkedin_poster = LinkedInPoster(
            Config.LINKEDIN_EMAIL,
            Config.LINKEDIN_PASSWORD,
            dry_run=Config.LINKEDIN_DRY_RUN,
            access_token=Config.LINKEDIN_ACCESS_TOKEN,
            api_version=Config.LINKEDIN_API_VERSION,
            author_urn=Config.resolve_linkedin_author_urn(),
        )
        self.scheduler = None
    
    def run_once(self) -> None:
        """
        Run the agent once: fetch news and publish a single LinkedIn post.
        """
        try:
            logger.info("🚀 Starting AI News LinkedIn Agent...")
            
            # Fetch latest AI news
            logger.info("📰 Fetching curated Data Platform + AI updates...")
            articles = self.news_fetcher.fetch_multiple_keywords()
            
            if not articles:
                logger.warning("❌ No articles found")
                return
            
            logger.info(f"✅ Found {len(articles)} candidate articles")
            
            # Publish a single LinkedIn post per run
            logger.info(
                "📤 %s one article to LinkedIn...",
                "Dry-running" if Config.LINKEDIN_DRY_RUN else "Posting"
            )
            success_count = self.linkedin_poster.post_multiple(articles, max_posts=1)
            
            logger.info(
                "✅ Completed %s for %s article(s) in this run",
                "dry run" if Config.LINKEDIN_DRY_RUN else "posting",
                success_count,
            )
            
            # Display summary
            self.linkedin_poster.display_posts_summary()
            
        except Exception as e:
            logger.error(f"❌ Error in agent: {e}")
    
    def start_scheduler(self, interval_hours: int = 24) -> None:
        """
        Start the scheduler to run the agent at regular intervals.
        
        Args:
            interval_hours: Interval in hours between runs
        """
        try:
            Config.validate()
            
            # Run once immediately
            logger.info("Starting first run...")
            self.run_once()
            
            self.scheduler = BackgroundScheduler()
            
            # Add job to run every N hours after the first run
            self.scheduler.add_job(
                self.run_once,
                'interval',
                hours=interval_hours,
                id='ai_news_job'
            )
            
            self.scheduler.start()
            logger.info(f"✅ Scheduler started - running every {interval_hours} hour(s)")
            
            # Keep the scheduler running
            try:
                while True:
                    pass
            except KeyboardInterrupt:
                logger.info("⏹️  Stopping scheduler...")
                self.scheduler.shutdown()
                
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("⏹️  Scheduler stopped")


def main():
    """Main entry point for the agent."""
    agent = AINewsLinkedInAgent()
    agent.start_scheduler(interval_hours=Config.SCHEDULE_INTERVAL_HOURS)


if __name__ == "__main__":
    main()
