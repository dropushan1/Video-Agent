import os
import shutil
import uuid
import glob
from data_handler import init_db, insert_record, analyze_batch, save_new_metadata
from media_handler import transcribe_audio, process_image

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

def get_unique_id():
    return str(uuid.uuid4())[:8]

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
    extensions = ['*.mp4', '*.mp3', '*.jpg', '*.jpeg', '*.png', '*.heic']
    files_to_process = []
    # glob is not recursive by default, works for top level
    for ext in extensions:
        files_to_process.extend(glob.glob(os.path.join(input_folder, ext)))
    
    if not files_to_process:
        print("No valid files found.")
        return
    
    print(f"Found {len(files_to_process)} files.\n")

    # 3. Pre-Processing (Copy & Extract Text)
    processed_items = [] # Stores dicts with text and char count
    
    for file_path in files_to_process:
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Unique ID & Copy
        uid = get_unique_id()
        new_filename = f"{uid}{file_ext}"
        dest_path = os.path.join(ALL_FILES_DIR, new_filename)
        
        try:
            shutil.copy2(file_path, dest_path)
            print(f"Processing {filename} -> {uid}")
        except Exception as e:
            print(f"[Error] Copy failed for {filename}: {e}")
            continue

        # Extract Text
        file_type = "Unknown"
        raw_text = ""
        
        if file_ext in ['.mp4', '.mp3']:
            file_type = "Video" if file_ext == '.mp4' else "Audio"
            raw_text = transcribe_audio(dest_path)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.heic']:
            file_type = "Image"
            raw_text = process_image(dest_path)
        
        if not raw_text: raw_text = ""

        # Check for Duplicates
        from data_handler import check_text_exists
        if check_text_exists(raw_text):
            print(f"⚠️ Warning: Duplicate content detected for '{filename}'! Skipping...")
            try:
                os.remove(dest_path)
            except OSError:
                pass
            continue
        
        processed_items.append({
            "id": uid,
            "file_path": dest_path,
            "raw_text": raw_text,
            "char_count": len(raw_text),
            "platform": platform,
            "file_type": file_type
        })

    # 4. Greedy Batching Strategy
    print("\n--- Starting AI Analysis (Greedy Batching) ---")
    
    batches = []
    current_batch = []
    current_chars = 0
    
    for item in processed_items:
        if current_chars + item['char_count'] > MAX_BATCH_CHARS:
            if current_batch:
                batches.append(current_batch)
            current_batch = [item]
            current_chars = item['char_count']
        else:
            current_batch.append(item)
            current_chars += item['char_count']
            
    if current_batch:
        batches.append(current_batch)

    print(f"Created {len(batches)} batches based on 10k char limit.\n")

    # 5. Process Batches
    for i, batch in enumerate(batches, 1):
        print(f"Processing Batch {i}/{len(batches)} ({len(batch)} items)...")
        
        ai_inputs = [{"id": x["id"], "raw_text": x["raw_text"], "platform": x["platform"]} for x in batch]
        
        ai_results = analyze_batch(ai_inputs)
        
        for item in batch:
            result = next((r for r in ai_results if r.get('id') == item['id']), None)
            
            if result:
                # Check for New Metadata
                # Map CSV keys to JSON keys found in prompt result
                # CSV Keys: Category, Tags, Types
                # JSON Keys: Category, Tags, Types
                
                check_map = {'Category': 'Category', 'Tags': 'Tags', 'Types': 'Types'}
                
                for csv_key, json_key in check_map.items():
                    val = str(result.get(json_key, ""))
                    if "(NEW)" in val:
                        clean_val = val.replace("(NEW)", "").strip()
                        print(f"✨ New {csv_key} Detected: {clean_val} ✨")
                        
                        if csv_key == 'Tags':
                            for tag in clean_val.split(','):
                                save_new_metadata('Tags', tag.strip())
                        else:
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
                    "file_path": item['file_path']
                }
                insert_record(record)
                print(f"   Saved ID {item['id']}")
            else:
                print(f"   [Error] No AI result for ID {item['id']}")

    print("\nWorkflow Complete!")

if __name__ == "__main__":
    init_db()
    process_workflow()
