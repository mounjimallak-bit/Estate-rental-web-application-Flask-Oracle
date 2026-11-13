--  VUES

-- VUE : annonces publiques 
CREATE OR REPLACE VIEW VUE_ANNONCES_PUBLIQUES AS
SELECT a.id_annonce, a.date_publication, a.statut, a.id_bien,
       b.titre, b.ville, b.prix, b.note_moyenne, b.capacite,
       (SELECT url_photo FROM PHOTO_BIEN WHERE id_bien = b.id_bien AND est_principale = 1 AND ROWNUM = 1) AS photo_principale
FROM ANNONCE a
JOIN BIEN b ON a.id_bien = b.id_bien
WHERE a.statut = 'disponible';

-- VUE : biens publics 
CREATE OR REPLACE VIEW VUE_BIENS_PUBLICS AS
SELECT b.id_bien, b.titre, SUBSTR(b.description,1,300) description, 
       b.ville, b.adresse, b.surface, b.prix, b.type_bien, b.capacite, b.note_moyenne,
       (SELECT url_photo FROM PHOTO_BIEN WHERE id_bien = b.id_bien AND est_principale = 1 AND ROWNUM = 1) AS photo_principale
FROM BIEN b;

-- VUE : utilisateurs publics
CREATE OR REPLACE VIEW VUE_UTILISATEURS_PUBLICS AS
SELECT id_utilisateur, nom, prenom, email
FROM UTILISATEUR;

-- VUE : mon profil
CREATE OR REPLACE VIEW VUE_MON_PROFIL AS
SELECT id_utilisateur, login_db, nom, prenom, email, telephone, role_app, date_inscription
FROM UTILISATEUR
WHERE UPPER(login_db) = USER; 

-- VUE : mes annonces
CREATE OR REPLACE VIEW VUE_MES_ANNONCES AS
SELECT a.*
FROM ANNONCE a
JOIN BIEN b ON a.id_bien = b.id_bien
JOIN PROPRIETAIRE p ON b.id_proprietaire = p.id_utilisateur
JOIN UTILISATEUR u ON p.id_utilisateur = u.id_utilisateur
WHERE UPPER(u.login_db) = USER;

-- VUE : reservations reçues
CREATE OR REPLACE VIEW VUE_RESERVATIONS_POUR_MOI AS
SELECT r.id_reservation, r.id_locataire, u.nom || ' ' || u.prenom AS client, r.id_bien, b.titre AS nom_bien,
r.date_debut, r.date_fin, r.statut, r.montant_reservation
FROM RESERVATION r
JOIN BIEN b ON r.id_bien = b.id_bien
JOIN PROPRIETAIRE p ON b.id_proprietaire = p.id_utilisateur
JOIN UTILISATEUR u ON r.id_locataire = u.id_utilisateur
WHERE p.id_utilisateur = (SELECT id_utilisateur FROM UTILISATEUR WHERE UPPER(login_db) = USER);

-- VUE : mes reservations
CREATE OR REPLACE VIEW VUE_MES_RESERVATIONS AS
SELECT r.*, b.titre AS nom_bien,
       (SELECT url_photo FROM PHOTO_BIEN WHERE id_bien = b.id_bien AND est_principale = 1 AND ROWNUM = 1) AS photo
FROM RESERVATION r
JOIN BIEN b ON r.id_bien = b.id_bien
WHERE r.id_locataire = (SELECT id_utilisateur FROM UTILISATEUR WHERE UPPER(login_db) = USER);


-- VUE : mes paiements
CREATE OR REPLACE VIEW VUE_MES_PAIEMENTS AS
SELECT p.*
FROM PAIEMENT p
JOIN LOCATION l ON p.id_location = l.id_location
JOIN RESERVATION r ON l.id_reservation = r.id_reservation
WHERE r.id_locataire = (SELECT id_utilisateur FROM UTILISATEUR WHERE UPPER(login_db) = USER);


-- VUE : revenue pour proprietaire
CREATE OR REPLACE VIEW VUE_MES_REVENUS AS
SELECT p.id_paiement, p.montant, p.date_paiement, p.statut_paiement, p.methode, 
       b.titre AS bien, l.date_debut, l.date_fin
FROM PAIEMENT p
JOIN LOCATION l ON p.id_location = l.id_location
JOIN RESERVATION r ON l.id_reservation = r.id_reservation
JOIN BIEN b ON r.id_bien = b.id_bien
WHERE b.id_proprietaire = (SELECT id_utilisateur FROM UTILISATEUR WHERE UPPER(login_db) = USER);


-- VUE : Mes Biens (Inventaire du propriétaire)
CREATE OR REPLACE VIEW VUE_MES_BIENS AS
SELECT id_bien, titre, description, ville, surface, prix, capacite, note_moyenne
FROM BIEN
WHERE id_proprietaire = (SELECT id_utilisateur FROM UTILISATEUR WHERE UPPER(login_db) = USER);



