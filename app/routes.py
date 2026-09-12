from io import BytesIO

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from datetime import date, datetime, timedelta
from app import db
from app.models import PAYMENT_METHODS, SALE_CATEGORIES, User, Sale, SaleItem, Stock, Product
import calendar
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

main = Blueprint('main', __name__)

def month_document_number(sale, document_type):
    month_start = date(sale.date.year, sale.date.month, 1)
    if sale.date.month == 12:
        month_end = date(sale.date.year + 1, 1, 1)
    else:
        month_end = date(sale.date.year, sale.date.month + 1, 1)

    serial = Sale.query.filter(
        Sale.document_type == document_type,
        Sale.date >= month_start,
        Sale.date < month_end,
        Sale.id < sale.id,
    ).count()
    return f'{sale.date.year % 100:02d}{sale.date.month:02d}{serial + 1:04d}'

@main.app_context_processor
def inject_now():
    return {'current_year': datetime.now().year}

@main.route('/')
def home():
    return redirect(url_for('main.dashboard'))

@main.route('/dashboard')
def dashboard():
    today = date.today()
    today_sales = Sale.query.filter(Sale.date == today).order_by(Sale.id.desc()).all()
    category_sales = {category: 0 for category in SALE_CATEGORIES}
    for sale in today_sales:
        for item in sale.items:
            category_sales[item.category] = round(category_sales.get(item.category, 0) + item.line_total, 2)
    recent_sales = Sale.query.order_by(Sale.id.desc()).limit(8).all()
    return render_template('dashboard.html', total_sales_today=round(sum(sale.amount for sale in today_sales), 2),
                           transaction_count_today=len(today_sales), category_sales=category_sales,
                           recent_sales=recent_sales, total_employees=User.query.count(),
                           total_receipts=Sale.query.filter_by(document_type='receipt').count())

@main.route('/sales', methods=['GET', 'POST'])
def sales():
    sales_query = Sale.query.order_by(Sale.id.desc())
    filter_date = request.args.get('filter_date', '')
    filter_category = request.args.get('category', '')
    filter_payment = request.args.get('payment_method', '')
    filter_document_type = (request.args.get('document_type', '') or '').lower().strip()

    if filter_document_type in {'receipt', 'invoice'}:
        sales_query = sales_query.filter(Sale.document_type == filter_document_type)

    if filter_date:
        sales_query = sales_query.filter(Sale.date == filter_date)
    if filter_category in SALE_CATEGORIES:
        sales_query = sales_query.filter(Sale.items.any(SaleItem.category == filter_category))
    if filter_payment in PAYMENT_METHODS:
        sales_query = sales_query.filter(Sale.payment_method == filter_payment)
    return render_template('sales.html', sales=sales_query.all(), categories=SALE_CATEGORIES,
                           payment_methods=PAYMENT_METHODS, selected_document_type=filter_document_type)

