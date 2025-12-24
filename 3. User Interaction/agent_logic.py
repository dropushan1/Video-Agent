import json
import os
from google import genai
import config

# Initialize Client
client = genai.Client(api_key=config.GOOGLE_API_KEY)

def _load_prompt(filename):
    path = os.path.join(config.PROMPTS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file {filename} not found at {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def _clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def run_filtering_agent(user_query, metadata, chat_history=None):
    """
    Agent 1: Decides filter criteria.
    chat_history: List of dicts [{"role":..., "content":...}]
    """
    prompt_template = _load_prompt("1_filter.txt")
    
    options_str = (
        f"Categories: {', '.join(metadata.get('Category', []))}\n"
        f"Tags: {', '.join(metadata.get('Tags', []))}\n"
        f"Types: {', '.join(metadata.get('Types', []))}"
    )
    
    history_context = ""
    if chat_history:
        # Format last 5 turns
        relevant_history = chat_history[-5:]
        history_context = "\nRECENT CONVERSATION HISTORY:\n"
        for h in relevant_history:
            role = "User" if h['role'] == 'user' else "AI"
            history_context += f"{role}: {h['content']}\n"
    
    prompt = f"{prompt_template}\n{history_context}\nUSER QUERY:\n{user_query}\n\nAVAILABLE OPTIONS:\n{options_str}"

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=prompt
        )
        cleaned = _clean_json_response(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"Error in Filtering Agent: {e}")
        return {}

def run_refinement_agent(user_query, video_candidates):
    # Agent 2 remains focused on the specific candidates search based on current query
    if not video_candidates:
        return []

    prompt_template = _load_prompt("2_refine.txt")
    
    candidates_str = ""
    for v in video_candidates:
        candidates_str += f"ID: {v['id']}\nTitle: {v['title']}\nSummary: {v['summary']}\n---\n"
    
    prompt = f"{prompt_template}\n\nUSER QUERY:\n{user_query}\n\nCANDIDATE VIDEOS:\n{candidates_str}"

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=prompt
        )
        cleaned = _clean_json_response(response.text)
        data = json.loads(cleaned)
        return data.get("selected_ids", [])
    except Exception as e:
        print(f"Error in Refinement Agent: {e}")
        return []

def run_response_agent(user_query, video_details_list, chat_history=None):
    """
    Agent 3: Generates final advice.
    """
    prompt_template = _load_prompt("3_response.txt")
    
    history_context = ""
    if chat_history:
        relevant_history = chat_history[-5:]
        history_context = "\nCONVERSATION HISTORY:\n"
        for h in relevant_history:
            role = "User" if h['role'] == 'user' else "Assistant"
            history_context += f"{role}: {h['content']}\n"

    content_str = ""
    for v in video_details_list:
        content_str += f"Video ID: {v['id']}\nTitle: {v['title']}\nPlatform: {v['platform']}\nContent:\n{v['refined_text']}\n###\n"
    
    prompt = f"{prompt_template}\n{history_context}\nUSER QUERY:\n{user_query}\n\nVIDEO CONTENTS:\n{content_str}"

    try:
        response = client.models.generate_content(
            model=config.MODEL_NAME,
            contents=prompt
        )
        cleaned = _clean_json_response(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"Error in Response Agent: {e}")
        return None