--  PROCÉDURES ET FONCTIONS


-- sInscrire : reçoit un hash Argon2id calculé par l'application (securite_mdp.py), jamais un mot de
-- passe en clair. Pas de COMMIT : l'application valide l'utilisateur et son rôle ensemble.
CREATE OR REPLACE PROCEDURE sInscrire(
    p_login     VARCHAR2,
    p_nom       VARCHAR2,
    p_prenom    VARCHAR2,
    p_email     VARCHAR2,
    p_telephone VARCHAR2,
    p_mdp_hache VARCHAR2,
    p_role_app  VARCHAR2
) IS
    v_id NUMBER;
BEGIN
    IF p_mdp_hache IS NULL OR SUBSTR(p_mdp_hache, 1, 10) <> '$argon2id$' THEN
        RAISE_APPLICATION_ERROR(-20001, 'sInscrire attend un hash Argon2id calculé par l''application.');
    END IF;
    INSERT INTO UTILISATEUR(login_db, nom, prenom, email, telephone, mot_de_passe, role_app)
    VALUES (p_login, p_nom, p_prenom, p_email, p_telephone, p_mdp_hache, p_role_app)
    RETURNING id_utilisateur INTO v_id;
END;
/

-- majMotDePasse : remplace le hash d'un compte (rehachage à la connexion des anciens comptes MD5).
CREATE OR REPLACE PROCEDURE majMotDePasse(p_id NUMBER, p_mdp_hache VARCHAR2) IS
BEGIN
    IF p_mdp_hache IS NULL OR SUBSTR(p_mdp_hache, 1, 10) <> '$argon2id$' THEN
        RAISE_APPLICATION_ERROR(-20002, 'majMotDePasse attend un hash Argon2id.');
    END IF;
    UPDATE UTILISATEUR SET mot_de_passe = p_mdp_hache WHERE id_utilisateur = p_id;
    IF SQL%ROWCOUNT <> 1 THEN
        RAISE_APPLICATION_ERROR(-20003, 'Utilisateur introuvable.');
    END IF;
END;
/

-- creerAnnonce 
CREATE OR REPLACE PROCEDURE creerAnnonce(p_id_bien NUMBER) IS
    v_id NUMBER;
BEGIN
    INSERT INTO ANNONCE(id_bien, date_publication, statut) 
    VALUES (p_id_bien, SYSDATE, 'disponible') 
    RETURNING id_annonce INTO v_id;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Annonce crée id=' || v_id);
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- modifierAnnonce 
CREATE OR REPLACE PROCEDURE modifierAnnonce(p_id_annonce NUMBER, p_statut VARCHAR2) IS
BEGIN
    UPDATE ANNONCE SET statut = p_statut WHERE id_annonce = p_id_annonce;
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/

-- supprimerAnnonce
CREATE OR REPLACE PROCEDURE supprimerAnnonce(p_id_annonce NUMBER) IS
BEGIN
    DELETE FROM ANNONCE WHERE id_annonce = p_id_annonce;
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Annonce supprimée id=' || p_id_annonce);
EXCEPTION
    WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/

-- verifierDisponibilite 
CREATE OR REPLACE FUNCTION verifierDisponibilite(
    p_id_bien NUMBER, 
    p_debut DATE, 
    p_fin DATE
) RETURN NUMBER IS
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count 
    FROM RESERVATION
    WHERE id_bien = p_id_bien
      AND statut IN ('EN_ATTENTE','CONFIRMEE')
      AND NOT (p_fin <= date_debut OR p_debut >= date_fin);
    RETURN v_count;
EXCEPTION
    WHEN OTHERS THEN RETURN 1;
END;
/

-- creerReservation
CREATE OR REPLACE PROCEDURE creerReservation(
    p_id_locataire NUMBER,
    p_id_bien NUMBER,
    p_date_deb DATE,
    p_date_fin DATE
) IS
    v_conf NUMBER;
    v_id_res NUMBER;
BEGIN
    v_conf := verifierDisponibilite(p_id_bien, p_date_deb, p_date_fin);
    
    IF v_conf > 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Bien non disponible sur ces dates');
    END IF;

    INSERT INTO RESERVATION(id_locataire, id_bien, id_annonce, date_demande, date_debut, date_fin, statut)
    VALUES(p_id_locataire, p_id_bien, NULL, SYSDATE, p_date_deb, p_date_fin, 'EN_ATTENTE')
    RETURNING id_reservation INTO v_id_res;
    
    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Reservation crée id=' || v_id_res);
EXCEPTION
    WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/

-- calculerPrixTotal 
CREATE OR REPLACE FUNCTION calculerPrixTotal(p_id_reservation NUMBER) RETURN NUMBER IS
    v_prix NUMBER;
    v_deb DATE;
    v_fin DATE;
    v_total NUMBER;
