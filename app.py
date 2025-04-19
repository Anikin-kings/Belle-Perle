import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, session, flash, redirect, url_for
from flask_wtf import CSRFProtect

app = Flask(__name__)
# Use environment variables for production secrets; note that these should be set in your production environment.
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['SESSION_COOKIE_SECURE'] = True   # Ensure cookies are sent over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True   # Mitigate the risk of client side script accessing the cookie

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# The dashboard password for login
PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'amina123bp')

def init_db():
    """Initialize the database and create tables if they don't exist."""
    with sqlite3.connect('client_data.db', timeout=10) as conn:
        conn.execute('PRAGMA journal_mode=WAL;')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS customers 
                     (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, email TEXT, 
                      waist REAL, wrist REAL, notes TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS sales 
                     (id INTEGER PRIMARY KEY, customer_id INTEGER, item TEXT, 
                      price REAL, date TEXT)''')
        conn.commit()

@app.route('/')
def home():
    """Home route."""
    return "Welcome to Belle Perle!"

@app.route('/customer-entry', methods=['GET', 'POST'])
def customer_entry():
    """Route for adding customer details."""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            phone = request.form.get('phone')
            email = request.form.get('email')
            waist = request.form.get('waist')
            wrist = request.form.get('wrist')
            notes = request.form.get('notes')

            # Convert waist and wrist values safely to float, if provided.
            waist_value = float(waist) if waist else None
            wrist_value = float(wrist) if wrist else None

            # Basic server-side field validation for required fields.
            if not name or not phone or not email:
                flash("Name, phone, and email are required.")
                return redirect(url_for('customer_entry'))

            with sqlite3.connect('client_data.db', timeout=10) as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO customers (name, phone, email, waist, wrist, notes) VALUES (?, ?, ?, ?, ?, ?)", 
                    (name, phone, email, waist_value, wrist_value, notes)
                )
                conn.commit()
            flash("Thank you! Customer details saved successfully.")
            return redirect(url_for('customer_entry'))
        except ValueError:
            flash("Error: Invalid waist or wrist value.")
            return redirect(url_for('customer_entry'))
        except sqlite3.Error as e:
            app.logger.error(f"Database error: {e}")
            flash("An error occurred. Please try again later.")
            return redirect(url_for('customer_entry'))
    return render_template('customer_entry.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    """Route for the dashboard."""
    if request.method == 'POST':
        # Handle login attempts
        if 'password' in request.form:
            if request.form['password'] == PASSWORD:
                session['authenticated'] = True
                flash("Logged in successfully!")
            else:
                flash("Incorrect password.")
            return redirect(url_for('dashboard'))
        # Handle adding a new sale, only if already authenticated
        elif 'item' in request.form and session.get('authenticated', False):
            try:
                customer_id = int(request.form['customer_id'])
                item = request.form.get('item')
                price = float(request.form.get('price'))
                # Using current date for the sale entry
                date = datetime.now().strftime("%Y-%m-%d")

                if not item or not price:
                    flash("Item and price are required.")
                    return redirect(url_for('dashboard'))

                with sqlite3.connect('client_data.db', timeout=10) as conn:
                    c = conn.cursor()
                    c.execute("SELECT id FROM customers WHERE id = ?", (customer_id,))
                    if c.fetchone():
                        c.execute(
                            "INSERT INTO sales (customer_id, item, price, date) VALUES (?, ?, ?, ?)", 
                            (customer_id, item, price, date)
                        )
                        conn.commit()
                        flash("Sale added successfully!")
                    else:
                        flash("Error: Invalid Customer ID")
            except ValueError:
                flash("Error: Invalid price or customer ID value.")
            except sqlite3.Error as e:
                app.logger.error(f"Database error: {e}")
                flash("An error occurred. Please try again later.")
            return redirect(url_for('dashboard'))

    authenticated = session.get('authenticated', False)
    customers = []
    sales = []
    total_sales = 0.0
    if authenticated:
        with sqlite3.connect('client_data.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM customers")
            customers = c.fetchall()
            c.execute("SELECT s.id, c.name, s.item, s.price, s.date FROM sales s JOIN customers c ON s.customer_id = c.id")
            sales = c.fetchall()
            total_sales = sum(sale[3] for sale in sales)
    return render_template('dashboard.html', authenticated=authenticated, customers=customers, sales=sales, total_sales=total_sales)

@app.route('/logout')
def logout():
    """Route to log out the user."""
    session.pop('authenticated', None)
    flash("Logged out successfully.")
    return redirect(url_for('dashboard'))

@app.route('/clear-sales', methods=['POST'])
def clear_sales():
    """Route to clear all sales records."""
    if not session.get('authenticated', False):
        flash("You must be logged in to clear sales.")
        return redirect(url_for('dashboard'))
    try:
        with sqlite3.connect('client_data.db', timeout=10) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM sales")
            conn.commit()
        flash("All sales records have been cleared.")
    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
        flash("An error occurred while clearing sales.")
    return redirect(url_for('dashboard'))

@app.route('/delete-customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    """Route to delete a customer and their associated sales."""
    if not session.get('authenticated', False):
        flash("You must be logged in to delete customers.")
        return redirect(url_for('dashboard'))
    try:
        with sqlite3.connect('client_data.db', timeout=10) as conn:
            c = conn.cursor()
            # First delete related sales then the customer record.
            c.execute("DELETE FROM sales WHERE customer_id = ?", (customer_id,))
            c.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            conn.commit()
        flash("Customer and their sales records deleted successfully.")
    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
        flash("An error occurred while deleting the customer.")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    # Note: In production, use a production-ready server (e.g., Gunicorn) and set debug=False.
    app.run(debug=True)
