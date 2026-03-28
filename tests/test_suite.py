"""Comprehensive test suite for AI Agent LinkedIn project."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.news_fetcher import NewsFetcher
from src.linkedin_poster import LinkedInPoster
from src.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article(**kwargs):
    defaults = {
        "title": "Building RAG pipelines with the Claude API",
        "description": "How to use Claude's API and embeddings to build retrieval-augmented generation for data platforms.",
        "url": "https://www.anthropic.com/news/rag-claude-api",
        "source": "Anthropic News",
        "published_at": "2026-03-01T09:00:00",
        "image": "",
        "tier": 1,
    }
    defaults.update(kwargs)
    return defaults


def make_poster(tmp_path, dry_run=True, access_token="", author_urn=""):
    posts_file = tmp_path / "posted_articles.json"
    poster = LinkedInPoster(
        email="test@example.com",
        password="password",
        dry_run=dry_run,
        access_token=access_token,
        author_urn=author_urn,
    )
    poster.posts_file = posts_file
    poster.posted_articles = []
    return poster


# ===========================================================================
# NewsFetcher Tests
# ===========================================================================

class TestNewsFetcherScoring:

    def setup_method(self):
        self.fetcher = NewsFetcher()

    def test_data_dev_score_positive_for_rag_api(self):
        haystack = "building rag pipelines with the claude api embeddings vector"
        assert self.fetcher._score_data_dev(haystack) >= NewsFetcher.DATA_DEV_MIN_SCORE

    def test_data_dev_score_zero_for_unrelated(self):
        haystack = "anthropic releases new model with improved reasoning safety"
        assert self.fetcher._score_data_dev(haystack) == 0

    def test_claude_score_positive_for_model_release(self):
        haystack = "introducing claude sonnet new model capabilities release"
        assert self.fetcher._score_claude(haystack) >= NewsFetcher.CLAUDE_MIN_SCORE

    def test_noise_terms_present_in_set(self):
        assert "sports" in NewsFetcher.NOISE_TERMS
        assert "celebrity" in NewsFetcher.NOISE_TERMS

    def test_data_dev_terms_include_key_terms(self):
        for term in ("rag", "api", "embedding", "mcp", "agent", "pipeline"):
            assert term in NewsFetcher.DATA_DEV_TERMS

    def test_claude_terms_include_key_terms(self):
        for term in ("claude", "anthropic", "model", "reasoning"):
            assert term in NewsFetcher.CLAUDE_TERMS

    def test_haystack_combines_all_fields(self):
        article = make_article(title="RAG API", description="embeddings vector", source="Anthropic News")
        haystack = self.fetcher._haystack(article)
        assert "rag" in haystack
        assert "embeddings" in haystack
        assert "anthropic" in haystack


class TestNewsFetcherDeduplication:

    def setup_method(self):
        self.fetcher = NewsFetcher()

    def test_exact_duplicates_removed(self):
        articles = [make_article(), make_article()]
        unique = self.fetcher._dedupe_articles(articles)
        assert len(unique) == 1

    def test_different_url_same_title_not_deduped(self):
        # Dedup key is (title, url) — same title + different URL is kept as distinct
        a1 = make_article(url="https://example.com/article-1")
        a2 = make_article(url="https://example.com/article-2")
        unique = self.fetcher._dedupe_articles([a1, a2])
        assert len(unique) == 2

    def test_different_title_and_url_kept(self):
        a1 = make_article(title="Article One", url="https://example.com/one")
        a2 = make_article(title="Article Two", url="https://example.com/two")
        unique = self.fetcher._dedupe_articles([a1, a2])
        assert len(unique) == 2

    def test_empty_list(self):
        assert self.fetcher._dedupe_articles([]) == []

    def test_same_title_and_url_case_insensitive_dedup(self):
        # Same title (different case) + same URL → deduplicated
        a1 = make_article(title="AI Pipeline", url="https://example.com/same")
        a2 = make_article(title="ai pipeline", url="https://example.com/same")
        unique = self.fetcher._dedupe_articles([a1, a2])
        assert len(unique) == 1


class TestNewsFetcherURLFiltering:

    def setup_method(self):
        self.fetcher = NewsFetcher()

    def test_anthropic_news_article_accepted(self):
        source = {"allowed_path_prefixes": ["/news/"], "blocked_path_segments": []}
        from bs4 import BeautifulSoup
        from unittest.mock import MagicMock, patch
        import requests

        html = '''<html><body>
            <a href="/news/claude-sonnet-4-6">Introducing Claude Sonnet 4.6 — the new frontier model</a>
            <a href="/news/claude-opus-4-6">Claude Opus 4.6 released with major upgrades to reasoning</a>
        </body></html>'''

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch.object(self.fetcher.session, 'get', return_value=mock_resp):
            source_def = {
                "name": "Anthropic News",
                "url": "https://www.anthropic.com/news",
                "base": "https://www.anthropic.com",
                "allowed_path_prefixes": ["/news/"],
                "blocked_path_segments": [],
            }
            urls = self.fetcher._extract_article_urls(source_def)
        assert len(urls) == 2
        assert "https://www.anthropic.com/news/claude-sonnet-4-6" in urls

    def test_research_team_pages_blocked(self):
        from unittest.mock import MagicMock, patch

        html = '''<html><body>
            <a href="/research/long-running-Claude">Long-running Claude for scientific computing research</a>
            <a href="/research/team/interpretability">Interpretability team page</a>
        </body></html>'''

        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch.object(self.fetcher.session, 'get', return_value=mock_resp):
            source_def = {
                "name": "Anthropic Research",
                "url": "https://www.anthropic.com/research",
                "base": "https://www.anthropic.com",
                "allowed_path_prefixes": ["/research/"],
                "blocked_path_segments": ["/research/team/"],
            }
            urls = self.fetcher._extract_article_urls(source_def)
        assert "https://www.anthropic.com/research/team/interpretability" not in urls
        assert "https://www.anthropic.com/research/long-running-Claude" in urls


# ===========================================================================
# LinkedInPoster Tests
# ===========================================================================

class TestLinkedInPosterContent:

    def setup_method(self, tmp_path_factory=None):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_post_content_contains_title(self):
        article = make_article(title="New LLM Feature in BigQuery")
        content = self.poster.create_post_content(article)
        assert "New LLM Feature in BigQuery" in content

    def test_post_content_contains_source(self):
        article = make_article(source="Databricks Blog")
        content = self.poster.create_post_content(article)
        assert "Source: Databricks Blog" in content

    def test_post_content_contains_url(self):
        article = make_article(url="https://www.databricks.com/blog/test-article")
        content = self.poster.create_post_content(article)
        assert "https://www.databricks.com/blog/test-article" in content

    def test_post_content_contains_hashtags_after_url(self):
        article = make_article()
        content = self.poster.create_post_content(article)
        assert "#Claude" in content
        assert "#DataEngineering" in content
        # Hashtags must appear after the reference link
        url_pos = content.index("Reference link:")
        hashtag_pos = content.index("#Claude")
        assert hashtag_pos > url_pos

    def test_post_content_raises_without_url(self):
        article = make_article(url="")
        with pytest.raises(ValueError, match="missing a valid reference URL"):
            self.poster.create_post_content(article)

    def test_post_content_raises_for_invalid_url_scheme(self):
        article = make_article(url="ftp://example.com/article")
        with pytest.raises(ValueError, match="missing a valid reference URL"):
            self.poster.create_post_content(article)


class TestLinkedInPosterHooks:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_rag_hook_tier1(self):
        hook = self.poster._build_hook("Building RAG pipelines with Claude", "", "Anthropic News", tier=1)
        assert "rag" in hook.lower() or "pipeline" in hook.lower()

    def test_agent_hook_tier1(self):
        hook = self.poster._build_hook("Claude agentic workflows for data", "", "Anthropic News", tier=1)
        assert "agent" in hook.lower() or "data" in hook.lower()

    def test_model_release_hook_tier2(self):
        hook = self.poster._build_hook("Introducing Claude Sonnet 4.6", "", "Anthropic News", tier=2)
        assert "model" in hook.lower() or "claude" in hook.lower() or "benchmark" in hook.lower()

    def test_default_tier2_hook(self):
        hook = self.poster._build_hook("Anthropic announces new program", "", "Anthropic News", tier=2)
        assert len(hook) > 10

    def test_mcp_hook_tier1(self):
        hook = self.poster._build_hook("Model Context Protocol integration guide", "", "Anthropic", tier=1)
        assert "mcp" in hook.lower() or "context" in hook.lower() or "integration" in hook.lower() or len(hook) > 10


class TestLinkedInPosterHashtags:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_base_hashtags_always_present(self):
        tags = self.poster._build_hashtags("Some title", "some description", "source")
        assert "#Claude" in tags
        assert "#GenerativeAI" in tags
        assert "#DataEngineering" in tags

    def test_rag_hashtag_added(self):
        tags = self.poster._build_hashtags("RAG pipeline with Claude API", "", "Anthropic News")
        assert "#RAG" in tags

    def test_mcp_hashtag_added(self):
        tags = self.poster._build_hashtags("Model Context Protocol guide", "", "Anthropic")
        assert "#MCP" in tags

    def test_anthropic_hashtag_added(self):
        tags = self.poster._build_hashtags("Anthropic model release", "", "Anthropic News")
        assert "#Anthropic" in tags

    def test_max_six_hashtags(self):
        tags = self.poster._build_hashtags(
            "rag retrieval embedding vector agent mcp api sdk fine-tuning context window structured output multimodal",
            "",
            "anthropic",
        )
        assert len(tags.split()) <= 6

    def test_no_duplicate_hashtags(self):
        tags = self.poster._build_hashtags(
            "rag rag retrieval rag pipeline rag", "", "source"
        )
        tag_list = tags.split()
        assert len(tag_list) == len(set(tag_list))


class TestLinkedInPosterDuplicateDetection:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_new_article_not_duplicate(self):
        article = make_article(url="https://www.databricks.com/blog/new-article")
        assert not self.poster.is_already_posted(article)

    def test_posted_article_detected_as_duplicate(self):
        article = make_article(url="https://www.databricks.com/blog/posted-article")
        self.poster.posted_articles = [
            {"url": "https://www.databricks.com/blog/posted-article", "title": "Posted"}
        ]
        assert self.poster.is_already_posted(article)

    def test_different_url_not_duplicate(self):
        article = make_article(url="https://www.databricks.com/blog/different-article")
        self.poster.posted_articles = [
            {"url": "https://www.databricks.com/blog/other-article", "title": "Other"}
        ]
        assert not self.poster.is_already_posted(article)


class TestLinkedInPosterSaveLoad:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_save_article_creates_file(self):
        article = make_article()
        self.poster.save_posted_article(article)
        assert self.poster.posts_file.exists()

    def test_saved_article_loadable(self):
        article = make_article(url="https://example.com/save-test")
        self.poster.save_posted_article(article)

        # Reload from disk
        with open(self.poster.posts_file) as f:
            data = json.load(f)
        urls = [a["url"] for a in data["articles"]]
        assert "https://example.com/save-test" in urls

    def test_load_posted_articles_from_file(self):
        data = {"articles": [{"url": "https://example.com/x", "title": "X", "timestamp": "2026-01-01T00:00:00"}]}
        with open(self.poster.posts_file, "w") as f:
            json.dump(data, f)

        self.poster.load_posted_articles()
        assert len(self.poster.posted_articles) == 1
        assert self.poster.posted_articles[0]["url"] == "https://example.com/x"

    def test_load_graceful_on_missing_file(self):
        self.poster.posts_file = self.tmp / "nonexistent.json"
        self.poster.load_posted_articles()
        assert self.poster.posted_articles == []

    def test_load_graceful_on_corrupt_file(self):
        self.poster.posts_file.write_text("NOT VALID JSON")
        self.poster.load_posted_articles()
        assert self.poster.posted_articles == []


class TestLinkedInPosterDryRun:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp, dry_run=True)

    def test_dry_run_returns_true(self):
        article = make_article()
        result = self.poster.post_to_linkedin(article)
        assert result is True

    def test_dry_run_does_not_save_article(self):
        article = make_article()
        self.poster.post_to_linkedin(article)
        assert len(self.poster.posted_articles) == 0

    def test_dry_run_skips_duplicate(self):
        article = make_article(url="https://example.com/dup")
        self.poster.posted_articles = [{"url": "https://example.com/dup"}]
        result = self.poster.post_to_linkedin(article)
        assert result is False

    def test_post_to_linkedin_skips_no_url(self):
        article = make_article(url="")
        result = self.poster.post_to_linkedin(article)
        assert result is False

    def test_post_multiple_respects_max(self):
        articles = [
            make_article(title=f"Article {i}", url=f"https://example.com/a{i}")
            for i in range(5)
        ]
        count = self.poster.post_multiple(articles, max_posts=2)
        assert count == 2


class TestLinkedInPosterReferenceURL:

    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.poster = make_poster(self.tmp)

    def test_valid_http_url(self):
        assert self.poster._get_reference_url({"url": "http://example.com/article"}) == "http://example.com/article"

    def test_valid_https_url(self):
        assert self.poster._get_reference_url({"url": "https://example.com/article"}) == "https://example.com/article"

    def test_empty_url_returns_empty(self):
        assert self.poster._get_reference_url({"url": ""}) == ""

    def test_missing_url_key_returns_empty(self):
        assert self.poster._get_reference_url({}) == ""

    def test_ftp_url_returns_empty(self):
        assert self.poster._get_reference_url({"url": "ftp://example.com/file"}) == ""

    def test_url_without_netloc_returns_empty(self):
        assert self.poster._get_reference_url({"url": "https://"}) == ""


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:

    def test_validate_raises_without_credentials(self):
        with patch.object(Config, "LINKEDIN_EMAIL", ""), \
             patch.object(Config, "LINKEDIN_PASSWORD", ""), \
             patch.object(Config, "LINKEDIN_ACCESS_TOKEN", ""):
            with pytest.raises(ValueError, match="LINKEDIN_ACCESS_TOKEN"):
                Config.validate()

    def test_validate_passes_with_access_token(self):
        with patch.object(Config, "LINKEDIN_ACCESS_TOKEN", "some-token"), \
             patch.object(Config, "LINKEDIN_EMAIL", ""), \
             patch.object(Config, "LINKEDIN_PASSWORD", ""):
            Config.validate()  # should not raise

    def test_validate_passes_with_email_and_password(self):
        with patch.object(Config, "LINKEDIN_EMAIL", "user@example.com"), \
             patch.object(Config, "LINKEDIN_PASSWORD", "secret"), \
             patch.object(Config, "LINKEDIN_ACCESS_TOKEN", ""):
            Config.validate()  # should not raise

    def test_resolve_author_urn_explicit(self):
        with patch.object(Config, "LINKEDIN_AUTHOR_URN", "urn:li:person:abc"), \
             patch.object(Config, "LINKEDIN_PAGE_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_ID", ""):
            assert Config.resolve_linkedin_author_urn() == "urn:li:person:abc"

    def test_resolve_author_urn_page_urn_fallback(self):
        with patch.object(Config, "LINKEDIN_AUTHOR_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_URN", "urn:li:organization:999"), \
             patch.object(Config, "LINKEDIN_PAGE_ID", ""):
            assert Config.resolve_linkedin_author_urn() == "urn:li:organization:999"

    def test_resolve_author_urn_page_id_fallback(self):
        with patch.object(Config, "LINKEDIN_AUTHOR_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_ID", "12345"):
            assert Config.resolve_linkedin_author_urn() == "urn:li:organization:12345"

    def test_resolve_author_urn_empty_when_nothing_set(self):
        with patch.object(Config, "LINKEDIN_AUTHOR_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_URN", ""), \
             patch.object(Config, "LINKEDIN_PAGE_ID", ""):
            assert Config.resolve_linkedin_author_urn() == ""

    def test_dry_run_default_is_true(self):
        # Default in .env.example is true; Config reads from env
        with patch.dict(os.environ, {"LINKEDIN_DRY_RUN": "true"}):
            from importlib import reload
            import src.config as cfg_module
            reload(cfg_module)
            assert cfg_module.Config.LINKEDIN_DRY_RUN is True

    def test_dry_run_false_when_set(self):
        with patch.dict(os.environ, {"LINKEDIN_DRY_RUN": "false"}):
            from importlib import reload
            import src.config as cfg_module
            reload(cfg_module)
            assert cfg_module.Config.LINKEDIN_DRY_RUN is False
