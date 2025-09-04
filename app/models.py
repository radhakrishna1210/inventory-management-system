from . import db, login_manager
from sqlalchemy.sql import func
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session

# The user_loader checks whether we are loading an admin or a customer
@login_manager.user_loader
def load_user(user_id):
    user_type = session.get('user_type')
    if user_type == 'admin':
        return AdminUser.query.get(int(user_id))
    elif user_type == 'customer':
        return Customer.query.get(int(user_id))
    return None

# Admin user model
class AdminUser(db.Model, UserMixin):
    __tablename__ = 'admin_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Customer user model
class Customer(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    bills = db.relationship('Bill', backref='customer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # --- CHANGE THESE LINES ---
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    category = db.Column(db.String(100), nullable=False, default='Uncategorized')
    batches = db.relationship('Batch', backref='product', lazy=True, cascade="all, delete-orphan")
    
    # --- FIX: Added the missing image_file column ---
    # This stores the filename for the product's image (e.g., 'product1.jpg').
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    
    # Added relationship to Batch for the 'stock' property to work correctly
    batches = db.relationship('Batch', backref='product', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Product {self.name}>'

    @property
    def stock(self):
        # This property calculates the total stock from all batches for this product
        return sum(batch.quantity for batch in self.batches)

# Batch model for inventory tracking
class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    date_added = db.Column(db.DateTime(timezone=True), server_default=func.now())

# Billing model
class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True) # Can be null for guest checkout
    customer_name = db.Column(db.String(150), nullable=False)
    customer_email = db.Column(db.String(150), nullable=True)
    customer_address = db.Column(db.Text, nullable=True)
    customer_city = db.Column(db.String(100), nullable=True)
    date = db.Column(db.DateTime(timezone=True), server_default=func.now())
    subtotal = db.Column(db.Float, nullable=False)
    tax_percentage = db.Column(db.Float, nullable=False, default=0)
    discount_amount = db.Column(db.Float, nullable=False, default=0)
    final_amount = db.Column(db.Float, nullable=False)
    items = db.relationship('BillItem', backref='bill', lazy=True, cascade="all, delete-orphan")

# Items associated with a bill
class BillItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('bill.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True) # Nullable in case product is deleted
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)
    cost_price_at_sale = db.Column(db.Float, nullable=False, default=0)
