import psycopg2
from psycopg2 import sql
import os
import re
from urllib.parse import urlparse
from functools import lru_cache

# Database connection URL (set DATABASE_URL in environment for Render)
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/financier')

# Simple cache to avoid repeated DB calls within a request
_step_cache = None
_step_cache_session_id = None

def get_db_connection():
    """Create and return a database connection"""
    try:
        url = os.getenv('DATABASE_URL')
        if not url:
            raise ValueError("DATABASE_URL environment variable is not set")
        return psycopg2.connect(url)
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise

# -------- INITIALISATION DE LA BASE --------
def init_db():
    conn = get_db_connection ()
    c = conn.cursor()
    
    try:
        # Table pour les revenus
        c.execute("""
        CREATE TABLE IF NOT EXISTS revenus (
            personne TEXT PRIMARY KEY,
            montant REAL
        )
        """)
        # Table pour les dépenses
        c.execute("""
        CREATE TABLE IF NOT EXISTS depenses (
            id SERIAL PRIMARY KEY,
            categorie TEXT NOT NULL,
            montant REAL,
            payeur TEXT DEFAULT 'partagé'
        )
        """)
        # Table pour l'étape actuelle du chatbot
        c.execute("""
        CREATE TABLE IF NOT EXISTS step (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        # Table pour les informations des personnes
        c.execute("""
        CREATE TABLE IF NOT EXISTS personnes (
            role TEXT PRIMARY KEY,
            prenom TEXT,
            age INTEGER
        )
        """)
        # Table des heures réelles (questionnaire)
        c.execute("""
        CREATE TABLE IF NOT EXISTS donnees_insee (
            id SERIAL PRIMARY KEY,
            sexe TEXT NOT NULL,
            activite TEXT NOT NULL,
            tranche_age TEXT NOT NULL,
            volume_horaire REAL NOT NULL,
            cout REAL NOT NULL,
            UNIQUE(sexe, activite, tranche_age)
        )
        """)

        # Table du travail domestique (INSEE)
        c.execute("""
        CREATE TABLE IF NOT EXISTS travail_domestique (
            id SERIAL PRIMARY KEY,
            prenom TEXT,
            age INTEGER,
            tranche_age TEXT,
            sexe TEXT NOT NULL,
            activite TEXT NOT NULL,            
            duree_minutes INTEGER NOT NULL,
            duree_heures REAL NOT NULL,
            cout_jour REAL NOT NULL,
            UNIQUE(sexe, activite, tranche_age)
        )
        """)

        # Données INSEE quotidiennes (minutes/jour)
        donnees_insee = [
             ("femme", "cuisine & ménage", "18-24 ans", 120),
            ("homme", "cuisine & ménage", "18-24 ans", 70),
            ("femme", "soins enfants", "18-24 ans", 50),
            ("homme", "soins enfants", "18-24 ans", 30),
            ("femme", "courses", "18-24 ans", 25),
            ("homme", "courses", "18-24 ans", 20),
            ("femme", "bricolage/jardinage", "18-24 ans", 10),
            ("homme", "bricolage/jardinage", "18-24 ans", 20),
            ("femme", "cuisine & ménage", "25-34 ans", 140),
            ("homme", "cuisine & ménage", "25-34 ans", 85),
            ("femme", "soins enfants", "25-34 ans", 95),
            ("homme", "soins enfants", "25-34 ans", 55),
            ("femme", "courses", "25-34 ans", 32),
            ("homme", "courses", "25-34 ans", 28),
            ("femme", "bricolage/jardinage", "25-34 ans", 12),
            ("homme", "bricolage/jardinage", "25-34 ans", 35),
            ("femme", "cuisine & ménage", "35-49 ans", 150),
            ("homme", "cuisine & ménage", "35-49 ans", 90),
            ("femme", "soins enfants", "35-49 ans", 105),
            ("homme", "soins enfants", "35-49 ans", 60),
            ("femme", "courses", "35-49 ans", 34),
            ("homme", "courses", "35-49 ans", 30),
            ("femme", "bricolage/jardinage", "35-49 ans", 15),
            ("homme", "bricolage/jardinage", "35-49 ans", 40),
            ("femme", "cuisine & ménage", "50-64 ans", 130),
            ("homme", "cuisine & ménage", "50-64 ans", 80),
            ("femme", "soins enfants", "50-64 ans", 30),
            ("homme", "soins enfants", "50-64 ans", 15),
            ("femme", "courses", "50-64 ans", 28),
            ("homme", "courses", "50-64 ans", 25),
            ("femme", "bricolage/jardinage", "50-64 ans", 12),
            ("homme", "bricolage/jardinage", "50-64 ans", 35),
        ]

        cout_horaire = 15  # €/h

        for sexe, activite, tranche_age, heures in donnees_insee:
            c.execute("""
            INSERT INTO donnees_insee
                (sexe, activite, tranche_age, volume_horaire, cout)
                VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (sexe, activite, tranche_age) DO NOTHING
            """, (
                sexe,
                activite,
                tranche_age,
                heures,
                round(heures * cout_horaire, 2)
            ))              
     
        conn.commit()
    finally:
        c.close()
        conn.close()

def reset_db():
    """Reset user data only (revenus, depenses, personnes, travail_domestique).
    Keep donnees_insee as reference data that should never be deleted."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM revenus")
        c.execute("DELETE FROM depenses")
        c.execute("DELETE FROM step")
        c.execute("DELETE FROM personnes")
        # NOTE: DO NOT delete donnees_insee - it's reference data that should persist
        c.execute("DELETE FROM travail_domestique")
        c.execute("INSERT INTO personnes (role, prenom, age) VALUES (%s, %s, %s)", ('femme', None, None))
        c.execute("INSERT INTO personnes (role, prenom, age) VALUES (%s, %s, %s)", ('homme', None, None))
        conn.commit()
    finally:
        c.close()
        conn.close()