BEGIN
    SELECT b.prix, r.date_debut, r.date_fin INTO v_prix, v_deb, v_fin
    FROM RESERVATION r 
    JOIN BIEN b ON r.id_bien = b.id_bien
    WHERE r.id_reservation = p_id_reservation;

    v_total := (v_fin - v_deb) * v_prix;
    RETURN v_total;
EXCEPTION
    WHEN NO_DATA_FOUND THEN RETURN 0;
    WHEN OTHERS THEN RETURN 0;
END;
/

-- confirmerReservation 
CREATE OR REPLACE PROCEDURE confirmerReservation(p_id_reservation NUMBER) IS
    v_debut  RESERVATION.date_debut%TYPE;
    v_fin    RESERVATION.date_fin%TYPE;
    v_statut RESERVATION.statut%TYPE;
    v_total  NUMBER;
    v_id_loc NUMBER;
BEGIN
    -- Lecture ET verrouillage de la réservation : deux confirmations simultanées
    -- de la même réservation sont exécutées l'une après l'autre.
    SELECT date_debut, date_fin, statut
      INTO v_debut, v_fin, v_statut
      FROM RESERVATION
     WHERE id_reservation = p_id_reservation
       FOR UPDATE;

    -- Seule une demande en attente peut être confirmée (pas de double confirmation).
    IF v_statut <> 'EN_ATTENTE' THEN
        RAISE_APPLICATION_ERROR(-20020,
            'Réservation non confirmable : statut actuel ' || v_statut);
    END IF;

    v_total := calculerPrixTotal(p_id_reservation);

    UPDATE RESERVATION
       SET statut = 'CONFIRMEE', montant_reservation = v_total
     WHERE id_reservation = p_id_reservation;

    -- INSERT ... VALUES : seule forme d'INSERT qui accepte RETURNING INTO.
    INSERT INTO LOCATION(id_reservation, date_debut, date_fin, montant)
    VALUES (p_id_reservation, v_debut, v_fin, v_total)
    RETURNING id_location INTO v_id_loc;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Reservation confirmée. Location créée id=' || v_id_loc);
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20022, 'Réservation introuvable : ' || p_id_reservation);
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- annulerReservation 
CREATE OR REPLACE PROCEDURE annulerReservation(p_id_reservation NUMBER) IS
    v_statut   RESERVATION.statut%TYPE;
    v_id_loc   LOCATION.id_location%TYPE;
    v_bloquant NUMBER;
BEGIN
    SELECT statut INTO v_statut
      FROM RESERVATION
     WHERE id_reservation = p_id_reservation
       FOR UPDATE;

    IF v_statut = 'CONFIRMEE' THEN
        -- Une réservation confirmée a une LOCATION. On ne l'annule que si rien n'en
        -- dépend (aucun paiement, même en attente, aucun avis), et la location est
        -- alors supprimée : une réservation annulée ne garde jamais de location.
        SELECT id_location INTO v_id_loc
          FROM LOCATION
         WHERE id_reservation = p_id_reservation;
        SELECT (SELECT COUNT(*) FROM PAIEMENT  WHERE id_location = v_id_loc)
             + (SELECT COUNT(*) FROM AVIS_BIEN WHERE id_location = v_id_loc)
          INTO v_bloquant
          FROM DUAL;
        IF v_bloquant > 0 THEN
            RAISE_APPLICATION_ERROR(-20023,
                'Réservation confirmée avec paiement ou avis : annulation impossible');
        END IF;
        DELETE FROM LOCATION WHERE id_location = v_id_loc;
    ELSIF v_statut <> 'EN_ATTENTE' THEN
        RAISE_APPLICATION_ERROR(-20020,
            'Réservation non annulable : statut actuel ' || v_statut);
    END IF;

    UPDATE RESERVATION SET statut = 'ANNULEE' WHERE id_reservation = p_id_reservation;
    COMMIT;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20022, 'Réservation introuvable : ' || p_id_reservation);
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- genererPaiement 
CREATE OR REPLACE PROCEDURE genererPaiement(p_id_location NUMBER, p_methode VARCHAR2) IS
    v_id NUMBER;
    v_montant NUMBER;
    v_deja NUMBER;
BEGIN
    -- Verrou sur la location : deux paiements simultanés de la même location
    -- sont traités l'un après l'autre.
    SELECT montant INTO v_montant FROM LOCATION WHERE id_location = p_id_location FOR UPDATE;
    
    IF v_montant IS NULL THEN
        RAISE_APPLICATION_ERROR(-20002, 'Montant absent pour cette location');
    END IF;

    SELECT COUNT(*) INTO v_deja FROM PAIEMENT
     WHERE id_location = p_id_location AND statut_paiement = 'REUSSI';
    IF v_deja > 0 THEN
        RAISE_APPLICATION_ERROR(-20026, 'Location déjà payée');
    END IF;

    INSERT INTO PAIEMENT(montant, date_paiement, id_location, statut_paiement, methode)
    VALUES(v_montant, SYSDATE, p_id_location, 'EN_ATTENTE', p_methode)
    RETURNING id_paiement INTO v_id;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Paiement créé id=' || v_id);
