from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import re, unicodedata, json
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -------- APP VERSION & METADATA --------
APP_VERSION = "0.1"
APP_AUTHOR = "Thierry Verdier"

from src.db import (
    init_db, get_revenus, set_revenu, add_depense, get_depenses,
    get_depenses_with_payeur, get_step, set_step, reset_db, set_personne, get_personnes, get_age,
    get_categories_domestiques, get_travail_domestique,
    get_estimation_insee, insert_travail_domestique_user,
    get_tranche_age_for_age, save_session_to_db, get_session_data, set_session_data
)
from src.intents import INTENTS
from src.state_result import StateResult
from src.utils.helpers import detect_intent, normaliser, extraire_depense, reply_json
from src.routes import chat_bp, api_bp, pages_bp

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Register blueprints
app.register_blueprint(pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(chat_bp)

# Initialize database with error handling
try:
    init_db()
except Exception as e:
    print(f"WARNING: Database initialization failed: {e}")
    print(f"DATABASE_URL is set: {bool(os.getenv('DATABASE_URL'))}")
    print("The app will still start but /chat endpoint may fail until DATABASE_URL is configured.")

# -------- DATA --------
with open("data/messages.json", "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

# -------- SESSION-BASED DATA BUFFERING --------
# Helper functions to store data in Flask session instead of directly to DB
def session_set_personne(role, prenom=None, age=None):
    """Store person data in session instead of database"""
    if 'personnes' not in session:
        session['personnes'] = {}
    if role not in session['personnes']:
        session['personnes'][role] = {}
    if prenom is not None:
        session['personnes'][role]['prenom'] = prenom
    if age is not None:
        session['personnes'][role]['age'] = age
    session.modified = True

def session_set_revenu(role, montant):
    """Store revenue in session instead of database"""
    if 'revenus' not in session:
        session['revenus'] = {}
    session['revenus'][role] = montant
    session.modified = True

def session_add_depense(description, montant, payeur):
    """Store expense in session instead of database"""
    if 'depenses' not in session:
        session['depenses'] = []
    session['depenses'].append({
        'description': description,
        'montant': montant,
        'payeur': payeur
    })
    session.modified = True

def session_add_travail_domestique(activite, role, heures):
    """Store domestic work in session instead of database"""
    if 'travail_domestique' not in session:
        session['travail_domestique'] = {}
    if activite not in session['travail_domestique']:
        session['travail_domestique'][activite] = {}
    session['travail_domestique'][activite][role] = heures
    session.modified = True

def save_session_data_to_db():
    """Save all buffered session data to database at once"""
    try:
        # Save personnes
        if 'personnes' in session:
            for role, data in session['personnes'].items():
                if 'prenom' in data:
                    set_personne(role, prenom=data['prenom'])
                if 'age' in data:
                    set_personne(role, age=data['age'])
        
        # Save revenus
        if 'revenus' in session:
            for role, montant in session['revenus'].items():
                set_revenu(role, montant)
        
        # Save depenses
        if 'depenses' in session:
            for depense in session['depenses']:
                add_depense(depense['description'], depense['montant'], depense['payeur'])
        
        # Save travail_domestique (full records from session)
        if 'travail_domestique_full' in session:
            for record in session['travail_domestique_full']:
                insert_travail_domestique_user(
                    prenom=record['prenom'],
                    age=record['age'],
                    tranche_age=record['tranche_age'],
                    sexe=record['sexe'],
                    activite=record['activite'],
                    heures_semaine=record['heures_semaine']
                )
        
        return True
    except Exception as e:
        print(f"ERROR saving session data to DB: {e}")
        return False

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

def session_get_depenses():
    """Get simple depenses dict from session only"""
    if 'depenses' in session:
        # Convert list format to dict format for backwards compatibility
        result = {}
        for i, depense in enumerate(session['depenses']):
            result[f"depense_{i}"] = depense['montant']
        return result
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

# -------- CALCULATOR FUNCTIONS --------
def calculer_part():
    revenus = session_get_revenus()
    depenses = session_get_depenses()

    rh = revenus.get("homme", 0)
    rf = revenus.get("femme", 0)
    total_revenu = rh + rf
    total_depenses = sum(depenses.values())

    if total_revenu == 0:
        return 0, 0, total_depenses

    return (
        total_depenses * rh / total_revenu,
        total_depenses * rf / total_revenu,
        total_depenses
    )

def calculer_equite():
    """Calcule l'indice d'équité entre les deux partenaires."""
    revenus = session_get_revenus()
    travail_user = session_get_travail_domestique()
    depenses_with_payeur = session_get_depenses_with_payeur()
    
    # Vérifier s'il y a suffisamment de données
    total_revenu = sum(revenus.values()) if revenus else 0
    total_heures = sum([sum([data.get(role, 0) for role in ["homme", "femme"]]) for data in travail_user.values()]) if travail_user else 0
    
    # Si aucune donnée saisie, retourner "non calculé"
    if total_revenu == 0 or total_heures == 0:
        return {
            "non_calculé": True,
            "score_equite": None,
            "ratio_revenu": None,
            "ratio_depense": None,
            "ratio_travail": None,
            "heures": None,
            "depense": None,
            "interpretation": "Veuillez remplir les revenus, les dépenses et le travail domestique pour calculer l'équité"
        }
    
    rh = revenus.get("homme", 0)
    rf = revenus.get("femme", 0)
    
    # Contribution attendue en fonction du revenu
    if total_revenu > 0:
        ratio_revenu_h = rh / total_revenu
        ratio_revenu_f = rf / total_revenu
    else:
        ratio_revenu_h = ratio_revenu_f = 0.5
    
    # Heures réelles de travail domestique
    heures_h = sum([data.get("homme", 0) for data in travail_user.values()]) if travail_user else 0
    heures_f = sum([data.get("femme", 0) for data in travail_user.values()]) if travail_user else 0
    
    # Convertir en heures/semaine (les valeurs sont en heures/jour)
    heures_h = heures_h * 7
    heures_f = heures_f * 7
    
    # Ratio travail domestique
    total_heures_ratiocalc = heures_h + heures_f
    if total_heures_ratiocalc > 0:
        ratio_travail_h = heures_h / total_heures_ratiocalc
        ratio_travail_f = heures_f / total_heures_ratiocalc
    else:
        ratio_travail_h = ratio_travail_f = 0.5
    
    # Calcul du ratio des dépenses payées
    depense_h = 0
    depense_f = 0
    depense_shared = 0
    
    for cat, montant, payeur in depenses_with_payeur:
        if payeur == "homme":
            depense_h += montant
        elif payeur == "femme":
            depense_f += montant
        else:  # partagé
            depense_shared += montant / 2
    
    depense_h += depense_shared
    depense_f += depense_shared
    total_depenses = depense_h + depense_f
    
    if total_depenses > 0:
        ratio_depense_h = depense_h / total_depenses
        ratio_depense_f = depense_f / total_depenses
    else:
        ratio_depense_h = ratio_depense_f = 0.5
    
    # Score d'équité (0-100): Compare revenu + dépenses vs travail domestique
    ratio_charge_h = (ratio_revenu_h + ratio_depense_h) / 2
    ratio_charge_f = (ratio_revenu_f + ratio_depense_f) / 2
    
    # Comparer charge financière vs travail domestique
    diff_h = abs(ratio_charge_h - ratio_travail_h)
    diff_f = abs(ratio_charge_f - ratio_travail_f)
    iniquite = (diff_h + diff_f) / 2
    score_equite = max(0, 100 - (iniquite * 100))
    
    return {
        "non_calculé": False,
        "score_equite": score_equite,
        "ratio_revenu": {"homme": ratio_revenu_h, "femme": ratio_revenu_f},
        "ratio_depense": {"homme": ratio_depense_h, "femme": ratio_depense_f},
        "ratio_travail": {"homme": ratio_travail_h, "femme": ratio_travail_f},
        "heures": {"homme": heures_h, "femme": heures_f},
        "depense": {"homme": depense_h, "femme": depense_f},
        "interpretation": get_interpretation_equite(score_equite, 
                                                     ratio_charge_h, ratio_charge_f,
                                                     ratio_travail_h, ratio_travail_f)
    }

def get_interpretation_equite(score, charge_h, charge_f, travail_h, travail_f):
    """Retourne une interprétation textuelle de l'équité."""
    if score >= 85:
        return "✅ Très équitable"
    elif score >= 70:
        return "⚠️ Relativement équitable"
    elif score >= 50:
        # Inéquité modérée - indiquer qui est désavantagé
        diff_h = charge_h - travail_h
        if diff_h < -0.05:  # L'homme fait plus de travail que sa charge
            return "⚠️ Inéquité modérée - L'homme supporte plus de travail domestique"
        elif diff_h > 0.05:  # L'homme a moins de travail que sa charge
            return "⚠️ Inéquité modérée - La femme supporte plus de travail domestique"
        else:
            return "⚠️ Inéquité modérée"
    else:
        # Forte inéquité - indiquer qui est désavantagé
        diff_h = charge_h - travail_h
        if diff_h < -0.05:  # L'homme fait beaucoup plus de travail que sa charge
            return "❌ Forte inéquité - L'homme supporte disproportionnément le travail domestique"
        elif diff_h > 0.05:  # L'homme a beaucoup moins de travail que sa charge
            return "❌ Forte inéquité - La femme supporte disproportionnément le travail domestique"
        else:
            return "❌ Forte inéquité"

# -------- QUESTIONS --------
def get_current_question(step):
    personnes = session_get_personnes()
    femme = personnes.get("femme", {})
    homme = personnes.get("homme", {})

    if step == "prenom_femme":
        return MESSAGES["prenom_femme_q"]

    if step == "age_femme":
        return MESSAGES["age_femme_q"].format(prenom=femme.get("prenom", "la femme"))

    if step == "revenu_femme":
        return MESSAGES["revenu_femme_q"].format(prenom=femme.get("prenom", "la femme"))

    if step == "prenom_homme":
        return MESSAGES["prenom_homme_q"]

    if step == "age_homme":
        return MESSAGES["age_homme_q"].format(prenom=homme.get("prenom", "l’homme"))

    if step == "revenu_homme":
        return MESSAGES["revenu_homme_q"].format(prenom=homme.get("prenom", "l’homme"))

    if step.startswith("heures_"):
        _, categorie, genre = step.split("_", 2)

        personne = femme if genre == "femme" else homme
        prenom = personne.get("prenom", "la personne")
        age = personne.get("age")       

        tranche = get_tranche_age_for_age(genre, categorie, age)

        estimation = (
            get_estimation_insee(genre, categorie, tranche)
            if tranche else None
        )        

        if estimation:
            return (
                f"Combien d’heures réelles par semaine {prenom} consacre à "
                f"{categorie} (INSEE ≈ {estimation} h/semaine) ?"
            )

        return f"Combien d’heures pour {categorie} ({prenom}) ?"

    if step == "depenses":
        return MESSAGES["depenses_q"]

    if step == "completed":
        return "✅ Données complètes ! Consultez le bilan ou tapez 'reset' pour recommencer."

    return ""

# -------- FSM --------
_steps_cache = None

def build_steps():
    """Build and cache the steps list."""
    global _steps_cache
    if _steps_cache is None:
        _steps_cache = []
        for cat in get_categories_domestiques():
            _steps_cache += [f"heures_{cat}_femme", f"heures_{cat}_homme"]
    return _steps_cache

def get_progress(step):
    """Get current progress (current, total) for the housework steps."""
    steps = build_steps()
    if step in steps:
        current = steps.index(step) + 1
        return current, len(steps)
    return None, None

def step_prenom_femme(msg):
    session_set_personne("femme", prenom=msg.title())
    return StateResult(get_current_question("age_femme"), "age_femme")

def step_age_femme(msg):
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES["age_err"])
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    session_set_personne("femme", age=age)
    return StateResult(get_current_question("revenu_femme"), "revenu_femme")

def step_revenu_femme(msg):
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES["revenu_err"])
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide. Veuillez réessayer.")
    session_set_revenu("femme", montant)
    return StateResult(
        MESSAGES["revenu_femme_ok"].format(montant=montant)
        + "<br>" + get_current_question("prenom_homme"),
        "prenom_homme"
    )

