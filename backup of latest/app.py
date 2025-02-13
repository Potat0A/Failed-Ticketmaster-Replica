from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import user_management
import shelve
import os
import pandas as pd
import re
from datetime import datetime
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

user_management.initialize_admins()
USER_DB_PATH = 'users.db'
TICKET_DB_PATH = 'tickets.db'
SHELVE_DB = 'users.db'
EVENT_DB_PATH = "events.db"
VOUCHER_DB_PATH = 'vouchers.db'
CART_DB_PATH = 'cart.db'


def generate_user_id():
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        last_id = db.get("last_id", 0)
        new_id = last_id + 1
        db["last_id"] = new_id  # Save the new ID back
        return f"{new_id:04}"  # Format the ID as 4 digits


# Role Selection Page
@app.route('/')
def index():
    return redirect(url_for('home'))


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
        return redirect(url_for('customer_dashboard'))
    return render_template('admin_dashboard.html')


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
                    'points': 0,
                    'redeemed_vouchers': []  # List of redeemed vouchers
                }
                session['user'] = username
                session['user_id'] = user_id
                session['role'] = 'customer'
                flash("Sign-up successful! Please log in again.")
                return redirect(url_for('customer_login'))

    return render_template('customer_signup.html')


# Home Page
@app.route('/home')
def home():
    return render_template('customer_dashboard.html')


# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('user_id', None)
    flash("You have been logged out.")
    return redirect(url_for('customer_login'))  # Redirect to login after logout


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
            return redirect(url_for('manage_events'))

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
        return redirect(url_for('customer_dashboard'))

    with shelve.open(TICKET_DB_PATH) as ticket_db:
        all_tickets = ticket_db.get('tickets', [])  # Load tickets from shelve

    with shelve.open(EVENT_DB_PATH) as event_db:
        all_events = event_db.get('events', [])  # Load events from shelve

    # Create a dictionary to map event_id to event data for easy access
    event_dict = {event['event_id']: event for event in all_events}

    if request.method == 'POST':
        searched_tickets = []
        searchinput = request.form.get('searchinput')
        for i in range(0, len(all_tickets)):
            if searchinput in all_tickets[i]['name']:
                searched_tickets.append(all_tickets[i])

        return render_template('tickets.html',  tickets=searched_tickets, event_dict=event_dict)

    # Pass the event dictionary instead of the entire events list
    return render_template('tickets.html', tickets=all_tickets, event_dict=event_dict)


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
            if start_seat_number < 1 or start_seat_number + seat_count - 1 > 10:
                errors.append("Each row can only have 10 seats.")
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
            for i in range(seat_count):
                seat_number = start_seat_number + i
                if (seat_row, seat_number, seat_section) in taken_seats:
                    errors.append(f"Seat {seat_row}-{seat_number}-{seat_section} is already taken.")
                else:
                    new_tickets.append({
                        "name": event['event_name'],
                        "event_desc": event.get('event_desc', 'No description available'),
                        "genre": event.get('genre', 'No genre available'),
                        'ticket_id': len(tickets) + len(new_tickets) + 1,
                        'event_id': int(event_id),
                        'seat_info': {
                            'number': seat_number,
                            'row': seat_row,
                            'section': seat_section
                        },
                        'type': ticket_type,
                        'price': price,
                        'image_path': event.get('poster_path', None)
                    })

            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template('add_ticket.html', events=events)

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
            ticket['price'] = request.form['price']
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
    if session.get('role') != 'customer':
        flash("Unauthorized access! Only customers can submit feedback.")
        return redirect(url_for('customer_dashboard'))

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
    if 'user' not in session or session.get('role') != 'customer':
        flash("Unauthorized access!")
        return redirect(url_for('customer_dashboard'))

    # Replace with actual logic to fetch tickets for the logged-in customer
    customer_id = session.get('user_id')
    with shelve.open(TICKET_DB_PATH) as db:
        tickets = [
            ticket for ticket in db.get('tickets', [])
            if ticket.get('customer_id') == customer_id
        ]

    return render_template('view_customer_tickets.html', tickets=tickets)


@app.route('/view_feedback')
def view_feedback():
    if 'user' not in session or session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can view feedback.")
        return redirect(url_for('customer_dashboard'))

    with shelve.open('feedback.db') as db:
        feedback_entries = db.get('feedback', [])

    return render_template('view_feedback.html', feedback_entries=feedback_entries)


