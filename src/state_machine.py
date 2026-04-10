"""State machine handlers for chatbot conversation flow."""
import re
import json
from flask import session
from src.state_result import StateResult
from src.session_manager import (
    session_set_personne, session_set_revenu, session_add_depense,
    session_get_personnes
)
from src.utils.helpers import normaliser, extraire_depense
from src.db import get_categories_domestiques

class StateMachineError(Exception):
    """Raised when state machine encounters an error."""
    pass

# Load messages globally
with open("data/messages.json", "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

# Cache for steps
_steps_cache = None

def build_steps():
    """Build and cache the steps list."""
    global _steps_cache
    if _steps_cache is None:
        _steps_cache = []
        try:
            for cat in get_categories_domestiques():
                _steps_cache += [f"heures_{cat}_femme", f"heures_{cat}_homme"]
        except Exception as e:
            print(f"Error building steps: {e}")
            _steps_cache = []
    return _steps_cache

def get_progress(step):
    """Get current progress for the housework steps."""
    steps = build_steps()
    if step in steps:
        current = steps.index(step) + 1
        return current, len(steps)
    return None, None

def get_current_question(step):
    """Get the question for the current step."""
    from src.db import get_tranche_age_for_age, get_estimation_insee
    
    personnes = session_get_personnes()
    femme = personnes.get("femme", {})
    homme = personnes.get("homme", {})

    if step == "prenom_femme":
        return MESSAGES.get("prenom_femme_q", "Quel est le prénom de la femme?")
    
    if step == "age_femme":
        prenom = femme.get("prenom", "la femme")
        return MESSAGES.get("age_femme_q", "Quel âge a {prenom}?").format(prenom=prenom)
    
    if step == "revenu_femme":
        prenom = femme.get("prenom", "la femme")
        return MESSAGES.get("revenu_femme_q", "Revenu mensuel de {prenom}?").format(prenom=prenom)
    
    if step == "prenom_homme":
        return MESSAGES.get("prenom_homme_q", "Quel est le prénom de l'homme?")
    
    if step == "age_homme":
        prenom = homme.get("prenom", "l'homme")
        return MESSAGES.get("age_homme_q", "Quel âge a {prenom}?").format(prenom=prenom)
    
    if step == "revenu_homme":
        prenom = homme.get("prenom", "l'homme")
        return MESSAGES.get("revenu_homme_q", "Revenu mensuel de {prenom}?").format(prenom=prenom)
    
    if step.startswith("heures_"):
        _, categorie, genre = step.split("_", 2)
        personne = femme if genre == "femme" else homme
        prenom = personne.get("prenom", "la personne")
        age = personne.get("age")
        tranche = get_tranche_age_for_age(genre, categorie, age)
        estimation = get_estimation_insee(genre, categorie, tranche) if tranche else None
        
        if estimation:
            return f"Combien d'heures réelles par semaine {prenom} consacre à {categorie} (INSEE ≈ {estimation} h/semaine) ?"
        return f"Heures par semaine pour {categorie} ({prenom}) ?"
    
    if step == "depenses":
        return MESSAGES.get("depenses_q", "Ajouter une dépense? (tapez 'fin' pour terminer)")
    
    if step == "completed":
        return "✅ Questionnaire terminé!"
    
    return ""

def step_prenom_femme(msg):
    """Handle female's name input."""
    session_set_personne("femme", prenom=msg.title())
    question = get_current_question("age_femme")
    return StateResult(question, "age_femme")

def step_age_femme(msg):
    """Handle female's age input."""
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES.get("age_err", "❌ Âge invalide"))
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    session_set_personne("femme", age=age)
    question = get_current_question("revenu_femme")
    return StateResult(question, "revenu_femme")

def step_revenu_femme(msg):
    """Handle female's income input."""
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES.get("revenu_err", "❌ Revenu invalide"))
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide.")
    session_set_revenu("femme", montant)
    ok_msg = MESSAGES.get("revenu_femme_ok", "✅ {montant}€").format(montant=montant)
    question = get_current_question("prenom_homme")
    return StateResult(ok_msg + "<br>" + question, "prenom_homme")

def step_prenom_homme(msg):
    """Handle male's name input."""
    session_set_personne("homme", prenom=msg.title())
    question = get_current_question("age_homme")
    return StateResult(question, "age_homme")

def step_age_homme(msg):
    """Handle male's age input."""
    age_match = re.search(r'\d+', msg.strip())
    if not age_match:
        return StateResult(MESSAGES.get("age_err", "❌ Âge invalide"))
    age = int(age_match.group())
    if age < 15 or age > 120:
        return StateResult("❌ L'âge doit être entre 15 et 120 ans.")
    session_set_personne("homme", age=age)
    question = get_current_question("revenu_homme")
    return StateResult(question, "revenu_homme")

