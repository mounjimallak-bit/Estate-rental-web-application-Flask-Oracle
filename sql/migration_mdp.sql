
CREATE TABLE UTILISATEUR_MDP_SAUV AS
SELECT id_utilisateur, login_db, mot_de_passe, SYSDATE AS sauvegarde_le FROM UTILISATEUR;

SELECT COUNT(*) AS comptes_md5 FROM UTILISATEUR WHERE REGEXP_LIKE(mot_de_passe, '^[0-9A-Fa-f]{32}$');

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

DROP FUNCTION seConnecter;

SELECT COUNT(*) AS comptes_md5_restants FROM UTILISATEUR WHERE REGEXP_LIKE(mot_de_passe, '^[0-9A-Fa-f]{32}$');

