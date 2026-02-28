from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import oracledb
from datetime import date, datetime
import os



app = Flask(__name__)
app.secret_key = ""

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DSN = os.getenv("DB_DSN")

def get_db():
    try:
        conn = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
        return conn, conn.cursor()
    except oracledb.Error as e:
        print(f"Erreur de connexion Oracle : {e}")
        return None, None

def rows_to_dicts(cursor, rows):
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


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


@app.route("/")
def home():
    conn, cursor = get_db()
    cursor.execute("SELECT * FROM VUE_BIENS_PUBLICS")
    columns = [col[0].lower() for col in cursor.description]
    biens = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return render_template("index.html", biens=biens, active_tab="all")


@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        q = (request.form.get("q") or "").strip()
        ville = (request.form.get("ville") or "").strip()
        type_filtre = (request.form.get("type") or "").strip()
        prix_min = (request.form.get("prix_min") or "").strip()
        prix_max = (request.form.get("prix_max") or "").strip()
        return redirect(url_for("search", q=q, ville=ville, type=type_filtre, prix_min=prix_min, prix_max=prix_max))
    q = (request.args.get("q") or "").strip()
    ville = (request.args.get("ville") or "").strip()
    type_filtre = (request.args.get("type") or "").strip()  # Piscine / Mer / vide
    prix_min = (request.args.get("prix_min") or "").strip()
    prix_max = (request.args.get("prix_max") or "").strip()
    conn, cursor = get_db()
    if not conn or not cursor:
        flash("Erreur de connexion à la base de données.", "error")
        return redirect(url_for("home"))
    try:
        sql = "SELECT * FROM VUE_BIENS_PUBLICS WHERE 1=1"
        params = {}

        if q:
            sql += " AND (LOWER(titre) LIKE :q OR LOWER(description) LIKE :q)"
            params["q"] = f"%{q.lower()}%"
     
        if ville:
            sql += " AND LOWER(ville) LIKE :ville"
            params["ville"] = f"%{ville.lower()}%"

        active_tab = "all"
        if type_filtre == "Piscine":
            sql += " AND LOWER(description) LIKE :piscine"
            params["piscine"] = "%piscine%"
            active_tab = "piscine"
        elif type_filtre == "Mer":
            sql += " AND (LOWER(description) LIKE :mer OR LOWER(description) LIKE :plage OR LOWER(description) LIKE :bord)"
            params["mer"] = "%mer%"
            params["plage"] = "%plage%"
            params["bord"] = "%bord de mer%"
            active_tab = "mer"

        if prix_min:
            try:
                sql += " AND prix >= :prix_min"
                params["prix_min"] = float(prix_min)
            except:
                pass

        if prix_max:
            try:
                sql += " AND prix <= :prix_max"
                params["prix_max"] = float(prix_max)
            except:
                pass

        sql += " ORDER BY id_bien DESC"

        cursor.execute(sql, params)

        columns = [col[0].lower() for col in cursor.description]
        biens = [dict(zip(columns, row)) for row in cursor.fetchall()]

        
        return render_template(
            "index.html",
            biens=biens,
            active_tab=active_tab,
            q=q,
            ville=ville,
            type_filtre=type_filtre,
            prix_min=prix_min,
            prix_max=prix_max
        )

    finally:
        try:
            cursor.close()
        except:
            pass
        conn.close() 

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
        cur.execute(
            "SELECT id_photo, url_photo, description_alt, est_principale FROM PHOTO_BIEN WHERE id_bien = :1 ORDER BY est_principale DESC, id_photo DESC",
            [id_bien],
        )
        photos = rows_to_dicts(cur, cur.fetchall())

       
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

       
        cur.execute("""
            SELECT date_debut, date_fin
            FROM RESERVATION
            WHERE id_bien = :id_bien
              AND statut IN ('CONFIRMEE','EN_COURS')
        """, {"id_bien": id_bien})

        indispos = []
        for d1, d2 in cur.fetchall():
            indispos.append({
                "start": d1.strftime("%Y-%m-%d"),
                "end": d2.strftime("%Y-%m-%d")
            })
        return render_template("property_detail.html", bien=bien, photos=photos, avis=avis, indispos=indispos)
    finally:
        conn.close()




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
    except Exception:
        flash("Dates invalides.", "error")
        return redirect(request.referrer or url_for("home"))

    conn, cur = get_db()
    try:
      
        cur.execute("""
            SELECT COUNT(*)
            FROM RESERVATION
            WHERE id_bien = :id_bien
              AND statut IN ('CONFIRMEE','EN_ATTENTE','ACCEPTEE')
              AND (:d1 <= date_fin AND :d2 >= date_debut)
        """, {"id_bien": id_bien, "d1": d1, "d2": d2})

        nb = cur.fetchone()[0]
        if nb > 0:
            flash("Dates indisponibles : ce logement est déjà réservé sur cette période.", "error")
            return redirect(request.referrer or url_for("home"))

       
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
        try:
            cur.close()
        except:
            pass
        conn.close()


