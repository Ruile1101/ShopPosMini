# PostgreSQL + LAN deployment for ShopPOS

This project is configured to use a PostgreSQL database through the `DATABASE_URL` environment variable. The existing Flask UI and SQLAlchemy models remain the same as much as possible.

## 1. Install PostgreSQL on the server PC

Install PostgreSQL on the Windows PC that will run the ShopPOS Flask server.

Recommended server installation steps:

1. Install PostgreSQL (the PostgreSQL server package, pgAdmin optional).
2. Start the PostgreSQL service.
3. Create a database and a database user.

## 2. Create the database

On the server PostgreSQL instance, open `psql` or pgAdmin and run:

```sql
CREATE DATABASE shoppos;
```

## 3. Create the database user

Create a server-side database user with a password that is not committed into source files:

```sql
CREATE USER shoppos WITH PASSWORD 'CHANGE_ME';
GRANT ALL PRIVILEGES ON DATABASE shoppos TO shoppos;
```

If your installation expects the role to access the schema, you can also run:

```sql
ALTER USER shoppos WITH CREATEDB;
```

## 4. Set DATABASE_URL

The Flask app reads the PostgreSQL connection string from the `DATABASE_URL` environment variable.

Example:

```powershell
set DATABASE_URL=postgresql+psycopg2://shoppos:CHANGE_ME@SERVER_IP:5432/shoppos
```

For a persistent server setup, set it as a Windows environment variable in the server PC. Do not hard-code credentials in the source code.

A safer pattern is:

```powershell
setx DATABASE_URL "postgresql+psycopg2://shoppos:CHANGE_ME@SERVER_IP:5432/shoppos"
```

Then restart the terminal or command window.

## 5. Initialize the database

From the project root, run:

```powershell
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database tables ready')"
```

This safely creates PostgreSQL tables without dropping data.

## 6. Migrate existing SQLite data if applicable

Your existing `pos.db` file should not be deleted.

To transfer the current SQLite shop records into PostgreSQL:

```powershell
set DATABASE_URL=postgresql+psycopg2://shoppos:CHANGE_ME@SERVER_IP:5432/shoppos
python migrate_sqlite_to_postgres.py
```

This script reads the source `pos.db` file and inserts the data into PostgreSQL while preserving the local SQLite file.

## 7. Find the server LAN IP

On the server Windows PC, run:

```powershell
ipconfig
```

Look for the IPv4 address under your network adapter, for example:

```text
192.168.1.50
```

## 8. Allow port 5000 through Windows Firewall

On the server PC, allow incoming traffic through port 5000:

```powershell
netsh advfirewall firewall add rule name="ShopPOS Flask" dir=in action=allow protocol=TCP localport=5000
```

## 9. Client laptops

Client laptops must open the browser URL:

```text
http://SERVER_IP:5000/
```

Example:

```text
http://192.168.1.50:5000/
```

Client laptops do not need Python, SQLite, or PostgreSQL installed.

## 10. Start the server

From the project root on the server PC:

```powershell
set DATABASE_URL=postgresql+psycopg2://shoppos:CHANGE_ME@SERVER_IP:5432/shoppos
set FLASK_RUN_HOST=0.0.0.0
set FLASK_RUN_PORT=5000
flask run --host=0.0.0.0 --port=5000
```

or equivalently:

```powershell
python start.py
```

The server should be reachable from other laptops on the same LAN by opening:

```text
http://SERVER_IP:5000/
```

## 11. Server role and authentication

The user model keeps the existing login/role system with the `role` field. Existing roles such as `admin` and `user` are preserved.

## 12. Multi-user concurrent sales

The app now reads and writes through PostgreSQL, not a single shared SQLite file. PostgreSQL supports concurrent access for multiple clients.
