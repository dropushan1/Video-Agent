import os
import shutil
import uuid
import glob
from data_handler import init_db, insert_record, analyze_batch, save_new_metadata, get_unique_id, check_text_exists, get_existing_data, load_metadata, check_filename_exists
from media_handler import transcribe_audio, process_image
import time

# Configuration
# Path to "All Files" relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALL_FILES_DIR = os.path.join(SCRIPT_DIR, "All Files")

if not os.path.exists(ALL_FILES_DIR):
    os.makedirs(ALL_FILES_DIR)

PLATFORM_MAP = {
    "1": "Tiktok",
    "2": "Twitter",
    "3": "Instagram",
    "4": "Photos"
}

MAX_BATCH_CHARS = 10000

def get_dest_folder(platform, file_type):
    """
    Returns the nested path: All Files / [Platform] / [type]
    """
    # Sanitize names for folders
    p = platform.strip() if platform else "Unknown"
    t = file_type.lower().strip() if file_type else "unknown"
    
    path = os.path.join(ALL_FILES_DIR, p, t)
    os.makedirs(path, exist_ok=True)
    return path


def process_batch(batch):
    """
    Processes a list of items (batch) using Gemini AI.
    Handles rotation and atomic saving (copy + DB).
    """
    if not batch:
        return
    
    print(f"\n--- Processing Batch ({len(batch)} items) ---")
    
    # Analyze_batch expects a list of: {'id':..., 'raw_text':..., 'platform':...}
    ai_inputs = [{"id": x["id"], "raw_text": x["raw_text"], "platform": x["platform"]} for x in batch]
    
    try:
        ai_results = analyze_batch(ai_inputs)
    except RuntimeError as e:
        if str(e) == "QUOTA_EXCEEDED":
            print(f"\n🚨 CRITICAL: Gemini API Quota Exceeded (429)! Stopping process.")
            import sys
            sys.exit(0)
        else:
            print(f"   [Error] Unexpected error: {e}")
            ai_results = []
    
    if not ai_results:
        print(f"   [Error] No AI results for this batch. Skipping.")
        return

    # Process each result in the batch mapping it back to the original items
    for item in batch:
        # Find corresponding AI result
        result = next((r for r in ai_results if r.get('id') == item['id']), None)
        
        if not result:
            print(f"   [Error] No results found for item {item['id']}")
            continue

        # Final destination check/copy (ATOMIC MOVE)
        dest_path = item['file_path']
        source_path = item['source_path']
        
        if not os.path.exists(dest_path):
            try:
                shutil.copy2(source_path, dest_path)
            except Exception as e:
                print(f"   [Error] Final file copy failed for {item['id']}: {e}")
                continue

        # Check for New Metadata
        check_map = {'Category': 'Category', 'Tags': 'Tags', 'Types': 'Types'}
        for csv_key, json_key in check_map.items():
            val = str(result.get(json_key, ""))
            if "(NEW)" in val:
                clean_val = val.replace("(NEW)", "").strip()
                
                # Double check against latest CSV
                current_meta = load_metadata()
                col_list = current_meta.get(csv_key, [])
                
                def is_val_new(v, existing_list):
                    return not any(ex.lower() == v.lower().strip() for ex in existing_list)

                if csv_key == 'Tags':
                    for tag in clean_val.split(','):
                        t = tag.strip()
                        if t and is_val_new(t, col_list):
                            print(f"✨ New Tag Detected: {t} ✨")
                            save_new_metadata('Tags', t)
                else:
                    if is_val_new(clean_val, col_list):
                        print(f"✨ New {csv_key} Detected: {clean_val} ✨")
                        save_new_metadata(csv_key, clean_val)
                    
        record = {
            "id": item['id'],
            "title": result.get("Title", ""),
            "summary": result.get("Summary", ""),
            "category": result.get("Category", ""),
            "tags": result.get("Tags", ""),
            "types": result.get("Types", ""),
            "refined_text": result.get("Refined Text", ""),
            "raw_text": item['raw_text'],
            "platform": item['platform'],
            "file_type": item['file_type'],
            "file_path": item['file_path'],
            "original_filename": item.get('original_filename')
        }
        insert_record(record)
        print(f"   ✅ Saved ID {item['id']}")