def step_prenom_homme(msg):
    session_set_personne("homme", prenom=msg.title())
    return StateResult(get_current_question("age_homme"), "age_homme")

def step_age_homme(msg):
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES["age_err"])
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    session_set_personne("homme", age=age)
    return StateResult(get_current_question("revenu_homme"), "revenu_homme")

def step_revenu_homme(msg):
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES["revenu_err"])
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide. Veuillez réessayer.")
    session_set_revenu("homme", montant)
    return StateResult(
        MESSAGES["revenu_homme_ok_next"].format(montant=montant)
        + "<br>" + get_current_question("depenses"),
        "depenses"
    )

END_DEPENSES = {"fin", "termine", "terminé", "ok", "next"}
_depense_temp = {}  # Stockage temporaire de la dernière dépense

def step_depenses(msg):
    global _depense_temp
    
    # Si l'utilisateur a terminé
    if normaliser(msg) in END_DEPENSES:
        steps = build_steps()
        return StateResult(
            "⏱️ Passons aux heures réelles.<br>" + get_current_question(steps[0]),
            steps[0]
        )
    
    # Vérifier si on attend une réponse sur qui paye
    if _depense_temp.get("awaiting_payeur"):
        payeur = normaliser(msg)
        
        # Valider le payeur
        if payeur in {"homme", "femme", "partagé", "partage"}:
            payeur_final = "partagé" if payeur == "partage" else payeur
            montant = _depense_temp["montant"]
            desc = _depense_temp["desc"]
            
            session_add_depense(desc, montant, payeur_final)
            _depense_temp = {}
            
            return StateResult(
                MESSAGES["depense_ok"].format(montant=montant, categorie=desc)
                + f"<br>👤 {payeur_final.capitalize()} paie cette dépense."
                + "<br>" + MESSAGES["depenses_q"],
                "depenses"
            )
        else:
            return StateResult(
                "❌ Qui a payé? Répondez: <b>homme</b>, <b>femme</b>, ou <b>partagé</b>",
                "depenses"
            )
    
    # Sinon, extraire la dépense
    montant, desc = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES["depense_err"])
    
    # Stocker temporairement et demander qui paie
    _depense_temp = {"montant": montant, "desc": desc, "awaiting_payeur": True}
    
    return StateResult(
        f"📝 Dépense: <b>{desc}</b> ({montant}€)<br>"
        "Qui a payé? Répondez: <b>homme</b>, <b>femme</b>, ou <b>partagé</b>",
        "depenses"
    )