@main.route('/add_sale', defaults={'document_type': 'invoice'}, methods=['GET', 'POST'])
@main.route('/add_sale/<document_type>', methods=['GET', 'POST'])
def add_sale(document_type='receipt'):
    if document_type.lower() not in {'receipt', 'invoice'}:
        flash('Choose either a receipt or an invoice document.', 'danger')
        return redirect(url_for('main.add_sale'))

    document_type = document_type.lower()

    invoice_service_choices = [
        {'value': 'normal_stamp_24', 'label': 'Normal Stamp (Round 24mm)', 'description': 'NORMAL STAMP - ROUND 24MM', 'price': 13.00},
        {'value': 'normal_stamp_28', 'label': 'Normal Stamp (Round 28mm)', 'description': 'NORMAL STAMP - ROUND 28MM', 'price': 14.00},
        {'value': 'color24_blue', 'label': 'Colop R24 Blue Ink', 'description': 'COLOP R24 - BLUE INK', 'price': 37.00},
        {'value': 'color24_black', 'label': 'Colop R24 Black Ink', 'description': 'COLOP R24 - BLACK INK', 'price': 37.00},
        {'value': 'color30_blue', 'label': 'Colop R30 Blue Ink', 'description': 'COLOP R30 - BLUE INK', 'price': 45.00},
        {'value': 'color30_black', 'label': 'Colop R30 Black Ink', 'description': 'COLOP R30 - BLACK INK', 'price': 45.00},
        {'value': 'p40_blue', 'label': 'Colop P40 Blue Ink', 'description': 'COLOP P40 - BLUE INK', 'price': 47.00},
        {'value': 'p40_black', 'label': 'Colop P40 Black Ink', 'description': 'COLOP P40 - BLACK INK', 'price': 47.00},
        {'value': 'common_seal', 'label': 'Common Seal', 'description': 'COMMON SEAL', 'price': 120.00},
    ]

    if request.method == 'POST':
        categories = request.form.getlist('category')
        descriptions = request.form.getlist('description')
        quantities = request.form.getlist('quantity')
        units = request.form.getlist('unit')
        prices = request.form.getlist('unit_price')
        product_ids = request.form.getlist('product_id')
        service_types = request.form.getlist('service_type')
        try:
            sale_date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
            payment_method = request.form.get('payment_method', 'Cash')
            customer_name = request.form.get('customer_name', '').strip() or None
            discount = round(float(request.form.get('discount', '0') or '0'), 2)
            deposit = round(float(request.form.get('deposit', '0') or '0'), 2)
            if payment_method not in PAYMENT_METHODS:
                raise ValueError
            if discount < 0 or deposit < 0:
                raise ValueError
            items = []
            fixed_prices = {
                'normal_stamp_24': {'description': 'NORMAL STAMP - ROUND 24MM', 'price': 13.00},
                'normal_stamp_28': {'description': 'NORMAL STAMP - ROUND 28MM', 'price': 14.00},
                'color24_blue': {'description': 'COLOP R24 - BLUE INK', 'price': 37.00},
                'color24_black': {'description': 'COLOP R24 - BLACK INK', 'price': 37.00},
                'color30_blue': {'description': 'COLOP R30 - BLUE INK', 'price': 45.00},
                'color30_black': {'description': 'COLOP R30 - BLACK INK', 'price': 45.00},
                'p40_blue': {'description': 'COLOP P40 - BLUE INK', 'price': 47.00},
                'p40_black': {'description': 'COLOP P40 - BLACK INK', 'price': 47.00},
                'common_seal': {'description': 'COMMON SEAL', 'price': 120.00},
            }
            for index in range(max(len(descriptions), len(quantities), len(prices), len(product_ids), len(service_types))):
                quantity = int(quantities[index]) if index < len(quantities) else 1
                unit = units[index] if index < len(units) and units[index] in {'PC', 'BOX', 'PACK', 'SET', 'UNIT'} else 'PC'
                unit_price = round(float(prices[index]), 2) if index < len(prices) and prices[index] else 0.00
                service_type = service_types[index] if index < len(service_types) else 'custom'
                description = descriptions[index].strip() if index < len(descriptions) else ''

                if document_type == 'invoice':
                    category = 'Other'
                    if service_type == 'custom':
                        if not description:
                            raise ValueError
                    elif service_type in fixed_prices:
                        description = description or fixed_prices[service_type]['description']
                        unit_price = fixed_prices[service_type]['price']
                    else:
                        description = description or 'Invoice service item'
                else:
                    category = categories[index] if index < len(categories) else 'Other'
                    if not category or category not in SALE_CATEGORIES:
                        raise ValueError
                    if service_type == 'custom':
                        description = description or 'Service item'
                    elif service_type in fixed_prices:
                        description = description or fixed_prices[service_type]['description']
                        unit_price = fixed_prices[service_type]['price']
                    else:
                        description = description or 'Service item'

                if quantity < 1 or unit_price < 0:
                    raise ValueError
                if document_type == 'receipt' and category not in SALE_CATEGORIES:
                    raise ValueError
                product_id = int(product_ids[index]) if index < len(product_ids) and product_ids[index] else None
                product = Product.query.get(product_id) if product_id else None
                if product and category == 'Stationery' and product.quantity < quantity:
                    flash(f'Not enough stock for {product.name}.', 'danger')
                    return redirect(url_for('main.add_sale', document_type=document_type))
                display_description = f"{description}|||{unit}"
                items.append((category, display_description, quantity, unit_price, product))
            if not items:
                raise ValueError
        except (TypeError, ValueError, IndexError):
            flash('Add at least one valid sale item and check the entered values.', 'danger')
            return redirect(url_for('main.add_sale', document_type=document_type))
        subtotal = round(
            sum(quantity * unit_price for _, _, quantity, unit_price, _ in items),
            2
        )

        discount = max(0, float(discount or 0))

        if discount > subtotal:
            discount = subtotal

        subtotal = round(sum(q * p for _, _, q, p, _ in items), 2); amount = round(subtotal - min(subtotal, max(0, float(discount or 0))), 2); first_product = next((p for _, _, _, _, p in items if p), None)
        cashier = User.query.order_by(User.id.asc()).first()
        if cashier is None:
            cashier = User(username='admin', email='admin@shop.local', password='password')
            db.session.add(cashier)
            db.session.commit()

        new_sale = Sale(amount=amount, date=sale_date, user_id=cashier.id,
                        product_id=first_product.id if first_product else None,
                        quantity=sum(item[2] for item in items), payment_method=payment_method,
                        customer_name=customer_name, document_type=document_type,
                        discount=discount, deposit=deposit)
        db.session.add(new_sale)
        db.session.flush()
        for category, description, quantity, unit_price, product in items:
            db.session.add(SaleItem(sale=new_sale, product_id=product.id if product else None,
                                    category=category, description=description or None,
                                    quantity=quantity, unit_price=unit_price,
                                    line_total=round(quantity * unit_price, 2)))
            if product:
                product.quantity -= quantity
                stock = Stock.query.filter_by(product_id=product.id).first()
                if stock:
                    stock.quantity = max(0, stock.quantity - quantity)
        db.session.commit()
        flash('Sale added successfully!', 'success')
        if document_type == 'invoice':
            return redirect(url_for('main.invoice', sale_id=new_sale.id))
        return redirect(url_for('main.sales'))

    products = Product.query.filter_by(category='Stationery').order_by(Product.name).all()
    return render_template('add_sale.html', products=products, categories=SALE_CATEGORIES,
                           payment_methods=PAYMENT_METHODS, today=date.today().isoformat(),
                           document_type=document_type, invoice_service_choices=invoice_service_choices)

