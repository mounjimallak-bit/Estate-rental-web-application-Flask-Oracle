-- =====================================================================================
-- Password migration: from unsalted MD5 to Argon2id hashes computed in Flask
--
-- Run this by hand, one step at a time, and only after taking a backup.
-- Steps 1 to 3 don't change any existing password. Steps 5 and 6 are commented out on
-- purpose: run them only once the migration period is over.
-- =====================================================================================

-- Step 1. Keep a copy of the current hashes, just in case something goes wrong.
-- Don't forget to delete this table at step 6: it still holds the old MD5 hashes.
CREATE TABLE UTILISATEUR_MDP_SAUV AS
SELECT id_utilisateur, login_db, mot_de_passe, SYSDATE AS sauvegarde_le FROM UTILISATEUR;

-- Step 2. How many accounts still use an old MD5 hash?
-- Those hashes are easy to spot: exactly 32 hexadecimal characters.
SELECT COUNT(*) AS comptes_md5 FROM UTILISATEUR WHERE REGEXP_LIKE(mot_de_passe, '^[0-9A-Fa-f]{32}$');

-- Step 3. New procedures. They replace sInscrire and seConnecter from sql/code_sql_pl.sql.

-- sInscrire now receives a hash that Flask has already computed, never a plain password.
-- The check below refuses anything that doesn't look like an Argon2id hash, so a plain
-- password can't end up in the table by mistake.
-- There's no COMMIT here on purpose: Flask commits the user and their role (tenant or
-- owner) together, so we never end up with a user who has no role.
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

-- majMotDePasse swaps an account's hash for a new one. Flask calls it right after an old
-- MD5 account logs in successfully, which is how existing users get upgraded quietly.
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

-- seConnecter used to compare MD5 hashes inside the database. Password checks now happen
-- in Flask, so this function has to go: leaving it around would offer a way to log in
-- that skips the new check entirely.
DROP FUNCTION seConnecter;

-- Step 4. Run this every now and then during the migration. The number should keep
-- going down as people log in again.
SELECT COUNT(*) AS comptes_md5_restants FROM UTILISATEUR WHERE REGEXP_LIKE(mot_de_passe, '^[0-9A-Fa-f]{32}$');

-- Step 5. END OF THE MIGRATION (on the date you picked in advance).
-- Any account still on MD5 gets disabled: its owner will need a new password set by the
-- administrator. Once this is done, remove the MD5 branch from securite_mdp.py too, so an
-- MD5 hash can never be accepted again.
-- UPDATE UTILISATEUR SET mot_de_passe = NULL WHERE REGEXP_LIKE(mot_de_passe, '^[0-9A-Fa-f]{32}$');
-- COMMIT;

-- Step 6. Delete the backup from step 1: it still contains the old MD5 hashes, and
-- keeping it would defeat the whole point of the migration.
-- DROP TABLE UTILISATEUR_MDP_SAUV PURGE;