# -------- REVENUS --------
def get_revenus():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT personne, montant FROM revenus")
        result = c.fetchall()
        return dict(result) if result else {}
    finally:
        c.close()
        conn.close()

def set_revenu(personne, montant):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO revenus (personne, montant) VALUES (%s, %s) ON CONFLICT (personne) DO UPDATE SET montant = %s", 
                  (personne, montant, montant))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Erreur lors de l'insertion des revenus: {e}")
        return False
    finally:
        c.close()
        conn.close()
    return True

# -------- DEPENSES --------
def get_depenses():
    """Retourne un dict des dépenses (pour compatibilité)"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT categorie, montant FROM depenses")
        result = c.fetchall()
        return dict(result) if result else {}
    finally:
        c.close()
        conn.close()

def get_depenses_with_payeur():
    """Retourne les dépenses avec le payeur (homme/femme/partagé)"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT categorie, montant, payeur FROM depenses")
        result = c.fetchall()
        return [(cat, mont, pay) for cat, mont, pay in result]
    finally:
        c.close()
        conn.close()

def add_depense(categorie, montant, payeur="partagé"):
    """Ajoute une dépense avec son payeur (homme/femme/partagé)"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO depenses (categorie, montant, payeur) VALUES (%s, %s, %s)", (categorie, montant, payeur))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Erreur lors de l'ajout de la dépense: {e}")
        return False
    finally:
        c.close()
        conn.close()
    return True

# -------- ETAPE DU CHATBOT --------
def get_step():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT value FROM step WHERE key=%s", ('current',))
        row = c.fetchone()
        return row[0] if row else None
    finally:
        c.close()
        conn.close()

def set_step(step):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO step (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s", 
                  ('current', step, step))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Erreur lors de l'insertion de l'étape: {e}")
        return False
    finally:
        c.close()
        conn.close()
    return True

# -------- PERSONNES --------
def set_personne(role, prenom=None, age=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT prenom, age FROM personnes WHERE role = %s", (role,))
        row = c.fetchone()
        if row:
            new_prenom = prenom if prenom is not None else row[0]
            new_age = age if age is not None else row[1]
            c.execute("UPDATE personnes SET prenom=%s, age=%s WHERE role=%s", (new_prenom, new_age, role))
        else:
            c.execute("INSERT INTO personnes (role, prenom, age) VALUES (%s, %s, %s)", (role, prenom, age))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Erreur lors de l'insertion des informations de {role}: {e}")
        return False
    finally:
        c.close()
        conn.close()
    return True

def get_personnes():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT role, prenom, age FROM personnes")
        result = c.fetchall()
        return {role: {"prenom": prenom or "", "age": age} for role, prenom, age in result}
    finally:
        c.close()
        conn.close()

# -------- DONNEES INSEE --------

def insert_donnees_insee(sexe, activite, volume_horaire, cout_horaire=15):
    cout = round(volume_horaire * cout_horaire, 2)
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO donnees_insee (sexe, activite, volume_horaire, cout)
            VALUES (%s, %s, %s, %s)
        """, (sexe, activite, volume_horaire, cout))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Erreur lors de l'insertion des heures réelles: {e}")
        return False
    finally:
        c.close()
        conn.close()
    return True

