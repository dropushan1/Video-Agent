import os
import sys
from yt_dlp import YoutubeDL

DOWNLOAD_DIR = "TT Videos"


def read_links_from_file(file_path):
    if not os.path.isfile(file_path):
        print("❌ File not found.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    if not links:
        print("❌ No URLs found in file.")
        sys.exit(1)

    return links


def download_links(links, mode):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": False,
    }

    if mode == "mp3":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:  # mp4
        ydl_opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        })

    with YoutubeDL(ydl_opts) as ydl:
        for index, link in enumerate(links, start=1):
            try:
                print(f"\n⬇️  Downloading {index}/{len(links)}")
                ydl.download([link])
            except Exception as e:
                print(f"⚠️ Failed to download: {link}")
                print(e)


def main():
    try:
        txt_path = input("Enter the full path to the TXT file: ").strip()

        print("\nChoose download format:")
        print("1 - MP3 (Audio)")
        print("2 - MP4 (Video)")
        choice = input("Enter 1 or 2: ").strip()

        if choice == "1":
            mode = "mp3"
        elif choice == "2":
            mode = "mp4"
        else:
            print("❌ Invalid choice.")
            return

        links = read_links_from_file(txt_path)
        print(f"\n📄 Found {len(links)} TikTok links")
        download_links(links, mode)

        print("\n✅ All downloads completed!")
        print(f"📁 Saved in folder: {DOWNLOAD_DIR}")

    except KeyboardInterrupt:
        print("\n❌ Cancelled by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
