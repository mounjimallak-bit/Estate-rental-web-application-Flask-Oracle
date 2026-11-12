"""Tests des routes /register et /login avec une base Oracle SIMULÉE (aucune connexion réelle).

Ils vérifient la logique Flask : ce qui est envoyé à Oracle, et les décisions prises selon la réponse.
Ils ne vérifient PAS le PL/SQL ni le comportement réel d'Oracle (voir la procédure manuelle).
"""
import hashlib
import re

import oracledb
import pytest

import app as appmod
from securite_mdp import hacher_mdp


class FausseBase:
    """Table UTILISATEUR en mémoire, et journal des appels."""

    def __init__(self):
        self.utilisateurs = {}          # login -> [id, mot_de_passe, nom, prenom, role]
        self.appels = []
        self.prochain_id = 1
        self.commits = 0

    def connexion(self):
        base = self

        class Curseur:
            def __init__(self):
                self._resultat = None

            def callproc(self, nom, params):
                base.appels.append((nom, list(params)))
                if nom == "sInscrire":
                    login, nom_, prenom, email, tel, mdp_hache, role = params
                    if not str(mdp_hache).startswith("$argon2id$"):
                        raise oracledb.DatabaseError(_erreur(20001, "ORA-20001: hash attendu"))
                    if login in base.utilisateurs:
                        raise oracledb.DatabaseError(_erreur(1, "ORA-00001: unique constraint (AIRBNB_V2.SYS_C0012345) violated"))
                    base.utilisateurs[login] = [base.prochain_id, mdp_hache, nom_, prenom, role]
                    base.prochain_id += 1
                elif nom == "majMotDePasse":
                    uid, h = params
                    for u in base.utilisateurs.values():
                        if u[0] == uid:
                            u[1] = h

            def execute(self, sql, params=None):
                base.appels.append(("execute", sql, list(params or [])))
                if sql.startswith("SELECT id_utilisateur, mot_de_passe"):
                    u = base.utilisateurs.get(params[0])
                    self._resultat = None if u is None else tuple(u)
                elif sql.startswith("SELECT id_utilisateur FROM UTILISATEUR"):
                    self._resultat = (base.utilisateurs[params[0]][0],)

            def fetchone(self):
                return self._resultat

        class Connexion:
            def commit(self):
                base.commits += 1

            def rollback(self):
                pass

            def close(self):
                pass

        return Connexion(), Curseur()


def _erreur(code, message):
    class E:
        pass
    e = E()
    e.code, e.message = code, message
    return e


@pytest.fixture
def client(monkeypatch):
    base = FausseBase()
    monkeypatch.setattr(appmod, "get_db", base.connexion)
    appmod.app.config.update(TESTING=True, SECRET_KEY="test")
    with appmod.app.test_client() as c:
        c.base = base
        yield c


FORM = dict(login="alice", nom="Martin", prenom="Alice", email="a@x.ma", telephone="0600000000",
            password="un-mot-de-passe-solide", role="Locataire")


def test_inscription_envoie_un_hash_et_jamais_le_mot_de_passe(client):
    r = client.post("/register", data=FORM)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    nom, params = client.base.appels[0]
    assert nom == "sInscrire"
    assert FORM["password"] not in params                      # le clair ne part pas vers Oracle
    assert params[5].startswith("$argon2id$")
    assert client.base.commits == 1                            # une seule validation


def test_inscription_mot_de_passe_trop_court(client):
    r = client.post("/register", data={**FORM, "password": "1234"}, follow_redirects=True)
    assert "au moins 8 caractères".encode() in r.data
    assert client.base.appels == []                            # rien n'est envoyé à Oracle


def test_inscription_doublon_message_generique(client):
    client.post("/register", data=FORM)
    r = client.post("/register", data=FORM, follow_redirects=True)
    assert "déjà utilisé".encode() in r.data
    assert b"SYS_C0012345" not in r.data and b"AIRBNB_V2" not in r.data   # pas de détail Oracle affiché


def test_connexion_reussie(client):
    client.post("/register", data=FORM)
    r = client.post("/login", data={"login": "alice", "password": FORM["password"]})
    assert r.status_code == 302 and r.headers["Location"].endswith("/tenant")
    with client.session_transaction() as s:
        assert s["user_id"] == 1 and s["user_role"] == "Locataire"


def test_mot_de_passe_incorrect(client):
    client.post("/register", data=FORM)
    r = client.post("/login", data={"login": "alice", "password": "faux-mot-de-passe"}, follow_redirects=True)
    assert "Identifiants invalides".encode() in r.data
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_identifiant_inconnu_meme_message(client):
    r = client.post("/login", data={"login": "personne", "password": "x"}, follow_redirects=True)
    assert "Identifiants invalides".encode() in r.data


def test_deux_comptes_meme_mot_de_passe_hashes_differents(client):
    client.post("/register", data=FORM)
    client.post("/register", data={**FORM, "login": "bob", "email": "b@x.ma"})
    h_alice, h_bob = client.base.utilisateurs["alice"][1], client.base.utilisateurs["bob"][1]
    assert h_alice != h_bob


def test_migration_ancien_md5_rehache_a_la_connexion(client):
    ancien = hashlib.md5("ancien-mdp-1234".encode()).hexdigest().upper()
    client.base.utilisateurs["prop1"] = [7, ancien, "Dupont", "Jean", "Proprietaire"]
    r = client.post("/login", data={"login": "prop1", "password": "ancien-mdp-1234"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/owner")
    nouveau = client.base.utilisateurs["prop1"][1]
    assert nouveau.startswith("$argon2id$") and nouveau != ancien     # MD5 remplacé
    assert ("majMotDePasse", [7, nouveau]) in client.base.appels
    # la connexion suivante n'utilise plus MD5 et ne réécrit plus rien
    n = len(client.base.appels)
    client.post("/login", data={"login": "prop1", "password": "ancien-mdp-1234"})
    assert not any(a[0] == "majMotDePasse" for a in client.base.appels[n:])


def test_migration_ancien_md5_mauvais_mot_de_passe_ne_rehache_pas(client):
    ancien = hashlib.md5("ancien-mdp-1234".encode()).hexdigest().upper()
    client.base.utilisateurs["prop1"] = [7, ancien, "Dupont", "Jean", "Proprietaire"]
    client.post("/login", data={"login": "prop1", "password": "faux"})
    assert client.base.utilisateurs["prop1"][1] == ancien
    assert not any(a[0] == "majMotDePasse" for a in client.base.appels)
