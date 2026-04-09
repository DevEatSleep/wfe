from flask import Flask, render_template, request, redirect, url_for, jsonify
import re, unicodedata, json
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -------- APP VERSION & METADATA --------
APP_VERSION = "0.1"
APP_AUTHOR = "Thierry Verdier"

from db import (
    init_db, get_revenus, set_revenu, add_depense, get_depenses,
    get_depenses_with_payeur, get_step, set_step, reset_db, set_personne, get_personnes, get_age,
    get_categories_domestiques, get_travail_domestique,
    get_estimation_insee, insert_travail_domestique_user,
    get_tranche_age_for_age
)
from intents import INTENTS
from state_result import StateResult

app = Flask(__name__)
init_db()

# -------- DATA --------
with open("data/messages.json", "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

# -------- UTILITAIRES --------
def reply_json(text):
    return jsonify({"reply": text})

def normaliser(message):
    return ''.join(
        c for c in unicodedata.normalize('NFD', message)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def detect_intent(message, intents):
    msg = message.lower()
    for intent, data in intents.items():
        if any(v in msg for v in data.get("verbs", [])):
            return intent
        if any(k in msg for k in data.get("keywords", [])):
            return intent
    return None

def extraire_depense(message):
    msg = message.lower()
    match = re.search(r'(\d+(?:[.,]\d+)?)', msg)
    montant = float(match.group(1).replace(',', '.')) if match else 0

    description = re.sub(
        r'\d+(?:[.,]\d+)?\s*(€|euros?)?', '',
        msg, flags=re.IGNORECASE
    ).strip()

    description = re.sub(r"\s+", " ", description)
    return montant, description or "autre"

def calculer_part():
    revenus = get_revenus() or {}
    depenses = get_depenses() or {}

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
    revenus = get_revenus() or {}
    travail_user = get_travail_domestique() or {}
    depenses_with_payeur = get_depenses_with_payeur() or []
    
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
    personnes = get_personnes() or {}
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
    set_personne("femme", prenom=msg.title())
    return StateResult(get_current_question("age_femme"), "age_femme")

def step_age_femme(msg):
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES["age_err"])
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    set_personne("femme", age=age)
    return StateResult(get_current_question("revenu_femme"), "revenu_femme")

def step_revenu_femme(msg):
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES["revenu_err"])
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide. Veuillez réessayer.")
    set_revenu("femme", montant)
    return StateResult(
        MESSAGES["revenu_femme_ok"].format(montant=montant)
        + "<br>" + get_current_question("prenom_homme"),
        "prenom_homme"
    )

def step_prenom_homme(msg):
    set_personne("homme", prenom=msg.title())
    return StateResult(get_current_question("age_homme"), "age_homme")

def step_age_homme(msg):
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES["age_err"])
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    set_personne("homme", age=age)
    return StateResult(get_current_question("revenu_homme"), "revenu_homme")

def step_revenu_homme(msg):
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES["revenu_err"])
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide. Veuillez réessayer.")
    set_revenu("homme", montant)
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
            
            add_depense(desc, montant, payeur_final)
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
    personnes = get_personnes() or {}
    personne = personnes.get(genre, {}) or {}
    prenom = personne.get("prenom", "la personne")
    age = personne.get("age")

    # --- Determine tranche for the current person ---
    tranche = get_tranche_age_for_age(genre, categorie, age)

    # --- Get INSEE estimation ---
    estimation = get_estimation_insee(genre, categorie, tranche)

    if estimation is None:
        return StateResult(f"❌ Estimation INSEE non trouvée pour {prenom} dans la tranche {tranche}. Veuillez entrer une valeur estimée.")

    # --- Insert user data ---
    try:
        insert_travail_domestique_user(
            prenom=prenom,
            age=age,
            tranche_age=tranche,
            sexe=genre,
            activite=categorie,
            heures_semaine=heures_semaine
        )
    except Exception as e:
        return StateResult(f"❌ Erreur lors de la sauvegarde : {str(e)}")

    # --- Confirmation message ---
    confirmation = f"✅ {prenom} : {heures_semaine} h pour {categorie}. Estimation INSEE ≈ {estimation} h/semaine."

    # --- Passer à l'étape suivante ---
    steps = build_steps()
    try:
        idx = steps.index(step)
    except ValueError:
        # All steps completed
        return StateResult(
            reply=f"{confirmation}<br><br>🎉 <strong>Félicitations !</strong> Toutes vos données ont été saisies avec succès.<br><br>📊 Vous pouvez maintenant :<br>• Consulter votre <strong>bilan détaillé</strong><br>• Taper <strong>'reset'</strong> pour recommencer avec de nouvelles données",
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
        return StateResult(
            reply=MESSAGES["reset"] + "<br><br>" + get_current_question("prenom_femme"),
            next_step="prenom_femme"
        )
    
    # For any other input, remind them data is ready
    return StateResult(
        reply="✅ Vos données sont sauvegardées et prêtes à être consultées. Vous pouvez :<br>• Accéder au <strong>bilan</strong><br>• Taper <strong>'reset'</strong> pour effacer et recommencer",
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
    message = request.json.get("message", "").strip()
    step = get_step()
    intent = detect_intent(message, INTENTS)

    # Handle reset intent first, with high priority
    if intent == "reset":
        reset_db()
        set_step("prenom_femme")
        return reply_json(MESSAGES["reset"] + "<br>" + get_current_question("prenom_femme"))

    # Handle completed state
    if step == "completed":
        result = step_completed(message)
        set_step(result.next_step)
        return reply_json(result.reply)

    # Initialize if no step is set
    if step is None:
        set_step("prenom_femme")
        return reply_json(MESSAGES["welcome_base"] + "<br>" + get_current_question("prenom_femme"))

    # Handle housework hours steps
    if step.startswith("heures_"):
        result = step_donnees_insee(message, step)
    else:
        # Handle other steps
        result = STATE_HANDLERS[step](message)

    set_step(result.next_step)
    return reply_json(result.reply)

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



# -------- MAIN --------
if __name__ == "__main__":
    app.run(debug=True)
