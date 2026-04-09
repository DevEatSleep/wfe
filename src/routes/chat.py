"""Chat API routes"""
from flask import Blueprint, request, jsonify
from src.db import get_step, set_step, reset_db
from src.intents import INTENTS
from src.utils.helpers import detect_intent, normaliser, reply_json
import json

chat_bp = Blueprint('chat', __name__)

# Load messages (will be imported from app context)
MESSAGES = None

# NOTE: The main /chat route is handled in app.py for now
# This blueprint is reserved for future refactoring of chat logic