# -------- TRAVAIL DOMESTIQUE --------
def insert_travail_domestique(sexe, activite, tranche_age, duree_minutes, cout_horaire=15):
    heures = duree_minutes / 60
    cout = heures * cout_horaire
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO travail_domestique (sexe, activite, tranche_age, duree_minutes, duree_heures, cout_jour)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(sexe, activite) DO UPDATE SET
                tranche_age = excluded.tranche_age,
                duree_minutes = excluded.duree_minutes,
                duree_heures = excluded.duree_heures,
                cout_jour = excluded.cout_jour
        """, (sexe, activite, tranche_age, duree_minutes, round(heures,2), round(cout,1)))
        conn.commit()
    finally:
        c.close()
        conn.close()

def get_travail_domestique():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT sexe, activite, duree_minutes, cout_jour
            FROM travail_domestique
        """)
        rows = c.fetchall()

        travail_domestique = {}

        for sexe, activite, minutes_jour, cout_jour in rows:
            # Convert daily minutes back to weekly hours
            # Original conversion: heures_semaine -> (heures_semaine * 60) / 7 = minutes_jour
            # Reverse: minutes_jour -> (minutes_jour / 60) * 7 = heures_semaine
            heures_semaine = (minutes_jour / 60) * 7

            if activite not in travail_domestique:
                travail_domestique[activite] = {
                    "homme": 0,
                    "femme": 0,
                    "cout_homme": 0,
                    "cout_femme": 0
                }

            if sexe == "homme":
                travail_domestique[activite]["homme"] += heures_semaine
                travail_domestique[activite]["cout_homme"] += cout_jour
            else:
                travail_domestique[activite]["femme"] += heures_semaine
                travail_domestique[activite]["cout_femme"] += cout_jour

        return travail_domestique
    finally:
        c.close()
        conn.close()


def get_categories_domestiques():
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT DISTINCT activite
            FROM donnees_insee
            ORDER BY activite
        """)
        rows = c.fetchall()
        return [r[0] for r in rows]
    finally:
        c.close()
        conn.close()


def get_estimation_insee(sexe, activite, tranche_age):
    """
    Retourne l'estimation INSEE en heures / semaine
    depuis des minutes / jour stockées en base.
    """
    if not tranche_age:
        return None

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT volume_horaire
            FROM donnees_insee
            WHERE sexe = %s
              AND activite = %s
              AND tranche_age = %s
        """, (sexe, activite, tranche_age))
        row = c.fetchone()

        if not row:
            return None

        minutes_jour = row[0]
        heures_semaine = (minutes_jour / 60) * 7

        return round(heures_semaine, 1)
    finally:
        c.close()
        conn.close()


