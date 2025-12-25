from flask import Flask, render_template, request, jsonify, send_from_directory
import agent_logic
import db_ops
import config
import chat_db
import os
import subprocess
import sys
import uuid

app = Flask(__name__)

# Directory where media files are stored
MEDIA_DIR = os.path.join(os.path.dirname(config.DB_PATH), "All Files")

CHARACTER_LIMIT = 50000

def open_file(path):
    if not path:
        return False
    try:
        path = os.path.abspath(path)
        if sys.platform == 'darwin':
            subprocess.run(['open', path])
        elif sys.platform == 'win32':
            os.startfile(path)
        else:
            subprocess.run(['xdg-open', path])
        return True
    except Exception as e:
        print(f"Could not open file {path}: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/media/<path:filename>')
def serve_media(filename):
    return send_from_directory(MEDIA_DIR, filename)

# --- Session Management ---
@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    return jsonify(chat_db.get_sessions())

@app.route('/api/sessions', methods=['POST'])
def create_session():
    data = request.json or {}
    session_id = str(uuid.uuid4())[:8]
    chat_db.create_session(session_id, data.get('name'))
    return jsonify({"id": session_id})

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    chat_db.delete_session(session_id)
    return jsonify({"success": True})

@app.route('/api/sessions/<session_id>', methods=['PUT'])
def rename_session(session_id):
    data = request.json
    chat_db.rename_session(session_id, data.get('name'))
    return jsonify({"success": True})

@app.route('/api/sessions/<session_id>/history', methods=['GET'])
def get_history(session_id):
    return jsonify(chat_db.get_chat_history(session_id))

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get('query', '').strip()
    session_id = data.get('session_id')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    if not session_id:
        return jsonify({"error": "No session provided"}), 400

    try:
        # Get History
        history = chat_db.get_chat_history(session_id)
        
        # Save user message
        chat_db.add_message(session_id, 'user', query)

        # Step 1: Filtering (Pass history)
        meta = db_ops.load_metadata()
        filter_criteria = agent_logic.run_filtering_agent(query, meta, chat_history=history)
        
        candidates = db_ops.search_videos_by_criteria(filter_criteria)
        if not candidates:
            msg = "I couldn't find any relevant videos in my database to help with that. Maybe try rephrasing or asking something else?"
            chat_db.add_message(session_id, 'ai', msg)
            return jsonify({
                "answer_text": msg,
                "recommendations_with_notes": [],
                "other_recommendations": []
            })

        # Step 2: Refining
        ranked_ids = agent_logic.run_refinement_agent(query, candidates)
        
        # Prune based on 50k limit
        final_video_details = []
        current_char_count = 0
        details_map = db_ops.get_full_video_details(ranked_ids)
        
        for vid_id in ranked_ids:
            if vid_id not in details_map:
                continue
            vid = details_map[vid_id]
            text = vid.get('refined_text', '') or ""
            text_len = len(text)
            
            if current_char_count + text_len <= CHARACTER_LIMIT:
                final_video_details.append(vid)
                current_char_count += text_len
            else:
                break

        if not final_video_details:
             msg = "Found relevant videos, but their content is too large to process. Please try a more specific question."
             chat_db.add_message(session_id, 'ai', msg)
             return jsonify({"error": msg}), 413

        # Step 3: Response (Pass history)
        response = agent_logic.run_response_agent(query, final_video_details, chat_history=history)
        
        if not response:
            return jsonify({"error": "Error generating response from AI."}), 500

        # Enhance response
        lookup = {v['id']: v for v in final_video_details}
        def enhance_recs(recs):
            enhanced = []
            for r in recs:
                vid_id = r.get('id')
                if vid_id in lookup:
                    v = lookup[vid_id]
                    r['title'] = v.get('title', 'Unknown')
                    r['file_path'] = v.get('file_path')
                    r['platform'] = v.get('platform')
                    enhanced.append(r)
            return enhanced

        response['recommendations_with_notes'] = enhance_recs(response.get('recommendations_with_notes', []))
        response['other_recommendations'] = enhance_recs(response.get('other_recommendations', []))

        # Save AI Response
        chat_db.add_message(session_id, 'ai', response['answer_text'], msg_type='result', metadata=response)

        return jsonify(response)

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/open-video', methods=['POST'])
def open_video():
    data = request.json
    path = data.get('path')
    if not path:
        return jsonify({"error": "No path provided"}), 400
    
    success = open_file(path)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to open video"}), 500

# --- Gallery API ---
@app.route('/api/gallery/filters', methods=['GET'])
def get_gallery_filters():
    return jsonify(db_ops.get_unique_filter_options())

@app.route('/api/gallery/videos', methods=['POST'])
def get_gallery_videos():
    data = request.json or {}
    filters = data.get('filters', {})
    # Support both structure: { ...filters, page: 1 } or { filters: {...}, page: 1 }
    # To maintain backward compatibility if JS sends filters directly in root:
    # If 'filters' key exists, use it. Otherwise assume root is filters, but extract page/limit.
    
    if 'filters' in data:
        filters = data['filters']
    else:
        # Shallow copy to avoid modifying original if needed, remove page/limit from filters
        filters = data.copy()
        filters.pop('page', None)
        filters.pop('limit', None)

    page = int(data.get('page', 1))
    limit = int(data.get('limit', 50))
    offset = (page - 1) * limit
    
    videos = db_ops.get_gallery_videos(filters, limit=limit, offset=offset)
    return jsonify(videos)

if __name__ == '__main__':
    app.run(debug=True, port=5001) # Use 5001 to avoid common occupancy
