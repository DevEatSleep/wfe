"""API routes for data endpoints"""
from flask import Blueprint, jsonify, session
from src.db import (reset_db, get_revenus, get_personnes, 
                    get_depenses_with_payeur, get_travail_domestique,
                    save_session_to_db)

api_bp = Blueprint('api', __name__)

# Session getters WITH DATABASE FALLBACK
def session_get_personnes():
    """Get person data from session, fallback to database if empty"""
    if 'personnes' in session and session['personnes']:
        return session['personnes']
    # Fallback to database
    try:
        return get_personnes()
    except:
        return {}

def session_get_revenus():
    """Get revenue data from session, fallback to database if empty"""
    if 'revenus' in session and session['revenus']:
        return session['revenus']
    # Fallback to database
    try:
        return get_revenus()
    except:
        return {}

def session_get_depenses_with_payeur():
    """Get depenses with payeur info from session, fallback to database if empty"""
    if 'depenses' in session and session['depenses']:
        # Convert session format to depenses_with_payeur format
        return [(d['description'], d['montant'], d['payeur']) for d in session['depenses']]
    # Fallback to database
    try:
        return get_depenses_with_payeur()
    except:
        return []

def session_get_travail_domestique():
    """Get domestic work data from session or database with calculated costs"""
    if 'travail_domestique_full' in session and session['travail_domestique_full']:
        # Convert list format back to dict format with cost calculations
        result = {}
        # Tarif horaire standard pour travail domestique en France: 13€/heure
        TARIF_HORAIRE = 13.0
        SEMAINES_PAR_MOIS = 4.33
        
        for record in session['travail_domestique_full']:
            activite = record['activite']
            sexe = record['sexe']
            heures_semaine = record['heures_semaine']
            
            if activite not in result:
                result[activite] = {}
            
            # Stocker les heures et calculer le coût
            result[activite][sexe] = heures_semaine
            # Ajouter le coût calculé
            cout_key = f'cout_{sexe}'
            heures_par_mois = heures_semaine * SEMAINES_PAR_MOIS
            result[activite][cout_key] = heures_par_mois * TARIF_HORAIRE
        
        return result
    # Fallback to database
    try:
        return get_travail_domestique()
    except:
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
    """Save all session data to remote database in one batch (and keep in session)"""
    try:
        success = save_session_to_db(session)
        if success:
            # Keep session data for current user, just save to DB
            return jsonify({"status": "success", "message": "Données sauvegardées avec succès!"})
        else:
            return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Erreur: {str(e)}"}), 500

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
