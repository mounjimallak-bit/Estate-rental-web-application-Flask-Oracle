# Real Estate Rental Platform (Flask + Oracle PL/SQL)

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
- Reviews allowed only after completed stays

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

requirements.txt


---

## Installation

### 1 Install Oracle XE

Create Oracle user:


DB_USER=your_username
DB_PASSWORD=your_password
DB_DSN=localhost:1521/XEPDB1


---

### 2 Run SQL Scripts

Run in Oracle SQL Developer:

sql/script_sql.sql

sql/code_sql_pl.sql


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

- Password hashing managed in Oracle PL/SQL
- Role-based access control
- Session authentication
- Owner-only property management
- Tenant-only reservations

---



## Author

Malak Mounji

ENSA Agadir

Data & AI Engineering Student
