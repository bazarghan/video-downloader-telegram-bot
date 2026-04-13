import os
import uuid
import asyncio
import yt_dlp

async def fetch_formats(url: str) -> list:
    """
    Returns a list of dictionaries with 'label' and 'format_id' (selector).
    Extracts available heights to offer valid options dynamically.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    options = []
    
    def _fetch():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            if not info or not info.get('formats'):
                return [{"label": "Best Quality", "format_id": "best"}]

            resolutions = set()
            for f in info.get('formats', []):
                # Try to grab height, ignore None or weird non-int streams
                h = f.get('height')
                if isinstance(h, int) and h >= 144:
                    resolutions.add(h)
                    
            # We will filter to some common resolutions to avoid cluttering the keyboard
            common_res = [144, 360, 480, 720, 1080]
            # Only keep common resolutions that actually exist in the video
            available_res = [r for r in common_res if any(abs(r - res) <= 20 for res in resolutions)]
            
            # Build options
            for r in available_res:
                options.append({
                    "label": f"{r}p",
                    "format_id": f"bestvideo[height<={r}]+bestaudio/best[height<={r}]"
                })
                
            if not options:
                options.append({"label": "Best Quality", "format_id": "best"})
                
            # Add audio option
            options.append({"label": "Audio Only (MP3)", "format_id": "bestaudio/best"})
            return options

        except Exception as e:
            print(f"Error fetching formats: {e}")
            # Fallback
            return [{"label": "Best Quality", "format_id": "best"}]

    return await asyncio.to_thread(_fetch)

async def download_video(url: str, format_selector: str) -> str:
    """
    Downloads the video and returns the path to the downloaded file.
    Runs asynchronously using asyncio.to_thread to not block the bot.
    """
    def _download():
        # Generate a unique path
        filename_template = f"downloads/{uuid.uuid4().hex}_%(title).100s.%(ext)s"
        
        # Ensure downloads folder exists
        os.makedirs("downloads", exist_ok=True)
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': filename_template,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        
        # If it's an audio extraction request, ensure mp3 conversion
        if format_selector == "bestaudio/best":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        # For video, ensure we merge to mp4 with ffmpeg if streams are separate
        else:
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # We use extract_info with download=True so we get the exact resulting file path
            info = ydl.extract_info(url, download=True)
            
            # Retrieve the created filename
            if 'requested_downloads' in info:
                return info['requested_downloads'][0]['filepath']
            else:
                # Basic fallback
                return ydl.prepare_filename(info)
                
    # Run the blocking yt-dlp call in a separate thread
    return await asyncio.to_thread(_download)

