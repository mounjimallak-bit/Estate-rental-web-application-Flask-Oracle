from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import oracledb
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "super_secret"

DB_USER = "airbnb_v2"
DB_PASSWORD = "airbnb"
DB_DSN = "localhost:1521/XEPDB1"


# -----------------------------
# DB helpers
# -----------------------------
def get_db():
    conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
    conn.autocommit = False
    return conn, conn.cursor()
def get_db_cursor():

    conn = oracledb.connect(
        user="airbnb_v2",
        password="airbnb",
        dsn="localhost:1521/XEPDB1"
    )

    return conn, conn.cursor()

def rows_to_dicts(cursor, rows):
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# -----------------------------
# Auth / Guards
# -----------------------------
def current_user():
    if "user_id" not in session:
        return None
    return {
        "id": session.get("user_id"),
        "name": session.get("user_name"),
        "role": session.get("user_role"),
    }


def login_required():
    if "user_id" not in session:
        flash("Connexion requise.", "warning")
        return False
    return True


def role_required(*roles):
    if not login_required():
        return False
    if session.get("user_role") not in roles:
        flash("Accès refusé.", "error")
        return False
    return True


@app.context_processor
def inject_user():
    return {"me": current_user()}


# -----------------------------
# Public: Home + Search
# -----------------------------
@app.route("/")
def home():
    conn, cursor = get_db_cursor()
    cursor.execute("SELECT * FROM VUE_BIENS_PUBLICS")
    columns = [col[0].lower() for col in cursor.description]
    biens = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return render_template("index.html", biens=biens, active_tab="all")


@app.route("/search")
def search():
    type_filtre = request.args.get("type")  # "Piscine" ou "Mer"

    conn, cursor = get_db_cursor()

    if type_filtre == "Piscine":
        cursor.execute("""
            SELECT * FROM VUE_BIENS_PUBLICS
            WHERE LOWER(description) LIKE '%piscine%'
        """)
        active_tab = "piscine"

    elif type_filtre == "Mer":
        cursor.execute("""
            SELECT * FROM VUE_BIENS_PUBLICS
            WHERE LOWER(description) LIKE '%mer%'
               OR LOWER(description) LIKE '%plage%'
               OR LOWER(description) LIKE '%bord de mer%'
        """)
        active_tab = "mer"

    else:
        cursor.execute("SELECT * FROM VUE_BIENS_PUBLICS")
        active_tab = "all"

    columns = [col[0].lower() for col in cursor.description]
    biens = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()

    return render_template("index.html", biens=biens, active_tab=active_tab)

@app.route("/bien/<int:id_bien>", methods=["GET"])
def bien_detail(id_bien):
    conn, cur = get_db()
    try:
        cur.execute("SELECT * FROM VUE_BIENS_PUBLICS WHERE id_bien = :1", [id_bien])
        row = cur.fetchone()
        if not row:
            abort(404)

        cols = [c[0].lower() for c in cur.description]
        bien = dict(zip(cols, row))

        # photos (galerie)
        cur.execute(
            "SELECT id_photo, url_photo, description_alt, est_principale FROM PHOTO_BIEN WHERE id_bien = :1 ORDER BY est_principale DESC, id_photo DESC",
            [id_bien],
        )
        photos = rows_to_dicts(cur, cur.fetchall())

        # avis (optionnel)
        cur.execute(
            """
            SELECT a.note, a.commentaire, a.date_avis
            FROM AVIS_BIEN a
            JOIN LOCATION l ON a.id_location = l.id_location
            JOIN RESERVATION r ON l.id_reservation = r.id_reservation
            WHERE r.id_bien = :1
            ORDER BY a.date_avis DESC
            """,
            [id_bien],
        )
        avis = rows_to_dicts(cur, cur.fetchall())

        return render_template("property_detail.html", bien=bien, photos=photos, avis=avis)
    finally:
        conn.close()


