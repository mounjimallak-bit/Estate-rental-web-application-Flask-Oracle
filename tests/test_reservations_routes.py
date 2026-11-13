"""Tests du contrôle d'appartenance des réservations (base Oracle SIMULÉE).

Un utilisateur connecté envoie un identifiant de réservation dans le formulaire. Ces tests
vérifient que Flask refuse d'agir sur une réservation qui n'est pas la sienne, avant tout
appel à Oracle, et qu'il agit normalement sur la sienne. Ils ne testent pas le PL/SQL
(voir sql/tests_regles_metier.sql).
"""
import pytest

import app as appmod


class FausseBase:
    """Réservations en mémoire : id -> (id_locataire, id_proprietaire, id_location)."""

    def __init__(self):
        self.reservations = {10: (1, 2, 100), 20: (3, 4, 200)}
        self.appels = []

    def connexion(self):
        base = self

        class Curseur:
            def __init__(self):
                self._ligne = None

            def execute(self, sql, params=None):
                base.appels.append(("execute", sql, list(params or [])))
                if "FROM RESERVATION WHERE id_reservation" in sql:          # locataire
                    id_res, id_user = params
                    r = base.reservations.get(id_res)
                    self._ligne = (1,) if r and r[0] == id_user else None
                elif "JOIN BIEN b ON b.id_bien = r.id_bien" in sql:         # propriétaire
                    id_res, id_user = params
                    r = base.reservations.get(id_res)
                    self._ligne = (1,) if r and r[1] == id_user else None
                elif "SELECT id_location FROM LOCATION" in sql:
                    r = base.reservations.get(params[0])
                    self._ligne = (r[2],) if r else None
                elif "SELECT MAX(id_paiement)" in sql:
                    self._ligne = (1,)
                else:
                    self._ligne = None

            def fetchone(self):
                return self._ligne

            def callproc(self, nom, params):
                base.appels.append(("callproc", nom, list(params)))

        class Connexion:
            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        return Connexion(), Curseur()

    def procedures(self):
        return [a[1] for a in self.appels if a[0] == "callproc"]

    def inserts(self):
        return [a for a in self.appels if a[0] == "execute" and "INSERT" in a[1]]


@pytest.fixture
def client(monkeypatch):
    base = FausseBase()
    monkeypatch.setattr(appmod, "get_db", base.connexion)
    appmod.app.config["TESTING"] = True
    with appmod.app.test_client() as c:
        c.base = base
        yield c


def messages(client):
    """Messages flash mémorisés pour la page suivante (sans charger cette page)."""
    with client.session_transaction() as s:
        return s.get("_flashes", [])


def connecter(client, user_id, role):
    with client.session_transaction() as s:
        s["user_id"] = user_id
        s["user_role"] = role
        s["user_name"] = "test"


@pytest.mark.parametrize("route, role, user_id, procedure", [
    ("/owner/reservation/accept", "Proprietaire", 4, "confirmerReservation"),
    ("/owner/reservation/reject", "Proprietaire", 4, "annulerReservation"),
    ("/tenant/pay", "Locataire", 3, "genererPaiement"),
])
def test_reservation_d_un_autre_refusee(client, route, role, user_id, procedure):
    connecter(client, user_id, role)
    r = client.post(route, data={"id_reservation": "10"})
    assert r.status_code == 302                                   # renvoyé au tableau de bord
    assert ("error", "Réservation introuvable.") in messages(client)
    assert procedure not in client.base.procedures()              # Oracle n'est pas appelé


def test_avis_sur_la_reservation_d_un_autre_refuse(client):
    connecter(client, 3, "Locataire")
    r = client.post("/tenant/review", data={"id_reservation": "10", "note": "1"})
    assert r.status_code == 302
    assert ("error", "Réservation introuvable.") in messages(client)
    assert client.base.inserts() == []


@pytest.mark.parametrize("route, role, user_id, procedure", [
    ("/owner/reservation/accept", "Proprietaire", 2, "confirmerReservation"),
    ("/owner/reservation/reject", "Proprietaire", 2, "annulerReservation"),
    ("/tenant/pay", "Locataire", 1, "genererPaiement"),
])
def test_sa_propre_reservation_acceptee(client, route, role, user_id, procedure):
    connecter(client, user_id, role)
    client.post(route, data={"id_reservation": "10"})
    assert procedure in client.base.procedures()


def test_avis_sur_sa_propre_reservation_accepte(client):
    connecter(client, 1, "Locataire")
    client.post("/tenant/review", data={"id_reservation": "10", "note": "5"})
    assert len(client.base.inserts()) == 1
