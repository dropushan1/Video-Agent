import sys
import agent_logic
import db_ops
import config
import os
import subprocess

CHARACTER_LIMIT = 50000

def open_file(path):
    if not path:
        return
    try:
        if sys.platform == 'darwin':
            subprocess.run(['open', path])
        elif sys.platform == 'win32':
            os.startfile(path)
        else:
            subprocess.run(['xdg-open', path])
    except Exception as e:
        print(f"Could not open file {path}: {e}")

def main():
    print("=== Video Agent User Interaction System ===")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        query = input("\nAsk a question: ").strip()
        if query.lower() in ['exit', 'quit']:
            break
        if not query:
            continue

        print("\n[1/3] Filtering Database...")
        meta = db_ops.load_metadata()
        filter_criteria = agent_logic.run_filtering_agent(query, meta)
        
        print(f"      Selected Criteria: {filter_criteria}")
        
        candidates = db_ops.search_videos_by_criteria(filter_criteria)
        print(f"      Found {len(candidates)} potential videos.")
        
        if not candidates:
            print("No videos found matching criteria. Try a different query.")
            continue

        print("\n[2/3] Refining Selection...")
        ranked_ids = agent_logic.run_refinement_agent(query, candidates)
        print(f"      AI selected {len(ranked_ids)} videos.")

        # Prune based on 50k limit
        final_video_details = []
        current_char_count = 0
        
        # We need to fetch details for these IDs to check length
        # Fetching all selected to check lengths is fine since list is small (<30)
        details_map = db_ops.get_full_video_details(ranked_ids)
        
        # Iterate in RANKED order
        used_ids = []
        skipped_count = 0
        
        for vid_id in ranked_ids:
            if vid_id not in details_map:
                continue
            
            vid = details_map[vid_id]
            text = vid.get('refined_text', '') or ""
            text_len = len(text)
            
            if current_char_count + text_len <= CHARACTER_LIMIT:
                final_video_details.append(vid)
                used_ids.append(vid_id)
                current_char_count += text_len
            else:
                # Limit reached
                skipped_count += 1
                # We stop here to preserve ranking importance
                # (Or we could skip large ones and try to fit smaller ones, 
                # but "ranking is key" usually means stop)
                # For now, I will stop to ensure highest quality.
                # However, the user said "just choose the top important ids which are less then 50,000"
                # which technically allows skipping a big one to fit a small one?
                # "system should only get the 1 and 2 id... if it takes the 4 as well [total > limit]"
                # This suggests simpler accumulation.
                pass
        
        print(f"      Context Buffer: {current_char_count}/{CHARACTER_LIMIT} chars used.")
        print(f"      Final count sent to AI: {len(final_video_details)} videos.")

        if not final_video_details:
             print("No videos fit within the limit context. (This shouldn't happen usually).")
             continue

        print("\n[3/3] Generating Response...")
        response = agent_logic.run_response_agent(query, final_video_details)
        
        if not response:
            print("Error generating response.")
            continue

        print("\n" + "="*40)
        print("AI RESPONSE:")
        print("="*40)
        print(response.get("answer_text", "No text provided."))
        print("\n" + "-"*40)
        print("RECOMMENDED VIDEOS:")
        
        recs = response.get("recommendations_with_notes", [])
        other_recs = response.get("other_recommendations", [])
        
        all_recs = recs + other_recs
        
        # Map back to file paths for opening
        # We have details in final_video_details (list of dicts)
        # We can look up in details_map if needed, but only for those passed to AI?
        # The AI might recommend IDs that were passed to it.
        # But wait, did we pass ALL ids to AI? No, only final_video_details.
        # So AI only knows about those.
        
        lookup = {v['id']: v for v in final_video_details}
        
        for i, item in enumerate(all_recs, 1):
            vid_id = item.get('id')
            note = item.get('note', '')
            
            if vid_id in lookup:
                vid = lookup[vid_id]
                title = vid.get('title', 'Unknown Title')
                print(f"\n{i}. {title}")
                if note:
                    print(f"   Note: {note}")
                
                # Interactive option? 
                # We can store these for post-loop interaction or just print path
                print(f"   Path: {vid.get('file_path', 'N/A')}")
            else:
                print(f"\n{i}. (Video ID {vid_id} not found in context)")

        print("="*40 + "\n")
        
        # Simple interaction to open video
        while True:
            choice = input("Enter number to open video (or 'n' for next query): ").strip()
            if choice.lower() == 'n':
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(all_recs):
                    vid_id_to_open = all_recs[idx].get('id')
                    if vid_id_to_open and vid_id_to_open in lookup:
                        path = lookup[vid_id_to_open].get('file_path')
                        if path:
                            print(f"Opening {path}...")
                            open_file(path)
                        else:
                            print("No file path available for this video.")
                    else:
                        print("Cannot open this video (not in local context).")
                else:
                    print("Invalid number.")
            except ValueError:
                print("Invalid input.")

if __name__ == "__main__":
    main()
