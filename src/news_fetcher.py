"""News fetching module — Claude platform capabilities from Anthropic sources."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class NewsFetcher:
    """Fetch Claude platform updates from official Anthropic sources.

    Scoring strategy (two-tier):
      Tier 1 — Data Developer: articles useful to data engineers / ML platform
               teams (RAG, embeddings, tool use, API, MCP, etc.).
      Tier 2 — General Claude update: anything about Claude capabilities,
               model releases, or the Anthropic platform.

    fetch_multiple_keywords() returns Tier-1 articles first; if fewer than
    *limit* are found it backfills with the best Tier-2 articles.
    """

    # ------------------------------------------------------------------ #
    # Sources
    # ------------------------------------------------------------------ #
    SOURCE_PAGES = [
        {
            "name": "Anthropic News",
            "url": "https://www.anthropic.com/news",
            "base": "https://www.anthropic.com",
            "allowed_path_prefixes": ["/news/"],
        },
        {
            "name": "Anthropic Research",
            "url": "https://www.anthropic.com/research",
            "base": "https://www.anthropic.com",
            "allowed_path_prefixes": ["/research/"],
            "blocked_path_segments": ["/research/team/"],
        },
    ]

    # ------------------------------------------------------------------ #
    # Term sets
    # ------------------------------------------------------------------ #

    # Tier-1: highly relevant to data / ML platform developers
    DATA_DEV_TERMS = {
        "api",
        "tool use",
        "function calling",
        "rag",
        "retrieval",
        "embedding",
        "embeddings",
        "vector",
        "mcp",
        "model context protocol",
        "data pipeline",
        "pipeline",
        "sql",
        "database",
        "data engineering",
        "data platform",
        "streaming",
        "batch",
        "fine-tuning",
        "fine tuning",
        "context window",
        "long context",
        "structured output",
        "json mode",
        "vision",
        "multimodal",
        "agent",
        "agents",
        "agentic",
        "workflow",
        "orchestration",
        "computer use",
        "files api",
        "prompt caching",
        "latency",
        "throughput",
        "sdk",
        "tokens",
        "cost",
    }

    # Tier-2: general Claude / Anthropic platform terms
    CLAUDE_TERMS = {
        "claude",
        "anthropic",
        "sonnet",
        "opus",
        "haiku",
        "model",
        "llm",
        "language model",
        "capability",
        "capabilities",
        "intelligence",
        "reasoning",
        "benchmark",
        "release",
        "launch",
        "update",
        "feature",
        "safety",
        "alignment",
    }

    # Noise — skip these regardless
    NOISE_TERMS = {
        "sports",
        "football",
        "celebrity",
        "entertainment",
        "children's book",
        "retirement",
        "digital marketing",
        "movie",
    }

    # Tier-1 threshold (data-dev score)
    DATA_DEV_MIN_SCORE = 2
    # Tier-2 threshold (general Claude score)
    CLAUDE_MIN_SCORE = 1

    REQUEST_TIMEOUT_SECONDS = 15
    INDEX_ARTICLES_PER_SOURCE = 10

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            }
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def fetch_multiple_keywords(self, keywords: Optional[List[str]] = None) -> List[Dict]:
        """Return top Claude-platform articles, prioritising data-dev relevance."""
        return self.fetch_claude_platform_news(limit=5)

    def fetch_claude_platform_news(self, limit: int = 5) -> List[Dict]:
        """Fetch, score, and rank articles from Anthropic sources.

        Returns Tier-1 (data-dev) articles first, backfilled with Tier-2
        (general Claude) articles up to *limit*.
        """
        all_candidates: List[Dict] = []

        for source in self.SOURCE_PAGES:
            try:
                urls = self._extract_article_urls(source)
                for url in urls:
                    article = self._fetch_article_details(url, source["name"])
                    if article:
                        all_candidates.append(article)
            except requests.RequestException as exc:
                print(f"⚠️  Could not fetch {source['name']}: {exc}")

        unique = self._dedupe_articles(all_candidates)

        tier1 = []
        tier2 = []
        for article in unique:
            haystack = self._haystack(article)
            if any(noise in haystack for noise in self.NOISE_TERMS):
                continue
            data_score = self._score_data_dev(haystack)
            claude_score = self._score_claude(haystack)
            if data_score >= self.DATA_DEV_MIN_SCORE:
                article["score"] = data_score * 3 + claude_score
                article["tier"] = 1
                tier1.append(article)
            elif claude_score >= self.CLAUDE_MIN_SCORE:
                article["score"] = claude_score
                article["tier"] = 2
                tier2.append(article)

        tier1.sort(key=lambda a: (a.get("score", 0), a.get("published_at") or ""), reverse=True)
        tier2.sort(key=lambda a: (a.get("score", 0), a.get("published_at") or ""), reverse=True)

        result = tier1[:limit]
        if len(result) < limit:
            result += tier2[: limit - len(result)]

        return result

    # ------------------------------------------------------------------ #
    # Scraping helpers
    # ------------------------------------------------------------------ #

    def _extract_article_urls(self, source: Dict) -> List[str]:
        response = self.session.get(source["url"], timeout=self.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        base = source.get("base", source["url"])
        allowed = source.get("allowed_path_prefixes", [])
        blocked_segments = source.get("blocked_path_segments", [])

        candidates: List[str] = []
        seen: set = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            full_url = href if href.startswith("http") else urljoin(base, href)
            path = urlparse(full_url).path.lower().rstrip("/")
            text = anchor.get_text(" ", strip=True)

            if not any(path.startswith(p.rstrip("/")) for p in allowed):
                continue
            if any(seg in path for seg in blocked_segments):
                continue
            if len(path.split("/")) < 3:
                continue
            if full_url in seen:
                continue

            seen.add(full_url)
            candidates.append(full_url)
            if len(candidates) >= self.INDEX_ARTICLES_PER_SOURCE:
                break

        return candidates

    def _fetch_article_details(self, article_url: str, source_name: str) -> Optional[Dict]:
        try:
            response = self.session.get(article_url, timeout=self.REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        title = (
            self._meta(soup, "property", "og:title")
            or (soup.title.get_text(strip=True) if soup.title else "")
            or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
        )
        description = (
            self._meta(soup, "property", "og:description")
            or self._meta(soup, "name", "description")
            or ""
        )
        published_at = self._extract_published_at(soup)

        if not title:
            return None

        return {
            "title": title,
            "description": description,
            "url": article_url,
            "image": self._meta(soup, "property", "og:image"),
            "source": source_name,
            "published_at": published_at,
        }

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    def _haystack(self, article: Dict) -> str:
        return " ".join([
            article.get("title", ""),
            article.get("description", ""),
            article.get("url", ""),
            article.get("source", ""),
        ]).lower()

    def _score_data_dev(self, haystack: str) -> int:
        return sum(1 for term in self.DATA_DEV_TERMS if term in haystack)

    def _score_claude(self, haystack: str) -> int:
        return sum(1 for term in self.CLAUDE_TERMS if term in haystack)

    # ------------------------------------------------------------------ #
    # Deduplication
    # ------------------------------------------------------------------ #

    def _dedupe_articles(self, articles: List[Dict]) -> List[Dict]:
        seen: set = set()
        unique: List[Dict] = []
        for article in articles:
            key = article.get("url", "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(article)
        return unique

    # ------------------------------------------------------------------ #
    # Metadata extraction utilities
    # ------------------------------------------------------------------ #

    def _meta(self, soup: BeautifulSoup, attr: str, value: str) -> str:
        tag = soup.find("meta", attrs={attr: value})
        return tag.get("content", "").strip() if tag else ""

    def _extract_published_at(self, soup: BeautifulSoup) -> str:
        candidates = [
            self._meta(soup, "property", "article:published_time"),
            self._meta(soup, "name", "publish-date"),
            self._meta(soup, "name", "date"),
            self._meta(soup, "itemprop", "datePublished"),
        ]
        time_tag = soup.find("time")
        if time_tag:
            candidates.append(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))

        for raw in candidates:
            if not raw:
                continue
            try:
                return parsedate_to_datetime(raw).isoformat()
            except Exception:
                if "T" in raw or "-" in raw:
                    return raw
        return ""
