import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp

import database as db
import downloader

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains how to use the bot."""
    welcome_text = (
        "👋 Welcome to the Video Downloader Bot!\n\n"
        "Send me a link from YouTube, Twitter, Instagram, TikTok, etc., "
        "and I will help you download the video directly here."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives a URL, fetches available formats, and replies with an inline keyboard."""
    url = update.message.text.strip()
    
    # Basic URL validation
    if not re.match(r'^https?://', url):
        await update.message.reply_text("Please provide a valid URL starting with http:// or https://")
        return

    status_message = await update.message.reply_text("🔍 Analyzing link...")
    
    # Fetch formats (this doesn't download the video, just metadata)
    options = await downloader.fetch_formats(url)
    
    # Save the full URL in DB to a short ID to bypass TGs 64-byte callback limit
    short_id = db.save_url(url)
    
    keyboard = []
    # format of callback_data: f"{short_id}|{index}" (index points to format options)
    # We will temporarily store options in context.chat_data to map index to format_id
    context.chat_data[short_id] = options
    
    for idx, opt in enumerate(options):
        callback_data = f"{short_id}|{idx}"
        keyboard.append([InlineKeyboardButton(opt['label'], callback_data=callback_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await status_message.edit_text("🎬 Select quality:", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user's quality selection."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    try:
        short_id, idx_str = data.split('|')
        idx = int(idx_str)
    except Exception:
        await query.edit_message_text("❌ Invalid callback data.")
        return
        
    url = db.get_url(short_id)
    if not url:
        await query.edit_message_text("❌ This link has expired. Please send the link again.")
        return
        
    options = context.chat_data.get(short_id)
    if not options or idx >= len(options):
        await query.edit_message_text("❌ Options expired. Please send the link again.")
        return
        
    selected_option = options[idx]
    format_id = selected_option['format_id']
    is_audio = format_id == "bestaudio/best"
    
    # Check cache
    cached_file_id = db.get_file_id(url, format_id)
    if cached_file_id:
        try:
            if is_audio:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=cached_file_id)
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=cached_file_id)
            await query.edit_message_text(f"✅ Served from cache: {selected_option['label']}")
            return
        except Exception as e:
            # If for some reason the cached file ID is invalid, we proceed to download
            print(f"Failed to send cached file: {e}")

    # No cache hit, proceed to download
    await query.edit_message_text(f"⏳ Downloading ({selected_option['label']}). Please wait...")
    
    file_path = None
    try:
        file_path = await downloader.download_video(url, format_id)
        
        # Check standard file existance and size
        if not file_path or not os.path.exists(file_path):
            # Sometimes yt-dlp adds the .mp3 extension over the initial filepath dict
            if is_audio and file_path and not file_path.endswith('.mp3') and os.path.exists(file_path + ".mp3"):
               file_path += ".mp3"
            elif file_path and not file_path.endswith('.mp4') and os.path.exists(file_path + ".mp4"):
               file_path += ".mp4"
            else:
                await query.edit_message_text("❌ Download failed or file not found.")
                return
                
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50.0:
            await query.edit_message_text(
                f"❌ The downloaded file is {file_size_mb:.1f}MB, which is bigger than Telegram's 50MB bot upload limit.\n\n"
                f"Please try again and select a lower quality."
            )
            return
            
        await query.edit_message_text("🚀 Uploading to Telegram...")
        
        # Upload
        message = None
        with open(file_path, 'rb') as f:
            if is_audio:
                message = await context.bot.send_audio(chat_id=query.message.chat_id, audio=f)
                file_id = message.audio.file_id
            else:
                message = await context.bot.send_video(chat_id=query.message.chat_id, video=f)
                file_id = message.video.file_id
                
        # Cache it for future
        db.save_file_id(url, format_id, file_id)
        
        await query.edit_message_text(f"✅ Upload successful! ({selected_option['label']})")
        
    except yt_dlp.utils.DownloadError as e:
        await query.edit_message_text(f"❌ yt-dlp Error: {str(e)[:100]}...")
    except Exception as e:
        await query.edit_message_text("❌ An unexpected error occurred.")
        print(f"Error during download or upload: {e}")
    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
