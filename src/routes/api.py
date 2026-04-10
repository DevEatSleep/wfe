"""API routes for data endpoints"""
from flask import Blueprint, jsonify, session, request
from src.db import (reset_db, get_revenus, get_personnes, 
                    get_depenses_with_payeur, get_travail_domestique,
                    save_session_to_db, delete_personne, delete_depense, update_depense, get_depenses)
from src.session_manager import (
    session_update_personne, session_update_revenu, session_delete_personne,
    session_delete_revenu, session_delete_depense, session_update_depense,
    session_get_personnes, session_get_revenus, session_get_depenses_with_payeur
)

api_bp = Blueprint('api', __name__)

# Session getters WITH DATABASE FALLBACK
def session_get_personnes():
    """Get person data from session, fallback to database if empty"""
    if 'personnes' in session and session['personnes']:
        return session['personnes']
    # Fallback to database
    try:
        return get_personnes()
    except Exception:
        return {}

def session_get_revenus():
    """Get revenue data from session, fallback to database if empty"""
    if 'revenus' in session and session['revenus']:
        return session['revenus']
    # Fallback to database
    try:
        return get_revenus()
    except Exception:
        return {}

def session_get_depenses_with_payeur():
    """Get depenses with payeur info from session, fallback to database if empty"""
    if 'depenses' in session and session['depenses']:
        # Convert session format to depenses_with_payeur format
        return [(d['description'], d['montant'], d['payeur']) for d in session['depenses']]
    # Fallback to database
    try:
        return get_depenses_with_payeur()
    except Exception:
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
    except Exception:
        return {}

def get_bilan_cached():
    """Get bilan without caching to ensure real-time updates from session"""
    try:
        # Always fetch fresh session data - no caching for instant updates
        # Query session ONLY, no database fallback during active chat
        revenus = session_get_revenus()
        depenses_details = session_get_depenses_with_payeur()
        personnes = session_get_personnes()
        travail_user = session_get_travail_domestique()
        
        # Ensure depenses_details is a list
        if not isinstance(depenses_details, list):
            depenses_details = []
        
        total_depenses = sum([float(mont) for _, mont, _ in depenses_details]) if depenses_details else 0
        
        # Calculate contribution (how much each person paid)
        contribution = {}
        depenses = {}
        for description, montant, payeur in depenses_details:
            try:
                montant = float(montant)
                # Add to depenses by payeur
                if payeur not in depenses:
                    depenses[payeur] = 0
                depenses[payeur] += montant
                
                # Add to contribution
                if payeur not in contribution:
                    contribution[payeur] = 0
                contribution[payeur] += montant
            except (ValueError, TypeError) as e:
                print(f"Error processing expense: {e}")
                continue
        
        # Calculate equity score
        equite = calculate_equite(revenus, contribution, travail_user, personnes)
        
        return {
            "revenus": revenus,
            "depenses": depenses,
            "depenses_details": depenses_details,
            "total_depenses": float(total_depenses),
            "personnes": personnes,
            "travail_domestique": travail_user,
            "contribution": contribution,
            "equite": equite,
            "status": "ok"
        }
    except Exception as e:
        print(f"Error in get_bilan_cached: {e}")
        import traceback
        traceback.print_exc()
        return {
            "revenus": {},
            "depenses": {},
            "depenses_details": [],
            "total_depenses": 0,
            "personnes": {},
            "travail_domestique": {},
            "contribution": {},
            "equite": {"non_calculé": True, "interpretation": f"Erreur serveur: {str(e)}"},
            "status": "error"
        }

