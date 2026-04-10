"""Session management for user data buffering."""
from flask import session

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
    """Store revenue in session"""
    if 'revenus' not in session:
        session['revenus'] = {}
    session['revenus'][role] = montant
    session.modified = True

def session_add_depense(description, montant, payeur):
    """Store expense in session"""
    if 'depenses' not in session:
        session['depenses'] = []
    session['depenses'].append({
        'description': description,
        'montant': montant,
        'payeur': payeur
    })
    session.modified = True

def session_add_travail_domestique(activite, role, heures):
    """Store domestic work in session"""
    if 'travail_domestique' not in session:
        session['travail_domestique'] = {}
    if activite not in session['travail_domestique']:
        session['travail_domestique'][activite] = {}
    session['travail_domestique'][activite][role] = heures
    session.modified = True

def session_get_personnes():
    """Get person data from session"""
    return session.get('personnes', {})

def session_get_revenus():
    """Get revenue data from session"""
    return session.get('revenus', {})

def session_get_depenses_with_payeur():
    """Get depenses with payeur info from session"""
    if 'depenses' in session and session['depenses']:
        return [(d['description'], d['montant'], d['payeur']) for d in session['depenses']]
    return []

def session_get_travail_domestique():
    """Get domestic work data from session with calculated costs"""
    if 'travail_domestique_full' not in session or not session['travail_domestique_full']:
        return {}
    
    result = {}
    TARIF_HORAIRE = 15.0
    
    for record in session['travail_domestique_full']:
        activite = record['activite']
        sexe = record['sexe']
        heures_semaine = record['heures_semaine']
        
        if activite not in result:
            result[activite] = {}
        
        result[activite][sexe] = heures_semaine
        cout_key = f'cout_{sexe}'
        heures_par_mois = heures_semaine * 4.33
        result[activite][cout_key] = heures_par_mois * TARIF_HORAIRE
    
    return result

def session_get_depenses():
    """Get simple depenses dict from session"""
    if 'depenses' in session and session['depenses']:
        result = {}
        for i, depense in enumerate(session['depenses']):
            result[f"depense_{i}"] = depense['montant']
        return result
    return {}

def save_session_data_to_db():
    """Save all buffered session data to database at once"""
    from src.db import set_personne, set_revenu, add_depense, insert_travail_domestique_user
    
    try:
        print(f"DEBUG: Saving session data to DB. Session keys: {list(session.keys())}")
        
        # Save personnes
        if 'personnes' in session:
            print(f"  Saving {len(session['personnes'])} personnes")
            for role, data in session['personnes'].items():
                if 'prenom' in data:
                    set_personne(role, prenom=data['prenom'])
                if 'age' in data:
                    set_personne(role, age=data['age'])
        
        # Save revenus
        if 'revenus' in session:
            print(f"  Saving {len(session['revenus'])} revenus")
            for role, montant in session['revenus'].items():
                set_revenu(role, montant)
        
        # Save depenses
        if 'depenses' in session:
            print(f"  Saving {len(session['depenses'])} depenses")
            for depense in session['depenses']:
                add_depense(depense['description'], depense['montant'], depense['payeur'])
        
        # Save travail_domestique (full records from session)
        if 'travail_domestique_full' in session:
            print(f"  Saving {len(session['travail_domestique_full'])} travail_domestique records")
            for record in session['travail_domestique_full']:
                print(f"    - {record['sexe']} {record['activite']}: {record['heures_semaine']}h")
                insert_travail_domestique_user(
                    prenom=record['prenom'],
                    age=record['age'],
                    tranche_age=record['tranche_age'],
                    sexe=record['sexe'],
                    activite=record['activite'],
                    heures_semaine=record['heures_semaine']
                )
        else:
            print("  ✗ No travail_domestique_full in session!")
        
        print("✓ Session saved to DB successfully")
        return True
    except Exception as e:
        print(f"✗ ERROR saving session data to DB: {e}")
        import traceback
        traceback.print_exc()
        return False
