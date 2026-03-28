# AI News LinkedIn Agent

An intelligent Python agent that collects Data Platform + AI updates from curated official vendor sources and posts them to your LinkedIn profile or LinkedIn Page.

## Features

- 🔍 **Curated Source Fetching** - Pulls updates from official Data Platform + AI sources
- 📱 **LinkedIn Integration** - Automatically posts news to your LinkedIn profile or LinkedIn Page
- ⏰ **Scheduled Execution** - Runs at configurable intervals (default: 24 hours)
- 🎯 **Stricter Relevance Filtering** - Requires both AI and Data Platform signals before posting
- 📊 **Duplicate Prevention** - Avoids posting the same article twice
- 🛡️ **Secure Configuration** - Uses environment variables for credentials

## Prerequisites

- Python 3.9 or higher
- LinkedIn account credentials

## Installation

1. **Clone or download this project**

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env` and add your credentials**:
   ```
   LINKEDIN_EMAIL=your.email@example.com
   LINKEDIN_PASSWORD=your_password
   LINKEDIN_ACCESS_TOKEN=
   LINKEDIN_API_VERSION=202603
   LINKEDIN_PAGE_ID=
   LINKEDIN_DRY_RUN=true
   NEWS_KEYWORDS=artificial intelligence,machine learning,deep learning
   SCHEDULE_INTERVAL_HOURS=24
   ```

## Usage

### Run Once

To fetch and process news immediately:

```bash
.venv/bin/python -c "from src.ai_agent import AINewsLinkedInAgent; AINewsLinkedInAgent().run_once()"
```

Or with the task runner:

```bash
source .venv/bin/activate
python -m src.ai_agent
```

### How It Works

1. **Fetch Updates** - Crawls curated official vendor blogs and pages
2. **Publish or Preview** - Publishes directly to LinkedIn, or previews when dry run is enabled
3. **Track Posts** - Saves to `posted_articles.json` to avoid duplicates
4. **Display Summary** - Shows what happened during the run

### Understanding the Output

When the agent runs, you'll see:
- `📰 Fetching curated Data Platform + AI updates...` - Collecting updates from curated sources
- `✅ Found 5 articles` - Successfully retrieved articles
- `📤 Dry-running articles to LinkedIn...` or `📤 Posting articles to LinkedIn...`
- `🧪 Dry run only, not posted:` - Preview mode is enabled
- `✅ Posted to LinkedIn:` - New article was published
- `⊘ Article already posted:` - Duplicate (won't post again)
- `❌ Error posting to LinkedIn:` - Authentication or publish failed
- `📱 LINKEDIN POSTING SUMMARY` - Summary with mode and totals

### Dry Run Safety Switch

Use `LINKEDIN_DRY_RUN=true` while testing. In that mode the app:

1. Authenticates only when needed for real posting
2. Prints a preview of the LinkedIn post text
3. Does not publish to LinkedIn
4. Does not add the article to `posted_articles.json`

Set `LINKEDIN_DRY_RUN=false` when you are ready to publish.

### Official LinkedIn Posting

For reliable direct posting, use LinkedIn's official API with `LINKEDIN_ACCESS_TOKEN`.

- If `LINKEDIN_ACCESS_TOKEN` is set, the app uses LinkedIn's official Posts API.
- If it is not set, the app falls back to the unofficial credential-based voyager flow, which may fail because LinkedIn can change or restrict those endpoints at any time.
- To post as a LinkedIn Page instead of your personal profile, set one of:
  - `LINKEDIN_AUTHOR_URN=urn:li:organization:<page_id>`
  - `LINKEDIN_PAGE_URN=urn:li:organization:<page_id>`
  - `LINKEDIN_PAGE_ID=<page_id>`
- When none of those are set, official posting defaults to your personal profile (`urn:li:person:...`).
- Page posting requires a LinkedIn access token with Page posting permissions and admin access to that Page.

### Automated Scheduling

To run the agent automatically every 24 hours (runs immediately on start, then every 24 hours):

```bash
source .venv/bin/activate
python -m src.ai_agent
```

The scheduler will:
- **Run immediately** on startup (first batch of posts)
- **Run again** every 24 hours automatically
- **Track posted articles** to avoid duplicates
- **Continue running** until you stop it with Ctrl+C

Output:
```
2026-03-23 23:04:24,011 - apscheduler.scheduler - INFO - Scheduler started
🧪 Dry run only, not posted: Article Title...
📱 LINKEDIN POSTING SUMMARY
Total articles tracked as posted: 5
```

## Configuration

Edit `.env` file to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_EMAIL` | - | LinkedIn email (required) |
| `LINKEDIN_PASSWORD` | - | LinkedIn password (required) |
| `LINKEDIN_ACCESS_TOKEN` | - | Official LinkedIn OAuth token for direct posting |
| `LINKEDIN_API_VERSION` | `202603` | LinkedIn REST API version header |
| `LINKEDIN_AUTHOR_URN` | - | Explicit posting author URN such as `urn:li:organization:123456` |
| `LINKEDIN_PAGE_URN` | - | Convenience alias for a LinkedIn Page author URN |
| `LINKEDIN_PAGE_ID` | - | Convenience Page id; converted to `urn:li:organization:<id>` |
| `LINKEDIN_DRY_RUN` | `true` | Preview posts without publishing |
| `NEWS_KEYWORDS` | AI, ML, DL | Comma-separated keywords |
| `SCHEDULE_INTERVAL_HOURS` | 24 | How often to run (hours) |
| `SCHEDULE_TIME` | 09:00 | Time to run (24-hour format) |