def step_donnees_insee(message, step):
    """
    Gère une saisie d'heures réelles pour une catégorie & une personne.
    """
    # --- Validate input ---
    try:
        heures_semaine = float(message.replace(",", "."))
    except Exception:
        return StateResult("❌ Merci d’indiquer un nombre d’heures valide.")

    # --- Parse current step ---
    try:
        _, categorie, genre = step.split("_", 2)
    except Exception:
        return StateResult("❌ Erreur interne : étape invalide.")

    # --- Get current person's info ---
    personnes = session_get_personnes()
    personne = personnes.get(genre, {}) or {}
    prenom = personne.get("prenom", "la personne")
    age = personne.get("age")

    # --- Determine tranche for the current person ---
    tranche = get_tranche_age_for_age(genre, categorie, age)

    # --- Get INSEE estimation ---
    estimation = get_estimation_insee(genre, categorie, tranche)

    if estimation is None:
        return StateResult(f"❌ Estimation INSEE non trouvée pour {prenom} dans la tranche {tranche}. Veuillez entrer une valeur estimée.")

    # --- Insert user data to session buffer ---
    try:
        if 'travail_domestique_full' not in session:
            session['travail_domestique_full'] = []
        session['travail_domestique_full'].append({
            'prenom': prenom,
            'age': age,
            'tranche_age': tranche,
            'sexe': genre,
            'activite': categorie,
            'heures_semaine': heures_semaine
        })
        session.modified = True
    except Exception as e:
        return StateResult(f"❌ Erreur lors de la sauvegarde : {str(e)}")

    # --- Confirmation message ---
    confirmation = f"✅ {prenom} : {heures_semaine} h pour {categorie}. Estimation INSEE ≈ {estimation} h/semaine."

    # --- Passer à l'étape suivante ---
    steps = build_steps()
    try:
        idx = steps.index(step)
    except ValueError:
        # All steps completed - save all session data to DB
        save_session_data_to_db()
        return StateResult(
            reply=f"{confirmation}<br><br>🎉 <strong>Félicitations !</strong> Toutes vos données ont été saisies avec succès et sauvegardées.<br><br>📊 Vous pouvez maintenant :<br>• Consulter votre <strong>bilan détaillé</strong><br>• Taper <strong>'reset'</strong> pour recommencer avec de nouvelles données",
            next_step="completed"
        )

    if idx + 1 < len(steps):
        next_step = steps[idx + 1]
        progress, total = get_progress(next_step)
        progress_text = f"<small>({progress}/{total})</small>" if progress else ""
        return StateResult(
            reply=f"{confirmation}<br><br>⏳ {progress_text} Passons à la prochaine activité :<br>{get_current_question(next_step)}",
            next_step=next_step
        )

    # All steps completed
    return StateResult(
        reply=f"{confirmation}<br><br>🎉 <strong>Félicitations !</strong> Toutes vos données ont été saisies avec succès.<br><br>📊 Vous pouvez maintenant :<br>• Consulter votre <strong>bilan détaillé</strong><br>• Taper <strong>'reset'</strong> pour recommencer avec de nouvelles données",
        next_step="completed"
    )

