# FILE: app/main/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import Product, Customer, AdminUser, Bill, BillItem

main = Blueprint('main', __name__)

# --- Storefront Routes ---

@main.route('/')
def home():
    products = Product.query.order_by(Product.name).all()
    return render_template('home.html', products=products)

@main.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product_detail.html', product=product)

# --- Authentication Routes ---

@main.route('/register', methods=['GET', 'POST'])
def customer_register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        customer = Customer.query.filter_by(email=email).first()
        if customer:
            flash('Email address already registered.', 'danger')
            return redirect(url_for('main.customer_register'))
            
        new_customer = Customer(email=email, name=name)
        new_customer.set_password(password)
        db.session.add(new_customer)
        db.session.commit()
        
        # Log in the new customer immediately
        login_user(new_customer)
        session['user_type'] = 'customer'
        flash('Registration successful! Welcome.', 'success')
        return redirect(url_for('main.home'))
        
    return render_template('register.html')


@main.route('/login', methods=['GET', 'POST'])
def customer_login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        customer = Customer.query.filter_by(email=email).first()
        
        if customer and customer.check_password(password):
            login_user(customer)
            session['user_type'] = 'customer'
            return redirect(url_for('main.home'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')
            
    return render_template('customer_login.html')


@main.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = AdminUser.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            login_user(admin)
            session['user_type'] = 'admin'
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Admin login failed. Please check your credentials.', 'danger')

    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.home'))
    
# --- Shopping Cart Routes ---

@main.route('/cart/add/<int:id>', methods=['POST'])
def add_to_cart(id):
    product = Product.query.get_or_404(id)
    quantity = int(request.form.get('quantity', 1))
    
    # Initialize cart in session if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}
        
    cart = session['cart']
    product_id_str = str(product.id)

    # Add or update quantity
    current_quantity = cart.get(product_id_str, 0)
    new_quantity = current_quantity + quantity
    
    if new_quantity > product.stock:
        flash(f'Cannot add {quantity} units. Only {product.stock - current_quantity} more available.', 'danger')
    else:
        cart[product_id_str] = new_quantity
        flash(f'Added {quantity} x {product.name} to your cart.', 'success')
        
    session.modified = True
    return redirect(request.referrer or url_for('main.home'))

@main.route('/cart')
def view_cart():
    cart_items = []
    total = 0
    if 'cart' in session:
        for product_id, quantity in session['cart'].items():
            product = Product.query.get(product_id)
            if product:
                item_total = product.selling_price * quantity
                cart_items.append({'product': product, 'quantity': quantity, 'total': item_total})
                total += item_total
                
    return render_template('cart.html', cart_items=cart_items, total=total)

@main.route('/cart/update/<int:id>', methods=['POST'])
def update_cart(id):
    quantity = int(request.form.get('quantity', 0))
    product_id_str = str(id)

    if 'cart' in session:
        cart = session['cart']
        if quantity > 0:
            cart[product_id_str] = quantity
            flash('Cart updated.', 'success')
        else: # If quantity is 0, remove the item
            cart.pop(product_id_str, None)
            flash('Item removed from cart.', 'success')
        session.modified = True

    return redirect(url_for('main.view_cart'))
    
# --- Checkout & Order Routes ---

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if 'cart' not in session or not session['cart']:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('main.home'))

    # Prepare cart details for display
    cart_items = []
    subtotal = 0
    for product_id, quantity in session['cart'].items():
        product = Product.query.get(product_id)
        if product:
            item_total = product.selling_price * quantity
            cart_items.append({'product': product, 'quantity': quantity, 'total': item_total})
            subtotal += item_total

    if request.method == 'POST':
        # Create a new Bill from the checkout form and cart
        new_bill = Bill(
            customer_id=current_user.id,
            customer_name=request.form.get('name'),
            customer_email=request.form.get('email'),
            customer_address=request.form.get('address'),
            customer_city=request.form.get('city'),
            subtotal=subtotal,
            final_amount=subtotal # Assuming no tax/discount from storefront for now
        )
        db.session.add(new_bill)
        db.session.flush() # Get the new bill's ID

        # Create BillItems and deduct stock
        for item in cart_items:
            product = item['product']
            quantity_to_sell = item['quantity']

            bill_item = BillItem(
                bill_id=new_bill.id,
                product_id=product.id,
                product_name=product.name,
                quantity=quantity_to_sell,
                price_per_unit=product.selling_price,
                cost_price_at_sale=product.cost_price
            )
            db.session.add(bill_item)
            
            # Deduct stock (same logic as admin panel)
            for batch in sorted(product.batches, key=lambda b: b.date_added):
                if quantity_to_sell > 0:
                    sell_from_batch = min(quantity_to_sell, batch.quantity)
                    batch.quantity -= sell_from_batch
                    quantity_to_sell -= sell_from_batch
        
        db.session.commit()
        
        # Clear the cart and redirect to success page
        session.pop('cart', None)
        return redirect(url_for('main.order_success', bill_id=new_bill.id))
        
    return render_template('checkout.html', cart_items=cart_items, total=subtotal)

@main.route('/order_success/<int:bill_id>')
@login_required
def order_success(bill_id):
    bill = Bill.query.get_or_404(bill_id)
    # Security check: ensure the current user owns this bill
    if bill.customer_id != current_user.id:
        return redirect(url_for('main.home'))
    return render_template('order_success.html', bill=bill)

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = Customer.query.get_or_404(current_user.id)
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.address = request.form.get('address')
        user.city = request.form.get('city')
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('main.profile'))

    return render_template('profile.html', user=user)

# This is the new customer-facing route for viewing a single bill
@main.route('/order/<int:bill_id>')
@login_required
def view_order(bill_id):
    bill = Bill.query.filter_by(id=bill_id, customer_id=current_user.id).first_or_404()
    return render_template('bill_detail.html', bill=bill)