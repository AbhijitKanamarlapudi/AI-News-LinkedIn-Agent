"""LinkedIn posting module for sharing AI news."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from linkedin_api import Linkedin

logger = logging.getLogger(__name__)


class LinkedInPoster:
    """Handle sharing AI news to LinkedIn profile."""
    
    def __init__(
        self,
        email: str,
        password: str,
        dry_run: bool = True,
        access_token: str = "",
        api_version: str = "202603",
        author_urn: str = "",
    ):
        """
        Initialize LinkedIn poster setup.
        
        Args:
            email: LinkedIn email
            password: LinkedIn password (stored for reference)
            dry_run: When True, generate and log posts without publishing
            access_token: Official LinkedIn OAuth access token
            api_version: LinkedIn API version for official REST calls
            author_urn: Optional LinkedIn member or organization URN to post as
        """
        self.email = email
        self.password = password
        self.dry_run = dry_run
        self.access_token = access_token
        self.api_version = api_version
        self.author_urn = author_urn.strip()
        self.client: Optional[Linkedin] = None
        self.owner_urn: Optional[str] = None
        self.posted_articles = []
        self.posts_file = Path("posted_articles.json")
        self.load_posted_articles()

    def authenticate(self) -> None:
        """Authenticate with LinkedIn and cache the posting identity."""
        if self.client is not None and self.owner_urn is not None:
            return

        logger.info("Authenticating with LinkedIn for %s", self.email)
        self.client = Linkedin(self.email, self.password)
        response = self.client._fetch("/me")
        if response.status_code != 200:
            raise ValueError(
                f"LinkedIn identity lookup failed with status {response.status_code}: "
                f"{response.text[:300]}"
            )

        data = response.json()
        mini_profile = data.get("miniProfile", {})
        member_urn = mini_profile.get("objectUrn")
        if not member_urn:
            raise ValueError("Could not determine the LinkedIn member URN from /me")

        self.owner_urn = member_urn
        logger.info("LinkedIn authentication succeeded for %s", self.email)

    def authenticate_official(self) -> None:
        """Resolve the posting identity for the official LinkedIn API."""
        if self.owner_urn is not None:
            return
        if not self.access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is not set")
        if self.author_urn:
            self.owner_urn = self.author_urn
            logger.info("Official LinkedIn author configured explicitly as %s", self.owner_urn)
            return

        response = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=20,
        )
        if response.status_code != 200:
            raise ValueError(
                f"Official LinkedIn userinfo lookup failed with status {response.status_code}: "
                f"{response.text[:300]}"
            )

        data = response.json()
        profile_id = data.get("sub")
        if not profile_id:
            raise ValueError("Official LinkedIn userinfo lookup did not return a subject id")

        self.owner_urn = f"urn:li:person:{profile_id}"
        logger.info("Official LinkedIn authentication succeeded for %s", self.email)
    
    def create_post_content(self, article: Dict) -> str:
        """
        Create an eye-catching LinkedIn post from a Claude platform article.

        Args:
            article: Article dictionary with title, description, URL

        Returns:
            Formatted LinkedIn post text
        """
        title = article.get("title", "")
        description = article.get("description", "")
        url = self._get_reference_url(article)
        if not url:
            raise ValueError("Article is missing a valid reference URL")
        source = article.get("source", "Source")
        tier = article.get("tier", 2)

        hook = self._build_hook(title, description, source, tier)
        why_it_matters = self._build_why_it_matters(title, description, tier)
        takeaway = self._build_takeaway(title, description, source)
        hashtags = self._build_hashtags(title, description, source)

        post_content = (
            f"{hook}\n\n"
            f"→ {title}\n\n"
            f"{why_it_matters}\n\n"
            f"{takeaway}\n\n"
            f"Source: {source}\n\n"
            f"Reference link: {url}\n\n"
            f"{hashtags}"
        )

        self._validate_post_content(post_content)
        return post_content

    def _validate_post_content(self, post_content: str) -> None:
        """Enforce the expected audience-facing post structure."""
        non_empty_lines = [line.strip() for line in post_content.splitlines() if line.strip()]
        if not non_empty_lines:
            raise ValueError("LinkedIn post content is empty")

        if len(non_empty_lines) < 3:
            raise ValueError("LinkedIn post content is missing required sections")

        source_line = next((line for line in non_empty_lines if line.startswith("Source: ")), "")
        if not source_line:
            raise ValueError("LinkedIn post must include a source line")

        hashtag_line = next((line for line in non_empty_lines if line.startswith("#")), "")
        if not hashtag_line:
            raise ValueError("LinkedIn post must include hashtags")

    def _get_reference_url(self, article: Dict) -> str:
        """Return a publishable reference URL or an empty string."""
        raw_url = (article.get("url") or "").strip()
        if not raw_url:
            return ""

        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""

        return raw_url

    def _build_hook(self, title: str, description: str, source: str, tier: int = 2) -> str:
        """Eye-catching opening line tailored to the article topic and tier."""
        haystack = f"{title} {description} {source}".lower()

        if tier == 1:
            # Data developer — direct and specific
            if "rag" in haystack or "retrieval" in haystack:
                return "If you're building RAG pipelines, Claude just got more powerful for your stack."
            if "embedding" in haystack or "vector" in haystack:
                return "Vector search + Claude: this is the combination your data platform has been waiting for."
            if "agent" in haystack or "agentic" in haystack or "computer use" in haystack:
                return "Autonomous agents that can reason over your data — Claude's latest move changes the game."
            if "mcp" in haystack or "model context protocol" in haystack:
                return "MCP is quietly becoming the backbone of AI-data integrations. Here's why that matters."
            if "context window" in haystack or "long context" in haystack:
                return "200K tokens of context. Your entire data schema, docs, and history — all in one prompt."
            if "api" in haystack or "sdk" in haystack:
                return "As a data developer, the Claude API just became a tool you need to know about."
            if "fine-tun" in haystack:
                return "Fine-tuning Claude for your domain data — this is what production AI actually looks like."
            if "structured output" in haystack or "json" in haystack:
                return "Structured outputs from Claude mean cleaner data pipelines and fewer parsing headaches."
            if "vision" in haystack or "multimodal" in haystack:
                return "Claude can now see your charts, dashboards, and data visualisations. Let that sink in."
            return "Data engineers — Claude just shipped something that belongs in your toolkit."
        else:
            # General Claude update
            if "sonnet" in haystack or "opus" in haystack or "haiku" in haystack:
                return "A new Claude model just dropped — and the benchmark numbers are worth your attention."
            if "safety" in haystack or "alignment" in haystack:
                return "Anthropic continues to set the bar for what responsible AI development looks like."
            if "reasoning" in haystack:
                return "Claude's reasoning capabilities just leveled up. Here's what that means in practice."
            return "Anthropic just published something worth reading if you're serious about AI."

    def _build_why_it_matters(self, title: str, description: str, tier: int = 2) -> str:
        """Short 'why this matters' block for the post body."""
        haystack = f"{title} {description}".lower()
        cleaned_desc = " ".join((description or "").split()).strip()
        snippet = (cleaned_desc[:200].rstrip(" .,;:-") + "...") if len(cleaned_desc) > 200 else cleaned_desc

        if tier == 1:
            prefix = "What this means for data teams:"
        else:
            prefix = "Why this matters:"

        if snippet:
            return f"{prefix}\n{snippet}"

        # Fallback without description
        if "agent" in haystack or "agentic" in haystack:
            return f"{prefix}\nAgentic workflows are moving from research into production data pipelines."
        if "rag" in haystack or "retrieval" in haystack:
            return f"{prefix}\nRAG on top of Claude gives your data platform a conversational intelligence layer."
        if "context window" in haystack:
            return f"{prefix}\nLonger context means you can feed entire datasets, schemas, or codebases in a single call."
        return f"{prefix}\nThis update shifts what's possible when combining Claude with your existing data infrastructure."

    def _build_takeaway(self, title: str, description: str, source: str) -> str:
        """One-line personal takeaway to drive engagement."""
        haystack = f"{title} {description} {source}".lower()

        if "rag" in haystack or "retrieval" in haystack:
            return "My take: RAG + Claude is becoming the default pattern for enterprise AI. Get ahead of it."
        if "embedding" in haystack or "vector" in haystack:
            return "My take: embeddings are no longer optional — they're the connective tissue of AI data stacks."
        if "agent" in haystack or "agentic" in haystack:
            return "My take: the gap between 'AI assistant' and 'AI coworker' is closing faster than most teams realise."
        if "mcp" in haystack or "model context protocol" in haystack:
            return "My take: MCP will be to AI what REST was to web APIs. Learn it now."
        if "context window" in haystack or "long context" in haystack:
            return "My take: when context is unlimited, the bottleneck becomes your ability to ask the right questions."
        if "fine-tun" in haystack:
            return "My take: domain-specific Claude models will outperform general ones for structured data tasks."
        if "safety" in haystack or "alignment" in haystack:
            return "My take: safety and capability are not a trade-off — Anthropic keeps proving that."
        if "sonnet" in haystack or "opus" in haystack or "haiku" in haystack:
            return "My take: every Claude release raises the ceiling on what data-driven AI can do."
        return "My take: if you're building data products, Claude's platform is worth a serious look right now."

    def _build_hashtags(self, title: str, description: str, source: str) -> str:
        """Generate relevant hashtags for Claude platform posts."""
        haystack = f"{title} {description} {source}".lower()
        hashtags = ["#Claude", "#GenerativeAI", "#DataEngineering"]

        keyword_map = [
            ("rag", "#RAG"),
            ("retrieval", "#RAG"),
            ("embedding", "#Embeddings"),
            ("vector", "#VectorSearch"),
            ("agent", "#AIAgents"),
            ("agentic", "#AIAgents"),
            ("mcp", "#MCP"),
            ("model context protocol", "#MCP"),
            ("api", "#ClaudeAPI"),
            ("sdk", "#ClaudeAPI"),
            ("fine-tun", "#FineTuning"),
            ("context window", "#LongContext"),
            ("structured output", "#StructuredAI"),
            ("multimodal", "#MultimodalAI"),
            ("vision", "#MultimodalAI"),
            ("computer use", "#ComputerUse"),
            ("safety", "#ResponsibleAI"),
            ("alignment", "#ResponsibleAI"),
            ("pipeline", "#DataPipeline"),
            ("data platform", "#DataPlatform"),
            ("anthropic", "#Anthropic"),
        ]

        for term, hashtag in keyword_map:
            if term in haystack and hashtag not in hashtags:
                hashtags.append(hashtag)

        return " ".join(hashtags[:6])

    def _build_post_payload(self, article: Dict, entity_location: Optional[str] = None) -> Dict:
        """Build a LinkedIn share payload for the authenticated member."""
        if not self.owner_urn:
            raise ValueError("LinkedIn owner URN is not available")

        payload = {
            "owner": self.owner_urn,
            "lifecycleState": "PUBLISHED",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "content": {
                "shareCommentary": {"text": self.create_post_content(article)},
                "shareMediaCategory": "NONE"
            }
        }

        if entity_location:
            payload["content"] = {
                "shareCommentary": {"text": self.create_post_content(article)},
                "shareMediaCategory": "ARTICLE",
                "entityLocation": entity_location
            }

        return payload

    def _build_official_article_content(self, article: Dict) -> Dict:
        """Build the official LinkedIn article content block."""
        reference_url = self._get_reference_url(article)
        if not reference_url:
            raise ValueError("Article is missing a valid reference URL")

        content = {
            "article": {
                "source": reference_url,
                "title": article.get("title", "Untitled article"),
            }
        }

        description = " ".join((article.get("description") or "").split()).strip()
        if description:
            content["article"]["description"] = description[:256]

        return content

    def _create_linkedin_share(self, article: Dict) -> bool:
        """Publish a share to LinkedIn using the unofficial voyager endpoints."""
        if self.client is None:
            raise ValueError("LinkedIn client is not authenticated")

        headers = {
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "content-type": "application/json; charset=UTF-8"
        }
        article_url = article.get("url")

        payload_candidates = [self._build_post_payload(article, article_url)]
        if article_url:
            payload_candidates.append(self._build_post_payload(article))

        endpoint_candidates = [
            "/contentcreation/normShares?action=create",
            "/feed/shares?action=create",
        ]

        last_error = None
        for endpoint in endpoint_candidates:
            for payload in payload_candidates:
                logger.info(
                    "Attempting LinkedIn publish for '%s' via %s",
                    article.get("title", "Untitled article"),
                    endpoint,
                )
                response = self.client._post(
                    endpoint,
                    data=json.dumps(payload),
                    headers=headers
                )
                if response.status_code in (200, 201):
                    logger.info(
                        "LinkedIn publish succeeded for '%s' via %s",
                        article.get("title", "Untitled article"),
                        endpoint,
                    )
                    return True

                last_error = (
                    f"LinkedIn returned {response.status_code} for {endpoint}: "
                    f"{response.text[:300]}"
                )
                logger.warning(last_error)

        raise RuntimeError(last_error or "LinkedIn post request failed")

    def _create_official_post(self, article: Dict) -> bool:
        """Publish a post through LinkedIn's official Posts API."""
        self.authenticate_official()
        if not self.owner_urn:
            raise ValueError("LinkedIn owner URN is not available for official posting")

        commentary = self.create_post_content(article)
        payload = {
            "author": self.owner_urn,
            "commentary": commentary,
            "content": self._build_official_article_content(article),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "LinkedIn-Version": self.api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if response.status_code in (200, 201):
            logger.info(
                "Official LinkedIn publish succeeded for '%s'",
                article.get("title", "Untitled article"),
            )
            return True

        raise RuntimeError(
            f"Official LinkedIn returned {response.status_code}: {response.text[:500]}"
        )
    
    def load_posted_articles(self):
        """Load list of already posted articles."""
        if self.posts_file.exists():
            try:
                with open(self.posts_file, 'r') as f:
                    data = json.load(f)
                    self.posted_articles = data.get('articles', [])
            except Exception as e:
                print(f"Warning: Could not load posted articles: {e}")
                self.posted_articles = []
    
    def save_posted_article(self, article: Dict):
        """Save article to posted list."""
        article_data = {
            "title": article.get("title"),
            "url": article.get("url"),
            "timestamp": datetime.now().isoformat()
        }
        self.posted_articles.append(article_data)
        
        with open(self.posts_file, 'w') as f:
            json.dump({"articles": self.posted_articles}, f, indent=2)
    
    def is_already_posted(self, article: Dict) -> bool:
        """Check if article was already posted."""
        article_url = self._get_reference_url(article)
        return any(a.get("url") == article_url for a in self.posted_articles)
    
    def post_to_linkedin(self, article: Dict) -> bool:
        """
        Publish or preview a LinkedIn post for an article.
        
        Args:
            article: Article dictionary with news info
            
        Returns:
            True if post content was published or dry-run preview succeeded
        """
        try:
            reference_url = self._get_reference_url(article)
            if not reference_url:
                print(f"⊘ Skipping article without reference link: {article.get('title', 'Untitled article')[:50]}...")
                logger.warning(
                    "Skipping article without a valid reference URL: %s",
                    article.get("title", "Untitled article"),
                )
                return False

            # Check if already posted
            if self.is_already_posted(article):
                print(f"⊘ Article already posted: {article.get('title')[:50]}...")
                logger.info("Skipping duplicate article URL: %s", reference_url)
                return False

            if self.dry_run:
                print(f"🧪 Dry run only, not posted: {article.get('title')[:50]}...")
                print(f"Content preview:\n{self.create_post_content(article)[:240]}...\n")
                logger.info("Dry run enabled, skipping LinkedIn publish for %s", reference_url)
                return True

            if self.access_token:
                self._create_official_post(article)
            else:
                self.authenticate()
                self._create_linkedin_share(article)
            print(f"✅ Posted to LinkedIn: {article.get('title')[:50]}...")
            self.save_posted_article(article)
            return True
            
        except Exception as e:
            print(f"❌ Error posting to LinkedIn: {e}")
            logger.exception("LinkedIn posting failed for URL %s", article.get("url"))
            return False
    
    def post_multiple(self, articles: list[Dict], max_posts: int = 1) -> int:
        """
        Publish up to a limited number of articles to LinkedIn.
        
        Args:
            articles: List of article dictionaries
            max_posts: Maximum number of articles to publish in this run
            
        Returns:
            Number of successfully prepared articles
        """
        success_count = 0
        for article in articles:
            if self.post_to_linkedin(article):
                success_count += 1
            if success_count >= max_posts:
                break
        
        return success_count
    
    def display_posts_summary(self):
        """Display summary of published posts."""
        print("\n" + "="*60)
        print("📱 LINKEDIN POSTING SUMMARY")
        print("="*60)
        print(f"Total articles tracked as posted: {len(self.posted_articles)}")
        print(f"Dry run mode: {'ON' if self.dry_run else 'OFF'}")
        print("\nEach newly published article is saved locally in posted_articles.json")
        print("="*60 + "\n")