def step_revenu_homme(msg):
    """Handle male's income input."""
    montant, _ = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES.get("revenu_err", "❌ Revenu invalide"))
    if montant > 1000000:
        return StateResult("❌ Le revenu saisi semble invalide.")
    session_set_revenu("homme", montant)
    ok_msg = MESSAGES.get("revenu_homme_ok_next", "✅ {montant}€").format(montant=montant)
    question = get_current_question("depenses")
    return StateResult(ok_msg + "<br>" + question, "depenses")

def step_depenses(msg):
    """Handle expense input."""
    END_DEPENSES = {"fin", "termine", "terminé", "ok", "next"}
    
    # Check if finished with expenses
    if normaliser(msg) in END_DEPENSES:
        steps = build_steps()
        if not steps:
            raise StateMachineError("Aucune catégorie d'activité disponible.")
        question = get_current_question(steps[0])
        return StateResult("⏱️ Passons aux heures réelles.<br>" + question, steps[0])
    
    # Check if awaiting payer response
    depense_temp = session.get('depense_temp', {})
    if depense_temp.get("awaiting_payeur"):
        payeur = normaliser(msg)
        payeur_mapping = {
            "femme": "femme", "f": "femme", "woman": "femme",
            "homme": "homme", "h": "homme", "man": "homme",
            "partagé": "partagé", "partage": "partagé", "shared": "partagé",
            "both": "partagé", "moitié": "partagé", "moitie": "partagé"
        }
        
        payeur_final = payeur_mapping.get(payeur)
        if payeur_final:
            montant = depense_temp["montant"]
            desc = depense_temp["desc"]
            session_add_depense(desc, montant, payeur_final)
            session.pop('depense_temp', None)
            session.modified = True
            
            ok_msg = MESSAGES.get("depense_ok", "{montant}€ - {categorie}").format(
                montant=montant, categorie=desc
            )
            return StateResult(
                ok_msg + f"<br>👤 {payeur_final.capitalize()} paie.<br>" + 
                MESSAGES.get("depenses_q", "Autre dépense?"),
                "depenses"
            )
        else:
            return StateResult(
                "❓ Qui a payé? Répondez: <b>homme</b>, <b>femme</b>, ou <b>partagé</b>",
                "depenses"
            )
    
    # Extract new expense
    montant, desc = extraire_depense(msg)
    if montant <= 0:
        return StateResult(MESSAGES.get("depense_err", "❌ Dépense invalide"))
    
    # Store temporarily and ask who paid
    session['depense_temp'] = {"montant": montant, "desc": desc, "awaiting_payeur": True}
    session.modified = True
    
    return StateResult(
        f"📝 Dépense: <b>{desc}</b> ({montant}€)<br>"
        "Qui a payé? Répondez: <b>homme</b>, <b>femme</b>, ou <b>partagé</b>",
        "depenses"
    )

def step_donnees_insee(message, step):
    """
    Gère une saisie d'heures réelles pour une catégorie & une personne.
    """
    from src.db import get_tranche_age_for_age, get_estimation_insee, set_step
    from src.session_manager import save_session_data_to_db
    
    # --- Validate input ---
    try:
        heures_semaine = float(message.replace(",", "."))
    except Exception:
        return StateResult("❌ Merci d'indiquer un nombre d'heures valide.")

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
        # All steps completed - transition to completed state
        # Savings will happen in step_completed
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
    from src.db import reset_db, set_step
    from src.session_manager import save_session_data_to_db
    
    # Save data to DB on first entry to completed state
    if 'session_saved' not in session:
        save_session_data_to_db()
        session['session_saved'] = True
        session.modified = True
    
    normalized_msg = normaliser(msg)
    
    # Check for reset commands
    reset_keywords = {"reset", "réinitialiser", "recommencer", "nouveau", "effacer", "vider"}
    if normalized_msg in reset_keywords:
        reset_db()
        session.clear()  # Clear buffered session data
        return StateResult(
            reply=MESSAGES.get("reset", "🔄 Réinitialisation...") + "<br><br>" + get_current_question("prenom_femme"),
            next_step="prenom_femme"
        )
    
    # For any other input, remind them data is ready and already saved
    return StateResult(
        reply="✅ Vos données ont été sauvegardées dans la base de données. Vous pouvez :<br>• Consulter le <strong>bilan</strong><br>• Taper <strong>'reset'</strong> pour effacer et recommencer",
        next_step="completed"
    )

# State handlers mapping (only non-housework steps)
# Housework steps (heures_*) are handled separately by step_donnees_insee in the chat route
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
