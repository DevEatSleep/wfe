"""Chat API routes"""
from flask import Blueprint, request, jsonify
from src.db import get_step, set_step, reset_db
from src.intents import INTENTS
from src.utils.helpers import detect_intent, normaliser, reply_json
import json

chat_bp = Blueprint('chat', __name__)

# Load messages (will be imported from app context)
MESSAGES = None

@chat_bp. route("/chat", methods=["POST"])
def chat():
    """Chat endpoint - processes user messages"""
    # Note: This is a placeholder - actual logic stays in app.py for now
    # Will be refactored in future versions
    message = request.json.get("message", "").strip()
    
    if not message:
        return jsonify({"error": "Empty message"}), 400
    
    return jsonify({"status": "ok"})
