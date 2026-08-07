# HadithBot

A Discord bot that sends daily Islamic hadiths and the 99 beautiful names of Allah to configured Discord channels. The bot automatically sends messages at 6:00 PM Toronto time and provides slash commands for interactive hadith and name retrieval.

## Features

- **Daily Automated Messages**: Sends hadiths and Allah's names daily at 6:00 PM Toronto time
- **Supabase Database**: Stores hadith data and tracks channel states using Supabase
- **Slash Commands**: Interactive commands for retrieving specific or random hadiths and names
- **Multi-Channel Support**: Can be configured to send messages to multiple Discord channels
- **State Persistence**: Tracks progress through hadiths and names for each channel
- **Error Handling**: Comprehensive logging and error recovery mechanisms

## Architecture

- **Discord Bot** (`bot.py`): Main bot logic with slash commands and scheduled tasks
- **Database Layer** (`db.py`): Supabase integration for data storage and retrieval
- **Utilities** (`utils.py`): Data models and message formatting functions
- **Web Server** (`server.py`): Flask server for health checks and bot hosting
- **Data Files**: Local JSON files containing the 99 names of Allah

## Project Files

- `bot.py` - Main Discord bot application
- `server.py` - Flask web server for hosting and health checks
- `db.py` - Database operations and Supabase integration
- `utils.py` - Data models and utility functions
- `test_setup.py` - Setup verification script
- `update_site.py` - Regenerates the site's usage counts and community wall (`make site`)
- `update_books_page.py` - Regenerates `docs/books.html`, the book/chapter id reference (`make books`)
- `OUTREACH.md` - Copy-paste templates for introducing the bot to new communities
- `pyproject.toml` / `uv.lock` - Dependencies and lockfile (managed with uv)
- `Makefile` - Common dev tasks (`make dev` / `test` / `lint`)
- `.env.example` - Environment variables template
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Multi-container orchestration
- `Procfile` - Heroku deployment configuration
- `data/99names.json` - The 99 beautiful names of Allah
- `docs/data/communities.json` - Communities listed on the website, opt-in only

## Prerequisites

- Python 3.11+
- Discord Bot Token
- Supabase Account and Project
- [uv](https://docs.astral.sh/uv/) (Python package/dependency manager)

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/SaiyedRushan/HadithBot.git
cd HadithBot
```

### 2. Install Dependencies

This project uses [uv](https://docs.astral.sh/uv/). With uv installed:

```bash
uv sync
```

This creates a `.venv` with all dependencies (runtime + dev) from `uv.lock`.
Run commands with `uv run ...`, or use the `Makefile` shortcuts:

```bash
make dev      # run the bot with autoreload on save
make test     # run tests
make lint     # static checks (undefined names, bad imports)
```

### 3. Environment Configuration

Create a `.env` file in the project root:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here

# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

### 4. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token to your `.env` file
4. Enable the following bot permissions:
   - Send Messages
   - Use Slash Commands
   - Read Message History
5. Invite the bot to your Discord server with these permissions

### 5. Supabase Setup

1. Create a new project at [Supabase](https://supabase.com)
2. Set up the following tables in your Supabase database:

#### `discord_channel_state` table:

```sql
CREATE TABLE discord_channel_state (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT,
    guild_id TEXT,
    guild_name TEXT,
    last_hadith_no INTEGER NOT NULL DEFAULT 1,
    last_name_no INTEGER NOT NULL DEFAULT 1,
    last_book_id INTEGER NOT NULL DEFAULT 1,
    last_chapter_id INTEGER NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    hadiths_per_day INTEGER NOT NULL DEFAULT 3,
    names_per_day INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

`channel_name`, `guild_name`, and `guild_id` are stored purely for readability
(so you can tell rows apart in the Supabase dashboard) — the bot keys everything
off `channel_id`. They're refreshed on every save, so renames stay in sync.

#### `hadiths` table:

```sql
CREATE TABLE hadiths (
    id SERIAL PRIMARY KEY,
    id_in_book INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    chapter_id INTEGER NOT NULL,
    english_narrator TEXT,
    english_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `chapters` table:

```sql
CREATE TABLE chapters (
    id SERIAL PRIMARY KEY,
    english TEXT NOT NULL,
    arabic TEXT,
    book_id INTEGER NOT NULL
);
```

#### `books_metadata` table:

```sql
CREATE TABLE books_metadata (
    id SERIAL PRIMARY KEY,
    english_title TEXT NOT NULL,
    arabic_title TEXT
);
```

3. Copy your Supabase URL and anon key to the `.env` file

### 6. Verify Setup

Run the setup test script to verify everything is configured correctly:

```bash
python test_setup.py
```

This script will check:

- Python version compatibility
- Required dependencies installation
- Environment variables configuration
- Data files existence
- Database connectivity
- Data loading functionality

## Running Locally

### Option 1: Run Bot Only

```bash
python bot.py
```

### Option 2: Run with Web Server (Recommended for Production)

```bash
python server.py
```

This starts both the Discord bot and a Flask web server on port 8080 for health checks.

## Testing

### Manual Testing Commands

Once the bot is running and added to your Discord server, you can test it using these slash commands:

#### Setup Commands

```
/bismillah setup channel_id:<channel_id> start_book_id:1 start_chapter_id:1 start_hadith_id:1 start_name:1
```

Sets up daily messages for a specific channel.

#### Hadith Commands

```
/bismillah random
/bismillah specific book_no:1 chapter_no:1 hadith_no:1
```

#### Name Commands

```
/bismillah random_name
/bismillah specific_name number:1
/bismillah specific_names number:1
```

#### Management Commands

```
/bismillah stop channel_id:<channel_id>
```

Stops daily messages for a specific channel.

### Testing Daily Messages

To test the daily message functionality without waiting for 6:00 PM:

1. Temporarily modify the schedule in `bot.py`:

```python
# Change this line (around line 73):
@tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))

