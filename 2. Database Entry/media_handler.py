import os
import shutil
import assemblyai as aai
from moviepy import VideoFileClip
from PIL import Image
from io import BytesIO
from pillow_heif import register_heif_opener
import requests

# Register HEIF opener
register_heif_opener()

# API Keys (Ideally these should be in a config/env file, but keeping here for simplicity as per previous code)
AAI_API_KEY = "620c0557617d4821a0f29514237e2e08"
OCR_API_KEY = "K83546019488957"

aai.settings.api_key = AAI_API_KEY

def transcribe_audio(file_path):
    """
    Handles Audio/Video transcription.
    1. If MP4, convert to temporary MP3.
    2. Transcribe using AssemblyAI (Nano model).
    3. Return text.
    """
    temp_audio_path = "temp_converted_audio.mp3"
    target_path = file_path
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    is_video = any(file_path.lower().endswith(ext) for ext in video_exts)
    transcript_text = ""

    try:
        # Convert video to audio if needed
        if is_video:
            print(f"   Note: Converting video to audio...")
            try:
                # Use a random temp name to avoid collisions in threading (though we are single threaded mostly)
                # But kept simple as per original
                video = VideoFileClip(file_path)
                video.audio.write_audiofile(temp_audio_path, logger=None)
                video.close()
                target_path = temp_audio_path
            except Exception as e:
                print(f"   [Error] Video conversion failed: {e}")
                return None

        # Transcribe
        config = aai.TranscriptionConfig(speech_model='nano', language_code='en')
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(target_path)

        if transcript.status == aai.TranscriptStatus.error:
            print(f"   [Error] Transcription API: {transcript.error}")
        else:
            transcript_text = transcript.text

    except Exception as e:
        print(f"   [Error] Transcription exception: {e}")
    finally:
        # Cleanup temp file
        if is_video and os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass

    return transcript_text or "[No audio text found]"

def process_image(file_path):
    """
    Handles Image OCR.
    1. Convert to JPG in memory.
    2. Compress if > 1MB.
    3. Send to OCR.space API.
    4. Return text.
    """
    def get_file_size_kb(file_obj):
        file_obj.seek(0, 2)
        size = file_obj.tell() / 1024
        file_obj.seek(0)
        return size

    try:
        img = Image.open(file_path)
        # Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=95, optimize=True)
        buffer.seek(0)

        # Compress if needed
        size_kb = get_file_size_kb(buffer)
        if size_kb > 1024:
            print(f"   Note: Compressing image ({size_kb:.1f} KB)...")
            quality = 90
            while size_kb > 1024 and quality > 10:
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                size_kb = get_file_size_kb(buffer)
                quality -= 10
        
        buffer.seek(0)
        
        # API Request
        payload = {'apikey': OCR_API_KEY, 'language': 'eng'}
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'image.jpg': buffer},
            data=payload,
        )
        result = response.json()
        
        if result.get('OCRExitCode') == 1:
            return result['ParsedResults'][0]['ParsedText']
        else:
            print(f"   [Error] OCR API: {result.get('ErrorMessage')}")
            return None

    except Exception as e:
        print(f"   [Error] Image processing exception: {e}")
        return None