def process_workflow():
    # 1. Inputs
    input_folder = input("Enter the full path to the source folder: ").strip('"').strip("'")
    if not os.path.exists(input_folder):
        print(f"[Error] Folder '{input_folder}' not found.")
        return

    print("Select Platform:")
    for k, v in PLATFORM_MAP.items():
        print(f"{k}. {v}")
    plat_choice = input("Enter number: ").strip()
    platform = PLATFORM_MAP.get(plat_choice, "Unknown")

    print(f"\nScanning: {input_folder}")
    print(f"Platform: {platform}")
    
    # 2. Gather Files
    video_exts = {'.mp4', '.mov'} # Using set for O(1) lookup
    audio_exts = {'.mp3'}
    image_exts = {'.jpg', '.jpeg', '.png', '.heic', '.webp'}
    valid_exts = video_exts | audio_exts | image_exts

    files_to_process = []
    for f in os.listdir(input_folder):
        ext = os.path.splitext(f)[1].lower()
        if ext in valid_exts:
            full_path = os.path.join(input_folder, f)
            if os.path.isfile(full_path):
                files_to_process.append(full_path)
    
    if not files_to_process:
        print("No valid files found.")
        return
    
    print(f"Found {len(files_to_process)} files.\n")

    # 3. Processing Loop (Batching)
    current_batch = []
    current_chars = 0

    for index, file_path in enumerate(files_to_process, 1):
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        print(f"\n--- Scanning {index}/{len(files_to_process)}: {filename} ---")
        
        # 1. Robust Extraction: Determine ID and Original Name
        uid = None
        original_name = filename # Default if not already prefixed
        file_ext = os.path.splitext(filename)[1].lower()

        # Check for {8 chars}_ pattern
        if len(filename) > 9 and filename[8] == '_':
            potential_uid = filename[:8]
            if potential_uid.isalnum():
                uid = potential_uid
                original_name = filename[9:] # Everything after the first '_'

        # 2. Early Duplicate Checks
        # A) Check by Original Name (The text after the ID_ or the raw filename)
        match_id = check_filename_exists(original_name)
        if match_id:
            print(f"⚠️ Skipped: Filename duplicate detected (Matches existing ID: {match_id})")
            continue
        
        # B) Check by ID (If we extracted one from the filename)
        if uid:
            data = get_existing_data(uid)
            if data:
                # If fully processed, skip
                if data[0] and data[1]:
                    print(f"⚠️ Skipped: Already processed (Matches existing ID: {uid})")
                    continue
        
        # 3. Generate ID if new
        if not uid:
            uid = get_unique_id()
        
        new_filename = f"{uid}_{original_name}"

        # 4. Determine Type
        file_type = "Unknown"
        video_exts = {'.mp4', '.mov'}
        audio_exts = {'.mp3'}
        image_exts = {'.jpg', '.jpeg', '.png', '.heic', '.webp'}

        if file_ext in video_exts:
            file_type = "Video"
        elif file_ext in audio_exts:
            file_type = "Audio"
        elif file_ext in image_exts:
            file_type = "Image"
        
        dest_folder = get_dest_folder(platform, file_type)
        dest_path = os.path.join(dest_folder, new_filename)

        # 3. Smart Resume Logic (Condition A)
        raw_text = ""
        
        if uid:
            data = get_existing_data(uid)
            if data:
                existing_raw_text, existing_refined_text = data
                
                # Condition A: Already fully processed
                if existing_raw_text and existing_refined_text:
                    print(f"⚠️ Skipped: Already processed (Matches existing ID: {uid})")
                    if not os.path.exists(dest_path):
                         try:
                            shutil.copy2(file_path, dest_path)
                         except:
                            pass 
                    continue
                
                # Condition B: Resume AI (Has raw but no refined)
                if existing_raw_text:
                    print(f"🔄 Resuming: Has text, adding to queue (ID: {uid})")
                    raw_text = existing_raw_text
                    
                    item = {
                        "id": uid,
                        "file_path": dest_path,
                        "source_path": file_path,
                        "raw_text": raw_text,
                        "char_count": len(raw_text),
                        "platform": platform,
                        "file_type": file_type,
                        "original_filename": original_name
                    }
                    
                    # Batch Management
                    if current_chars + item['char_count'] > MAX_BATCH_CHARS:
                        process_batch(current_batch)
                        current_batch = []
                        current_chars = 0
                    
                    current_batch.append(item)
                    current_chars += item['char_count']
                    continue 

        # Condition C: New File (Transcription needed)
        # 5. Extract Text (Delay copying)
        if file_type == "Audio" or file_type == "Video":
            raw_text = transcribe_audio(file_path)
        elif file_type == "Image":
            raw_text = process_image(file_path)
        
        if not raw_text: raw_text = ""

        # 6. Check for Content Duplicates (DO THIS BEFORE SAVING)
        matching_id = check_text_exists(raw_text)
        if matching_id:
            print(f"⚠️ Skipped: Duplicate content detected (Matches existing ID: {matching_id})")
            continue

        # 5.5 Save Partial Record and Copy File (EAGER SAVE)
        # This ensures we don't lose the transcription if Gemini fails
        partial_record = {
            "id": uid,
            "raw_text": raw_text,
            "platform": platform,
            "file_type": file_type,
            "file_path": dest_path,
            "original_filename": original_name
        }
        insert_record(partial_record)
        
        if not os.path.exists(dest_path):
            try:
                shutil.copy2(file_path, dest_path)
            except Exception as e:
                print(f"   [Error] Eager file copy failed: {e}")
        
        item = {
            "id": uid,
            "file_path": dest_path,
            "source_path": file_path,
            "raw_text": raw_text,
            "char_count": len(raw_text),
            "platform": platform,
            "file_type": file_type,
            "original_filename": original_name
        }
        
        # Batch Management
        if current_chars + item['char_count'] > MAX_BATCH_CHARS:
            process_batch(current_batch)
            current_batch = []
            current_chars = 0
        
        current_batch.append(item)
        current_chars += item['char_count']

    # Final batch
    process_batch(current_batch)

    print("\nWorkflow Complete!")

if __name__ == "__main__":
    init_db()
    process_workflow()
