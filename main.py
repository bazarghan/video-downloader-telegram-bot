import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

import database as db
import handlers

# Setup basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Make sure we have a bot token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Initialize the database
    db.init_db("bot.db")
    
    # Ensure downloads directory exists
    os.makedirs("downloads", exist_ok=True)

    # Build the application
    builder = ApplicationBuilder().token(token)

    local_api_url = os.environ.get("LOCAL_API_URL")
    if local_api_url:
        logger.info(f"Using local Bot API server at: {local_api_url}")
        builder.base_url(f"{local_api_url}")
        builder.base_file_url(f"{local_api_url}/file")

    application = builder.build()

    # Register handlers
    application.add_handler(CommandHandler('start', handlers.start))
    
    # Message handler filters out command starting with '/' 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    # Callback query handler for inline keyboard response
    application.add_handler(CallbackQueryHandler(handlers.handle_callback))

    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
