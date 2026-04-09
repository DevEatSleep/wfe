"""Utility helper functions for WFE application"""
import re
import unicodedata

def reply_json(text):
    """Create JSON reply for chatbot"""
    from flask import jsonify
    return jsonify({"reply": text})

def normaliser(message):
    """Normalize French text for comparison"""
    return ''.join(
        c for c in unicodedata.normalize('NFD', message)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def detect_intent(message, intents):
    """Detect intent from user message using keywords and verbs"""
    msg = message.lower()
    for intent, data in intents.items():
        if any(v in msg for v in data.get("verbs", [])):
            return intent
        if any(k in msg for k in data.get("keywords", [])):
            return intent
    return None

def extraire_depense(message):
    """Extract expense amount and description from user message"""
    msg = message.lower()
    match = re.search(r'(\d+(?:[.,]\d+)?)', msg)
    montant = float(match.group(1).replace(',', '.')) if match else 0

    description = re.sub(
        r'\d+(?:[.,]\d+)?\s*(€|euros?)?', '',
        msg, flags=re.IGNORECASE
    ).strip()

    description = re.sub(r"\s+", " ", description)
    return montant, description or "autre"
