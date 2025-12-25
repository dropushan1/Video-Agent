import os
import sys
from yt_dlp import YoutubeDL

# Add path to data_handler
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
ENTRY_DIR = os.path.join(PARENT_DIR, "2. Database Entry")
sys.path.append(ENTRY_DIR)

# from data_handler import init_db, check_link_exists, insert_record, get_unique_id

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

    for index, link in enumerate(links, start=1):
        print(f"\n--- Processing {index}/{len(links)} ---")
        
        # Prepare Options
        out_tmpl = os.path.join(DOWNLOAD_DIR, f"%(title)s.%(ext)s")
        
        ydl_opts = {
            "outtmpl": out_tmpl,
            "restrictfilenames": True,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True
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

        # 3. Download
        try:
            print(f"⬇️  Downloading: {link}")
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                final_filename = ydl.prepare_filename(info)
                if mode == "mp3":
                    final_filename = os.path.splitext(final_filename)[0] + ".mp3"
                
                print(f"✅ Downloaded: {os.path.basename(final_filename)}")

        except Exception as e:
            print(f"⚠️ Failed to download: {link}")


def main():
    try:
        txt_path = input("Enter the full path to the TXT file: ").strip().strip('"').strip("'")

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