# To this for testing (runs every 10 seconds):
@tasks.loop(seconds=10)
```

2. Restart the bot and observe the messages being sent every 10 seconds
3. Remember to revert this change before deploying to production

### Unit Testing

Create test files to verify functionality:

```bash
# Test database connections
python -c "from db import get_channels; print('Database connection successful:', get_channels())"

# Test data loading
python -c "from utils import *; import json; print('Data files loaded successfully')"
```

## Production Deployment

### Environment Variables

Ensure these environment variables are set in your production environment:

```env
DISCORD_TOKEN=your_production_discord_bot_token
SUPABASE_URL=your_production_supabase_url
SUPABASE_KEY=your_production_supabase_key
```

### Deployment Options

#### Option 1: Traditional Server Deployment

1. **Install dependencies**:

```bash
uv sync --frozen --no-dev
```

2. **Run with Gunicorn**:

```bash
uv run gunicorn -w 1 -b 0.0.0.0:8080 server:app
```

3. **Set up process manager** (systemd, supervisor, etc.):

```ini
# /etc/systemd/system/hadithbot.service
[Unit]
Description=HadithBot Discord Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/HadithBot
Environment=PATH=/path/to/HadithBot/.venv/bin
ExecStart=/path/to/HadithBot/.venv/bin/gunicorn -w 1 -b 0.0.0.0:8080 server:app
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Option 2: Docker Deployment

**Using Docker Compose (Recommended)**:

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your actual values

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Using Docker directly**:

```bash
# Build the image
docker build -t hadithbot .

# Run the container
docker run -d \
  --name hadithbot \
  -p 8080:8080 \
  --env-file .env \
  -v $(pwd)/data:/app/data:ro \
  hadithbot

# View logs
docker logs -f hadithbot
```

The project includes a `Dockerfile` and `docker-compose.yml` for easy containerized deployment.

#### Option 3: Cloud Platform Deployment

**Heroku**:

The project includes a `Procfile` for Heroku deployment.

1. Deploy:

```bash
heroku create your-hadithbot-app
heroku config:set DISCORD_TOKEN=your_token
heroku config:set SUPABASE_URL=your_url
heroku config:set SUPABASE_KEY=your_key
git push heroku main
```

**Railway/Render**: Similar process with their respective deployment methods.

### Production Monitoring

#### Health Check Endpoint

The Flask server provides a health check endpoint:

```
GET http://your-domain:8080/
Response: "Hello. I am alive!"
```

#### Logging

The bot includes comprehensive logging. Monitor logs for:

- Daily message delivery status
- Database connection issues
- Discord API errors
- Command execution errors

#### Database Monitoring

Monitor your Supabase dashboard for:

- API usage
- Database performance
- Error rates

### Scheduled Tasks

The bot automatically handles daily message scheduling using Discord.py's task loops. No external cron jobs are required.

**Daily Schedule**: 6:00 PM Toronto Time (America/Toronto timezone)

### Scaling Considerations

- **Single Instance**: The current architecture is designed for single-instance deployment
- **Database**: Supabase handles scaling automatically
- **Rate Limits**: Discord API rate limits are handled by the discord.py library
- **Memory Usage**: Minimal - only loads the 99 names JSON file into memory

## Troubleshooting

### Common Issues

1. **Bot not responding to commands**:
   - Verify bot permissions in Discord server
   - Check if commands are synced (`await self.tree.sync()` in setup_hook)
   - Ensure bot token is correct

2. **Database connection errors**:
   - Verify Supabase URL and key
   - Check Supabase project status
   - Ensure tables exist with correct schema

3. **Daily messages not sending**:
   - Check timezone configuration
   - Verify channel IDs in database
   - Review bot permissions in target channels

4. **Import errors**:
   - Ensure all dependencies are installed
   - Check Python version (3.11+ required)
   - Verify data files exist in `data/` directory

### Debug Mode

Enable debug logging by modifying the logging level in `bot.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please ensure compliance with Discord's Terms of Service and API guidelines when using this bot.
