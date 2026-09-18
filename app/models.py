from app import db
from datetime import datetime

SALE_CATEGORIES = ['Printing', 'Binding', 'Laminating', 'Sticker', 'Stationery', 'Other']
PAYMENT_METHODS = ['Cash', 'QR', 'Card', 'Other']

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='cashier')  # can be admin, manager, cashier



class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # ForeignKey to User
    user = db.relationship('User', backref=db.backref('sales', lazy=True))  # Relationship with User
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)  # Legacy first product
    product = db.relationship('Product', backref=db.backref('sales', lazy=True))  # Relationship with Product
    quantity = db.Column(db.Integer, nullable=True)  # Legacy total quantity
    payment_method = db.Column(db.String(20), nullable=False, default='Cash')
    customer_name = db.Column(db.String(120), nullable=True)
    document_type = db.Column(db.String(20), nullable=False, default='receipt')
    discount = db.Column(db.Float, nullable=False, default=0.00)
    deposit = db.Column(db.Float, nullable=False, default=0.00)
    items = db.relationship('SaleItem', back_populates='sale', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Sale {self.id} - {self.amount}>'


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    is_lump_sum = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey('sale.id'),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey('product.id'),
        nullable=True
    )

    category = db.Column(
        db.String(30),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    unit = db.Column(
        db.String(20),
        nullable=False,
        default='PC'
    )

    unit_price = db.Column(
        db.Float,
        nullable=False
    )

    line_total = db.Column(
        db.Float,
        nullable=False
    )

    sale = db.relationship(
        'Sale',
        back_populates='items'
    )

    product = db.relationship(
        'Product',
        backref=db.backref(
            'sale_items',
            lazy=True
        )
    )




class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(30), nullable=False, default='Stationery')
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}>'





class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product = db.relationship('Product', backref=db.backref('stock', lazy=True))
    quantity = db.Column(db.Integer, nullable=False)