def step_completed(msg):
    """Handle user interaction after all data is completed."""
    normalized_msg = normaliser(msg)
    
    # Check for reset commands
    reset_keywords = {"reset", "réinitialiser", "recommencer", "nouveau", "effacer", "vider"}
    if normalized_msg in reset_keywords:
        reset_db()
        session.clear()  # Clear buffered session data
        return StateResult(
            reply=MESSAGES["reset"] + "<br><br>" + get_current_question("prenom_femme"),
            next_step="prenom_femme"
        )
    
    # For any other input, remind them data is ready and already saved
    return StateResult(
        reply="✅ Vos données ont été sauvegardées dans la base de données. Vous pouvez :<br>• Consulter le <strong>bilan</strong><br>• Taper <strong>'reset'</strong> pour effacer et recommencer",
        next_step="completed"
    )

STATE_HANDLERS = {
    "prenom_femme": step_prenom_femme,
    "age_femme": step_age_femme,
    "revenu_femme": step_revenu_femme,
    "prenom_homme": step_prenom_homme,
    "age_homme": step_age_homme,
    "revenu_homme": step_revenu_homme,
    "depenses": step_depenses,
    "completed": step_completed
}

# -------- ROUTES --------
@app.route("/")
def index():
    return redirect(url_for("dashboard_page"))