EXCEPTION
    WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/

-- validerPaiement 
CREATE OR REPLACE PROCEDURE validerPaiement(p_id_paiement NUMBER) IS
    v_id_loc PAIEMENT.id_location%TYPE;
    v_statut PAIEMENT.statut_paiement%TYPE;
    v_verrou NUMBER;
    v_deja   NUMBER;
BEGIN
    SELECT id_location, statut_paiement INTO v_id_loc, v_statut
      FROM PAIEMENT
     WHERE id_paiement = p_id_paiement
       FOR UPDATE;
    -- Même verrou que genererPaiement : une location ne peut pas être payée deux fois.
    SELECT id_location INTO v_verrou FROM LOCATION WHERE id_location = v_id_loc FOR UPDATE;

    IF v_statut <> 'EN_ATTENTE' THEN
        RAISE_APPLICATION_ERROR(-20027,
            'Paiement non validable : statut actuel ' || v_statut);
    END IF;
    SELECT COUNT(*) INTO v_deja FROM PAIEMENT
     WHERE id_location = v_id_loc AND statut_paiement = 'REUSSI';
    IF v_deja > 0 THEN
        RAISE_APPLICATION_ERROR(-20026, 'Location déjà payée');
    END IF;

    UPDATE PAIEMENT 
    SET statut_paiement = 'REUSSI', date_paiement = SYSDATE 
    WHERE id_paiement = p_id_paiement;
    COMMIT;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20022, 'Paiement introuvable : ' || p_id_paiement);
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- echouerPaiement 
CREATE OR REPLACE PROCEDURE echouerPaiement(p_id_paiement NUMBER) IS
BEGIN
    UPDATE PAIEMENT SET statut_paiement = 'ECHOUE' WHERE id_paiement = p_id_paiement;
    COMMIT;
EXCEPTION
    WHEN OTHERS THEN ROLLBACK; RAISE;
END;
/

-- emettreRemboursement
CREATE OR REPLACE PROCEDURE emettreRemboursement(p_id_paiement NUMBER) IS
    v_id_loc NUMBER;
    v_mont NUMBER;
    v_statut PAIEMENT.statut_paiement%TYPE;
    v_new NUMBER;
BEGIN
    SELECT id_location, montant, statut_paiement INTO v_id_loc, v_mont, v_statut
    FROM PAIEMENT 
    WHERE id_paiement = p_id_paiement
    FOR UPDATE;

    -- Seul un paiement réussi se rembourse, et une seule fois.
    IF v_statut <> 'REUSSI' THEN
        RAISE_APPLICATION_ERROR(-20025,
            'Seul un paiement réussi peut être remboursé (statut actuel ' || v_statut || ')');
    END IF;

    INSERT INTO PAIEMENT(montant, date_paiement, id_location, statut_paiement, methode)
    VALUES(-v_mont, SYSDATE, v_id_loc, 'REMBOURSE', 'REMBOURSEMENT') 
    RETURNING id_paiement INTO v_new;

    -- Transition REUSSI -> REMBOURSE : la seule que trg_no_update_paiement_if_reussi autorise.
    UPDATE PAIEMENT SET statut_paiement = 'REMBOURSE' WHERE id_paiement = p_id_paiement;

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Remboursement créé id=' || v_new);
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20022, 'Paiement introuvable : ' || p_id_paiement);
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
/

-- get_mes_reservations 
CREATE OR REPLACE FUNCTION get_mes_reservations(p_id_utilisateur NUMBER)
RETURN SYS_REFCURSOR IS
    v_cursor SYS_REFCURSOR;
BEGIN
    OPEN v_cursor FOR
        SELECT r.id_reservation, r.date_debut, r.date_fin, r.statut, r.montant_reservation,
               b.titre, b.ville, b.prix
        FROM RESERVATION r
        JOIN BIEN b ON r.id_bien = b.id_bien
        WHERE r.id_locataire = p_id_utilisateur
        ORDER BY r.date_demande DESC;
    RETURN v_cursor;
END;
/

-- get_mes_biens 
CREATE OR REPLACE FUNCTION get_mes_biens(p_id_proprietaire NUMBER)
RETURN SYS_REFCURSOR IS
    v_cursor SYS_REFCURSOR;
BEGIN
    OPEN v_cursor FOR SELECT * FROM BIEN WHERE id_proprietaire = p_id_proprietaire;
    RETURN v_cursor;
END;
/

-- get_mes_annonces 
CREATE OR REPLACE FUNCTION get_mes_annonces(p_id_proprietaire NUMBER)
RETURN SYS_REFCURSOR IS
    v_cursor SYS_REFCURSOR;
BEGIN
    OPEN v_cursor FOR
        SELECT a.* FROM ANNONCE a
        JOIN BIEN b ON a.id_bien = b.id_bien
        WHERE b.id_proprietaire = p_id_proprietaire;
    RETURN v_cursor;