@main.route('/edit_sale/<int:sale_id>', methods=['GET', 'POST'])
def edit_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    invoice_service_choices = [
        {'value': 'normal_stamp_24', 'label': 'Normal Stamp (Round 24mm)', 'description': 'NORMAL STAMP - ROUND 24MM', 'price': 13.00},
        {'value': 'normal_stamp_28', 'label': 'Normal Stamp (Round 28mm)', 'description': 'NORMAL STAMP - ROUND 28MM', 'price': 14.00},
        {'value': 'color24_blue', 'label': 'Colop R24 Blue Ink', 'description': 'COLOP R24 - BLUE INK', 'price': 37.00},
        {'value': 'color24_black', 'label': 'Colop R24 Black Ink', 'description': 'COLOP R24 - BLACK INK', 'price': 37.00},
        {'value': 'color30_blue', 'label': 'Colop R30 Blue Ink', 'description': 'COLOP R30 - BLUE INK', 'price': 45.00},
        {'value': 'color30_black', 'label': 'Colop R30 Black Ink', 'description': 'COLOP R30 - BLACK INK', 'price': 45.00},
        {'value': 'p40_blue', 'label': 'Colop P40 Blue Ink', 'description': 'COLOP P40 - BLUE INK', 'price': 47.00},
        {'value': 'p40_black', 'label': 'Colop P40 Black Ink', 'description': 'COLOP P40 - BLACK INK', 'price': 47.00},
        {'value': 'common_seal', 'label': 'Common Seal', 'description': 'COMMON SEAL', 'price': 120.00},
    ]

    if request.method == 'POST':
        try:
            sale_date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
            payment_method = request.form.get('payment_method', 'Cash')
            if payment_method not in PAYMENT_METHODS:
                raise ValueError

            customer_name = request.form.get('customer_name', '').strip() or None
            sale.customer_name = customer_name
            sale.payment_method = payment_method
            sale.date = sale_date

            discount = round(float(request.form.get('discount', '0') or '0'), 2)
            deposit = round(float(request.form.get('deposit', '0') or '0'), 2)
            if discount < 0 or deposit < 0:
                raise ValueError
            sale.discount = discount
            sale.deposit = deposit

            categories = request.form.getlist('category')
            descriptions = request.form.getlist('description')
            quantities = request.form.getlist('quantity')
            prices = request.form.getlist('unit_price')
            product_ids = request.form.getlist('product_id')
            service_types = request.form.getlist('service_type')

            if sale.document_type == 'invoice':
                # The editable invoice row is a single service-style item; the per-row category is forced to Other.
                if not sale.items:
                    raise ValueError
                item = sale.items[0]
                item.description = descriptions[0].strip() if descriptions else item.description
                item.quantity = int(quantities[0]) if quantities and quantities[0] else item.quantity
                item.unit_price = round(float(prices[0]), 2) if prices and prices[0] else item.unit_price
                item.line_total = round(item.quantity * item.unit_price, 2)
                if service_types and service_types[0] != 'custom':
                    item.description = descriptions[0].strip() if descriptions and descriptions[0].strip() else service_types[0]
                item.category = 'Other'
                product_id = int(product_ids[0]) if product_ids and product_ids[0] else None
                item.product_id = product_id
                item.product = Product.query.get(product_id) if product_id else None
                subtotal = round(
                sum(i.quantity * i.unit_price for i in sale.items),
                2
                )

                discount = max(0, float(sale.discount or 0))

                if discount > subtotal:
                    discount = subtotal

                sale.discount = round(discount, 2)
                sale.amount = round(subtotal - sale.discount, 2)
                sale.quantity = sum(i.quantity for i in sale.items)
                sale.product_id = item.product_id
            else:
                if not sale.items:
                    raise ValueError
                for index, item in enumerate(sale.items):
                    item.category = categories[index] if index < len(categories) else item.category
                    item.description = descriptions[index].strip() if index < len(descriptions) else item.description
                    item.quantity = int(quantities[index]) if index < len(quantities) and quantities[index] else item.quantity
                    item.unit_price = round(float(prices[index]), 2) if index < len(prices) and prices[index] else item.unit_price
                    item.line_total = round(item.quantity * item.unit_price, 2)
                    product_id = int(product_ids[index]) if index < len(product_ids) and product_ids[index] else None
                    item.product_id = product_id
                    item.product = Product.query.get(product_id) if product_id else None

                subtotal = round(sum((i.quantity or 0) * (i.unit_price or 0) for i in (sale.items or [])), 2); sale.discount = round(min(subtotal, max(0, float(sale.discount or 0))), 2); sale.amount = round(subtotal - sale.discount, 2); sale.quantity = sum((i.quantity or 0) for i in (sale.items or [])); db.session.commit()
            db.session.commit();
            flash('Sale updated successfully!', 'success')
            if sale.document_type == 'invoice':
                return redirect(url_for('main.invoice', sale_id=sale.id))
            return redirect(url_for('main.receipt', sale_id=sale.id))
        except (TypeError, ValueError, IndexError):
            db.session.rollback()
            flash('Update failed. Check the item rows, quantities, unit prices, and customer name.', 'danger')
            return redirect(url_for('main.edit_sale', sale_id=sale.id))

    products = Product.query.order_by(Product.name).all()
    return render_template(
        'edit_sale.html',
        sale=sale,
        products=products,
        categories=SALE_CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        document_type=sale.document_type,
        invoice_service_choices=invoice_service_choices,
        today=date.today().isoformat(),
    )
