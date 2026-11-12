"""Hachage et vérification des mots de passe (Argon2id), avec prise en charge temporaire des anciens
hashes MD5 non salés pour la migration.

- Argon2id (RFC 9106), via argon2-cffi : un salt aléatoire de 16 octets par hash, et les paramètres
  stockés dans le hash lui-même (format PHC : $argon2id$v=19$m=...,t=...,p=...$sel$hash).
- Le mot de passe en clair ne quitte jamais le processus Flask : Oracle ne reçoit que le hash.
- Les anciens hashes MD5 (32 caractères hexadécimaux, produits par l'ancienne procédure sInscrire) sont
  acceptés uniquement pendant la migration ; à la première connexion réussie, ils sont remplacés par un
  hash Argon2id (voir app.py, route /login).
"""
import hashlib
import hmac
import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Paramètres : profil « faible mémoire » recommandé par la RFC 9106 (t=3, m=64 Mio, p=4), valeurs par
# défaut d'argon2-cffi. Ils dépassent le minimum de l'OWASP (m=19 Mio, t=2, p=1). À ajuster après mesure
# sur le serveur : viser 50 à 500 ms par hash (voir benchmark_argon2 ci-dessous).
_PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)

_MD5_HEX = re.compile(r"^[0-9A-Fa-f]{32}$")

# Hash factice, calculé une fois : vérifié quand l'identifiant n'existe pas, pour que la réponse prenne
# le même temps qu'un mot de passe faux (sinon le temps de réponse révèle quels identifiants existent).
_HASH_FACTICE = _PH.hash("identifiant-inexistant")


def hacher_mdp(mdp: str) -> str:
    """Hash Argon2id d'un mot de passe, avec un salt aléatoire propre à ce hash."""
    if not isinstance(mdp, str) or mdp == "":
        raise ValueError("mot de passe vide")
    return _PH.hash(mdp)


def est_ancien_md5(hash_stocke: str | None) -> bool:
    """True pour un hash de l'ancienne procédure (MD5 non salé, 32 caractères hexadécimaux)."""
    return bool(hash_stocke) and bool(_MD5_HEX.match(hash_stocke))


def verifier_mdp(hash_stocke: str | None, mdp: str) -> tuple[bool, bool]:
    """Vérifie un mot de passe. Renvoie (valide, a_rehacher).

    a_rehacher est True quand le hash stocké doit être remplacé : ancien MD5, ou paramètres Argon2
    plus faibles que les paramètres actuels. Toute erreur (hash absent, corrompu) donne (False, False) :
    jamais d'exception vers la route, jamais de connexion acceptée par défaut.
    """
    if not hash_stocke:
        _verifier_factice(mdp)
        return False, False
    if est_ancien_md5(hash_stocke):
        calcule = hashlib.md5(mdp.encode("utf-8")).hexdigest().upper()   # RAWTOHEX : majuscules
        valide = hmac.compare_digest(calcule, hash_stocke.upper())       # comparaison à temps constant
        return valide, valide
    try:
        _PH.verify(hash_stocke, mdp)                                     # comparaison à temps constant
    except VerifyMismatchError:
        return False, False
    except (VerificationError, InvalidHashError):
        return False, False
    return True, _PH.check_needs_rehash(hash_stocke)


def verifier_identifiant_inconnu(mdp: str) -> None:
    """À appeler quand l'identifiant n'existe pas : même coût qu'une vérification réelle."""
    _verifier_factice(mdp)


def _verifier_factice(mdp: str) -> None:
    try:
        _PH.verify(_HASH_FACTICE, mdp or "")
    except (VerificationError, InvalidHashError):
        pass


def benchmark_argon2(n: int = 5) -> float:
    """Durée moyenne d'un hash, en secondes, avec les paramètres actuels (pour régler le coût)."""
    import time
    t0 = time.perf_counter()
    for _ in range(n):
        _PH.hash("mesure-du-cout")
    return (time.perf_counter() - t0) / n
