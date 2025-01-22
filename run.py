from flask import Flask, render_template, request, redirect, url_for, flash, session
import shelve
import os

#template and static folders path
app = Flask(__name__,
            template_folder='app/templates',  #Point templates directory
            static_folder='app/static')  #Point static directory

app.secret_key = 'development-key'  # Simple key for DevOps


#routes
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('email')
        password = request.form.get('password')

        # Simple login without encryption
        with shelve.open('database/admin') as db:
            if username in db and db[username]['password'] == password:
                session['logged_in'] = True
                return redirect(url_for('home'))
            flash('Invalid credentials')
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('email')
        password = request.form.get('password')

        # Simple registration without encryption
        with shelve.open('database/admin') as db:
            db[username] = {
                'password': password,
                'first_name': request.form.get('first_name'),
                'last_name': request.form.get('last_name')
            }
        return redirect(url_for('login'))
    return render_template('auth/register.html')


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        feedback_data = {
            'type': request.form.get('feedback_type'),
            'message': request.form.get('message'),
            'name': request.form.get('first_name') + ' ' + request.form.get('last_name'),
            'email': request.form.get('email')
        }
        with shelve.open('database/feedback') as db:
            if 'count' not in db:
                db['count'] = 0
            db['count'] += 1
            db[str(db['count'])] = feedback_data
        flash('Feedback submitted successfully!')
        return redirect(url_for('home'))
    return render_template('feedback.html')


# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('email')
        password = request.form.get('password')

        # Simple admin check
        if username == "admin@example.com" and password == "admin":
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials')
    return render_template('admin/login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin/dashboard.html')


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    # Create database directory if it doesn't exist
    os.makedirs('database', exist_ok=True)

    # Create admin account if it doesn't exist
    with shelve.open('database/admin') as db:
        if 'admin@example.com' not in db:
            db['admin@example.com'] = {
                'password': 'admin',
                'role': 'admin'
            }

    app.run(debug=True)