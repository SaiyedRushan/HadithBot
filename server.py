from flask import Flask, jsonify
import asyncio
import threading
import os
import logging
from dotenv import load_dotenv

# Import your bot components
from bot import HadithBot, HadithCommands

app = Flask(__name__)

# Global bot instance
bot_instance = None
bot_task = None


@app.route("/")
def home():
    return "Hello. I am alive!"


@app.route("/health")
def health():
    """Enhanced health check with bot status"""
    if bot_instance and not bot_instance.is_closed():
        return (
            jsonify(
                {
                    "status": "healthy",
                    "bot": "online",
                    "latency": (
                        f"{bot_instance.latency * 1000:.2f}ms"
                        if bot_instance.latency
                        else "N/A"
                    ),
                    "guilds": len(bot_instance.guilds) if bot_instance.guilds else 0,
                }
            ),
            200,
        )
    else:
        return jsonify({"status": "unhealthy", "bot": "offline"}), 503


@app.route("/bot/restart", methods=["POST"])
def restart_bot():
    """Endpoint to restart the bot if needed"""
    global bot_instance, bot_task
    try:
        if bot_instance and not bot_instance.is_closed():
            asyncio.create_task(bot_instance.close())

        # Start new bot instance
        start_bot()
        return jsonify({"status": "Bot restart initiated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_bot_async():
    """Run the Discord bot in an asyncio event loop"""
    global bot_instance

    try:
        load_dotenv()
        discord_token = os.getenv("DISCORD_TOKEN")

        if not discord_token:
            raise Exception("DISCORD_TOKEN is not set")

        # Create bot instance
        bot_instance = HadithBot()
        bot_instance.tree.add_command(HadithCommands(bot_instance))

        @bot_instance.event
        async def on_ready():
            if bot_instance is not None:
                logging.info(f"Bot logged in as {bot_instance.user}\n")
            else:
                logging.info("Bot instance is None\n")

        # Run the bot
        bot_instance.run(discord_token, log_handler=None)

    except Exception as e:
        logging.error(f"Bot failed to start: {e}")
        raise


def start_bot():
    """Start the bot in a separate thread"""
    global bot_task
    bot_task = threading.Thread(target=run_bot_async, daemon=True)
    bot_task.start()
    logging.info("Bot thread started\n")


# Initialize bot when module loads
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Start the bot
    start_bot()

    # Start Flask server
    app.run(host="0.0.0.0", port=8080, debug=False)
else:
    # When running with Gunicorn
    logging.basicConfig(level=logging.INFO)
    start_bot()