@app.route("/chat", methods=["POST"])
def chat():
    try:
        message = request.json.get("message", "").strip()
        
        # Use session cache if available to avoid repeated get_step() calls
        if 'current_step' in session:
            step = session['current_step']
        else:
            step = get_step()
            session['current_step'] = step
        
        intent = detect_intent(message, INTENTS)

        # Handle reset intent first, with high priority
        if intent == "reset":
            reset_db()
            # Clear all buffered session data but keep current_step
            session.clear()
            session['current_step'] = "prenom_femme"
            session.modified = True
            return reply_json(MESSAGES["reset"] + "<br>" + get_current_question("prenom_femme"))

        # Handle completed state
        if step == "completed":
            result = step_completed(message)
            session['current_step'] = result.next_step
            set_step(result.next_step)
            return reply_json(result.reply)

        # Initialize if no step is set
        if step is None:
            session['current_step'] = "prenom_femme"
            set_step("prenom_femme")
            return reply_json(MESSAGES["welcome_base"] + "<br>" + get_current_question("prenom_femme"))

        # Handle housework hours steps
        if step.startswith("heures_"):
            result = step_donnees_insee(message, step)
        else:
            # Handle other steps
            result = STATE_HANDLERS[step](message)

        # Update session cache with new step
        session['current_step'] = result.next_step
        set_step(result.next_step)
        return reply_json(result.reply)
    except Exception as e:
        print(f"ERROR in /chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return reply_json(f"Erreur serveur: {str(e)[:100]}")

@app.route("/chatbot")
def chatbot_page():
    return render_template("chat.html")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")

@app.route("/api/bilan")
def api_bilan():
    revenus = get_revenus() or {}
    depenses = get_depenses() or {}
    depenses_details = get_depenses_with_payeur()
    personnes = get_personnes() or {}

    # Total des dépenses mensuelles (recalculé depuis depenses_details)
    total_depenses = sum([mont for _, mont, _ in depenses_details]) if depenses_details else 0

    # Calcul des contributions de chaque personne aux dépenses
    contribution_homme, contribution_femme, _ = calculer_part()

    # Calcul de l'équité
    equite = calculer_equite()

    # Heure de travail domestique : calcul mensuel
    travail_user = get_travail_domestique() or {}
    
    # Calculer les heures mensuelles pour l'homme et la femme
    heures_mensuelles_homme = 0
    heures_mensuelles_femme = 0
    couts_mensuels_homme = 0
    couts_mensuels_femme = 0

    # Calculer les heures et coûts mensuels
    for activite, data in travail_user.items():
        heures_mensuelles_homme += data["homme"] * 30.44
        heures_mensuelles_femme += data["femme"] * 30.44

        couts_mensuels_homme += data["cout_homme"] * 30.44
        couts_mensuels_femme += data["cout_femme"] * 30.44

    # Formater la réponse finale
    reply = MESSAGES["bilan"].format(
        total=total_depenses,
        homme=contribution_homme,
        femme=contribution_femme,
        url=url_for("dashboard_page")
    )

    # Retourner les heures et coûts mensuels
    return jsonify({
        "revenus": revenus,
        "depenses": depenses,
        "depenses_details": get_depenses_with_payeur(),
        "total_depenses": total_depenses,
        "contribution": {"homme": contribution_homme, "femme": contribution_femme},
        "personnes": personnes,
        "travail_domestique": travail_user,  # Données entrées par l'utilisateur
        "heures_mensuelles": {
            "homme": heures_mensuelles_homme,
            "femme": heures_mensuelles_femme
        },
        "couts_mensuels": {
            "homme": couts_mensuels_homme,
            "femme": couts_mensuels_femme
        },
        "equite": equite,
        "reply": reply
    })

@app.route("/api/save-to-db", methods=["POST"])
def save_to_db():
    """Save all session data to remote database in one batch"""
    success = save_session_to_db(session)
    if success:
        session.clear()  # Clear session after successful save
        return jsonify({"status": "success", "message": "Données sauvegardées avec succès!"})
    else:
        return jsonify({"status": "error", "message": "Erreur lors de la sauvegarde"}), 500



# -------- MAIN --------
if __name__ == "__main__":
    app.run(debug=True)
