# FILE: app/admin/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, json, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, distinct
from app import db
from app.models import Product, Batch, Bill, BillItem, AdminUser, Customer
from app import ml_models
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from decimal import Decimal

admin = Blueprint('admin', __name__)

def save_picture(form_picture):
    """Saves a picture to the filesystem."""
    filename = secure_filename(form_picture.filename)
    picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    form_picture.save(picture_path)
    return filename

@admin.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    start_of_month = today.replace(day=1)
    thirty_days_ago = datetime.now() - timedelta(days=30)

    # --- Today's & Month's Profit ---
    todays_bill_items = db.session.query(BillItem).join(Bill).filter(func.date(Bill.date) == today).all()
    months_bill_items = db.session.query(BillItem).join(Bill).filter(Bill.date >= start_of_month).all()
    todays_profit = sum((item.price_per_unit - item.cost_price_at_sale) * item.quantity for item in todays_bill_items)
    months_profit = sum((item.price_per_unit - item.cost_price_at_sale) * item.quantity for item in months_bill_items)
    
    # --- Sales Chart ---
    daily_sales = db.session.query(
        func.date(Bill.date).label('sale_date'),
        func.sum(Bill.final_amount).label('total_sales')
    ).filter(Bill.date >= thirty_days_ago).group_by('sale_date').order_by('sale_date').all()
    sales_chart_labels = [sale.sale_date.strftime('%b %d') for sale in daily_sales]
    sales_chart_data = [round(float(sale.total_sales), 2) for sale in daily_sales]

    # --- Top Products ---
    top_products_by_revenue = db.session.query(BillItem.product_name, func.sum(BillItem.price_per_unit * BillItem.quantity).label('total_revenue')).group_by(BillItem.product_name).order_by(db.desc('total_revenue')).limit(5).all()
    top_products_by_units = db.session.query(BillItem.product_name, func.sum(BillItem.quantity).label('total_units')).group_by(BillItem.product_name).order_by(db.desc('total_units')).limit(5).all()

    # --- Customer Stats ---
    all_customers = db.session.query(distinct(Bill.customer_email)).filter(Bill.customer_email.isnot(None)).count()
    returning_customers = db.session.query(Bill.customer_email).filter(Bill.customer_email.isnot(None)).group_by(Bill.customer_email).having(func.count(Bill.id) > 1).count()
    new_customers = all_customers - returning_customers

    # --- Category Revenue ---
    revenue_by_category = db.session.query(Product.category, func.sum(BillItem.price_per_unit * BillItem.quantity).label('total_revenue')).join(Product, BillItem.product_id == Product.id).group_by(Product.category).order_by(db.desc('total_revenue')).all()
    category_chart_labels = [item.category for item in revenue_by_category]
    category_chart_data = [round(float(item.total_revenue), 2) for item in revenue_by_category]

    return render_template('admin/dashboard.html',
                           todays_profit=todays_profit, months_profit=months_profit,
                           sales_chart_labels=json.dumps(sales_chart_labels), sales_chart_data=json.dumps(sales_chart_data),
                           top_products_by_revenue=top_products_by_revenue, top_products_by_units=top_products_by_units,
                           new_customers=new_customers, returning_customers=returning_customers,
                           category_chart_labels=json.dumps(category_chart_labels), category_chart_data=json.dumps(category_chart_data))

@admin.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        name = request.form.get('name')
        cost_price = request.form.get('cost_price')
        selling_price = request.form.get('selling_price')
        description = request.form.get('description')
        category = request.form.get('category', 'Uncategorized')
        
        image_filename = 'placeholder.jpg'
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename != '':
                image_filename = save_picture(file)

        if name and selling_price and cost_price:
            # CORRECTED: Use Decimal to maintain precision
            new_product = Product(name=name, cost_price=Decimal(cost_price), selling_price=Decimal(selling_price), description=description, category=category, image_file=image_filename)
            db.session.add(new_product)
            db.session.commit()
            flash('Product added successfully!', 'success')
        else:
            flash('Missing required fields.', 'danger')
        return redirect(url_for('admin.manage_products'))
    
    products = Product.query.all()
    return render_template('admin/products.html', products=products)


@admin.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        # CORRECTED: Use Decimal to maintain precision
        product.cost_price = Decimal(request.form.get('cost_price'))
        product.selling_price = Decimal(request.form.get('selling_price'))
        product.category = request.form.get('category', 'Uncategorized')
        
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename != '':
                product.image_file = save_picture(file)

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin.manage_products'))
    
    return render_template('admin/edit_product.html', product=product)

@admin.route('/product/delete/<int:id>')
@login_required
def delete_product(id):
    product_to_delete = Product.query.get_or_404(id)
    
    bill_items_to_update = BillItem.query.filter_by(product_id=id).all()
    for item in bill_items_to_update:
        item.product_id = None
        
    db.session.commit()
    
    db.session.delete(product_to_delete)
    db.session.commit()
    
    flash('Product deleted successfully! Sales records are preserved.', 'success')
    return redirect(url_for('admin.manage_products'))

@admin.route('/billing')
@login_required
def billing():
    products_query = Product.query.order_by(Product.name).all()
    # CORRECTED: Convert Decimal to float for JSON serialization
    products_list = [{"id": p.id, "name": p.name, "price": float(p.selling_price), "stock": p.stock} for p in products_query]
    return render_template('admin/billing.html', products_json=json.dumps(products_list))