# -----------------------------
# Reservation (Locataire)
# -----------------------------
@app.route("/reservation/create", methods=["POST"])
def reservation_create():
    if not role_required("Locataire"):
        return redirect(url_for("login"))

    id_bien = int(request.form.get("id_bien"))
    date_debut = request.form.get("date_debut")
    date_fin = request.form.get("date_fin")

    try:
        d1 = datetime.strptime(date_debut, "%Y-%m-%d").date()
        d2 = datetime.strptime(date_fin, "%Y-%m-%d").date()
        if d2 <= d1:
            flash("Dates invalides (date fin doit être > date début).", "error")
            return redirect(request.referrer or url_for("home"))
    except:
        flash("Dates invalides.", "error")
        return redirect(request.referrer or url_for("home"))

    conn, cur = get_db()
    try:
        # Procedure PL/SQL creerReservation :contentReference[oaicite:10]{index=10}
        cur.callproc("creerReservation", [session["user_id"], id_bien, d1, d2])
        conn.commit()
        flash("Demande de réservation envoyée (EN_ATTENTE).", "success")
        return redirect(url_for("tenant_dashboard"))
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur réservation : {err.message}", "error")
        return redirect(request.referrer or url_for("home"))
    finally:
        conn.close()


@app.route("/tenant", methods=["GET"])
def tenant_dashboard():
    if not role_required("Locataire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
        # get_mes_reservations :contentReference[oaicite:11]{index=11}
        ref = cur.callfunc("get_mes_reservations", oracledb.CURSOR, [session["user_id"]])
        reservations = []
        for r in ref:
            reservations.append(
                {
                    "id_reservation": r[0],
                    "date_debut": r[1],
                    "date_fin": r[2],
                    "statut": r[3],
                    "montant": r[4],
                    "titre": r[5],
                    "ville": r[6],
                    "prix_nuit": r[7],
                }
            )

        # paiement status par reservation (si confirmée)
        pay_status = {}
        for res in reservations:
            if res["statut"] == "CONFIRMEE":
                cur.execute(
                    """
                    SELECT p.statut_paiement
                    FROM PAIEMENT p
                    WHERE p.id_location = (
                        SELECT l.id_location
                        FROM LOCATION l
                        WHERE l.id_reservation = :1
                    )
                    """,
                    [res["id_reservation"]],
                )
                row = cur.fetchone()
                pay_status[res["id_reservation"]] = row[0] if row else None

        return render_template("tenant_dashboard.html", reservations=reservations, pay_status=pay_status)
    finally:
        conn.close()


@app.route("/tenant/pay", methods=["POST"])
def tenant_pay():
    if not role_required("Locataire"):
        return redirect(url_for("login"))

    id_res = int(request.form.get("id_reservation"))

    conn, cur = get_db()
    try:
        # retrouver location
        cur.execute("SELECT id_location FROM LOCATION WHERE id_reservation = :1", [id_res])
        row = cur.fetchone()
        if not row:
            flash("Location introuvable (réservation pas confirmée).", "error")
            return redirect(url_for("tenant_dashboard"))

        id_loc = row[0]

        # genererPaiement + validerPaiement :contentReference[oaicite:12]{index=12}
        cur.callproc("genererPaiement", [id_loc, "CB"])
        cur.execute("SELECT MAX(id_paiement) FROM PAIEMENT WHERE id_location = :1", [id_loc])
        id_pay = cur.fetchone()[0]
        cur.callproc("validerPaiement", [id_pay])

        conn.commit()
        flash("Paiement validé (REUSSI).", "success")
        return redirect(url_for("tenant_dashboard"))
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur paiement : {err.message}", "error")
        return redirect(url_for("tenant_dashboard"))
    finally:
        conn.close()


@app.route("/tenant/review", methods=["POST"])
def tenant_review():
    if not role_required("Locataire"):
        return redirect(url_for("login"))

    id_res = int(request.form.get("id_reservation"))
    note = int(request.form.get("note", "5"))
    commentaire = (request.form.get("commentaire") or "").strip()

    conn, cur = get_db()
    try:
        cur.execute("SELECT id_location FROM LOCATION WHERE id_reservation = :1", [id_res])
        row = cur.fetchone()
        if not row:
            flash("Impossible : location introuvable.", "error")
            return redirect(url_for("tenant_dashboard"))
        id_loc = row[0]

        # 1 avis par location (uq_avis_location) :contentReference[oaicite:13]{index=13}
        cur.execute(
            "INSERT INTO AVIS_BIEN(note, commentaire, id_location) VALUES (:1, :2, :3)",
            [note, commentaire, id_loc],
        )
        conn.commit()
        flash("Avis enregistré.", "success")
        return redirect(url_for("tenant_dashboard"))
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur avis : {err.message}", "error")
        return redirect(url_for("tenant_dashboard"))
    finally:
        conn.close()


# -----------------------------
# Owner (Proprietaire)
# -----------------------------
@app.route("/owner", methods=["GET"])
def owner_dashboard():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
        # Mes biens (fonction)
        ref = cur.callfunc("get_mes_biens", oracledb.CURSOR, [session["user_id"]])
        my_biens = []
        for r in ref:
            # SELECT * FROM BIEN => on garde simple
            my_biens.append(
                {
                    "id_bien": r[0],
                    "titre": r[1],
                    "description": r[2],
                    "adresse": r[3],
                    "ville": r[4],
                    "surface": r[5],
                    "prix": r[6],
                    "type_bien": r[7],
                    "capacite": r[8],
                    "note_moyenne": r[9],
                }
            )

        # Demandes reçues: requête adaptée de ton Streamlit :contentReference[oaicite:14]{index=14}
        cur.execute(
            """
            SELECT r.id_reservation,
                   r.id_locataire,
                   u.nom || ' ' || u.prenom AS client,
                   r.id_bien,
                   b.titre AS nom_bien,
                   r.date_debut,
                   r.date_fin,
                   r.statut,
                   r.montant_reservation
            FROM RESERVATION r
            JOIN BIEN b ON r.id_bien = b.id_bien
            JOIN PROPRIETAIRE p ON b.id_proprietaire = p.id_utilisateur
            JOIN UTILISATEUR u ON r.id_locataire = u.id_utilisateur
            WHERE p.id_utilisateur = :1
            ORDER BY r.date_demande DESC
            """,
            [session["user_id"]],
        )
        demandes = rows_to_dicts(cur, cur.fetchall())

        return render_template("owner_dashboard.html", my_biens=my_biens, demandes=demandes)
    finally:
        conn.close()


@app.route("/owner/reservation/accept", methods=["POST"])
def owner_accept():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    id_res = int(request.form.get("id_reservation"))

    conn, cur = get_db()
    try:
        # procedure confirmerReservation :contentReference[oaicite:15]{index=15}
        cur.callproc("confirmerReservation", [id_res])
        conn.commit()
        flash("Réservation acceptée (CONFIRMEE + LOCATION créée).", "success")
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur acceptation : {err.message}", "error")
    finally:
        conn.close()

    return redirect(url_for("owner_dashboard"))


@app.route("/owner/reservation/reject", methods=["POST"])
def owner_reject():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    id_res = int(request.form.get("id_reservation"))

    conn, cur = get_db()
    try:
        cur.callproc("annulerReservation", [id_res])
        conn.commit()
        flash("Réservation refusée/annulée.", "success")
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur refus : {err.message}", "error")
    finally:
        conn.close()

    return redirect(url_for("owner_dashboard"))


@app.route("/owner/new-bien", methods=["GET", "POST"])
def owner_new_bien():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("owner_new_bien.html")

    titre = (request.form.get("titre") or "").strip()
    ville = (request.form.get("ville") or "").strip()
    adresse = (request.form.get("adresse") or "").strip()
    description = (request.form.get("description") or "").strip()
    type_bien = (request.form.get("type_bien") or "Appartement").strip()
    photo_url = (request.form.get("photo_url") or "https://via.placeholder.com/400x300").strip()

    try:
        prix = float(request.form.get("prix") or "0")
        capacite = int(request.form.get("capacite") or "1")
        surface = float(request.form.get("surface") or "0")
    except:
        flash("Champs numériques invalides.", "error")
        return redirect(url_for("owner_new_bien"))

    if not titre or not ville or prix <= 0:
        flash("Titre, ville et prix sont obligatoires.", "error")
        return redirect(url_for("owner_new_bien"))

    conn, cur = get_db()
    try:
        id_out = cur.var(oracledb.NUMBER)

        cur.execute(
            """
            INSERT INTO BIEN(titre, description, adresse, ville, surface, prix, type_bien, capacite, id_proprietaire)
            VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9)
            RETURNING id_bien INTO :10
            """,
            [titre, description, adresse, ville, surface, prix, type_bien, capacite, session["user_id"], id_out],
        )
        new_id = int(id_out.getvalue())

        cur.execute(
            "INSERT INTO PHOTO_BIEN(url_photo, est_principale, id_bien) VALUES (:1, 1, :2)",
            [photo_url, new_id],
        )

        # publier l'annonce via PL/SQL :contentReference[oaicite:16]{index=16}
        cur.callproc("creerAnnonce", [new_id])

        conn.commit()
        flash("Bien publié (annonce disponible).", "success")
        return redirect(url_for("owner_dashboard"))
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur création bien : {err.message}", "error")
        return redirect(url_for("owner_new_bien"))
    finally:
        conn.close()


# -----------------------------
# Auth: login/register/logout
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth_login.html")

    username = (request.form.get("login") or "").strip()
    password = (request.form.get("password") or "").strip()

    conn, cur = get_db()
    try:
        # seConnecter (hash en DB) :contentReference[oaicite:17]{index=17}
        user_id = cur.callfunc("seConnecter", oracledb.NUMBER, [username, password])
        if not user_id:
            flash("Identifiants invalides.", "error")
            return redirect(url_for("login"))

        cur.execute("SELECT nom, prenom, role_app FROM UTILISATEUR WHERE id_utilisateur = :1", [user_id])
        row = cur.fetchone()
        if not row:
            flash("Utilisateur introuvable.", "error")
            return redirect(url_for("login"))

        session["user_id"] = int(user_id)
        session["user_name"] = f"{row[1]} {row[0]}"
        session["user_role"] = row[2]

        flash("Connexion réussie.", "success")

        if session["user_role"] == "Proprietaire":
            return redirect(url_for("owner_dashboard"))
        return redirect(url_for("tenant_dashboard"))
    finally:
        conn.close()


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth_register.html")

    login_db = (request.form.get("login") or "").strip()
    nom = (request.form.get("nom") or "").strip()
    prenom = (request.form.get("prenom") or "").strip()
    email = (request.form.get("email") or "").strip()
    telephone = (request.form.get("telephone") or "").strip()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "").strip()  # "Locataire" ou "Proprietaire"

    if role not in ("Locataire", "Proprietaire"):
        flash("Rôle invalide.", "error")
        return redirect(url_for("register"))

    conn, cur = get_db()
    try:
        # sInscrire :contentReference[oaicite:18]{index=18}
        cur.callproc("sInscrire", [login_db, nom, prenom, email, telephone, password, role])

        # IMPORTANT: sInscrire n'insère que dans UTILISATEUR, donc on crée la ligne LOCATAIRE/PROPRIETAIRE :contentReference[oaicite:19]{index=19}
        cur.execute("SELECT id_utilisateur FROM UTILISATEUR WHERE login_db = :1", [login_db])
        uid = cur.fetchone()[0]

        if role == "Locataire":
            cur.execute("INSERT INTO LOCATAIRE(id_utilisateur) VALUES (:1)", [uid])
        else:
            cur.execute("INSERT INTO PROPRIETAIRE(id_utilisateur) VALUES (:1)", [uid])

        conn.commit()
        flash("Inscription validée. Connectez-vous.", "success")
        return redirect(url_for("login"))
    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur inscription : {err.message}", "error")
        return redirect(url_for("register"))
    finally:
        conn.close()


@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté.", "success")
    return redirect(url_for("home"))


if __name__ == '__main__':


    app.run(debug=True)