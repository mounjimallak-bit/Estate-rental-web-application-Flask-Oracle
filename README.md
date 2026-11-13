# Real Estate Rental Platform (Flask + Oracle PL/SQL)

*Coursework project, ENSA Agadir, 2024. Uploaded to GitHub in 2026.*

A full-stack real estate rental platform developed with **Flask** and **Oracle PL/SQL**.

The application allows tenants to search and reserve properties while property owners manage listings and reservations.

This project demonstrates backend development, database design and business logic implementation using Oracle PL/SQL.

---

## Live Demo

Video demonstration:

https://youtu.be/xxOOS9JRwuo

The demo shows:

- User registration and login
- Tenant reservations
- Owner dashboard
- Property management
- Availability checking

---

## Features

### Tenant Features

- Browse available properties
- View property details
- Check availability dates
- Make reservation requests
- Pay confirmed reservations
- Leave reviews
- Manage reservations

---

### Owner Features

- Owner dashboard
- Add new properties
- Edit properties
- Delete properties
- Manage reservation requests
- Accept or reject reservations

---

### Reservation System

Business rules implemented:

- No overlapping reservations allowed
- Only tenants can reserve
- Only owners can manage properties
- Reservations must be confirmed before payment
- One review per confirmed rental

---

## Technologies Used

Backend:

- Python
- Flask

Database:

- Oracle SQL
- PL/SQL
- Stored Procedures
- Functions
- Triggers

Frontend:

- HTML
- CSS
- TailwindCSS

---

## Database Design

The database includes:

- Users (Locataire / Proprietaire)
- Properties 
- Reservations
- Locations
- Payments
- Reviews
- Property Photos

Oracle PL/SQL is used for:

- Authentication
- Reservation creation
- Payment processing
- Business rules enforcement
- Automatic updates (triggers)

---

## Project Structure

app.py

templates/

index.html

property_detail.html

auth_login.html

auth_register.html

owner_dashboard.html

tenant_dashboard.html

owner_new_bien.html

owner_bien_edit.html

sql/

script_sql.sql

code_sql_pl.sql

roles_grants.sql

migration_mdp.sql

tests_regles_metier.sql

requirements.txt


---

## Installation

### 1 Install Oracle XE and create the schema user

The security triggers exempt the schema owner by its name, `AIRBNB_V2`, so the schema user
must have this name. As an administrator (for example `SYSTEM`), in the pluggable database:

```sql
CREATE USER AIRBNB_V2 IDENTIFIED BY "choose_a_password" QUOTA UNLIMITED ON USERS;
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW,
      CREATE PROCEDURE, CREATE TRIGGER, CREATE ROLE TO AIRBNB_V2;
```

Then create a file named `.env` at the root of the project
(it is git-ignored and never published):

```
DB_USER=AIRBNB_V2
DB_PASSWORD=your_password
DB_DSN=localhost:1521/XEPDB1
FLASK_SECRET_KEY=any_long_random_string
```

If `FLASK_SECRET_KEY` is missing, a random key is generated at start-up (sessions are
then lost on restart). Set `FLASK_DEBUG=1` only for local development.

### 2 Run the SQL scripts, in this order

Connected as `AIRBNB_V2` (SQL Developer or SQL*Plus):

1. `sql/script_sql.sql`: tables, constraints and indexes
2. `sql/code_sql_pl.sql`: views, functions, procedures, triggers and demo data
3. `sql/roles_grants.sql`: roles and privileges, last because they refer to the views and procedures

A clean installation reports no Oracle error. `sql/migration_mdp.sql` is only needed for a
database created before the move to Argon2id password hashes.


---

### 3 Install Dependencies


pip install -r requirements.txt


---

### 4 Run Application


python app.py


Open:


http://localhost:5000


---

## Security

- Passwords hashed with Argon2id in the Flask layer (`securite_mdp.py`, argon2-cffi: per-password random salt, parameters stored in the hash, constant-time verification); Oracle only stores the hash and `sInscrire` rejects anything that is not an Argon2id hash. Legacy MD5 hashes are upgraded at the next successful login (`sql/migration_mdp.sql` for existing databases). Tests: `python -m pytest -q tests`.
- Demo accounts created by `sql/code_sql_pl.sql`: `prop1` and `loc1`, password `demo1234`.
- Role-based access control
- Session authentication
- Owner-only property management
- Tenant-only reservations
- Every reservation action (accept, reject, pay, review) checks that the reservation belongs to the logged-in user

---

## Tests

- Flask logic, with a simulated database: `python -m pytest -q tests`
- Business rules enforced by Oracle: on a fresh **test** installation, connected as `AIRBNB_V2`,
  run `sql/tests_regles_metier.sql`. It prints PASS or FAIL for each rule (confirmation,
  overlapping bookings, ratings, cancellation, payment and refund). It creates and commits
  data: never run it on real data.

---

## Business Rules 
- Role-based access: Tenant vs Owner
- Reservation workflow with statuses (request → accept/reject → payment)
- No overlapping active reservations (pending or confirmed) for the same property, enforced by a trigger whatever the write path
- A confirmed reservation can be cancelled only before any payment or review; its rental is then removed
- A rental is paid once; a successful payment can only be refunded, once
- Owners can manage only their own listings
- Tenants can review a property once per confirmed rental

## Author

Malak Mounji

ENSA Agadir

Data & AI Engineering Student
