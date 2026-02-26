#  Real Estate Rental Platform 

bien_immobilier-flask-oracle is a real estate rental web application developed using **Flask** and **Oracle PL/SQL**.

The platform allows tenants to search and reserve properties and allows owners to manage their properties and reservations.

This project demonstrates the integration of a web application with an Oracle relational database using SQL and PL/SQL.

## Technologies

- Python
- Flask
- Oracle SQL
- PL/SQL
- HTML
- CSS
- Tailwind

## Features

### Tenant Features

- Browse available properties
- Search properties
- Make reservations
- View reservations

### Owner Features

- Manage properties
- View reservations
- Add and delete properties

### Oracle Database

- Relational tables
- SQL views
- PL/SQL procedures
- Triggers
- Constraints

## Project Structure


app.py

templates/
index.html
auth_login.html
auth_register.html
owner_dashboard.html
tenant_dashboard.html
property_detail.html

static/

sql/
script_sql.sql
code_sql_pl.sql

requirements.txt


## Installation

### 1 - Oracle Database Setup

Create an Oracle user:

User:
Password:
DSN:
localhost:1521/XEPDB1

### 2 - Run SQL Scripts
Execute the following scripts using Oracle SQL Developer:

sql/script_sql.sql
sql/code_sql_pl.sql


### 3 - Install Dependencies
pip install -r requirements.txt


### 4 - Run the Application
python app.py
Then open:
http://localhost:5000

## Author

Engineering Student – ENSA Agadir (Data / AI)
