"""API routes for data endpoints"""
from flask import Blueprint, jsonify, session
from src.db import (
    save_session_to_db, get_revenus, get_depenses_with_payeur,
    get_travail_domestique, get_personnes, reset_db
)

api_bp = Blueprint('api', __name__)

@api_bp.route("/api/save-to-db", methods=["POST"])
def save_to_db():
    """Save all session data to remote database in one batch"""
    success = save_session_to_db(session)
    if success:
        session.clear()
        return jsonify({"status": "success", "message": "Données sauvegardées avec succès!"})
    else:
        return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde"}), 500

@api_bp.route("/api/bilan", methods=["GET"])
def api_bilan():
    """Get summary/bilan of entered data"""
    revenus = get_revenus() or {}
    depenses_details = get_depenses_with_payeur()
    personnes = get_personnes() or {}
    travail_user = get_travail_domestique() or {}
    
    total_depenses = sum([mont for _, mont, _ in depenses_details]) if depenses_details else 0
    
    return jsonify({
        "revenus": revenus,
        "depenses_details": depenses_details,
        "total_depenses": total_depenses,
        "personnes": personnes,
        "travail_domestique": travail_user,
        "status": "ok"
    })

@api_bp.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all data"""
    reset_db()
    return jsonify({"status": "success", "message": "Données réinitialisées"})