@app.route("/tenant", methods=["GET"])
def tenant_dashboard():
    if not role_required("Locataire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
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
    
        cur.execute("SELECT id_location FROM LOCATION WHERE id_reservation = :1", [id_res])
        row = cur.fetchone()
        if not row:
            flash("Location introuvable (réservation pas confirmée).", "error")
            return redirect(url_for("tenant_dashboard"))

        id_loc = row[0]

    
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



@app.route("/owner", methods=["GET"])
def owner_dashboard():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
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


@app.route("/owner/bien/new", methods=["GET", "POST"])
@app.route("/owner/bien/new/", methods=["GET", "POST"])
def owner_new_bien():
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("owner_new_bien.html")

  
    titre = request.form.get("titre", "").strip()
    ville = request.form.get("ville", "").strip()
    adresse = request.form.get("adresse", "").strip() or None
    type_bien = request.form.get("type_bien", "Appartement").strip()
    description = request.form.get("description", "").strip() or None
    photo_url = request.form.get("photo_url", "").strip() or None

 
    try:
        prix = float(request.form.get("prix"))
        capacite = int(request.form.get("capacite"))
        surface_raw = request.form.get("surface", "").strip()
        surface = float(surface_raw) if surface_raw else None
    except Exception:
        flash("Champs numériques invalides (prix/capacité/surface).", "error")
        return redirect(request.referrer or url_for("owner_dashboard"))

    conn, cur = get_db()
    try:
        id_out = cur.var(oracledb.NUMBER)

        cur.execute("""
            INSERT INTO BIEN (titre, description, ville, adresse, surface, prix, type_bien, capacite, id_proprietaire)
            VALUES (:titre, :description, :ville, :adresse, :surface, :prix, :type_bien, :capacite, :id_prop)
            RETURNING id_bien INTO :id_out
        """, {
            "titre": titre,
            "description": description,
            "ville": ville,
            "adresse": adresse,
            "surface": surface,
            "prix": prix,
            "type_bien": type_bien,
            "capacite": capacite,
            "id_prop": session["user_id"],
            "id_out": id_out
        })

       
        new_id_val = id_out.getvalue()
        if isinstance(new_id_val, list):
            new_id_val = new_id_val[0]
        new_id = int(new_id_val)

       
        if photo_url:
            cur.execute("""
                INSERT INTO PHOTO_BIEN (url_photo, est_principale, id_bien)
                VALUES (:url, 1, :id_bien)
            """, {"url": photo_url, "id_bien": new_id})

        conn.commit()
        flash("Bien publié avec succès ", "success")
        return redirect(url_for("owner_dashboard"))

    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur publication : {err.message}", "error")
        return redirect(request.referrer or url_for("owner_dashboard"))

    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()




@app.route("/owner/bien/<int:id_bien>/edit", methods=["GET", "POST"])
def owner_edit_bien(id_bien):
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
      
        cur.execute("""
            SELECT id_bien, titre, description, adresse, ville, surface, prix, type_bien, capacite
            FROM BIEN
            WHERE id_bien = :id_bien AND id_proprietaire = :id_prop
        """, {"id_bien": id_bien, "id_prop": session["user_id"]})
        row = cur.fetchone()
        if not row:
            flash("Bien introuvable ou accès refusé.", "error")
            return redirect(url_for("owner_dashboard"))

        cols = [c[0].lower() for c in cur.description]
        bien = dict(zip(cols, row))

       
        cur.execute("""
            SELECT url_photo
            FROM PHOTO_BIEN
            WHERE id_bien = :id_bien AND est_principale = 1
            FETCH FIRST 1 ROWS ONLY
        """, {"id_bien": id_bien})
        rph = cur.fetchone()
        photo_url = rph[0] if rph else ""

        if request.method == "GET":
            return render_template("owner_bien_edit.html", bien=bien, photo_url=photo_url)

       
        titre = request.form.get("titre", "").strip()
        ville = request.form.get("ville", "").strip()
        adresse = request.form.get("adresse", "").strip() or None
        type_bien = request.form.get("type_bien", "Appartement").strip()
        description = request.form.get("description", "").strip() or None
        new_photo_url = request.form.get("photo_url", "").strip() or None

        try:
            prix = float(request.form.get("prix"))
            capacite = int(request.form.get("capacite"))
            surface_raw = request.form.get("surface", "").strip()
            surface = float(surface_raw) if surface_raw else None
        except Exception:
            flash("Champs numériques invalides (prix/capacité/surface).", "error")
            return redirect(url_for("owner_edit_bien", id_bien=id_bien))

   
        cur.execute("""
            UPDATE BIEN
            SET titre = :titre,
                description = :description,
                adresse = :adresse,
                ville = :ville,
                surface = :surface,
                prix = :prix,
                type_bien = :type_bien,
                capacite = :capacite
            WHERE id_bien = :id_bien AND id_proprietaire = :id_prop
        """, {
            "titre": titre,
            "description": description,
            "adresse": adresse,
            "ville": ville,
            "surface": surface,
            "prix": prix,
            "type_bien": type_bien,
            "capacite": capacite,
            "id_bien": id_bien,
            "id_prop": session["user_id"],
        })

       
        if new_photo_url:
           
            cur.execute("""
                UPDATE PHOTO_BIEN
                SET est_principale = 0
                WHERE id_bien = :id_bien
            """, {"id_bien": id_bien})

          
            cur.execute("""
                SELECT id_photo FROM PHOTO_BIEN
                WHERE id_bien = :id_bien AND url_photo = :url
                FETCH FIRST 1 ROWS ONLY
            """, {"id_bien": id_bien, "url": new_photo_url})
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE PHOTO_BIEN
                    SET est_principale = 1
                    WHERE id_photo = :id_photo
                """, {"id_photo": existing[0]})
            else:
                cur.execute("""
                    INSERT INTO PHOTO_BIEN(url_photo, est_principale, id_bien)
                    VALUES(:url, 1, :id_bien)
                """, {"url": new_photo_url, "id_bien": id_bien})

        conn.commit()
        flash("Bien modifié avec succès", "success")
        return redirect(url_for("owner_dashboard"))

    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur modification : {err.message}", "error")
        return redirect(url_for("owner_dashboard"))
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()


@app.route("/owner/bien/<int:id_bien>/delete", methods=["POST"])
def owner_delete_bien(id_bien):
    if not role_required("Proprietaire"):
        return redirect(url_for("login"))

    conn, cur = get_db()
    try:
       
        cur.execute("""
            SELECT COUNT(*) FROM BIEN
            WHERE id_bien = :id_bien AND id_proprietaire = :id_prop
        """, {"id_bien": id_bien, "id_prop": session["user_id"]})
        if cur.fetchone()[0] == 0:
            flash("Accès refusé ou bien introuvable.", "error")
            return redirect(url_for("owner_dashboard"))

       
        cur.execute("""
            SELECT COUNT(*) FROM RESERVATION
            WHERE id_bien = :id_bien
        """, {"id_bien": id_bien})
        if cur.fetchone()[0] > 0:
            flash("Suppression impossible : ce bien a déjà des réservations.", "error")
            return redirect(url_for("owner_dashboard"))

      
        cur.execute("DELETE FROM PHOTO_BIEN WHERE id_bien = :id_bien", {"id_bien": id_bien})
        cur.execute("""
            DELETE FROM BIEN
            WHERE id_bien = :id_bien AND id_proprietaire = :id_prop
        """, {"id_bien": id_bien, "id_prop": session["user_id"]})

        conn.commit()
        flash("Bien supprimé ", "success")
        return redirect(url_for("owner_dashboard"))

    except oracledb.DatabaseError as e:
        conn.rollback()
        err, = e.args
        flash(f"Erreur suppression : {err.message}", "error")
        return redirect(url_for("owner_dashboard"))
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth_login.html")

    username = (request.form.get("login") or "").strip()
    password = (request.form.get("password") or "").strip()

    conn, cur = get_db()
    try:
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
        cur.callproc("sInscrire", [login_db, nom, prenom, email, telephone, password, role])

       
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