END;
/


CREATE OR REPLACE FUNCTION rechercherBiens(
    p_ville VARCHAR2,
    p_prix_max NUMBER,
    p_nb_personnes NUMBER,
    p_date_debut DATE,
    p_date_fin DATE
) RETURN SYS_REFCURSOR IS
    v_cursor SYS_REFCURSOR;
BEGIN
    OPEN v_cursor FOR
        SELECT b.id_bien, b.titre, b.prix, b.ville, b.note_moyenne,
               (SELECT url_photo FROM PHOTO_BIEN WHERE id_bien = b.id_bien AND est_principale = 1 AND ROWNUM = 1) as photo_principale
        FROM BIEN b
        WHERE UPPER(b.ville) LIKE '%' || UPPER(p_ville) || '%'
        AND b.prix <= p_prix_max
        AND b.capacite >= p_nb_personnes
        -- Vérifier qu'il n'y a PAS de réservation confirmée qui chevauche
        AND NOT EXISTS (
            SELECT 1 FROM RESERVATION r
            WHERE r.id_bien = b.id_bien
            AND r.statut IN ('CONFIRMEE', 'EN_ATTENTE')
            AND (p_date_fin > r.date_debut AND p_date_debut < r.date_fin)
        );
        
    RETURN v_cursor;
END;
/


-- TRIGGERS



-- 1. Securite BIEN : Seul le propriétaire peut toucher à son bien
-- Indicateur interne : vrai uniquement pendant le recalcul automatique de la note
-- moyenne (procédure majNoteMoyenne). Aucun utilisateur ne reçoit EXECUTE sur ce
-- package : seul le code du schéma peut le lire ou le modifier.
CREATE OR REPLACE PACKAGE pkg_note_moyenne AS
    g_en_cours BOOLEAN := FALSE;
END pkg_note_moyenne;
/

CREATE OR REPLACE TRIGGER trg_secu_bien_owner
BEFORE UPDATE OR DELETE ON BIEN
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF; -- Bypass Admin
    IF pkg_note_moyenne.g_en_cours THEN RETURN; END IF; -- recalcul automatique de la note

    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    
    IF :OLD.id_proprietaire != v_user_id THEN
        RAISE_APPLICATION_ERROR(-20091, 'SÉCURITÉ : Ce bien ne vous appartient pas.');
    END IF;
EXCEPTION WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20090, 'Utilisateur non identifié.');
END;
/

-- 2. Sécurité ANNONCE : Verifie le propriétaire du bien lié
CREATE OR REPLACE TRIGGER trg_secu_annonce_owner
BEFORE INSERT OR UPDATE OR DELETE ON ANNONCE
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
    v_proprio_bien NUMBER;
    v_target_bien_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;

    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    IF DELETING THEN v_target_bien_id := :OLD.id_bien; ELSE v_target_bien_id := :NEW.id_bien; END IF;
    
    SELECT id_proprietaire INTO v_proprio_bien FROM BIEN WHERE id_bien = v_target_bien_id;

    IF v_proprio_bien != v_user_id THEN
        RAISE_APPLICATION_ERROR(-20092, 'SÉCURITÉ : Vous ne pouvez pas gérer les annonces des autres.');
    END IF;
END;
/

-- 3. Securite PHOTOS : Verifie le propriétaire du bien liee
CREATE OR REPLACE TRIGGER trg_secu_photo_owner
BEFORE INSERT OR UPDATE OR DELETE ON PHOTO_BIEN
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
    v_proprio_bien NUMBER;
    v_target_bien_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;

    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    IF DELETING THEN v_target_bien_id := :OLD.id_bien; ELSE v_target_bien_id := :NEW.id_bien; END IF;

    SELECT id_proprietaire INTO v_proprio_bien FROM BIEN WHERE id_bien = v_target_bien_id;

    IF v_proprio_bien != v_user_id THEN
        RAISE_APPLICATION_ERROR(-20093, 'SÉCURITÉ : Vous ne pouvez pas modifier les photos d''un autre bien.');
    END IF;
END;
/

-- 4. Securite EQUIPEMENTS : Verifie le propriétaire du bien lie
CREATE OR REPLACE TRIGGER trg_secu_equipement_owner
BEFORE INSERT OR DELETE ON BIEN_EQUIPEMENT
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
    v_proprio_bien NUMBER;
    v_target_bien_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;

    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    IF DELETING THEN v_target_bien_id := :OLD.id_bien; ELSE v_target_bien_id := :NEW.id_bien; END IF;

    SELECT id_proprietaire INTO v_proprio_bien FROM BIEN WHERE id_bien = v_target_bien_id;

    IF v_proprio_bien != v_user_id THEN
        RAISE_APPLICATION_ERROR(-20095, 'SÉCURITÉ : Vous ne pouvez pas modifier les équipements des autres.');
    END IF;
