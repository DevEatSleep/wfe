"""API routes for data endpoints"""
from flask import Blueprint, jsonify, session
from src.db import (
    save_session_to_db, get_revenus, get_depenses_with_payeur,
    get_travail_domestique, get_personnes, reset_db
)
from functools import lru_cache
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)

# Cache the bilan response for 2 seconds to reduce DB load
_bilan_cache = None
_bilan_cache_time = None
BILAN_CACHE_DURATION = 2  # seconds

# Session-aware getters (same as in app.py)
def session_get_personnes():
    """Get person data from session, fallback to database if not in session"""
    if 'personnes' in session:
        return session['personnes']
    return get_personnes() or {}

def session_get_revenus():
    """Get revenue data from session, fallback to database"""
    if 'revenus' in session:
        return session['revenus']
    return get_revenus() or {}

def session_get_depenses_with_payeur():
    """Get depenses with payeur info from session or database"""
    if 'depenses' in session:
        # Convert session format to depenses_with_payeur format
        return [(d['description'], d['montant'], d['payeur']) for d in session['depenses']]
    return get_depenses_with_payeur() or []

def session_get_travail_domestique():
    """Get domestic work data from session or database"""
    if 'travail_domestique_full' in session:
        # Convert list format back to dict format
        result = {}
        for record in session['travail_domestique_full']:
            activite = record['activite']
            sexe = record['sexe']
            if activite not in result:
                result[activite] = {}
            result[activite][sexe] = record['heures_semaine']
        return result
    return get_travail_domestique() or {}

def get_bilan_cached():
    """Get bilan with 2-second caching to reduce database queries"""
    global _bilan_cache, _bilan_cache_time
    
    now = datetime.now()
    # Return cached result if still valid
    if _bilan_cache and _bilan_cache_time and (now - _bilan_cache_time).total_seconds() < BILAN_CACHE_DURATION:
        return _bilan_cache
    
    # Query session first, then fallback to database
    revenus = session_get_revenus()
    depenses_details = session_get_depenses_with_payeur()
    personnes = session_get_personnes()
    travail_user = session_get_travail_domestique()
    
    total_depenses = sum([mont for _, mont, _ in depenses_details]) if depenses_details else 0
    
    _bilan_cache = {
        "revenus": revenus,
        "depenses_details": depenses_details,
        "total_depenses": total_depenses,
        "personnes": personnes,
        "travail_domestique": travail_user,
        "status": "ok"
    }
    _bilan_cache_time = now
    
    return _bilan_cache

@api_bp.route("/api/save-to-db", methods=["POST"])
def save_to_db():
    """Save all session data to remote database in one batch"""
    global _bilan_cache, _bilan_cache_time
    
    success = save_session_to_db(session)
    # Clear cache after save
    _bilan_cache = None
    _bilan_cache_time = None
    
    if success:
        session.clear()
        return jsonify({"status": "success", "message": "Données sauvegardées avec succès!"})
    else:
        return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde"}), 500

@api_bp.route("/api/bilan", methods=["GET"])
def api_bilan():
    """Get summary/bilan of entered data (cached for 2 seconds)"""
    return jsonify(get_bilan_cached())

@api_bp.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all data"""
    global _bilan_cache, _bilan_cache_time
    
    reset_db()
    # Clear cache after reset
    _bilan_cache = None
    _bilan_cache_time = None
    
    return jsonify({"status": "success", "message": "Données réinitialisées"})
