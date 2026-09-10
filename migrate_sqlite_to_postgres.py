#!/usr/bin/env python3
"""Safe one-way SQLite -> PostgreSQL migration for ShopPOS.

This script reads the existing SQLite file (pos.db by default) and inserts the
records into the PostgreSQL database named by the DATABASE_URL environment
variable. It does NOT delete or overwrite the source SQLite file.

Example:
    set DATABASE_URL=postgresql+psycopg2://shoppos:password@192.168.1.50:5432/shoppos
    python migrate_sqlite_to_postgres.py

The script uses the same SQLAlchemy models already declared in this project,
so it preserves the existing model-layer structure and keeps the User,
Product, Sale, SaleItem, and Stock relationships consistent.
"""

import os
import sqlite3
import sys
from datetime import datetime, date

try:
    from app import create_app, db
    from app.models import User, Product, Stock, Sale, SaleItem
except Exception as exc:
    print("Could not import the ShopPOS Flask app. Make sure you are running this from the project root and DATABASE_URL is set.", file=sys.stderr)
    print(str(exc), file=sys.stderr)
    raise


def sqlite_to_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').date()
        except Exception:
            return None


def main():
    database_url = os.getenv('DATABASE_URL')
    sqlite_path = os.getenv('SQLITE_DB_PATH', os.path.join(os.getcwd(), 'pos.db'))

    if not database_url:
        print("DATABASE_URL is required. Example: postgresql+psycopg2://shoppos:password@SERVER-IP:5432/shoppos", file=sys.stderr)
        return 2

    if not os.path.exists(sqlite_path):
        print(f"SQLite source database not found: {sqlite_path}", file=sys.stderr)
        return 2

    app = create_app()
    with app.app_context():
        db.create_all()
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row

        print(f"Migrating from SQLite: {sqlite_path}")
        print(f"Migrating into PostgreSQL: {database_url.split('@')[-1] if '@' in database_url else database_url}")

        # Users
        users = sqlite_conn.execute("SELECT * FROM user ORDER BY id").fetchall()
        for row in users:
            existing = User.query.get(row['id'])
            if not existing:
                user = User(
                    id=row['id'],
                    username=row['username'],
                    email=row['email'],
                    password=row['password'],
                    role=row['role'] if row['role'] else 'user',
                )
                db.session.add(user)
        db.session.commit()

        # Products
        products = sqlite_conn.execute("SELECT * FROM product ORDER BY id").fetchall()
        for row in products:
            existing = Product.query.get(row['id'])
            if not existing:
                product = Product(
                    id=row['id'],
                    name=row['name'],
                    price=float(row['price']),
                    quantity=int(row['quantity']),
                    category=row['category'] if row['category'] else 'Stationery',
                    date_added=datetime.fromisoformat(row['date_added']) if row['date_added'] else datetime.utcnow(),
                )
                db.session.add(product)
        db.session.commit()

        # Stock
        stocks = sqlite_conn.execute("SELECT * FROM stock ORDER BY id").fetchall()
        for row in stocks:
            existing = Stock.query.get(row['id'])
            if not existing:
                stock = Stock(
                    id=row['id'],
                    product_id=row['product_id'],
                    quantity=int(row['quantity']),
                )
                db.session.add(stock)
        db.session.commit()

        # Sales
        sales = sqlite_conn.execute("SELECT * FROM sale ORDER BY id").fetchall()
        for row in sales:
            existing = Sale.query.get(row['id'])
            if not existing:
                sale = Sale(
                    id=row['id'],
                    amount=float(row['amount']),
                    date=sqlite_to_date(row['date']),
                    user_id=row['user_id'],
                    product_id=row['product_id'],
                    quantity=row['quantity'],
                    payment_method=row['payment_method'] if row['payment_method'] else 'Cash',
                    customer_name=row['customer_name'],
                    document_type=row['document_type'] if 'document_type' in row.keys() else 'receipt',
                )
                db.session.add(sale)
        db.session.commit()

        # SaleItems
        sale_items = sqlite_conn.execute("SELECT * FROM sale_item ORDER BY id").fetchall()
        for row in sale_items:
            existing = SaleItem.query.get(row['id'])
            if not existing:
                item = SaleItem(
                    id=row['id'],
                    sale_id=row['sale_id'],
                    product_id=row['product_id'],
                    category=row['category'],
                    description=row['description'],
                    quantity=int(row['quantity']),
                    unit_price=float(row['unit_price']),
                    line_total=float(row['line_total']),
                )
                db.session.add(item)
        db.session.commit()

        print(f"Migration complete. Imported users={len(users)}, products={len(products)}, stock={len(stocks)}, sales={len(sales)}, sale_items={len(sale_items)}")

    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Migration failed:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        raise