# Delete Sale Route
@main.route('/delete_sale/<int:sale_id>', methods=['GET', 'POST'])
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    
    flash('Sale deleted successfully!', 'danger')
    return redirect(url_for('main.sales'))

# View Sale Route
@main.route('/view_sale/<int:sale_id>')
def view_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('view_sale.html', sale=sale)


@main.route('/receipt/<int:sale_id>')
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    receipt_number = month_document_number(sale, 'receipt')
    return render_template('receipt.html', sale=sale, receipt_number=receipt_number)

@main.route('/invoice/<int:sale_id>')
def invoice(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    invoice_number = month_document_number(sale, 'invoice')
    return render_template('invoice.html', sale=sale, invoice_number=invoice_number)

# Products Route
@main.route('/products')
def products():
    # Fetch all products
    products_data = Product.query.all()
    return render_template('products.html', products=products_data)

# Add Product Route
@main.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        quantity = request.form['quantity']
        category = request.form.get('category', 'Stationery')
        
        new_product = Product(name=name, price=price, quantity=quantity, category=category)
        db.session.add(new_product)
        db.session.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('main.products'))
    
    return render_template('add_product.html')

# View Product Route
@main.route('/product/<int:product_id>')
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('view_product.html', product=product)

# Edit Product Route
@main.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = request.form['price']
        product.quantity = request.form['quantity']
        product.category = request.form.get('category', 'Stationery')
        db.session.commit()

        flash('Product updated successfully!', 'success')
        return redirect(url_for('main.products'))

    return render_template('edit_product.html', product=product)