def get_tranche_age_for_age(sexe, activite, age):
    """
    Retourne la tranche_age (ex: '25-34 ans') correspondant à l'âge,
    en se basant sur la table donnees_insee.
    """
    if age is None:
        return None

    try:
        age = int(age)
    except (ValueError, TypeError):
        return None

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT DISTINCT tranche_age
            FROM donnees_insee
            WHERE sexe = %s
              AND activite = %s
        """, (sexe, activite))

        tranches = [row[0] for row in c.fetchall()]

        for tranche in tranches:
            match = re.match(r"(\d+)\s*-\s*(\d+)\s*ans", tranche)
            if not match:
                continue

            age_min, age_max = map(int, match.groups())
            if age_min <= age <= age_max:
                return tranche

        return None
    finally:
        c.close()
        conn.close()


def get_age(role):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT age FROM personnes WHERE role = %s", (role,))
        row = c.fetchone()
        return row[0] if row else None
    finally:
        c.close()
        conn.close()

def insert_travail_domestique_user(
    prenom,
    age,
    tranche_age,
    sexe,
    activite,
    heures_semaine
):
    # heures/semaine → minutes/jour
    minutes_jour = round((heures_semaine * 60) / 7)

    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute("""
            INSERT INTO travail_domestique (
                prenom, age, tranche_age, sexe, activite,
                duree_minutes, duree_heures, cout_jour
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prenom,
            age,
            tranche_age,
            sexe,
            activite,
            minutes_jour,
            round(minutes_jour / 60, 2),
            round((minutes_jour / 60) * 15, 2)
        ))

        conn.commit()
    finally:
        c.close()
        conn.close()

# -------- SESSION-BASED STORAGE (for poor network) --------
# Store data in Flask session, save to DB only at the end

def get_session_data(flask_session):
    """Get data from Flask session"""
    return {
        'revenus': flask_session.get('revenus', {}),
        'depenses': flask_session.get('depenses', []),
        'personnes': flask_session.get('personnes', {}),
        'step': flask_session.get('step', None),
        'travail_domestique': flask_session.get('travail_domestique', [])
    }

def set_session_data(flask_session, data_key, value):
    """Set data in Flask session"""
    flask_session[data_key] = value
    flask_session.modified = True

def save_session_to_db(flask_session):
    """Save all session data to remote database in one batch"""
    try:
        data = get_session_data(flask_session)
        conn = get_db_connection()
        c = conn.cursor()
        
        # Save revenus
        for personne, montant in data.get('revenus', {}).items():
            c.execute("INSERT INTO revenus (personne, montant) VALUES (%s, %s) ON CONFLICT (personne) DO UPDATE SET montant = %s", 
                      (personne, montant, montant))
        
        # Save depenses (stored as dicts with 'description', 'montant', 'payeur')
        for depense in data.get('depenses', []):
            c.execute("INSERT INTO depenses (categorie, montant, payeur) VALUES (%s, %s, %s)", 
                      (depense.get('description'), depense.get('montant'), depense.get('payeur')))
        
        # Save personnes
        for role, info in data.get('personnes', {}).items():
            c.execute("INSERT INTO personnes (role, prenom, age) VALUES (%s, %s, %s) ON CONFLICT (role) DO UPDATE SET prenom = %s, age = %s", 
                      (role, info.get('prenom'), info.get('age'), info.get('prenom'), info.get('age')))
        
        # Save travail_domestique
        for item in data.get('travail_domestique', []):
            prenom, age, tranche_age, sexe, activite, heures_semaine = item
            c.execute("""
                INSERT INTO travail_domestique (prenom, age, tranche_age, sexe, activite, duree_minutes, duree_heures, cout_jour)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (prenom, age, tranche_age, sexe, activite, round(heures_semaine * 60), round(heures_semaine, 2), round(heures_semaine * 15, 2)))
        
        conn.commit()
        c.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"Erreur lors de la sauvegarde en base: {e}")
        return False