## Project Structure

```
ai-news-linkedin-agent/
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── news_fetcher.py     # Curated source crawling and filtering
│   ├── linkedin_poster.py  # LinkedIn posting logic
│   └── ai_agent.py         # Main agent orchestrator
├── tests/
│   └── __init__.py
├── .env.example            # Environment template
├── .gitignore
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
└── README.md               # This file
```

## API Keys

### LinkedIn

Use your regular LinkedIn email and password for the fallback flow. For official profile or Page posting, prefer `LINKEDIN_ACCESS_TOKEN`.

## Troubleshooting

**LinkedIn login fails**
- Check email and password in `.env`
- If `LINKEDIN_DRY_RUN=false`, LinkedIn may block the login with a challenge or verification step
- Check the console logs for the exact HTTP status and endpoint failure

**LinkedIn post returns authorization errors**
- Prefer `LINKEDIN_ACCESS_TOKEN` over email/password posting
- Make sure your LinkedIn app and token include the permissions needed to create member posts

**LinkedIn Page post fails**
- Confirm the access token belongs to a Page admin
- Confirm the token has the permissions needed to publish as the Page
- Set `LINKEDIN_PAGE_ID` or `LINKEDIN_PAGE_URN` in `.env`

**No articles found**
- Check your internet connection
- Some official source pages may have changed structure
- Adjust filtering if you want broader or narrower coverage

## Development

### Run Tests

```bash
pytest tests/
```

### Code Quality

```bash
black src/
flake8 src/
```

## Limitations

- Official LinkedIn API requires app registration and has strict posting restrictions
- Source page HTML can change, which may require parser updates
- Direct posting here relies on unofficial LinkedIn endpoints and may break if LinkedIn changes them
- LinkedIn may require extra verification, 2FA, or block automated publishing attempts

## Future Enhancements (Requires Official LinkedIn API)

- [ ] Email digest option
- [ ] Twitter/X integration
- [ ] Content summarization with AI
- [ ] Sentiment analysis for articles
- [ ] Web dashboard for monitoring
- [ ] Database to track posted articles
- [ ] Advanced filtering by article quality

## License

MIT License - feel free to use and modify

## Support

For issues or questions, check the error logs and ensure all credentials are correct in `.env`.