# Delete Product Route
@main.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()

    flash('Product deleted successfully!', 'danger')
    return redirect(url_for('main.products'))

# Stock Route
@main.route('/stock')
def stock():
    # Fetch stock levels for all products
    stock_data = Stock.query.all()
    return render_template('stock.html', stock=stock_data)

# Receipts Route
@main.route('/receipts')
def receipts():
    receipts_data = Sale.query.filter_by(document_type='receipt').order_by(Sale.id.desc()).all()
    return render_template('receipts.html', receipts=receipts_data)

@main.route('/revenue')
def revenue():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    total_revenue = round(sum(sale.amount for sale in Sale.query.all()), 2)
    period_totals = {
        'Today': round(sum(sale.amount for sale in Sale.query.filter(Sale.date == today).all()), 2),
        'This week': round(sum(sale.amount for sale in Sale.query.filter(Sale.date >= week_start).all()), 2),
        'This month': round(sum(sale.amount for sale in Sale.query.filter(Sale.date >= month_start).all()), 2),
    }
    daily = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        daily.append((day.strftime('%a %d'), round(sum(sale.amount for sale in Sale.query.filter(Sale.date == day).all()), 2)))
    monthly = []
    for offset in range(5, -1, -1):
        month_date = (today.replace(day=1) - timedelta(days=offset * 28)).replace(day=1)
        next_month = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        total = sum(sale.amount for sale in Sale.query.filter(Sale.date >= month_date, Sale.date < next_month).all())
        monthly.append((month_date.strftime('%b %Y'), round(total, 2)))
    return render_template('revenue.html', total_revenue=total_revenue, period_totals=period_totals,
                           daily=daily, monthly=monthly)


