from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import forms
import user_management
import shelve
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from flask_socketio import SocketIO
import os
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from admin_calculation import calculate_date_range_data
from forms import PaymentForm, TicketListing
from payment import Payment, PaymentMethod, Ticket, Amount
from ticketmanager import TicketManager


app = Flask(__name__)
app.secret_key = 'your_secret_key'

socketio = SocketIO(app)

PROFILE_FOLDER = "static/profile_pics"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

user_management.initialize_admins()
USER_DB_PATH = 'users.db'
TICKET_DB_PATH = 'tickets.db'
SHELVE_DB = 'users.db'
EVENT_DB_PATH = "events.db"
VOUCHER_DB_PATH = 'vouchers.db'
CART_DB_PATH = 'cart.db'

def get_total_sales():
    try:
        with shelve.open("orders.db") as db:
            orders = db.get("orders", [])
            sales_data = {}
            for order in orders:
                date_str = order.get("date", "Unknown")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                total_amount = float(order.get("total_amount", 0))

                if date_obj in sales_data:
                    sales_data[date_obj] += total_amount
                else:
                    sales_data[date_obj] = total_amount

            # Sort sales data by date
            sorted_sales = sorted(sales_data.items())
            dates = [str(date) for date, _ in sorted_sales]
            total_sales = [amount for _, amount in sorted_sales]
            return dates, total_sales
    except Exception as e:
        print(f"Error fetching sales data: {e}")
        return [], []


# Dash App Initialization
dash_app = dash.Dash(__name__, server=app, url_base_pathname="/sales_dashboard/")

# Dash Layout
dash_app.layout = html.Div([
    html.H3("Total Sales Chart"),
    dcc.Graph(id="sales_chart"),
    dcc.Interval(
        id="update_interval",
        interval=5000,  # Update every 5 seconds
        n_intervals=0
    )
])


# Dash Callback for Real-Time Updates
@dash_app.callback(
    Output("sales_chart", "figure"),
    Input("update_interval", "n_intervals")
)
def update_chart(_):
    dates, sales = get_total_sales()

    figure = go.Figure(data=[
        go.Scatter(x=dates, y=sales, mode="lines+markers", name="Total Sales")
    ])

    figure.update_layout(title="Total Sales Over Time", xaxis_title="Date", yaxis_title="Sales ($)")
    return figure

@socketio.on("request_sales_update")
def send_sales_update():
    dates, sales = get_total_sales()
    socketio.emit("sales_update", {"dates": dates, "sales": sales})

def generate_user_id():
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        last_id = db.get("last_id", 0)
        new_id = last_id + 1
        db["last_id"] = new_id  # Save the new ID back
        return f"{new_id:04}"  # Format the ID as 4 digits


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate username is not empty
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for('admin_login'))

        # Validate password is not empty
        if not password:
            flash("Password is required.", "error")
            return redirect(url_for('admin_login'))

        # Use authenticate_admin from user_management to verify credentials
        if user_management.authenticate_admin(username, password):
            session['role'] = 'admin'
            session['user'] = username
            flash("Admin login successful!")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid admin credentials. Please try again.")

    return render_template('admin_login.html')


@app.route('/customer_login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate username is not empty
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for('customer_login'))

        # Validate username length is <= 20 characters
        if len(username) > 20:
            flash("Username cannot exceed 20 characters.", "error")
            return redirect(url_for('customer_login'))

        # Validate username contains only alphanumeric characters
        if not username.isalnum():
            flash("Username can only contain letters and numbers.", "error")
            return redirect(url_for('customer_login'))

        # Validate password is not empty
        if not password:
            flash("Password is required.", "error")
            return redirect(url_for('customer_login'))

        with shelve.open(SHELVE_DB) as db:
            customer = db.get(username)
            if customer and customer['password'] == password:
                session['role'] = 'customer'
                session['user'] = username
                session['user_id'] = customer['id']
                session['email'] = customer['email']
                session['points'] = customer['points']

                flash("Customer login successful!")
                return redirect(url_for('home'))  # Redirect customers to home

        flash("Invalid customer username or password. Please try again.")
    return render_template('customer_login.html')


# Admin Dashboard Route
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user' not in session or session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can access this page.")
        return redirect(url_for('customer_login'))

    stats = {
        'new_orders': 0,
        'on_hold': 0,
        'out_of_stock': 0,
        'total_orders': 0,
        'total_customers': 0,
        'new_customers': 0,
        'total_sales': 0,
        'recent_reviews': []
    }

    # Get user/customer data
    try:
        with shelve.open(SHELVE_DB) as db:
            # Count total customers (excluding admins)
            customers = [user for user in db.values()
                         if isinstance(user, dict) and user.get('role') == 'customer']
            stats['total_customers'] = len(customers)

            # Count new customers in last 7 days
            one_week_ago = datetime.now() - timedelta(days=7)
            stats['new_customers'] = len([c for c in customers
                                          if 'join_date' in c and
                                          datetime.strptime(c['join_date'], "%Y-%m-%d") > one_week_ago])
    except Exception as e:
        flash(f"Error loading customer data: {str(e)}")

    # Get ticket data
    try:
        with shelve.open(TICKET_DB_PATH) as db:
            tickets = db.get('tickets', [])
            # Count tickets with no available seats
            stats['out_of_stock'] = len([t for t in tickets if t.get('available_seats', 0) == 0])
    except Exception as e:
        flash(f"Error loading ticket data: {str(e)}")

    # Get order data
    try:
        with shelve.open('orders.db') as db:
            orders = db.get('orders', [])

            # Count orders by status
            stats['total_orders'] = len(orders)
            stats['new_orders'] = len([o for o in orders
                                       if o.get('status') == 'pending'])
            stats['on_hold'] = len([o for o in orders
                                    if o.get('status') == 'on_hold'])

            # Calculate total sales
            stats['total_sales'] = sum(float(order.get('total_amount', 0))
                                       for order in orders)

            # Get orders from last 7 days
            recent_orders = [o for o in orders
                             if datetime.strptime(o.get('date', ''), "%Y-%m-%d") > one_week_ago]
            stats['weekly_orders'] = len(recent_orders)
            stats['weekly_sales'] = sum(float(order.get('total_amount', 0))
                                        for order in recent_orders)
    except Exception as e:
        flash(f"Error loading order data: {str(e)}")

    # Get feedback/reviews
    try:
        with shelve.open('feedback.db') as db:
            feedback = db.get('feedback', [])
            # Get most recent reviews
            stats['recent_reviews'] = sorted(feedback,
                                             key=lambda x: x.get('date', ''),
                                             reverse=True)[:5]
    except Exception as e:
        flash(f"Error loading feedback data: {str(e)}")

    # Calculate percentage changes for stats
    try:
        previous_week_orders = len([o for o in orders
                                    if datetime.strptime(o.get('date', ''), "%Y-%m-%d") >
                                    (one_week_ago - timedelta(days=7))])
        stats['order_growth'] = calculate_percentage_change(previous_week_orders,
                                                            stats['weekly_orders'])

        previous_week_sales = sum(float(order.get('total_amount', 0))
                                  for order in orders
                                  if datetime.strptime(order.get('date', ''), "%Y-%m-%d") >
                                  (one_week_ago - timedelta(days=7)))
        stats['sales_growth'] = calculate_percentage_change(previous_week_sales,
                                                            stats['weekly_sales'])
    except Exception as e:
        flash(f"Error calculating growth rates: {str(e)}")

    # Get voucher usage statistics
    try:
        with shelve.open(VOUCHER_DB_PATH) as db:
            vouchers = db.get('vouchers', [])
            stats['voucher_stats'] = calculate_voucher_usage(vouchers)
    except Exception as e:
        flash(f"Error loading voucher data: {str(e)}")

    return render_template('admin_dashboard.html', stats=stats)


