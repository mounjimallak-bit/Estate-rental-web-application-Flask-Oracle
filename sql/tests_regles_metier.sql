-- Tests des règles métier appliquées par la base.
-- À exécuter connecté en AIRBNB_V2, sur une base de TEST fraîchement installée selon le
-- README (les trois scripts, avec leurs données de démonstration). Le script crée,
-- modifie et valide des données : ne jamais l'exécuter sur des données réelles.
-- Chaque règle affiche PASS ou FAIL, puis le total.
SET SERVEROUTPUT ON SIZE UNLIMITED
SET FEEDBACK OFF
DECLARE
    v_loc NUMBER;  v_r NUMBER;  v_l NUMBER;  v_p NUMBER;  v_n NUMBER;
    g_ok  NUMBER := 0;
    g_ko  NUMBER := 0;

    PROCEDURE verifier(p_nom VARCHAR2, p_condition BOOLEAN) IS
    BEGIN
        IF p_condition THEN
            g_ok := g_ok + 1; DBMS_OUTPUT.PUT_LINE('PASS  ' || p_nom);
        ELSE
            g_ko := g_ko + 1; DBMS_OUTPUT.PUT_LINE('FAIL  ' || p_nom);
        END IF;
    END;

    -- Exécute une instruction ; renvoie 0 si elle réussit, sinon le code d'erreur Oracle.
    FUNCTION code_erreur(p_sql VARCHAR2) RETURN NUMBER IS
    BEGIN
        EXECUTE IMMEDIATE p_sql;
        COMMIT;
        RETURN 0;
    EXCEPTION WHEN OTHERS THEN
        ROLLBACK;
        RETURN SQLCODE;
    END;

    FUNCTION note(p_bien NUMBER) RETURN NUMBER IS v NUMBER;
    BEGIN SELECT note_moyenne INTO v FROM BIEN WHERE id_bien = p_bien; RETURN v; END;

    FUNCTION statut(p_res NUMBER) RETURN VARCHAR2 IS v VARCHAR2(20);
    BEGIN SELECT statut INTO v FROM RESERVATION WHERE id_reservation = p_res; RETURN v; END;

    FUNCTION statut_paiement(p_id NUMBER) RETURN VARCHAR2 IS v VARCHAR2(20);
    BEGIN SELECT statut_paiement INTO v FROM PAIEMENT WHERE id_paiement = p_id; RETURN v; END;

    FUNCTION reserver(p_bien NUMBER, p_debut DATE, p_nuits NUMBER) RETURN NUMBER IS v NUMBER;
    BEGIN
        creerReservation(v_loc, p_bien, p_debut, p_debut + p_nuits);
        SELECT MAX(id_reservation) INTO v FROM RESERVATION;
        RETURN v;
    END;

    FUNCTION location_de(p_res NUMBER) RETURN NUMBER IS v NUMBER;
    BEGIN SELECT id_location INTO v FROM LOCATION WHERE id_reservation = p_res; RETURN v; END;
BEGIN
    SELECT id_utilisateur INTO v_loc FROM UTILISATEUR WHERE login_db = 'loc1';

    -- 1. Confirmation (confirmerReservation)
    v_r := reserver(1, DATE '2030-01-10', 3);
    confirmerReservation(v_r);
    SELECT COUNT(*) INTO v_n FROM LOCATION WHERE id_reservation = v_r;
    verifier('confirmation : une location créée', v_n = 1);
    verifier('confirmation : double confirmation refusée (-20020)',
             code_erreur('BEGIN confirmerReservation(' || v_r || '); END;') = -20020);
    verifier('confirmation : réservation inexistante (-20022)',
             code_erreur('BEGIN confirmerReservation(999999); END;') = -20022);

    -- 2. Chevauchement (trg_resa_sans_chevauchement), y compris par INSERT direct
    verifier('chevauchement : INSERT direct refusé (-20001)',
             code_erreur('INSERT INTO RESERVATION(id_locataire, id_bien, date_debut, date_fin, statut) '
                      || 'VALUES (' || v_loc || ', 1, DATE ''2030-01-11'', DATE ''2030-01-12'', ''EN_ATTENTE'')') = -20001);
    verifier('chevauchement : dates accolées acceptées',
             code_erreur('INSERT INTO RESERVATION(id_locataire, id_bien, date_debut, date_fin, statut) '
                      || 'VALUES (' || v_loc || ', 1, DATE ''2030-01-13'', DATE ''2030-01-15'', ''EN_ATTENTE'')') = 0);

    -- 3. Note moyenne (trg_maj_note_bien)
    v_l := location_de(v_r);
    INSERT INTO AVIS_BIEN(note, commentaire, id_location) VALUES (4, 'test', v_l);
    COMMIT;
    verifier('note : avis inséré compté (4)', note(1) = 4);
    UPDATE AVIS_BIEN SET note = 2 WHERE id_location = v_l;
    COMMIT;
    verifier('note : avis modifié pris en compte (2)', note(1) = 2);
    DELETE FROM AVIS_BIEN WHERE id_location = v_l;
    COMMIT;
    verifier('note : dernier avis supprimé, retour à 0', note(1) = 0);

    -- 4. Annulation (annulerReservation)
    v_r := reserver(2, DATE '2030-02-01', 2);
    annulerReservation(v_r);
    verifier('annulation : demande en attente annulée', statut(v_r) = 'ANNULEE');
    v_r := reserver(2, DATE '2030-03-01', 2);
    confirmerReservation(v_r);
    annulerReservation(v_r);
    SELECT COUNT(*) INTO v_n FROM LOCATION WHERE id_reservation = v_r;
    verifier('annulation : réservation confirmée sans paiement, location supprimée',
             v_n = 0 AND statut(v_r) = 'ANNULEE');

    -- 5. Paiement et remboursement
    v_r := reserver(2, DATE '2030-04-01', 2);
    confirmerReservation(v_r);
    v_l := location_de(v_r);
    genererPaiement(v_l, 'CB');
    SELECT MAX(id_paiement) INTO v_p FROM PAIEMENT WHERE id_location = v_l;
    validerPaiement(v_p);
    verifier('paiement : paiement validé (REUSSI)', statut_paiement(v_p) = 'REUSSI');
    verifier('paiement : second paiement refusé (-20026)',
             code_erreur('BEGIN genererPaiement(' || v_l || ', ''CB''); END;') = -20026);
    verifier('paiement : modification d''un paiement réussi refusée (-20011)',
             code_erreur('UPDATE PAIEMENT SET montant = 1 WHERE id_paiement = ' || v_p) = -20011);
    verifier('annulation : réservation payée non annulable (-20023)',
             code_erreur('BEGIN annulerReservation(' || v_r || '); END;') = -20023);
    emettreRemboursement(v_p);
    SELECT COUNT(*) INTO v_n FROM PAIEMENT WHERE id_location = v_l AND montant < 0;
    verifier('remboursement : ligne négative créée, paiement marqué REMBOURSE',
             v_n = 1 AND statut_paiement(v_p) = 'REMBOURSE');
    verifier('remboursement : second remboursement refusé (-20025)',
             code_erreur('BEGIN emettreRemboursement(' || v_p || '); END;') = -20025);

    DBMS_OUTPUT.PUT_LINE('----');
    DBMS_OUTPUT.PUT_LINE(g_ok || ' PASS, ' || g_ko || ' FAIL');
END;
/