@admin.route('/billing/create', methods=['POST'])
@login_required
def create_bill():
    data = request.get_json()
    if not data:
        return {"error": "Invalid request"}, 400
        
    customer_name = data.get('customer_name')
    items = data.get('items')
    
    # CORRECTED: Convert all incoming financial data to Decimal
    tax_percentage = Decimal(data.get('tax_percentage', '0'))
    discount_amount = Decimal(data.get('discount_amount', '0'))

    if not items:
        return {"error": "Cannot create an empty bill."}, 400

    subtotal = Decimal('0.0') # Initialize as a Decimal
    
    # First pass: Check stock and calculate subtotal
    for item in items:
        product = Product.query.get(item['id'])
        if not product or product.stock < int(item['quantity']):
            return {"error": f"Not enough stock for {product.name if product else 'Unknown Product'}"}, 400
        
        subtotal += product.selling_price * int(item['quantity'])
    
    # CORRECTED: Perform all calculations using Decimal
    tax_amount = subtotal * (tax_percentage / Decimal('100'))
    final_amount = (subtotal + tax_amount) - discount_amount

    new_bill = Bill(customer_name=customer_name, customer_email=data.get('customer_email'), 
                    subtotal=float(subtotal), tax_percentage=float(tax_percentage), 
                    discount_amount=float(discount_amount), final_amount=float(final_amount))
    db.session.add(new_bill)
    db.session.flush()

    # Second pass: Create BillItems and deduct stock
    for item in items:
        product = Product.query.get(item['id'])
        quantity_to_sell = int(item['quantity'])
        
        bill_item = BillItem(bill_id=new_bill.id, product_id=product.id, product_name=product.name,
                             quantity=quantity_to_sell, price_per_unit=float(product.selling_price),
                             cost_price_at_sale=float(product.cost_price))
        db.session.add(bill_item)

        # FIFO stock deduction
        for batch in sorted(product.batches, key=lambda b: b.date_added):
            if quantity_to_sell > 0:
                sell_from_batch = min(quantity_to_sell, batch.quantity)
                batch.quantity -= sell_from_batch
                quantity_to_sell -= sell_from_batch
    
    db.session.commit()
    return {"success": True, "bill_id": new_bill.id}

@admin.route('/bill/<int:id>')
@login_required
def bill_detail(id):
    bill = Bill.query.get_or_404(id)
    return render_template('admin/bill_detail.html', bill=bill)

@admin.route('/inventory', methods=['GET', 'POST'])
@login_required
def manage_inventory():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        quantity = request.form.get('quantity')
        if product_id and quantity and int(quantity) > 0:
            new_batch = Batch(product_id=int(product_id), quantity=int(quantity))
            db.session.add(new_batch)
            db.session.commit()
            flash('Inventory batch added!', 'success')
        else:
            flash('Invalid product or quantity.', 'danger')
        return redirect(url_for('admin.manage_inventory'))
        
    batches = Batch.query.order_by(Batch.date_added.desc()).all()
    products = Product.query.order_by(Product.name).all()
    return render_template('admin/inventory.html', batches=batches, products=products)

@admin.route('/inventory/summary')
@login_required
def inventory_summary():
    products_with_stock = Product.query.all()
    return render_template('admin/inventory_summary.html', inventory=products_with_stock)

@admin.route('/forecasting')
@login_required
def forecasting():
    predicted_demand = ml_models.predict_future_demand(db.engine)
    return render_template('admin/forecasting.html', prediction=predicted_demand)

@admin.route('/train-model')
@login_required
def train_model_route():
    ml_models.train_and_save_demand_model(db.engine)
    flash('Demand forecasting model has been re-trained.', 'success')
    return redirect(url_for('admin.forecasting'))

# --- User Management Routes ---
@admin.route('/users/admins', methods=['GET', 'POST'])
@login_required
def manage_admins():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            if AdminUser.query.filter_by(username=username).first():
                flash('Username already exists.', 'danger')
            else:
                new_admin = AdminUser(username=username)
                new_admin.set_password(password)
                db.session.add(new_admin)
                db.session.commit()
                flash('Admin user created successfully.', 'success')
        return redirect(url_for('admin.manage_admins'))

    admins = AdminUser.query.all()
    return render_template('admin/manage_admins.html', admins=admins)

@admin.route('/users/admin/delete/<int:id>')
@login_required
def delete_admin(id):
    if AdminUser.query.count() == 1:
        flash('Cannot delete the last admin user.', 'danger')
    else:
        admin_to_delete = AdminUser.query.get_or_404(id)
        db.session.delete(admin_to_delete)
        db.session.commit()
        flash('Admin user deleted successfully.', 'success')
    return redirect(url_for('admin.manage_admins'))

@admin.route('/users/customers')
@login_required
def manage_customers():
    customers = Customer.query.all()
    return render_template('admin/manage_customers.html', customers=customers)

@admin.route('/users/customer/delete/<int:id>')
@login_required
def delete_customer(id):
    customer_to_delete = Customer.query.get_or_404(id)
    db.session.delete(customer_to_delete)
    db.session.commit()
    flash('Customer account deleted successfully.', 'success')
    return redirect(url_for('admin.manage_customers'))