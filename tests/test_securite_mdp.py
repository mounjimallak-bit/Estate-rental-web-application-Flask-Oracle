"""Tests du module securite_mdp (sans Oracle)."""
import hashlib

import pytest

from securite_mdp import (_PH, est_ancien_md5, hacher_mdp, verifier_identifiant_inconnu,
                          verifier_mdp)


def test_hash_argon2id_et_non_reversible():
    h = hacher_mdp("motdepasse-solide")
    assert h.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert "motdepasse-solide" not in h
    assert len(h) <= 200                       # tient dans UTILISATEUR.mot_de_passe VARCHAR2(200)


def test_deux_mots_de_passe_identiques_donnent_des_hashes_differents():
    h1, h2 = hacher_mdp("meme-mot-de-passe"), hacher_mdp("meme-mot-de-passe")
    assert h1 != h2                            # salt aléatoire propre à chaque hash
    assert verifier_mdp(h1, "meme-mot-de-passe") == (True, False)
    assert verifier_mdp(h2, "meme-mot-de-passe") == (True, False)


def test_mot_de_passe_incorrect():
    h = hacher_mdp("bon-mot-de-passe")
    assert verifier_mdp(h, "mauvais-mot-de-passe") == (False, False)
    assert verifier_mdp(h, "") == (False, False)


def test_mot_de_passe_vide_refuse_a_l_inscription():
    with pytest.raises(ValueError):
        hacher_mdp("")


def test_hash_absent_ou_corrompu_ne_connecte_jamais():
    assert verifier_mdp(None, "x") == (False, False)
    assert verifier_mdp("", "x") == (False, False)
    assert verifier_mdp("$argon2id$corrompu", "x") == (False, False)
    assert verifier_mdp("texte-quelconque", "texte-quelconque") == (False, False)


def test_ancien_md5_accepte_puis_marque_a_rehacher():
    # Hash produit par l'ancienne procédure : RAWTOHEX(DBMS_CRYPTO.HASH(..., HASH_MD5)), en majuscules
    ancien = hashlib.md5("1234".encode("utf-8")).hexdigest().upper()
    assert ancien == "81DC9BDB52D04DC20036DBD8313ED055"
    assert est_ancien_md5(ancien)
    assert verifier_mdp(ancien, "1234") == (True, True)        # valide ET à remplacer
    assert verifier_mdp(ancien, "12345") == (False, False)
    assert verifier_mdp(ancien.lower(), "1234") == (True, True)


def test_hash_argon2_plus_faible_marque_a_rehacher():
    from argon2 import PasswordHasher
    faible = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash("x-mot-de-passe")
    assert verifier_mdp(faible, "x-mot-de-passe") == (True, True)


def test_identifiant_inconnu_ne_leve_pas_d_erreur():
    verifier_identifiant_inconnu("nimporte-quoi")
    verifier_identifiant_inconnu("")