END;
/

-- 5. Securite RÉSERVATION : Anti-Usurpation Locataire
CREATE OR REPLACE TRIGGER trg_secu_resa_locataire
BEFORE INSERT ON RESERVATION
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;
    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    
    -- Force l'ID à être celui de l'utilisateur connecté
    IF :NEW.id_locataire != v_user_id THEN
         :NEW.id_locataire := v_user_id; -- Correction automatique silencieuse
    END IF;

    -- Une réservation écrite directement par un utilisateur est toujours une
    -- demande en attente : seul confirmerReservation peut la confirmer.
    :NEW.statut := 'EN_ATTENTE';
    :NEW.montant_reservation := NULL;
    :NEW.date_demande := SYSDATE;
END;
/

-- Sécurité AVIS_BIEN : un locataire ne peut noter que ses propres locations
-- (ROLE_LOCATAIRE a le droit INSERT direct sur AVIS_BIEN).
CREATE OR REPLACE TRIGGER trg_secu_avis_locataire
BEFORE INSERT ON AVIS_BIEN
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
    v_n       NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;
    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;

    SELECT COUNT(*) INTO v_n
      FROM LOCATION l
      JOIN RESERVATION r ON r.id_reservation = l.id_reservation
     WHERE l.id_location = :NEW.id_location
       AND r.id_locataire = v_user_id;
    IF v_n = 0 THEN
        RAISE_APPLICATION_ERROR(-20093, 'SÉCURITÉ : Cette location ne vous appartient pas.');
    END IF;
EXCEPTION WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20090, 'Utilisateur non identifié.');
END;
/

-- Sécurité PAIEMENT : un locataire ne peut créer qu'un paiement EN_ATTENTE, du montant
-- de sa propre location (ROLE_LOCATAIRE a le droit INSERT direct sur PAIEMENT).
CREATE OR REPLACE TRIGGER trg_secu_paiement_locataire
BEFORE INSERT ON PAIEMENT
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
    v_montant NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;
    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;

    BEGIN
        SELECT l.montant INTO v_montant
          FROM LOCATION l
          JOIN RESERVATION r ON r.id_reservation = l.id_reservation
         WHERE l.id_location = :NEW.id_location
           AND r.id_locataire = v_user_id;
    EXCEPTION WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20093, 'SÉCURITÉ : Cette location ne vous appartient pas.');
    END;

    :NEW.statut_paiement := 'EN_ATTENTE';
    :NEW.montant         := v_montant;
    :NEW.date_paiement   := SYSDATE;
EXCEPTION WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20090, 'Utilisateur non identifié.');
END;
/

-- 6. Sécurité MESSAGERIE : Anti-Usurpation Expéditeur
CREATE OR REPLACE TRIGGER trg_secu_message_identity
BEFORE INSERT ON MESSAGE
FOR EACH ROW
DECLARE
    v_user_id NUMBER;
BEGIN
    IF USER IN ('AIRBNB_V2', 'SYSTEM', 'SYS') THEN RETURN; END IF;
    SELECT id_utilisateur INTO v_user_id FROM UTILISATEUR WHERE UPPER(login_db) = USER;
    
    -- Force l'expéditeur à être l'utilisateur connecté
    :NEW.id_expediteur := v_user_id;
END;
/

-- 7. Intégrité : On ne supprime pas un bien réservé
CREATE OR REPLACE TRIGGER trg_no_delete_bien_with_active_res
BEFORE DELETE ON BIEN
FOR EACH ROW
DECLARE 
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM RESERVATION
    WHERE id_bien = :OLD.id_bien AND statut IN ('EN_ATTENTE','CONFIRMEE');
    
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20010, 'Impossible de supprimer : réservations actives en cours.');
    END IF;
END;
/

-- 8. Finance : On ne modifie pas un paiement réussi (Immuabilité)
CREATE OR REPLACE TRIGGER trg_no_update_paiement_if_reussi
BEFORE UPDATE ON PAIEMENT
FOR EACH ROW
BEGIN
    IF :OLD.statut_paiement = 'REUSSI' THEN
        -- Un paiement réussi est figé. Seule exception : le remboursement
        -- (emettreRemboursement), qui passe le statut à REMBOURSE sans rien changer d'autre.
        IF NOT (    :NEW.statut_paiement = 'REMBOURSE'
                AND :NEW.montant = :OLD.montant
                AND :NEW.id_location = :OLD.id_location
                AND NVL(:NEW.date_paiement, DATE '1900-01-01') = NVL(:OLD.date_paiement, DATE '1900-01-01')
                AND NVL(:NEW.methode, '#') = NVL(:OLD.methode, '#')) THEN
            RAISE_APPLICATION_ERROR(-20011, 'Fraude détectée : Paiement déjà validé, modification interdite.');
        END IF;
    END IF;
END;
/