def calculate_percentage_change(old_value, new_value):
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 100 if new_value > 0 else 0
    return ((new_value - old_value) / old_value) * 100


def calculate_voucher_usage(vouchers):
    """Calculate voucher usage statistics"""
    total_usage = sum(v.get('times_used', 0) for v in vouchers)
    if total_usage == 0:
        return {
            'percentage_discount': 0,
            'fixed_discount': 0,
            'product_discount': 0
        }

    return {
        'percentage_discount': sum(v.get('times_used', 0) for v in vouchers
                                   if v.get('type') == 'percentage') / total_usage * 100,
        'fixed_discount': sum(v.get('times_used', 0) for v in vouchers
                              if v.get('type') == 'fixed') / total_usage * 100,
        'product_discount': sum(v.get('times_used', 0) for v in vouchers
                                if v.get('type') == 'product') / total_usage * 100
    }


@app.route('/admin/search')
def admin_search():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    query = request.args.get('q', '').lower()
    results = []

    if query:
        with shelve.open('tickets.db') as ticket_db, \
                shelve.open('orders.db') as order_db, \
                shelve.open('users.db') as user_db:

            # Search tickets
            tickets = ticket_db.get('tickets', [])
            for ticket in tickets:
                if query in ticket['name'].lower():
                    results.append({
                        'id': ticket['ticket_id'],
                        'type': 'ticket',
                        'details': f"{ticket['name']} - ${ticket['price']}"
                    })

            # Search orders
            orders = order_db.get('orders', [])
            for order in orders:
                if query in str(order['order_id']):
                    results.append({
                        'id': order['order_id'],
                        'type': 'order',
                        'details': f"Order #{order['order_id']} - {order['date']}"
                    })

    return jsonify({'results': results})


@app.route('/admin/export-tickets')
def admin_export_tickets():
    if session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can export tickets.")
        return redirect(url_for('customer_dashboard'))

    # Create a temporary file
    temp_file = f'temp_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    try:
        # Get tickets from shelve database
        with shelve.open(TICKET_DB_PATH) as ticket_db, \
                shelve.open(EVENT_DB_PATH) as event_db:

            tickets = ticket_db.get('tickets', [])
            events = event_db.get('events', [])
            event_dict = {event['event_id']: event for event in events}

            # Prepare data for Excel
            excel_data = []
            for ticket in tickets:
                event = event_dict.get(ticket.get('event_id'), {})
                excel_data.append({
                    'Ticket ID': ticket.get('ticket_id', ''),
                    'Event Name': ticket.get('name', ''),
                    'Price': ticket.get('price', ''),
                    'Type': ticket.get('type', ''),
                    'Row': ticket.get('seat_info', {}).get('row', ''),
                    'Seat Number': ticket.get('seat_info', {}).get('number', ''),
                    'Section': ticket.get('seat_info', {}).get('section', ''),
                    'Event Date': event.get('date_time', 'N/A'),
                    'Venue': event.get('venue_name', 'N/A')
                })

        # Create DataFrame
        df = pd.DataFrame(excel_data)

        # Create Excel file with formatting
        with pd.ExcelWriter(temp_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Tickets', index=False)

            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Tickets']

            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#0056b3',
                'font_color': 'white',
                'border': 1
            })

            # Format the header
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, len(str(value)) + 5)

        # Send the file
        return send_file(
            temp_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'tickets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )

    except Exception as e:
        flash(f"Error exporting tickets: {str(e)}")
        return redirect(url_for('admin_dashboard'))

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


# Customer Signup Route
@app.route('/customer_signup', methods=['GET', 'POST'])
def customer_signup():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Validate email is not empty and is valid format
        if not email:
            flash("Email is required.", "error")
            return redirect(url_for('customer_signup'))
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash("Invalid email address.", "error")
            return redirect(url_for('customer_signup'))

        # Validate username is not empty, is alphanumeric, and doesn't exceed 20 chars
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for('customer_signup'))
        elif not username.isalnum():
            flash("Username can only contain letters and numbers.", "error")
            return redirect(url_for('customer_signup'))
        elif len(username) > 20:
            flash("Username cannot exceed 20 characters.", "error")
            return redirect(url_for('customer_signup'))

        # Validate password is not empty and is at least 8 chars
        if not password:
            flash("Password is required.", "error")
            return redirect(url_for('customer_signup'))
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for('customer_signup'))

        with shelve.open(SHELVE_DB) as db:
            if username in db:
                flash("Username already exists. Please choose a different username.")
            elif email in db:
                flash("email already in use, Please try a different email")
            else:
                user_id = generate_user_id()
                db[username] = {
                    'email': email,
                    'password': password,
                    'id': user_id,
                    'role': 'customer',  # Explicitly set role
                    'points': 100,
                    'redeemed_vouchers': []  # List of redeemed vouchers
                }
                session['user'] = username
                session['user_id'] = user_id
                session['role'] = 'customer'
                flash("Sign-up successful! Please log in again.")
                return redirect(url_for('customer_login'))

    return render_template('customer_signup.html')


# Home Page
@app.route('/')
def home():
    try:
        # Get events data
        with shelve.open(EVENT_DB_PATH) as event_db:
            events = event_db.get('events', [])

        # Get tickets data for pricing
        with shelve.open(TICKET_DB_PATH) as ticket_db:
            tickets = ticket_db.get('tickets', [])

        # Create a lookup for minimum ticket price per event
        event_prices = {}
        for ticket in tickets:
            event_id = ticket.get('event_id')
            price = float(ticket.get('price', 0))
            if event_id not in event_prices or price < event_prices[event_id]:
                event_prices[event_id] = price

        # Add minimum price to each event and sort by date
        for event in events:
            event['min_price'] = event_prices.get(event['event_id'], 0)

        # Sort events by date and take the most recent 4
        sorted_events = sorted(events, key=lambda x: x['date_time'])[:4]

        return render_template('customer_dashboard.html',
                               recommended_events=sorted_events)

    except Exception as e:
        print(f"Error loading dashboard: {str(e)}")
        return render_template('customer_dashboard.html', recommended_events=[])


# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))  # Redirect to login after logout


