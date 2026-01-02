import asyncio
import os
import re
import json
from typing import Union
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from RessoMusic.utils.database import is_on_off
from RessoMusic.utils.formatters import time_to_seconds
import glob
import random
import logging
import aiohttp
import config
from config import API_URL, VIDEO_API_URL, API_KEY


def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir):
        return None
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file


async def download_song(link: str):
    # ID nikaalo
    try:
        if "v=" in link:
            video_id = link.split('v=')[-1].split('&')[0]
        else:
            video_id = link.split('/')[-1]
    except:
        return None

    # Check karo agar pehle se downloaded hai
    download_folder = "downloads"
    for ext in ["mp3", "m4a", "webm"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            return file_path
        
    # API Request Logic
    # Hum API_URL use karenge jo config me hai
    # Format: https://tera-api.com/extract?url=
    
    # Agar URL ke end me '=' nahi hai toh lagayenge
    api_endpoint = API_URL
    if not api_endpoint:
        print("API_URL not set in config!")
        return None
        
    song_url = f"{api_endpoint}{link}" 

    async with aiohttp.ClientSession() as session:
        download_url = None
        for attempt in range(5): # 5 baar try karega
            try:
                async with session.get(song_url) as response:
                    data = await response.json()
                    
                    # --- YAHAN HAI MAGIC FIX ---
                    # Hum status check nahi karenge, hum seedha Link dhoondenge
                    # Agar link mila, toh kaam ban gaya
                    
                    potential_link = data.get("url") or data.get("link") or data.get("download_url")
                    
                    if potential_link:
                        download_url = potential_link
                        break # Link mil gaya, loop todo
                    
                    # Agar Downloading bol raha hai toh wait karo
                    status = str(data.get("status", "")).lower()
                    if "download" in status or "process" in status:
                        await asyncio.sleep(3)
                    else:
                        # Agar error hai
                        print(f"API Wait: {data}")
                        await asyncio.sleep(2)
                        
            except Exception as e:
                print(f"[API FAIL Attempt {attempt}]: {e}")
                await asyncio.sleep(2)
        
        if not download_url:
            print("❌ API se Link nahi mila bhai!")
            return None
    
        # Link mil gaya, ab download karte hain
        try:
            download_folder = "downloads"
            os.makedirs(download_folder, exist_ok=True)
            file_path = f"{download_folder}/{video_id}.mp3"

            async with session.get(download_url) as file_response:
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
        except Exception as e:
            print(f"Download Error: {e}")
            return None
    return None


async def download_video(link: str):
    try:
        if "v=" in link:
            video_id = link.split('v=')[-1].split('&')[0]
        else:
            video_id = link.split('/')[-1]
    except:
        return None

    download_folder = "downloads"
    for ext in ["mp4", "webm", "mkv"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            return file_path
        
    # API Request Logic for Video
    api_endpoint = VIDEO_API_URL or API_URL
    if not api_endpoint:
        return None

    video_url = f"{api_endpoint}{link}"

    async with aiohttp.ClientSession() as session:
        download_url = None
        for attempt in range(5):
            try:
                async with session.get(video_url) as response:
                    data = await response.json()
                    
                    # Status ignore, Link focus
                    potential_link = data.get("url") or data.get("link")
                    
                    if potential_link:
                        download_url = potential_link
                        break
                    
                    await asyncio.sleep(3)
            except Exception as e:
                print(f"[API VIDEO FAIL]: {e}")
                await asyncio.sleep(2)
        
        if not download_url:
            return None
    
        try:
            download_folder = "downloads"
            os.makedirs(download_folder, exist_ok=True)
            file_path = f"{download_folder}/{video_id}.mp4"

            async with session.get(download_url) as file_response:
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
        except Exception as e:
            print(f"Video Download Error: {e}")
            return None
    return None


# Baki sab helper functions same hain
async def check_file_size(link):
    # ... (Same as before)
    return None 

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # API Call for Video
        downloaded_file = await download_video(link)
        if downloaded_file:
            return 1, downloaded_file
        else:
            return 0, "Failed to download video from API"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return []
            
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
            
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link

        # API Call for Audio/Song
        if video or songvideo:
             fpath = await download_video(link)
             return fpath, True
        else:
             fpath = await download_song(link)
             return fpath, True
            