-- 9. Cohérence : La fin du séjour doit être après le début
CREATE OR REPLACE TRIGGER trg_reservation_check
BEFORE UPDATE OF statut ON RESERVATION
FOR EACH ROW
BEGIN
    IF :NEW.statut = 'CONFIRMEE' AND :NEW.date_fin <= :NEW.date_debut THEN
        RAISE_APPLICATION_ERROR(-20015, 'Dates incohérentes : date_fin doit être > date_debut');
    END IF;
END;
/

-- 9 bis. Aucun chevauchement entre réservations actives (EN_ATTENTE ou CONFIRMEE)
-- d'un même bien, quelle que soit la façon dont la ligne est écrite : procédure,
-- application ou INSERT/UPDATE direct (ROLE_LOCATAIRE a le droit INSERT sur RESERVATION).
-- Le verrou sur la ligne du bien sérialise les écritures concurrentes : la seconde
-- transaction attend la validation de la première, puis voit sa réservation.
CREATE OR REPLACE TRIGGER trg_resa_sans_chevauchement
FOR INSERT OR UPDATE OF id_bien, date_debut, date_fin, statut ON RESERVATION
COMPOUND TRIGGER
    TYPE t_biens IS TABLE OF BOOLEAN INDEX BY PLS_INTEGER;
    g_biens t_biens;

    AFTER EACH ROW IS
    BEGIN
        IF :NEW.statut IN ('EN_ATTENTE', 'CONFIRMEE') THEN
            g_biens(:NEW.id_bien) := TRUE;
        END IF;
    END AFTER EACH ROW;

    AFTER STATEMENT IS
        v_id       PLS_INTEGER := g_biens.FIRST;
        v_verrou   NUMBER;
        v_conflits NUMBER;
    BEGIN
        WHILE v_id IS NOT NULL LOOP
            SELECT id_bien INTO v_verrou FROM BIEN WHERE id_bien = v_id FOR UPDATE;

            SELECT COUNT(*) INTO v_conflits
              FROM RESERVATION r1
              JOIN RESERVATION r2
                ON r2.id_bien = r1.id_bien
               AND r2.id_reservation > r1.id_reservation
             WHERE r1.id_bien = v_id
               AND r1.statut IN ('EN_ATTENTE', 'CONFIRMEE')
               AND r2.statut IN ('EN_ATTENTE', 'CONFIRMEE')
               AND r1.date_debut < r2.date_fin
               AND r2.date_debut < r1.date_fin;

            IF v_conflits > 0 THEN
                RAISE_APPLICATION_ERROR(-20001, 'Bien non disponible sur ces dates');
            END IF;
            v_id := g_biens.NEXT(v_id);
        END LOOP;
    END AFTER STATEMENT;
END trg_resa_sans_chevauchement;
/

-- 10. Calcul automatique de la note moyenne (Procédure + Trigger)
-- Recalcule la note moyenne d'un bien à partir de tous ses avis. Pas de transaction
-- autonome ni de COMMIT : la procédure s'exécute dans la transaction qui a modifié
-- AVIS_BIEN et voit donc l'avis qui vient d'être inséré, modifié ou supprimé.
CREATE OR REPLACE PROCEDURE majNoteMoyenne(p_id_bien NUMBER) IS
    v_id NUMBER;
BEGIN
    -- Verrou sur le bien : deux transactions qui notent le même bien sont
    -- sérialisées, et la seconde recalcule après la validation de la première.
    SELECT id_bien INTO v_id FROM BIEN WHERE id_bien = p_id_bien FOR UPDATE;

    pkg_note_moyenne.g_en_cours := TRUE;   -- voir trg_secu_bien_owner
    UPDATE BIEN
       SET note_moyenne = (
             SELECT NVL(ROUND(AVG(a.note), 1), 0)    -- 0 = aucun avis ("Nouveau")
               FROM AVIS_BIEN a
               JOIN LOCATION l    ON a.id_location = l.id_location
               JOIN RESERVATION r ON l.id_reservation = r.id_reservation
              WHERE r.id_bien = p_id_bien)
     WHERE id_bien = p_id_bien;
    pkg_note_moyenne.g_en_cours := FALSE;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        pkg_note_moyenne.g_en_cours := FALSE;   -- bien supprimé : rien à recalculer
    WHEN OTHERS THEN
        pkg_note_moyenne.g_en_cours := FALSE;
        RAISE;
END;
/