@app.route('/restricted_page')
def restricted_page():
    if 'user' not in session or session.get('role') != 'admin':
        flash("Unauthorized access! Only admins can access this page.")
        return redirect(url_for('customer_dashboard'))
    return "Restricted content for admins only."

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
@app.route('/rewards')
def rewards():
    # Initialize vouchers if they don't exist
    with shelve.open("vouchers") as db:
        if "vouchers" not in db:
            vouchers = [
                {"discount": 8, "points": 80, "code": "890", "description": "Buy one get one 50% off"}
            ]
            db["vouchers"] = vouchers
            print("Vouchers initialized in the database.")

    # Retrieve vouchers from the database
    with shelve.open("vouchers") as db:
        vouchers = db.get("vouchers", [])

    # Retrieve the current customer's data
    current_customer = None
    user_id = session.get('user_id')
    if user_id:
        with shelve.open(SHELVE_DB) as db:
            for customer_name in db.keys():
                customer = db.get(customer_name)
                if isinstance(customer, dict) and customer.get("id") == user_id:
                    current_customer = customer
                    break

    # Retrieve customer-specific vouchers
    with shelve.open('customer_vouchers') as db:
        customer_vouchers = db.get(str(user_id), [])  # Ensure user_id is a string for the key

    return render_template('rewards.html', vouchers=vouchers,
                           customer=current_customer, customer_vouchers=customer_vouchers)


@app.route("/rewards/redeem/<code>")
def rewards_redeem(code):
    customer_id = session.get('user_id')

    with shelve.open('vouchers') as db:
        for voucher in db["vouchers"]:
            if voucher["code"] == code:
                current_voucher = voucher

    with shelve.open('customer_vouchers') as db:
        customer_vouchers = db.get(customer_id, [])
        customer_vouchers.append(current_voucher)
        db[customer_id] = customer_vouchers

    with shelve.open(SHELVE_DB) as db:
        customer_id = session.get('user_id')
        for customer_id in db.keys():
            customer = db.get(customer_id)
            if customer["id"] == customer_id:
                customer["points"] -= current_voucher["points"]
                db[customer_id] = customer

    return redirect(url_for('rewards'))


# #ADMIN
@app.route('/add-voucher', methods=['GET', 'POST'])
def add_voucher():
    if request.method == 'POST':
        # Collect form data
        voucher_name = request.form.get('voucher_name', '').strip()
        discount = request.form.get('discount', '').strip()
        expiry_date = request.form.get('expiry_date', '').strip()
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

            # Create a new voucher with points_required instead of voucher_desc
            new_voucher = {
                'voucher_id': voucher_id,
                'voucher_name': voucher_name,
                'points_required': points_required,  # Store points required for redemption
                'discount': discount,
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
        return redirect(url_for('add_voucher'))


@app.route('/view-vouchers', methods=['GET'])
def view_vouchers():
    with shelve.open(VOUCHER_DB_PATH) as db:
        # Fetch all vouchers from the database
        vouchers = db.get('vouchers', [])

    return render_template('view_vouchers.html', vouchers=vouchers)


@app.route("/main_page", methods=["GET", "POST"])
def main_page():
    with shelve.open(TICKET_DB_PATH) as ticket_db:
        all_tickets = ticket_db.get("tickets", [])  # Retrieve all tickets

    search_results = all_tickets  # Default to all tickets

    if request.method == "POST":  # Handle search
        search_input = request.form.get("searchinput", "").lower()
        search_results = [
            ticket
            for ticket in all_tickets
            if search_input in ticket["name"].lower()
        ]

    return render_template("main.html", ticket=search_results)


@app.route("/add_to_cart/<int:ticket_id>", methods=["POST"])
def add_to_cart(ticket_id):
    # Fetch tickets from the database
    with shelve.open(TICKET_DB_PATH) as ticket_db:
        all_tickets = ticket_db.get("tickets", [])

    # Find the ticket to add
    ticket_to_add = next((ticket for ticket in all_tickets if ticket["ticket_id"] == ticket_id), None)

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
        # Handle quantity update, deletion, or other actions
        ticket_id = int(request.form.get("ticket_id"))
        action = request.form.get("action")

        # Retrieve the cart from the session
        cart = session.get("cart", [])

        if action == "update_quantity":
            new_quantity = int(request.form["quantity"])

            # Update the quantity of the specified ticket
            for item in cart:
                if item["ticket_id"] == ticket_id:
                    item["quantity"] = new_quantity
                    break

            # If the quantity is zero, remove the item from the cart
            if new_quantity == 0:
                flash("This item has been removed from the cart.", "warning")
                cart = [item for item in cart if item["quantity"] > 0]  # Remove items with 0 quantity

        elif action == "delete_ticket":
            # Remove the ticket from the cart
            cart = [item for item in cart if item["ticket_id"] != ticket_id]
            flash("Ticket has been removed from your cart.", "success")

        # Save the updated cart back to the session
        session["cart"] = cart

    # Retrieve the cart to display
    cart = session.get("cart", [])

    # Recalculate the total based on the updated quantity and price
    total = sum(float(item['price']) * int(item['quantity']) for item in cart)

    return render_template("cart.html", cart=cart, total=total)


if __name__ == '__main__':
    app.run(debug=True)