@app.route('/manage_events', methods=['GET', 'POST'])
def manage_events():
    with shelve.open(EVENT_DB_PATH, writeback=True) as db:
        events = db.get('events', [])

        if request.method == 'POST':
            event_name = request.form['event_name']
            event_desc = request.form['event_desc']
            venue_name = request.form['venue_name']
            date_time = request.form['date_time']
            genre = request.form['genre']
            artist = request.form['artist']
            poster = request.files.get('poster')  # ✅ Handle file upload

            # Ensure a unique event ID
            event_id = len(events) + 1

            # Handle poster upload
            poster_path = None
            if poster and poster.filename:
                upload_folder = os.path.join("static", "uploads")  # ✅ Correct storage path
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)  # Create folder if missing

                filename = secure_filename(poster.filename)  # Prevent invalid filenames
                file_path = os.path.join(upload_folder, filename)
                poster.save(file_path)  # Save the file

                poster_path = f"uploads/{filename}"  # ✅ Store relative path (for use in templates)

            # Create the event object
            new_event = {
                'event_id': event_id,
                'event_name': event_name,
                'event_desc': event_desc,
                'venue_name': venue_name,
                'date_time': date_time,
                'genre': genre,
                'artist': artist,
                'poster_path': poster_path  # ✅ Store poster path
            }

            # Add to events list
            events.append(new_event)
            db['events'] = events

            flash("Event added successfully!")
            return redirect(url_for('add_ticket'))

    return render_template('manage_events.html', events=events)


@app.route('/add-event', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        # Collect form data
        event_name = request.form['event_name']
        event_desc = request.form['event_desc']
        venue_name = request.form['venue_name']
        date_time = request.form['date_time']
        genre = request.form['genre']
        artist = request.form['artist']
        poster = request.files.get('poster')  # FIXED: Ensure field name matches the form

        poster_path = None
        if poster and poster.filename != '':
            filename = os.path.join(app.config['UPLOAD_FOLDER'], poster.filename)
            poster.save(filename)  # Save to static/uploads/
            poster_path = f'uploads/{poster.filename}'  # Store relative path

        with shelve.open(EVENT_DB_PATH, writeback=True) as db:
            events = db.get('events', [])
            event_id = len(events) + 1  # Generate a new event ID
            new_event = {
                'event_id': event_id,
                'event_name': event_name,
                'event_desc': event_desc,
                'venue_name': venue_name,
                'date_time': date_time,
                'genre': genre,
                'artist': artist,
                'poster_path': poster_path  # Store correct relative path
            }
            events.append(new_event)
            db['events'] = events

        flash(f"Event '{event_name}' added successfully!")
        return redirect(url_for('manage_events'))

    return render_template('add_event.html')


@app.route('/delete-event/<int:event_id>', methods=['GET', 'POST'])
def delete_event(event_id):
    with shelve.open(EVENT_DB_PATH, writeback=True) as db:
        events = db.get('events', [])
        # Adjust to match your event key (e.g., event_id)
        event = next((e for e in events if e.get('event_id') == event_id), None)

        if not event:
            flash(f"Event with ID {event_id} does not exist.")
            return redirect(url_for('manage_events'))

        if request.method == 'POST':
            # Delete the event
            updated_events = [e for e in events if e.get('event_id') != event_id]
            db['events'] = updated_events
            flash(f"Event {event['event_name']} deleted successfully!")
            return redirect(url_for('manage_events'))

    return render_template('delete_event.html', event=event)


# View All Tickets
@app.route('/tickets', methods=['GET', 'POST'])
def tickets():
    if session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can view tickets.")
        return redirect(url_for('home'))

    try:
        search_query = request.form.get('searchinput', '').lower() if request.method == 'POST' else ''
        filter_type = request.form.get('filter_type', 'all')
        min_price = request.form.get('min_price', '')
        max_price = request.form.get('max_price', '')

        with shelve.open(TICKET_DB_PATH) as ticket_db:
            all_tickets = ticket_db.get('tickets', [])

        with shelve.open(EVENT_DB_PATH) as event_db:
            all_events = event_db.get('events', [])

        # Create event lookup dictionary
        event_dict = {event['event_id']: event for event in all_events}

        # Filter tickets based on search criteria
        filtered_tickets = []
        for ticket in all_tickets:
            event = event_dict.get(ticket['event_id'], {})
            ticket_price = float(ticket.get('price', 0))

            # Apply search filters
            matches_search = (
                    search_query in ticket['name'].lower() or
                    search_query in event.get('event_name', '').lower() or
                    search_query in event.get('artist', '').lower() or
                    search_query in event.get('genre', '').lower() or
                    search_query in ticket.get('type', '').lower()
            )

            matches_type = (
                    filter_type == 'all' or
                    filter_type == ticket.get('type', '').lower()
            )

            matches_price = True
            if min_price and max_price:
                try:
                    min_p = float(min_price)
                    max_p = float(max_price)
                    matches_price = min_p <= ticket_price <= max_p
                except ValueError:
                    pass

            if matches_search and matches_type and matches_price:
                filtered_tickets.append(ticket)

        return render_template('tickets.html',
                               tickets=filtered_tickets,
                               event_dict=event_dict,
                               search_query=search_query,
                               filter_type=filter_type,
                               min_price=min_price,
                               max_price=max_price)

    except Exception as e:
        flash(f"Error loading tickets: {str(e)}")
        return redirect(url_for('admin_dashboard'))


# Add New Concert Ticket
@app.route('/add_ticket', methods=['GET', 'POST'])
def add_ticket():
    with shelve.open(EVENT_DB_PATH) as event_db:
        events = event_db.get('events', [])

    with shelve.open(TICKET_DB_PATH, writeback=True) as ticket_db:
        tickets = ticket_db.get('tickets', [])

        if request.method == 'POST':
            event_id = request.form.get('event_id')
            seat_row = request.form.get('seat_row').upper()
            seat_section = request.form.get('seat_section').upper()
            start_seat_number = int(request.form.get('start_seat_number'))
            seat_count = int(request.form.get('seat_count'))
            ticket_type = request.form.get('type')
            price = request.form['price']

            errors = []

            if seat_row < 'A' or seat_row > 'Z':
                errors.append("Row must be between A-Z.")
            if seat_section < 'A' or seat_section > 'Z':
                errors.append("Section must be between A-Z.")
            if start_seat_number < 1 or start_seat_number > 10:
                errors.append("Starting seat number must be between 1 and 10.")
            try:
                price = float(price)
                if price <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append("Price must be a valid positive number.")

            event = next((event for event in events if event['event_id'] == int(event_id)), None)
            if not event:
                errors.append("Selected event is invalid.")

            taken_seats = [
                (ticket['seat_info']['row'], ticket['seat_info']['number'], ticket['seat_info']['section'])
                for ticket in tickets if ticket['event_id'] == int(event_id)
            ]

            new_tickets = []
            unavailable_seats = []
            row = ord(seat_row)  # Convert row to ASCII value
            section = ord(seat_section)  # Convert section to ASCII value
            seat_number = start_seat_number

            # Distribute tickets across multiple rows and sections if necessary
            for i in range(seat_count):
                # Check if the current seat is taken
                if (chr(row), seat_number, chr(section)) in taken_seats:
                    unavailable_seats.append(f"Seat {chr(row)}-{seat_number}-{chr(section)} is already taken.")
                else:
                    new_tickets.append({
                        "name": event['event_name'],
                        "event_desc": event.get('event_desc', 'No description available'),
                        "genre": event.get('genre', 'No genre available'),
                        'ticket_id': len(tickets) + len(new_tickets) + 1,
                        'event_id': int(event_id),
                        'seat_info': {
                            'number': seat_number,
                            'row': chr(row),
                            'section': chr(section)
                        },
                        'type': ticket_type,
                        'price': price,
                        'image_path': event.get('poster_path', None)
                    })

                # Update the seat number
                seat_number += 1
                if seat_number > 10:  # If seat number exceeds 10, move to the next row
                    seat_number = 1
                    row += 1  # Move to the next row

                if row > ord('Z'):  # If row exceeds Z, move to the next section
                    row = ord('A')
                    section += 1  # Move to the next section

                    if section > ord('Z'):  # If section exceeds Z, give an error or stop
                        errors.append("All sections are filled. Cannot add more tickets.")

            # Show any seat-specific errors but still allow adding available tickets
            if unavailable_seats:
                for error in unavailable_seats:
                    flash(error, "warning")

            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template('add_ticket.html', events=events)

            # Only update the tickets list after confirming the new tickets can be added
            if new_tickets:
                tickets.extend(new_tickets)
                ticket_db['tickets'] = tickets

            flash("Tickets added successfully!")
            return redirect(url_for('tickets'))

    return render_template('add_ticket.html', events=events)


@app.route('/edit_ticket/<int:ticket_id>', methods=['GET', 'POST'])
def edit_ticket(ticket_id):
    with shelve.open(TICKET_DB_PATH, writeback=True) as db:
        tickets = db.get('tickets', [])
        ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)

        if not ticket:
            flash("Ticket not found!")
            return redirect(url_for('tickets'))

        # Fetch event information to display the genre
        with shelve.open(EVENT_DB_PATH) as event_db:
            events = event_db.get('events', [])
            event = next((e for e in events if e['event_id'] == ticket['event_id']), None)

        if not event:
            flash("Event not found!")
            return redirect(url_for('tickets'))

        if request.method == 'POST':
            # Get form data (excluding genre)
            ticket['name'] = request.form['name']
            ticket['event_desc'] = request.form['event_desc']
            ticket['price'] = float(request.form['price'])
            ticket['type'] = request.form['type']

            # Save changes to database
            db['tickets'] = tickets
            flash("Ticket updated successfully!")

            # Redirect to the tickets page
            return redirect(url_for('tickets'))

    return render_template('edit_ticket.html', ticket=ticket, event=event)