-- Trigger composé : collecte les biens concernés ligne par ligne, puis recalcule
-- leur note une seule fois, après l'instruction (AVIS_BIEN n'est alors plus en
-- cours de modification et peut être lu). Couvre INSERT, UPDATE et DELETE.
CREATE OR REPLACE TRIGGER trg_maj_note_bien
FOR INSERT OR UPDATE OR DELETE ON AVIS_BIEN
COMPOUND TRIGGER
    TYPE t_biens IS TABLE OF BOOLEAN INDEX BY PLS_INTEGER;
    g_biens t_biens;

    PROCEDURE retenir_bien(p_id_location NUMBER) IS
        v_id_bien NUMBER;
    BEGIN
        SELECT r.id_bien INTO v_id_bien
          FROM LOCATION l
          JOIN RESERVATION r ON l.id_reservation = r.id_reservation
         WHERE l.id_location = p_id_location;
        g_biens(v_id_bien) := TRUE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN NULL;
    END retenir_bien;

    AFTER EACH ROW IS
    BEGIN
        IF INSERTING OR UPDATING THEN retenir_bien(:NEW.id_location); END IF;
        IF DELETING  OR UPDATING THEN retenir_bien(:OLD.id_location); END IF;
    END AFTER EACH ROW;

    AFTER STATEMENT IS
        v_id PLS_INTEGER := g_biens.FIRST;
    BEGIN
        WHILE v_id IS NOT NULL LOOP
            majNoteMoyenne(v_id);
            v_id := g_biens.NEXT(v_id);
        END LOOP;
    END AFTER STATEMENT;
END trg_maj_note_bien;
/

-- TEST 

SET SERVEROUTPUT ON;
DECLARE
    v_id_prop NUMBER;
    v_id_loc  NUMBER;
    v_id_bien1 NUMBER;
    v_id_bien2 NUMBER;
    v_id_equip1 NUMBER;
    v_id_equip2 NUMBER;
BEGIN
   
    sInscrire('prop1', 'Dupont', 'Jean', 'jean@immo.com', '0611111111', '$argon2id$v=19$m=65536,t=3,p=4$QQ30Ro6n6DVq1A6Yzppplw$F+RwCFcQqsAHGvA5kvnHrftp2PK/zKVkkwqO8jPzDh4', 'Proprietaire');
    SELECT id_utilisateur INTO v_id_prop FROM UTILISATEUR WHERE login_db = 'prop1';
    INSERT INTO PROPRIETAIRE(id_utilisateur) VALUES (v_id_prop);

   
    sInscrire('loc1', 'Martin', 'Alice', 'alice@mail.com', '0622222222', '$argon2id$v=19$m=65536,t=3,p=4$FJTRmZ9h9yq5ayCg2USb1g$Xl4lBMaK1yd8ANl7iVM9t2gjz9sY6mcQzKdHGdiSeqk', 'Locataire');
    SELECT id_utilisateur INTO v_id_loc FROM UTILISATEUR WHERE login_db = 'loc1';
    INSERT INTO LOCATAIRE(id_utilisateur) VALUES (v_id_loc);

    
    INSERT INTO TYPE_EQUIPEMENT(nom_equipement, icone_url) VALUES ('Wifi', 'wifi.png') RETURNING id_equipement INTO v_id_equip1;
    INSERT INTO TYPE_EQUIPEMENT(nom_equipement, icone_url) VALUES ('Piscine', 'pool.png') RETURNING id_equipement INTO v_id_equip2;

   
    INSERT INTO BIEN(titre, description, adresse, ville, surface, prix, type_bien, capacite, id_proprietaire)
    VALUES ('Appart Vue Mer', 'Superbe vue sur la marina', 'Marina', 'Agadir', 80, 800, 'Appartement', 4, v_id_prop)
    RETURNING id_bien INTO v_id_bien1;
    creerAnnonce(v_id_bien1);
    
   
    INSERT INTO PHOTO_BIEN(url_photo, description_alt, est_principale, id_bien)
    VALUES ('https://cloud.com/agadir_salon.jpg', 'Salon vue mer', 1, v_id_bien1);
    
   
    INSERT INTO BIEN_EQUIPEMENT(id_bien, id_equipement) VALUES (v_id_bien1, v_id_equip1);

   
    INSERT INTO BIEN(titre, description, adresse, ville, surface, prix, type_bien, capacite, id_proprietaire)
    VALUES ('Villa Palmeraie', 'Grande piscine et jardin', 'Route de Fes', 'Marrakech', 400, 2500, 'Villa', 10, v_id_prop)
    RETURNING id_bien INTO v_id_bien2;
    creerAnnonce(v_id_bien2);
    
 
    INSERT INTO PHOTO_BIEN(url_photo, est_principale, id_bien) VALUES ('https://cloud.com/kech_pool.jpg', 1, v_id_bien2);
    
  
    INSERT INTO BIEN_EQUIPEMENT(id_bien, id_equipement) VALUES (v_id_bien2, v_id_equip1);
    INSERT INTO BIEN_EQUIPEMENT(id_bien, id_equipement) VALUES (v_id_bien2, v_id_equip2);

  
    INSERT INTO MESSAGE(contenu, id_expediteur, id_destinataire, id_bien)
    VALUES ('Bonjour, le Wifi est-il haut débit ?', v_id_loc, v_id_prop, v_id_bien1);

    COMMIT;
    DBMS_OUTPUT.PUT_LINE('Données de test étendues insérées avec succès !');
END;
/