import shelve
import bcrypt

# Path to the admin users shelve file
USER_DB_PATH = 'admin_users.db'

def hash_password(password):
    """Hashes the password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(password, hashed_password):
    """Checks if the password matches the hashed password."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def initialize_admins():
    """Initialize the database with a default admin if not present."""
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        if 'admins' not in db:
            db['admins'] = {'admin': hash_password('password123')}  # Default admin with hashed password

def add_admin(username, password):
    """Add a new admin to the admin_users database."""
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        admins = db.get('admins', {})
        if username in admins:
            raise ValueError("Admin username already exists.")
        admins[username] = hash_password(password)
        db['admins'] = admins

def update_admin_password(username, new_password):
    """Update the password of an existing admin."""
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        admins = db.get('admins', {})
        if username not in admins:
            raise ValueError("Admin username does not exist.")
        admins[username] = hash_password(new_password)
        db['admins'] = admins

def delete_admin(username):
    """Delete an admin user from the admin_users database."""
    with shelve.open(USER_DB_PATH, writeback=True) as db:
        admins = db.get('admins', {})
        if username not in admins:
            raise ValueError("Admin username does not exist.")
        del admins[username]
        db['admins'] = admins

def get_admins():
    """Retrieve all admin users."""
    with shelve.open(USER_DB_PATH) as db:
        admins = db.get('admins', {})
    return admins

def authenticate_admin(username, password):
    """Authenticate an admin by checking the credentials."""
    with shelve.open(USER_DB_PATH) as db:
        admins = db.get('admins', {})
        hashed_password = admins.get(username)
        if hashed_password:
            return check_password(password, hashed_password)
        return False