def calculate_equite(revenus, contribution, travail_domestique, personnes):
    """Calculate equity score: compares financial charge (income+expenses) vs domestic work."""
    try:
        total_revenu = sum(float(v) for v in revenus.values()) if revenus else 0
        total_heures = sum(
            sum(float(data.get(r, 0)) for r in ['homme', 'femme'])
            for data in travail_domestique.values()
            if isinstance(data, dict)
        ) if travail_domestique else 0

        if total_revenu == 0 or total_heures == 0:
            return {"non_calculé": True, "interpretation": "Données insuffisantes pour calculer le score."}

        rh = float(revenus.get('homme', 0))
        rf = float(revenus.get('femme', 0))

        # Revenue ratios
        ratio_revenu_h = rh / total_revenu if total_revenu > 0 else 0.5
        ratio_revenu_f = rf / total_revenu if total_revenu > 0 else 0.5

        # Domestic work hours (hours/week)
        heures_h = sum(float(data.get('homme', 0)) for data in travail_domestique.values() if isinstance(data, dict))
        heures_f = sum(float(data.get('femme', 0)) for data in travail_domestique.values() if isinstance(data, dict))
        total_h = heures_h + heures_f
        ratio_travail_h = heures_h / total_h if total_h > 0 else 0.5
        ratio_travail_f = heures_f / total_h if total_h > 0 else 0.5

        # Expense ratios
        depense_h = float(contribution.get('homme', 0))
        depense_f = float(contribution.get('femme', 0))
        total_dep = depense_h + depense_f
        ratio_depense_h = depense_h / total_dep if total_dep > 0 else 0.5
        ratio_depense_f = depense_f / total_dep if total_dep > 0 else 0.5

        # Financial charge = average of income ratio and expense ratio
        charge_h = (ratio_revenu_h + ratio_depense_h) / 2
        charge_f = (ratio_revenu_f + ratio_depense_f) / 2

        # Equity score: how closely financial charge matches domestic work share
        diff_h = abs(charge_h - ratio_travail_h)
        diff_f = abs(charge_f - ratio_travail_f)
        iniquite = (diff_h + diff_f) / 2
        score_equite = max(0.0, 100.0 - (iniquite * 100))

        # Advantage scores: positive = advantaged (high charge, low domestic work)
        # negative = disadvantaged (low charge, high domestic work)
        scores_avantage = {
            'homme': round(float(charge_h - ratio_travail_h), 4),
            'femme': round(float(charge_f - ratio_travail_f), 4)
        }

        role_desav = min(scores_avantage, key=lambda r: scores_avantage[r])
        score_desav = scores_avantage[role_desav]
        prenom_desav = personnes.get(role_desav, {}).get('prenom', role_desav) if isinstance(personnes.get(role_desav), dict) else role_desav

        if score_desav < -0.15:
            severity = "très fortement désavantagé(e)"
        elif score_desav < -0.05:
            severity = "fortement désavantagé(e)"
        elif score_desav < 0:
            severity = "légèrement désavantagé(e)"
        else:
            severity = "en position équilibrée"

        if score_equite >= 85:
            interpretation = "✅ L'équité est bonne ! Les contributions sont bien équilibrées."
        elif score_equite >= 70:
            interpretation = f"⚠️ L'équité est modérée. {prenom_desav} est {severity}."
        else:
            interpretation = f"❌ L'équité est faible. {prenom_desav} est {severity}."

        return {
            "non_calculé": False,
            "score_equite": round(score_equite, 2),
            "interpretation": interpretation,
            "ratio_revenu": {"homme": round(ratio_revenu_h, 4), "femme": round(ratio_revenu_f, 4)},
            "ratio_depense": {"homme": round(ratio_depense_h, 4), "femme": round(ratio_depense_f, 4)},
            "ratio_travail": {"homme": round(ratio_travail_h, 4), "femme": round(ratio_travail_f, 4)},
            "heures": {"homme": round(heures_h, 2), "femme": round(heures_f, 2)},
            "avantage_scores": scores_avantage,
            "le_plus_desavantage": {
                "role": role_desav,
                "prenom": prenom_desav,
                "score": round(score_desav, 4)
            }
        }
    except Exception as e:
        print(f"Error in calculate_equite: {e}")
        import traceback
        traceback.print_exc()
        return {"non_calculé": True, "interpretation": f"Erreur de calcul: {str(e)}"}

# -------- CRUD API ENDPOINTS --------

# GET ENDPOINTS
@api_bp.route("/api/data/personnes", methods=["GET"])
def get_personnes_api():
    """Get all personnes from session or database"""
    return jsonify(session_get_personnes())

@api_bp.route("/api/data/revenus", methods=["GET"])
def get_revenus_api():
    """Get all revenus from session or database"""
    return jsonify(session_get_revenus())

@api_bp.route("/api/data/depenses", methods=["GET"])
def get_depenses_api():
    """Get all depenses from session or database"""
    depenses_list = session_get_depenses_with_payeur()
    return jsonify({
        "depenses": [
            {"id": i, "description": d[0], "montant": d[1], "payeur": d[2]}
            for i, d in enumerate(depenses_list)
        ]
    })

# PUT ENDPOINTS (UPDATE)
@api_bp.route("/api/data/personnes/<role>", methods=["PUT"])
def update_personne_api(role):
    """Update a personne"""
    try:
        data = request.json
        success = session_update_personne(role, prenom=data.get('prenom'), age=data.get('age'))
        if success:
            return jsonify({"status": "success", "message": "Personne mise à jour"})
        else:
            return jsonify({"status": "error", "message": "Erreur lors de la mise à jour"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@api_bp.route("/api/data/revenus/<role>", methods=["PUT"])
def update_revenu_api(role):
    """Update a revenu"""
    try:
        data = request.json
        montant = data.get('montant')
        success = session_update_revenu(role, montant)
        if success:
            return jsonify({"status": "success", "message": "Revenu mis à jour"})
        else:
            return jsonify({"status": "error", "message": "Erreur lors de la mise à jour"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@api_bp.route("/api/data/depenses/<int:depense_id>", methods=["PUT"])
def update_depense_api(depense_id):
    """Update a depense"""
    try:
        data = request.json
        success = session_update_depense(depense_id, description=data.get('description'), 
                                         montant=data.get('montant'), payeur=data.get('payeur'))
        if success:
            return jsonify({"status": "success", "message": "Dépense mise à jour"})
        else:
            return jsonify({"status": "error", "message": "Erreur lors de la mise à jour"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# DELETE ENDPOINTS
@api_bp.route("/api/data/personnes/<role>", methods=["DELETE"])
def delete_personne_api(role):
    """Delete a personne"""
    try:
        success = session_delete_personne(role)
        if success:
            return jsonify({"status": "success", "message": "Personne supprimée"})
        else:
            return jsonify({"status": "error", "message": "Personne non trouvée"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@api_bp.route("/api/data/depenses/<int:depense_id>", methods=["DELETE"])
def delete_depense_api(depense_id):
    """Delete a depense"""
    try:
        success = session_delete_depense(depense_id)
        if success:
            return jsonify({"status": "success", "message": "Dépense supprimée"})
        else:
            return jsonify({"status": "error", "message": "Dépense non trouvée"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

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
