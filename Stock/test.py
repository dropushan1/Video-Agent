import os
import sys
from yt_dlp import YoutubeDL

# Folder where videos will be saved
DOWNLOAD_DIR = "TT Videos"

def read_links_from_file(file_path):
    # Remove quotes if the user copied the path with them
    file_path = file_path.strip('"').strip("'")
    
    if not os.path.isfile(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    if not links:
        print("❌ No URLs found in file.")
        sys.exit(1)

    return links

def download_videos(links):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Configuration for high-quality MP4 download
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": False,
        # Added a standard user-agent to avoid being blocked by TikTok
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }

    with YoutubeDL(ydl_opts) as ydl:
        for index, link in enumerate(links, start=1):
            try:
                print(f"\n⬇️  Downloading {index}/{len(links)}")
                ydl.download([link])
            except Exception as e:
                print(f"⚠️ Failed to download: {link}")
                print(f"Error: {e}")

def main():
    try:
        txt_path = input("Enter the full path to the TXT file: ").strip()
        
        links = read_links_from_file(txt_path)
        print(f"\n📄 Found {len(links)} links. Starting MP4 downloads...")
        
        download_videos(links)

        print("\n✅ All downloads completed!")
        print(f"📁 Saved in folder: {os.path.abspath(DOWNLOAD_DIR)}")

    except KeyboardInterrupt:
        print("\n❌ Cancelled by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()