# Delete Concert Ticket
@app.route('/delete-ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    with shelve.open(TICKET_DB_PATH, writeback=True) as db:
        tickets = db.get('tickets', [])

        # Find and remove the ticket by ticket_id
        tickets = [ticket for ticket in tickets if ticket['ticket_id'] != ticket_id]
        db['tickets'] = tickets

    flash("Ticket deleted successfully!")
    return redirect(url_for('tickets'))


# Feedback form page
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'user' not in session or session.get('role') != 'customer':
        flash("Please create an account first!")
        return redirect(url_for('customer_login'))

    if request.method == 'POST':
        name = session['user']  # Fetch name from session
        email = session['email']  # Fetch email from session
        event = request.form['event']
        rating = request.form['rating']
        comments = request.form['comments']

        feedback_entry = {
            'name': name,
            'email': email,
            'event': event,
            'rating': rating,
            'comments': comments
        }

        with shelve.open('feedback.db', writeback=True) as db:
            if 'feedback' not in db:
                db['feedback'] = []
            db['feedback'].append(feedback_entry)

        flash("Thank you for your feedback!")
        return redirect(url_for('confirmation'))

    return render_template('feedback.html')


# Handle feedback submission
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if 'user' not in session or session.get('role') != 'customer':
        flash("Only customers can submit feedback.")
        return redirect(url_for('customer_dashboard'))

    name = session['user']
    email = request.form['email']
    event = request.form['event']
    rating = request.form['rating']
    comments = request.form['comments']

    feedback_entry = {
        'name': name,
        'email': email,
        'event': event,
        'rating': rating,
        'comments': comments
    }

    with shelve.open('feedback.db', writeback=True) as db:
        if 'feedback' not in db:
            db['feedback'] = []
        db['feedback'].append(feedback_entry)

    flash("Thank you for your feedback!")
    return redirect(url_for('confirmation'))


# Confirmation page with feedback summary
@app.route('/confirmation')
def confirmation():
    with shelve.open('feedback.db') as db:
        feedback_list = db.get('feedback', [])
        latest_feedback = feedback_list[-1] if feedback_list else None
    return render_template('confirmation.html', feedback=latest_feedback)


@app.route('/view_customer_tickets')
def view_customer_tickets():
    if 'user' not in session:
        flash('Please log in to view your tickets', 'error')
        return redirect(url_for('customer_login'))

    try:
        ticket_manager = TicketManager()
        owned_tickets = ticket_manager.get_user_owned_tickets(session['user'])
        return render_template('view_customer_tickets.html', tickets=owned_tickets)
    except Exception as e:
        flash(f'Error loading tickets: {str(e)}', 'error')
        return redirect(url_for('main_page'))


@app.route('/view_feedback')
def view_feedback():
    if 'user' not in session or session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can view feedback.")
        return redirect(url_for('customer_dashboard'))

    rating_filter = request.args.get('rating')  # Get rating from query parameter

    with shelve.open('feedback.db') as db:
        feedback_entries = db.get('feedback', [])

        if rating_filter:  # Filter feedback if a rating is selected
            feedback_entries = [entry for entry in feedback_entries if entry['rating'] == rating_filter]

    return render_template('view_feedback.html', feedback_entries=feedback_entries, selected_rating=rating_filter)


@app.route('/restricted_page')
def restricted_page():
    if 'user' not in session or session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can access this page.")
        return redirect(url_for('customer_dashboard'))
    return "Restricted content for admins only."


def allowed_file(filename):
    """Check if uploaded file has a valid extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = session.get("user")
    if not user:
        flash("Please log in to access your profile.", "error")
        return redirect(url_for("customer_login"))

    with shelve.open(SHELVE_DB, writeback=True) as db:
        customer = db.get(user)
        if not customer:
            flash("User not found!", "error")
            return redirect(url_for("home"))

        # Handle profile picture upload
        if request.method == "POST" and "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{user}_{file.filename}")
                filepath = os.path.join(PROFILE_FOLDER, filename)
                os.makedirs(PROFILE_FOLDER, exist_ok=True)  # Ensure directory exists
                file.save(filepath)
                customer["profile_picture"] = filename  # Save new profile pic
                session['profile_pic'] = filename  # Update session
                db[user] = customer
                flash("Profile picture updated successfully!", "success")
                return redirect(url_for("profile"))
            else:
                flash("Invalid file type! Only images are allowed.", "error")

    # Retrieve user's vouchers
    with shelve.open("customer_vouchers") as vouchers_db:
        customer_vouchers = vouchers_db.get(user, [])

    return render_template(
        "profile.html",
        customer=customer,
        customer_vouchers=customer_vouchers,
    )


@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file uploaded!')
        return redirect(url_for('profile'))

    file = request.files['profile_pic']

    if file.filename == '':
        flash('No selected file!')
        return redirect(url_for('profile'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(PROFILE_FOLDER, filename)
        file.save(filepath)

        # Update the database and session
        user = session.get("user")
        if not user:
            flash('User not logged in!', 'error')
            return redirect(url_for('customer_login'))

        with shelve.open(SHELVE_DB, writeback=True) as db:
            customer = db.get(user)
            if customer:
                customer["profile_picture"] = filename  # Save filename in the database
                db[user] = customer
                session['profile_pic'] = filename  # Update session
                flash('Profile picture updated successfully!')
            else:
                flash('User not found!', 'error')

    return redirect(url_for('profile'))


@app.context_processor
def inject_profile_picture():
    if 'user' in session:
        with shelve.open(SHELVE_DB) as db:
            customer = db.get(session['user'])
            if customer:
                profile_picture = customer.get('profile_picture', 'default.png')
                return {'profile_picture': profile_picture}
    return {'profile_picture': None}


# ---------------------------------JOY'S CODE--------------------------------------------------
@app.route('/search', methods=['GET', 'POST'])
def search_tickets():
    db = shelve.open('tickets.db', 'c')

    try:
        tickets_dict = db['tickets']
    except:
        print('Error in retrieving tickets')
        tickets_dict = {}

    tickets = tickets_dict

    if request.method == 'POST':
        searched_tickets = []
        searchinput = request.form.get('searchinput')
        for i in range(0, len(tickets)):
            if searchinput in tickets[i]['name'].lower():
                searched_tickets.append(tickets[i])

        db.close()
        return render_template('search.html', tickets=searched_tickets)

    return render_template('search.html', tickets=tickets)


#Customer rewards page
@app.route("/rewards")
def rewards():
    user = session.get('user')  # Retrieve using username

    if not user:
        flash("You must be logged in to view rewards!", "error")
        return redirect(url_for('login'))

    # Get available vouchers
    with shelve.open(VOUCHER_DB_PATH) as vouchers_db:
        vouchers_list = vouchers_db.get("vouchers", [])
        print(f"Available Vouchers: {vouchers_list}")  # Debugging

        if not isinstance(vouchers_list, list):
            flash("Voucher data is corrupted or not properly stored.", "error")
            return redirect(url_for('home'))

        for voucher in vouchers_list:
            if not isinstance(voucher, dict):
                flash("Voucher data is corrupted or not properly stored.", "error")
                return redirect(url_for('home'))

    # Retrieve customer data from the session
    with shelve.open(SHELVE_DB) as db:
        customer = db.get(user)
        if not customer:
            flash("Customer not found.", "error")
            return redirect(url_for('home'))

    # Count how many times each voucher has been redeemed by this customer
    with shelve.open('customer_vouchers', writeback=True) as vouchers_db:
        customer_vouchers = vouchers_db.get(user, [])
        customer_vouchers_count = {}

        # Count the number of redemptions for each voucher
        for voucher in customer_vouchers:
            if isinstance(voucher, dict):  # Ensure we're dealing with a dictionary
                code = voucher.get('code', '')
                if code:
                    customer_vouchers_count[code] = customer_vouchers_count.get(code, 0) + 1

    # Pass both `customer_vouchers` and `customer_vouchers_count` to the template
    return render_template('rewards.html', vouchers=vouchers_list, customer_vouchers=customer_vouchers, customer_vouchers_count=customer_vouchers_count)


@app.route("/rewards/redeem/<code>")
def rewards_redeem(code):
    user = session.get('user')  # Retrieve using username

    if not user:
        flash("You must be logged in to redeem rewards!", "error")
        return redirect(url_for('login'))

    # Get the voucher details
    with shelve.open(VOUCHER_DB_PATH) as vouchers_db:
        vouchers_list = vouchers_db.get("vouchers", [])
        voucher = next((v for v in vouchers_list if v["code"] == code), None)

    if not voucher:
        flash("Voucher not found!", "error")
        return redirect(url_for('rewards'))

    # Retrieve customer using username
    with shelve.open(SHELVE_DB, writeback=True) as customer_db:
        customer = customer_db.get(user)  # Use username as key

        if not customer:
            flash("Customer not found!", "error")
            return redirect(url_for('rewards'))

        points_required = voucher.get("points_required")
        if points_required is None:
            flash("Voucher data is corrupted or missing required points.", "error")
            return redirect(url_for('rewards'))

        # Check if the user has already redeemed this voucher 5 times
        with shelve.open('customer_vouchers', writeback=True) as vouchers_db:
            # Retrieve the redeemed vouchers for the user, default to an empty list
            customer_vouchers = vouchers_db.get(user, [])

            # Ensure customer_vouchers is a list
            if not isinstance(customer_vouchers, list):
                customer_vouchers = []  # Initialize as an empty list if not a list

            # Count how many times the voucher has been redeemed
            redeemed_count = sum(1 for v in customer_vouchers if isinstance(v, dict) and v.get('code') == code)

            if redeemed_count >= 5:
                flash("You have already redeemed this voucher 5 times!", "error")
                return redirect(url_for('rewards'))

            if customer["points"] >= points_required:
                # Deduct points
                customer["points"] -= points_required
                customer_db[user] = customer  # Save updated customer

                # Update session to reflect the new points
                session['points'] = customer["points"]

                # Add the full voucher data to the customer's redeemed vouchers
                customer_vouchers.append({
                    'voucher_name': voucher['voucher_name'],
                    'description': voucher.get('terms_conditions', 'No description'),
                    'code': voucher['code'],
                    'discount': voucher['discount'],
                })
                vouchers_db[user] = customer_vouchers  # Save updated redeemed vouchers

                flash(f"Voucher {voucher['code']} redeemed successfully!", "success")
            else:
                flash("Not enough points to redeem this voucher!", "error")

    return redirect(url_for('rewards'))


@app.route('/add-voucher', methods=['GET', 'POST'])
def add_voucher():
    if request.method == 'POST':
        # Collect form data
        voucher_name = request.form.get('voucher_name', '').strip()
        discount = request.form.get('discount', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
        code = request.form.get('code', '').strip()
        terms_conditions = request.form.get('terms_conditions', '').strip()
        points_required = int(request.form.get('points_required', 0))
        # Validation
        errors = []

        # Validate Voucher Name
        if not voucher_name.strip():
            errors.append("Voucher name is required.")

        # Validate Points Required
        try:
            points_required = int(points_required)
            if points_required < 0:
                errors.append("Points required must be a non-negative number (0 or greater).")
        except ValueError:
            errors.append("Points required must be a valid number.")

        # Validate Discount (if it's a percentage or fixed value)
        try:
            discount = float(discount)
            if discount < 0 or discount > 100:  # Adjust if discount is percentage
                errors.append("Discount must be between 0 and 100.")
        except ValueError:
            errors.append("Discount must be a valid number.")

        # Validate Expiry Date
        if expiry_date:
            from datetime import datetime
            expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d')
            if expiry_date_obj < datetime.now():
                errors.append("Expiry date must be in the future.")
        else:
            errors.append("Expiry date is required.")

        # Validate Terms and Conditions (Optional but recommended)
        if not terms_conditions.strip():
            errors.append("Terms and conditions are required.")

        # If there are errors, show them to the user
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('add_voucher.html')

        # If no errors, proceed to save the voucher
        with shelve.open(VOUCHER_DB_PATH, writeback=True) as db:
            vouchers = db.get('vouchers', [])
            voucher_id = len(vouchers) + 1  # Generate a new voucher ID

            new_voucher = {
                'voucher_id': voucher_id,
                'voucher_name': voucher_name,
                'points_required': points_required,  # Store points required for redemption
                'discount': discount,
                'code' : code,
                'expiry_date': expiry_date,
                'terms_conditions': terms_conditions

            }
            vouchers.append(new_voucher)
            db['vouchers'] = vouchers

        flash(f"Voucher '{voucher_name}' added successfully! (Requires {points_required} points to redeem)")
        return redirect(url_for('add_voucher'))

    return render_template('add_voucher.html')


@app.route('/edit-voucher/<int:voucher_id>', methods=['GET', 'POST'])
def edit_voucher(voucher_id):
    with shelve.open(VOUCHER_DB_PATH, writeback=True) as db:
        vouchers = db.get('vouchers', [])
        voucher = next((v for v in vouchers if v['voucher_id'] == voucher_id), None)

        if not voucher:
            flash("Voucher not found.", 'error')
            return redirect(url_for('add_voucher'))

        if request.method == 'POST':
            # Collect updated data from form
            voucher_name = request.form.get('voucher_name', '').strip()
            discount = request.form.get('discount', '').strip()
            code = request.form.get('code', '').strip()
            expiry_date = request.form.get('expiry_date', '').strip()
            terms_conditions = request.form.get('terms_conditions', '').strip()
            points_required = int(request.form.get('points_required', 0))

            # Validation
            errors = []

            if not voucher_name:
                errors.append("Voucher name is required.")

            try:
                discount = float(discount)
                if discount < 0 or discount > 100:
                    errors.append("Discount must be between 0 and 100.")
            except ValueError:
                errors.append("Discount must be a valid number.")

            if expiry_date:
                from datetime import datetime
                expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d')
                if expiry_date_obj < datetime.now():
                    errors.append("Expiry date must be in the future.")
            else:
                errors.append("Expiry date is required.")

            if not terms_conditions:
                errors.append("Terms and conditions are required.")

            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('edit_voucher.html', voucher=voucher)

            # Update voucher details
            voucher['voucher_name'] = voucher_name
            voucher['discount'] = discount
            voucher['code'] = code
            voucher['expiry_date'] = expiry_date
            voucher['terms_conditions'] = terms_conditions
            voucher['points_required'] = points_required

            db['vouchers'] = vouchers
            flash(f"Voucher '{voucher_name}' updated successfully!")
            return redirect(url_for('add_voucher'))

    return render_template('edit_voucher.html', voucher=voucher)


@app.route('/delete-voucher/<int:voucher_id>', methods=['GET'])
def delete_voucher(voucher_id):
    with shelve.open(VOUCHER_DB_PATH, writeback=True) as db:
        vouchers = db.get('vouchers', [])
        voucher = next((v for v in vouchers if v['voucher_id'] == voucher_id), None)

        if not voucher:
            flash("Voucher not found.", 'error')
            return redirect(url_for('add_voucher'))

        # Remove the voucher
        vouchers.remove(voucher)
        db['vouchers'] = vouchers

        flash(f"Voucher '{voucher['voucher_name']}' deleted successfully!")
        return redirect(url_for('view_vouchers'))


@app.route('/view-vouchers', methods=['GET'])
def view_vouchers():
    with shelve.open(VOUCHER_DB_PATH) as db:
        # Fetch all vouchers from the database
        vouchers = db.get('vouchers', [])

    return render_template('view_vouchers.html', vouchers=vouchers)


@app.route("/main_page", methods=["GET", "POST"])
def main_page():
    # Retrieve all tickets
    with shelve.open(TICKET_DB_PATH) as ticket_db:
        all_tickets = ticket_db.get("tickets", [])

    # Retrieve all events and map them by event_id
    with shelve.open(EVENT_DB_PATH) as event_db:
        all_events = event_db.get("events", [])

    event_dict = {int(event["event_id"]): event for event in all_events}

    # Add event details to tickets
    for ticket in all_tickets:
        ticket["event_desc"] = event_dict.get(ticket["event_id"], {}).get("event_desc", "No description")
        ticket["image_path"] = event_dict.get(ticket["event_id"], {}).get("poster_path", "default.jpg")

    # Handle search functionality
    search_results = all_tickets  # Default to all tickets

    if request.method == "POST":  # Handle search
        search_input = request.form.get("searchinput", "").lower()
        search_results = [
            ticket
            for ticket in all_tickets
            if search_input in ticket["name"].lower()
        ]

    # Return the results (including the "No results found" message if necessary)
    if not search_results:
        flash("No results found", "warning")

    return render_template("main.html", tickets=search_results)


@app.route("/add_to_cart/<int:ticket_id>", methods=["POST"])
def add_to_cart(ticket_id):
    # Fetch tickets from the database
    with shelve.open(TICKET_DB_PATH) as ticket_db:
        all_tickets = ticket_db.get("tickets", [])

    # Find the ticket to add
    ticket_to_add = next((ticket for ticket in all_tickets if ticket["ticket_id"] == ticket_id), None)
    if ticket_to_add:
        ticket_to_add["price"] = float(ticket_to_add["price"])  # Convert price to float

    if ticket_to_add:
        # Initialize the cart if it doesn't exist in the session
        if "cart" not in session:
            session["cart"] = []

        # Check if the ticket is already in the cart
        cart = session["cart"]
        for item in cart:
            if item["ticket_id"] == ticket_id:
                item["quantity"] += 1  # Increment quantity if the ticket is already in the cart
                break
        else:
            # Add the ticket to the cart with a quantity of 1 if it's not in the cart
            ticket_to_add["quantity"] = 1
            cart.append(ticket_to_add)

        # Update the session
        session["cart"] = cart
        flash(f"{ticket_to_add['name']} has been added to your cart.", "success")
    else:
        flash("Ticket not found.", "error")

    # Redirect to the cart page to view the updated cart
    return redirect(url_for('view_cart'))


@app.route('/cart')
def cart_page():
    cart = session.get('cart', {})
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    return render_template('cart.html', cart=cart, total=total)


@app.route("/view_cart", methods=["GET", "POST"])
def view_cart():
    if request.method == "POST":
        ticket_id = int(request.form.get("ticket_id"))
        action = request.form.get("action")
        cart = session.get("cart", [])

        if action == "update_quantity":
            new_quantity = int(request.form.get("quantity"))

            # Update quantity and remove item if quantity is 0
            for item in cart:
                if item["ticket_id"] == ticket_id:
                    if new_quantity == 0:
                        cart.remove(item)
                        flash(f"{item['name']} has been removed from your cart.", "warning")
                    else:
                        item["quantity"] = new_quantity
                    break  # Exit loop after finding the item

        elif action == "delete_ticket":
            # Find the ticket before removing it
            removed_ticket = next((item for item in cart if item["ticket_id"] == ticket_id), None)

            # Remove ticket from the cart
            cart = [item for item in cart if item["ticket_id"] != ticket_id]

            if removed_ticket:
                flash(f"{removed_ticket['name']} has been removed from your cart.", "success")
            else:
                flash("Ticket has been removed from your cart.", "success")

        # Update session and ensure changes are saved
        session["cart"] = cart
        session.modified = True

    # Retrieve the updated cart
    cart = session.get("cart", [])

    # Recalculate total, ensuring proper rounding
    total = round(sum(float(item['price']) * int(item['quantity']) for item in cart), 2)

    return render_template("cart.html", cart=cart, total=total)


@app.route('/ticket_listing', methods=['GET', 'POST'])
def ticket_listing():
    if 'user' not in session:
        flash('Please log in to list tickets', 'error')
        return redirect(url_for('customer_login'))

    ticket_manager = TicketManager()

    try:
        # Get user's owned tickets
        owned_tickets = ticket_manager.get_user_owned_tickets(session['user'])

        if request.method == 'POST':
            ticket_id = request.form.get('ticket')
            listing_price = float(request.form.get('amount'))
            listing_type = request.form.get('sales_type')

            # List the ticket for resale
            listed_ticket = ticket_manager.list_ticket_for_resale(
                ticket_id=ticket_id,
                username=session['user'],
                listing_price=listing_price,
                listing_type=listing_type
            )

            flash('Ticket listed successfully!', 'success')
            # Redirect to the confirmation-secondary page
            return redirect(url_for('confirmation_secondary', ticket_id=ticket_id))

        # Pass seat details to the template
        return render_template('ticket_listing.html',
                               owned_tickets=owned_tickets,
                               ticket_listing=forms.TicketListing())

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('main_page'))


@app.route('/checkout_primary/<int:ticket_id>', methods=['GET', 'POST'])
def checkout_primary(ticket_id):
    try:
        # Get cart data from session
        cart = session.get("cart", [])
        if not cart:
            flash("Your cart is empty.", "warning")
            return redirect(url_for('main_page'))

        # Get ticket details from the shelve database
        with shelve.open(TICKET_DB_PATH, 'r') as db:
            tickets = db.get('tickets', [])
            ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)

            if not ticket:
                flash("Ticket not found.", "error")
                return redirect(url_for('main_page'))

        # Calculate prices using the Amount class
        try:
            price = float(ticket['price'])
            amount = Amount(
                base_price=price,
                platform_fee=price * 0.02,  # 2% platform fee
                GST=price * 0.09,  # 9% GST
                total=price * 1.11  # Total with fees
            )
        except (ValueError, KeyError) as e:
            app.logger.error(f"Error calculating price: {str(e)}")
            flash("Error calculating the price. Please try again.", "error")
            return redirect(url_for('main_page'))

        # Get event details if needed
        try:
            with shelve.open(EVENT_DB_PATH, 'r') as event_db:
                events = event_db.get('events', [])
                event = next((e for e in events if e['event_id'] == ticket['event_id']), None)
        except Exception as e:
            app.logger.error(f"Error accessing events database: {str(e)}")
            event = None

        # Prepare data for template
        ticket_data = {
            'ticket_id': ticket['ticket_id'],
            'name': ticket['name'],
            'seat_info': ticket['seat_info'],
            'type': ticket['type'],
            'event_name': event['event_name'] if event else 'Unknown Event',
            'price': amount.get_total(),
            'base_price': amount.get_base_price(),
            'platform_fee': amount.get_platform_fee(),
            'GST': amount.get_GST(),
        }

        return render_template(
            'checkout_primary.html',
            ticket=ticket_data,
            amount=amount,
            cart=cart,
            ticket_id=ticket_id
        )

    except Exception as e:
        app.logger.error(f"Error in checkout_primary: {str(e)}")
        flash(f"An error occurred during checkout. Please try again.{str(e)}", "error")
        return redirect(url_for('main_page'))


@app.route('/checkout_secondary/<int:ticket_id>', methods=['GET', 'POST'])
def checkout_secondary(ticket_id):
    try:
        # Get cart data from session
        cart = session.get("cart", [])
        if not cart:
            flash("Your cart is empty.", "warning")
            return redirect(url_for('main_page'))

        # Get ticket details from the shelve database
        with shelve.open(TICKET_DB_PATH, 'r') as db:
            tickets = db.get('tickets', [])
            ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)

            if not ticket:
                flash("Ticket not found.", "error")
                return redirect(url_for('main_page'))

        # Calculate prices using the Amount class
        try:
            price = float(ticket['price'])
            amount = Amount(
                base_price=price,
                platform_fee=price * 0.02,  # 2% platform fee
                GST=price * 0.09,  # 9% GST
                total=price * 1.11  # Total with fees
            )
        except (ValueError, KeyError) as e:
            app.logger.error(f"Error calculating price: {str(e)}")
            flash("Error calculating the price. Please try again.", "error")
            return redirect(url_for('main_page'))

        # Get event details if needed
        try:
            with shelve.open(EVENT_DB_PATH, 'r') as event_db:
                events = event_db.get('events', [])
                event = next((e for e in events if e['event_id'] == ticket['event_id']), None)
        except Exception as e:
            app.logger.error(f"Error accessing events database: {str(e)}")
            event = None

        # Prepare data for template
        ticket_data = {
            'ticket_id': ticket['ticket_id'],
            'name': ticket['name'],
            'seat_info': ticket['seat_info'],
            'type': ticket['type'],
            'event_name': event['event_name'] if event else 'Unknown Event',
            'price': amount.get_total(),
            'base_price': amount.get_base_price(),
            'platform_fee': amount.get_platform_fee(),
            'GST': amount.get_GST(),
        }

        return render_template(
            'checkout_secondary.html',
            ticket=ticket_data,
            amount=amount,
            cart=cart,
            ticket_id=ticket_id
        )

    except Exception as e:
        app.logger.error(f"Error in checkout_secondary: {str(e)}")
        flash(f"An error occurred during checkout. Please try again.{str(e)}", "error")
        return redirect(url_for('main_page'))


@app.route('/payment_primary/<int:ticket_id>', methods=['GET', 'POST'])
def payment_primary(ticket_id):
    # Store ticket_id in session for consistency
    session['ticket_id'] = ticket_id

    if request.method == 'POST':
        # Validate required form fields
        name = request.form.get('name')
        email = request.form.get('email')
        contact = request.form.get('contact')
        payment_method = request.form.get('payment_method')

        if not all([name, email, contact, payment_method]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('payment_primary', ticket_id=ticket_id))

        # Store the payment information in session
        session['payment_info'] = {
            'name': name,
            'email': email,
            'contact': contact,
            'payment_method': payment_method
        }

        # Redirect to confirmation page
        return redirect(url_for('confirmation_primary'))

    # GET request: Retrieve ticket details
    with shelve.open(TICKET_DB_PATH) as db:
        tickets = db.get('tickets', [])
        ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)

        if not ticket:
            flash('Ticket not found', 'error')
            return redirect(url_for('main_page'))

        amount = Amount(
            base_price=float(ticket['price']),
            platform_fee=float(ticket['price']) * 0.02,
            GST=float(ticket['price']) * 0.09,
            total=float(ticket['price']) * 1.11
        )

        return render_template('payment_primary.html',
                               ticket=ticket,
                               amount=amount)


@app.route('/payment_secondary/<int:ticket_id>', methods=['GET', 'POST'])
def payment_secondary(ticket_id):
    try:
        with shelve.open('tickets.db', 'c') as db:
            cart = session.get('cart', [])
            detailed_cart = []
            for item in cart:
                if item:
                    item_ticket_id = str(item['ticket_id'])
                    ticket_details = db.get(item_ticket_id)
                    if ticket_details:
                        detailed_cart.append(ticket_details)

                        if request.method == 'POST':
                            card_number = request.form.get('card_number', '')
                            expiry_date = request.form.get('expiry_date', '')
                            cvv = request.form.get('cvv', '')
                            payment_method = PaymentMethod(card_number,
                                                           expiry_date,
                                                           cvv)
                            for ticket in detailed_cart:
                                ticket['card_number'] = payment_method.get_card_number()
                                ticket['expiry_date'] = payment_method.get_expiry_date()
                                ticket['cvv'] = payment_method.get_cvv()

                                db[ticket['ticket_id']] = ticket

                            flash('Transaction successful!', 'success')
                            return redirect(url_for('payment_primary', ticket_id=ticket_id))
                        else:
                            flash(f'Ticket ID {ticket_id} not found.', 'danger')
                            return redirect(url_for('main', ticket_id=ticket_id))
    except Exception as e:
        flash(f'Error going through transaction: {str(e)}', 'danger')
        return render_template('payment_primary.html', detailed_cart=detailed_cart)
    return render_template('payment_secondary.html')


@app.route('/confirmation_primary', methods=['GET', 'POST'])
def confirmation_primary():
    if 'user' not in session:
        flash('Please log in to complete your purchase')
        return redirect(url_for('customer_login'))

    ticket_id = session.get('ticket_id')
    if not ticket_id:
        flash('No ticket selected', 'error')
        return redirect(url_for('main_page'))

    ticket_manager = TicketManager()

    if request.method == 'POST':
        try:
            # Process the purchase and get ticket details
            purchased_ticket = ticket_manager.process_ticket_purchase(ticket_id, session['user'])

            # Remove ticket from session
            session.pop('ticket_id', None)
            session.modified = True

            flash('Ticket purchased successfully!', 'success')

            return redirect(url_for('confirmation_primary', ticket_id=ticket_id))

        except Exception as e:
            flash(f'Error processing purchase: {str(e)}', 'error')
            return redirect(url_for('main_page'))

    try:
        with shelve.open(TICKET_DB_PATH) as db:
            tickets = db.get('tickets', [])
            ticket = next((t for t in tickets if t['ticket_id'] == ticket_id), None)

            if not ticket:
                flash('Ticket not found', 'error')
                return redirect(url_for('main_page'))

            amount = Amount(
                base_price=float(ticket['price']),
                platform_fee=float(ticket['price']) * 0.02,
                GST=float(ticket['price']) * 0.09,
                total=float(ticket['price']) * 1.11
            )

            return render_template('confirmation_primary.html',
                                   ticket=ticket,
                                   amount=amount,
                                   payment_info=session.get('payment_info', {}),
                                   seat_number=ticket.get('seat_number'),
                                   row=ticket.get('row'),
                                   section=ticket.get('section'))

    except Exception as e:
        flash(f'Error loading confirmation page: {str(e)}', 'error')
        return redirect(url_for('main_page'))


@app.route('/confirmation_secondary/<ticket_id>')
def confirmation_secondary(ticket_id):
    if 'user' not in session:
        flash('Please log in to view this page', 'error')
        return redirect(url_for('customer_login'))

    ticket_manager = TicketManager()

    try:
        # Fetch the listed ticket details
        listed_ticket = ticket_manager.get_ticket_details(ticket_id)

        if not listed_ticket:
            flash('Ticket not found', 'error')
            return redirect(url_for('main_page'))

        return render_template('confirmation_secondary.html', ticket=listed_ticket)

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('main_page'))


#==============================Zess========================
@app.route('/events')
def events():
    try:
        # Get events from events.db
        with shelve.open(EVENT_DB_PATH) as event_db:
            events = event_db.get('events', [])

        # Get tickets from tickets.db to get pricing info
        with shelve.open(TICKET_DB_PATH) as ticket_db:
            tickets = ticket_db.get('tickets', [])

        # Create a lookup for minimum ticket price per event
        event_prices = {}
        for ticket in tickets:
            event_id = ticket.get('event_id')
            price = float(ticket.get('price', 0))
            if event_id not in event_prices or price < event_prices[event_id]:
                event_prices[event_id] = price

        # Add minimum price to each event
        for event in events:
            event['min_price'] = event_prices.get(event['event_id'], 0)

        return render_template('event_list.html', events=events)
    except Exception as e:
        flash(f"Error loading events: {str(e)}")
        return redirect(url_for('home'))


@app.route('/event/<int:event_id>')
def event_detail(event_id):
    try:
        # Get event details
        with shelve.open(EVENT_DB_PATH) as event_db:
            events = event_db.get('events', [])
            event = next((e for e in events if e['event_id'] == event_id), None)

            if not event:
                flash("Event not found.")
                return redirect(url_for('events'))

        # Get tickets for this event
        with shelve.open(TICKET_DB_PATH) as ticket_db:
            all_tickets = ticket_db.get('tickets', [])
            event_tickets = [t for t in all_tickets if t['event_id'] == event_id]

        return render_template('events.html', event=event, tickets=event_tickets)
    except Exception as e:
        flash(f"Error loading event details: {str(e)}")
        return redirect(url_for('events'))


@app.route('/about_us')
def about_us():
    return render_template('about_us.html')


if __name__ == '__main__':
    app.run(debug=True)