@main.route('/revenue/report.pdf')
def sales_report_pdf():
    start_value = request.args.get('from', '').strip()
    end_value = request.args.get('to', '').strip()
    document_type = (request.args.get('document_type', '') or '').lower().strip()
    if document_type and document_type not in {'receipt', 'invoice'}:
        document_type = ''
    try:
        start_date = datetime.strptime(start_value, '%Y-%m-%d').date() if start_value else None
        end_date = datetime.strptime(end_value, '%Y-%m-%d').date() if end_value else None
    except ValueError:
        flash('Use valid dates for the report range.', 'danger')
        return redirect(url_for('main.revenue'))

    if start_date and end_date and start_date > end_date:
        flash('The report start date must be before the end date.', 'danger')
        return redirect(url_for('main.revenue'))

    sales_query = Sale.query.order_by(Sale.date.asc(), Sale.id.asc())
    if document_type:
        sales_query = sales_query.filter(Sale.document_type == document_type)
    if start_date:
        sales_query = sales_query.filter(Sale.date >= start_date)
    if end_date:
        sales_query = sales_query.filter(Sale.date <= end_date)
    sales_data = sales_query.all()

    daily_summary = {}
    category_summary = {}
    for sale in sales_data:
        day = sale.date.isoformat()
        daily_summary.setdefault(day, {'transactions': 0, 'items': 0, 'amount': 0.0})
        daily_summary[day]['transactions'] += 1
        daily_summary[day]['items'] += sum(item.quantity for item in sale.items)
        daily_summary[day]['amount'] = round(daily_summary[day]['amount'] + sale.amount, 2)

        for item in sale.items:
            category_summary.setdefault(item.category, {'transactions': 0, 'items': 0, 'amount': 0.0})
            category_summary[item.category]['transactions'] += 1
            category_summary[item.category]['items'] += item.quantity
            category_summary[item.category]['amount'] = round(category_summary[item.category]['amount'] + item.line_total, 2)

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=14 * mm,
                                 leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    styles['Title'].fontName = 'Helvetica-Bold'
    styles['Title'].fontSize = 16
    styles['Title'].leading = 20
    styles['Heading2'].fontName = 'Helvetica-Bold'
    styles['Heading2'].fontSize = 10
    styles['Heading2'].leading = 12
    styles['BodyText'].fontName = 'Helvetica'
    styles['BodyText'].fontSize = 8

    story = [Paragraph('MIN BOOK SHOP - DETAILED SALES REPORT', styles['Title'])]
    period = f'{start_date:%d/%m/%Y} to {end_date:%d/%m/%Y}' if start_date and end_date else \
        (f'From {start_date:%d/%m/%Y}' if start_date else (f'Until {end_date:%d/%m/%Y}' if end_date else 'All sales'))
    story.extend([Paragraph(period, styles['Normal']), Spacer(1, 8)])

    total_amount = sum(sale.amount for sale in sales_data)
    total_items = sum(sum(item.quantity for item in sale.items) for sale in sales_data)
    summary = [['Transactions', str(len(sales_data)), 'Items sold', str(total_items),
                'Total (RM)', f'{total_amount:,.2f}']]
    summary_table = Table(summary, colWidths=[27 * mm, 18 * mm, 22 * mm, 18 * mm, 23 * mm, 25 * mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eaf2f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#9aaab2')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.extend([summary_table, Spacer(1, 12)])

    story.append(Paragraph('Daily sales breakdown', styles['Heading2']))
    daily_rows = [['Date', 'Transactions', 'Items', 'Total (RM)']]
    for day in sorted(daily_summary.keys()):
        row = daily_summary[day]
        daily_rows.append([day, str(row['transactions']), str(row['items']), f'{row["amount"]:,.2f}'])
    daily_table = Table(daily_rows, repeatRows=1, colWidths=[30 * mm, 25 * mm, 24 * mm, 30 * mm])
    daily_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17212b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#b8c2c7')),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
    ]))
    story.extend([daily_table, Spacer(1, 12)])

    story.append(Paragraph('Category sales breakdown', styles['Heading2']))
    category_rows = [['Category', 'Transactions', 'Items', 'Total (RM)']]
    for category, row in sorted(category_summary.items()):
        category_rows.append([category, str(row['transactions']), str(row['items']), f'{row["amount"]:,.2f}'])
    category_table = Table(category_rows, repeatRows=1, colWidths=[35 * mm, 28 * mm, 24 * mm, 30 * mm])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17212b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#b8c2c7')),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
    ]))
    story.extend([category_table, Spacer(1, 12)])

    story.append(Paragraph('Detailed transactions', styles['Heading2']))
    rows = [['Date', 'Document', 'Customer', 'Cashier', 'Payment', 'Details', 'Amount (RM)']]
    for sale in sales_data:
        details = '<br/>'.join(
            f'{item.category}{" - " + item.description if item.description else ""} '
            f'x {item.quantity} @ RM {item.unit_price:,.2f}' for item in sale.items
        ) or 'No item details'
        rows.append([
            sale.date.strftime('%d/%m/%Y') if sale.date else '',
            month_document_number(sale, sale.document_type),
            sale.customer_name or '-', sale.user.username if sale.user else '-',
            sale.payment_method or '-', Paragraph(details, styles['BodyText']), f'{sale.amount:,.2f}'
        ])
    report_table = Table(rows, repeatRows=1, colWidths=[18 * mm, 17 * mm, 25 * mm, 22 * mm, 18 * mm, 57 * mm, 22 * mm])
    report_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17212b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#b8c2c7')),
        ('FONTSIZE', (0, 0), (-1, -1), 7), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7f8')]),
    ]))
    story.append(report_table)
    document.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True,
                     download_name='detailed-sales-report.pdf')

