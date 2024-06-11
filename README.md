# nginx log bot

Telegram bot that listens for changes in a default nginx access.log file
(mounted to the docker container as `/access.log`)
and sends the info about new accesses to the specified user.

## Required env vars:

    IPINFO_API_KEY = ""     # ipinfo.io API key 
    TELEGRAM_API_KEY = ""   # Bot API key
    TELEGRAM_USER_ID = ""   # ID of the user to send log updates to
    ENGINE_URL = ""         # DB URL for SQLAlchemy, can be simply an SQLite3 file like "sqlite:///access_logs.db"

Can be provided either as .env file or set in the Docker container 
(e.g. via `-e` or `--env-file` flags)
