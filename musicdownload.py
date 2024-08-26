import telebot
from telebot import types
import yt_dlp
import os
import requests
import urllib.parse
import time
import random

# Telegram bot token
TOKEN = '7186451521:AAH2QYHUQeIKRonn_MTp3j9Fp5NLVFriY4w'

# YouTube API key
YOUTUBE_API_KEY = 'AIzaSyAwLdpz3tMPrasYUDbuHgxbqBxHp65xv_Q'

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Define limits
MAX_BUTTON_TEXT_LENGTH = 64  # Maximum length for button text
MAX_CALLBACK_DATA_LENGTH = 64  # Maximum length for callback data

# Start image link
START_IMAGE_LINK = 'https://telegra.ph/file/82e3f9434e48d348fa223.jpg'
# Start menu text
START_MENU_TEXT = (
    "Hello there! I'm a song downloading bot with the following commands:\n\n"
    "🔍 Use /search to download YouTube video or song \n"
    "   For example, send:\n"
    "   /search royalty"
)

# Global variables
last_update_time = time.time()
rate_limit_retries = 0
MAX_RETRIES = 5
UPDATE_INTERVAL = 1  # Update progress every 2 seconds

@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.send_photo(message.chat.id, START_IMAGE_LINK, caption=START_MENU_TEXT)

@bot.message_handler(commands=['search'])
def search(message):
    try:
        query = message.text.split(' ', 1)[1]
        search_results = search_youtube(query)
        if search_results:
            keyboard = types.InlineKeyboardMarkup()
            for index, result in enumerate(search_results):
                video_url = result['url']
                video_title = result['title']
                # Encode URL and title
                encoded_url = urllib.parse.quote(video_url)
                encoded_title = urllib.parse.quote(video_title)
                
                # Truncate or shorten text and callback data
                button_text_audio = truncate_text(f"{index + 1}. Download Audio")
                button_text_video = truncate_text(f"{index + 1}. Download Video")
                callback_data_audio = truncate_text(f"audio {encoded_url} {encoded_title}")
                callback_data_video = truncate_text(f"video {encoded_url} {encoded_title}")
                
                audio_button = types.InlineKeyboardButton(text=button_text_audio, callback_data=callback_data_audio)
                video_button = types.InlineKeyboardButton(text=button_text_video, callback_data=callback_data_video)
                keyboard.add(audio_button, video_button)
            bot.send_message(message.chat.id, "Choose download format:", reply_markup=keyboard)
        else:
            bot.reply_to(message, "No results found.")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def search_youtube(query):
    try:
        search_url = (
            f"https://www.googleapis.com/youtube/v3/search?"
            f"part=snippet&q={urllib.parse.quote(query)}&type=video&key={YOUTUBE_API_KEY}&maxResults=5"
        )
        response = requests.get(search_url)
        results = response.json()

        search_results = []
        if 'items' in results:
            for item in results['items']:
                video_title = item['snippet']['title']
                video_url = f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                search_results.append({'title': video_title, 'url': video_url})

        return search_results
    except Exception as e:
        print(f"Error searching for YouTube videos: {e}")
        return None

def handle_download(message, youtube_link, is_audio, title):
    downloading_message = bot.send_message(message.chat.id, "Downloading 0%.")

    try:
        ydl_opts = {
            'format': 'bestaudio/best' if is_audio else 'best',
            'outtmpl': f'{sanitize_filename(title)}.%(ext)s',
            'progress_hooks': [lambda d: progress_callback(d, downloading_message)],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_link, download=True)
            file_path = ydl.prepare_filename(info_dict)

        # Determine file size and check Telegram's size limit
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
        max_size_mb = 50  # Telegram's max size limit for files

        if file_size_mb > max_size_mb:
            bot.reply_to(message, f"File size exceeds the Telegram limit of {max_size_mb} MB.")
            os.remove(file_path)
        else:
            uploading_message = bot.send_message(message.chat.id, "Uploading, please wait...")

            if is_audio:
                # Rename to MP3 if it’s audio
                mp3_path = f'{sanitize_filename(title)}.mp3'
                os.rename(file_path, mp3_path)
                file_path = mp3_path

                with open(file_path, 'rb') as media_file:
                    bot.send_audio(message.chat.id, media_file, reply_to_message_id=downloading_message.message_id)
            else:
                with open(file_path, 'rb') as media_file:
                    bot.send_video(message.chat.id, media_file, reply_to_message_id=downloading_message.message_id)

            os.remove(file_path)
            bot.delete_message(message.chat.id, uploading_message.message_id)
            bot.send_message(message.chat.id, "Download complete!")

    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")
        print(f"Error handling download: {e}")
        bot.delete_message(message.chat.id, downloading_message.message_id)

def progress_callback(d, downloading_message):
    global last_update_time
    current_time = time.time()
    
    if d['status'] == 'downloading':
        percent = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
        
        # Update every 2 seconds
        if current_time - last_update_time >= UPDATE_INTERVAL:
            last_update_time = current_time
            current_message = f"Downloading {percent}%."
            if current_message != downloading_message.text:
                try:
                    bot.edit_message_text(current_message, chat_id=downloading_message.chat.id, message_id=downloading_message.message_id)
                except telebot.apihelper.ApiException as e:
                    print(f"API Exception: {e}")
                    handle_rate_limit(e)

def sanitize_filename(title):
    # Replace any characters that are invalid in file names
    return ''.join(c for c in title if c.isalnum() or c in (' ', '_', '-'))

def truncate_text(text, max_length=MAX_BUTTON_TEXT_LENGTH):
    return text[:max_length]  # Truncate text to the maximum length

def decode_callback_data(data):
    # Decode URL and title from callback data
    parts = data.rsplit(' ', 1)
    if len(parts) == 2:
        url = urllib.parse.unquote(parts[0])
        title = urllib.parse.unquote(parts[1])
        return url, title
    return None, None

def download_audio(message, data):
    try:
        youtube_link, title = decode_callback_data(data)
        handle_download(message, youtube_link, is_audio=True, title=title)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def download_video(message, data):
    try:
        youtube_link, title = decode_callback_data(data)
        handle_download(message, youtube_link, is_audio=False, title=title)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def handle_rate_limit(e):
    global rate_limit_retries
    if e.result.status_code == 429:  # Too Many Requests
        rate_limit_retries += 1
        if rate_limit_retries <= MAX_RETRIES:
            retry_after = int(e.result.headers.get('Retry-After', 30))  # Default to 30 seconds if not provided
            print(f"Rate limit exceeded. Retrying after {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            print("Max retries reached. Exiting.")
            exit()
    else:
        print(f"Unexpected API error: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        command, data = call.data.split(' ', 1)
        if command == "audio":
            download_audio(call.message, data)
        elif command == "video":
            download_video(call.message, data)
    except Exception as e:
        print(f"Error handling callback query: {e}")
        send_message_with_retry(call.message.chat.id, f"Error: {str(e)}")

def send_message_with_retry(chat_id, text):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            bot.send_message(chat_id, text)
            return
        except telebot.apihelper.ApiException as e:
            if e.result.status_code == 429:  # Too Many Requests
                retry_after = int(e.result.headers.get('Retry-After', 30))  # Default to 30 seconds if not provided
                time.sleep(retry_after)
            else:
                print(f"Unexpected API error: {e}")
                retries += 1
                time.sleep(random.uniform(1, 3))  # Random delay before retrying
    print("Max retries reached. Exiting.")

# Start the bot
bot.polling()