# Employees Route
@main.route('/employees')
def employees():
    # Fetch all employees (you can adjust this query as per your database design)
    employees_data = User.query.all()  # Assuming you're using the User model for employees
    return render_template('employees.html', employees=employees_data)
# View Employee
@main.route('/employee/<int:user_id>')
def view_employee(user_id):
    employee = User.query.get_or_404(user_id)
    return render_template('view_employee.html', employee=employee)

# Edit Employee
@main.route('/edit_employee/<int:user_id>', methods=['GET', 'POST'])
def edit_employee(user_id):
    employee = User.query.get_or_404(user_id)
    if request.method == 'POST':
        employee.username = request.form['username']
        employee.email = request.form['email']
        db.session.commit()
        flash('Employee updated successfully!', 'success')
        return redirect(url_for('main.employees'))
    return render_template('edit_employee.html', employee=employee)

# Delete Employee
@main.route('/delete_employee/<int:user_id>', methods=['POST'])
def delete_employee(user_id):
    employee = User.query.get_or_404(user_id)
    db.session.delete(employee)
    db.session.commit()
    flash('Employee deleted successfully!', 'danger')
    return redirect(url_for('main.employees'))


@main.route('/sales/records')
def sales_records():
    search_term = (request.args.get('search', '') or '').strip()
    selected_document_type = (request.args.get('document_type', '') or '').lower().strip()
    if selected_document_type not in {'receipt', 'invoice', ''}:
        selected_document_type = ''

    sales_query = Sale.query.order_by(Sale.date.desc(), Sale.id.desc())
    if selected_document_type:
        sales_query = sales_query.filter(Sale.document_type == selected_document_type)

    if search_term:
        try:
            parsed_date = datetime.strptime(search_term, '%Y-%m-%d').date()
            sales_query = sales_query.filter(Sale.date == parsed_date)
        except ValueError:
            sales_query = sales_query.filter(Sale.customer_name.ilike(f'%{search_term}%'))

    sales = sales_query.all()
    total_amount = round(sum(sale.amount for sale in sales), 2)
    total_items = sum(sum(item.quantity for item in sale.items) for sale in sales)

    daily_totals = {}
    for sale in sales:
        daily_key = sale.date.isoformat()
        daily_totals[daily_key] = round(daily_totals.get(daily_key, 0) + sale.amount, 2)

    daily_sales = [
        {'date': day, 'amount': round(amount, 2)}
        for day, amount in sorted(daily_totals.items(), key=lambda item: item[0], reverse=True)
    ]

    return render_template(
        'sales_records.html',
        sales=sales,
        search_term=search_term,
        total_sales=total_amount,
        total_transactions=len(sales),
        total_items=total_items,
        daily_sales=daily_sales,
        selected_document_type=selected_document_type,
    )
