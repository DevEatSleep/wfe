"""API routes for data endpoints"""
from flask import Blueprint, jsonify, session
from src.db import reset_db

api_bp = Blueprint('api', __name__)

# Session-only getters (NO database fallback - dashboard reads ONLY from active chat session)
def session_get_personnes():
    """Get person data from session ONLY (no database fallback)"""
    if 'personnes' in session:
        return session['personnes']
    return {}

def session_get_revenus():
    """Get revenue data from session ONLY (no database fallback)"""
    if 'revenus' in session:
        return session['revenus']
    return {}

def session_get_depenses_with_payeur():
    """Get depenses with payeur info from session ONLY (no database fallback)"""
    if 'depenses' in session:
        # Convert session format to depenses_with_payeur format
        return [(d['description'], d['montant'], d['payeur']) for d in session['depenses']]
    return []

def session_get_travail_domestique():
    """Get domestic work data from session ONLY (no database fallback)"""
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
    return {}

def get_bilan_cached():
    """Get bilan without caching to ensure real-time updates from session"""
    # Always fetch fresh session data - no caching for instant updates
    # Query session ONLY, no database fallback during active chat
    revenus = session_get_revenus()
    depenses_details = session_get_depenses_with_payeur()
    personnes = session_get_personnes()
    travail_user = session_get_travail_domestique()
    
    total_depenses = sum([mont for _, mont, _ in depenses_details]) if depenses_details else 0
    
    return {
        "revenus": revenus,
        "depenses_details": depenses_details,
        "total_depenses": total_depenses,
        "personnes": personnes,
        "travail_domestique": travail_user,
        "status": "ok"
    }

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
