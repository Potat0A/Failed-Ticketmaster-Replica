import shelve
import uuid
from datetime import datetime


class User:
    def __init__(self, email, username, password, role='customer'):
        self.id = str(uuid.uuid4())
        self.email = email
        self.username = username
        self.password = password  # Note: In production, this should be hashed
        self.role = role
        self.points = 100  # Starting points for new users
        self.registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.tickets = []  # List of ticket IDs owned by user
        self.redeemed_vouchers = []  # List of redeemed voucher IDs
        self.purchase_history = []  # List of purchase transaction IDs
        self.profile_picture = None

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'password': self.password,
            'role': self.role,
            'points': self.points,
            'registration_date': self.registration_date,
            'tickets': self.tickets,
            'redeemed_vouchers': self.redeemed_vouchers,
            'purchase_history': self.purchase_history,
            'profile_picture': self.profile_picture
        }


class UserManager:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path

    def create_user(self, email, username, password, role='customer'):
        """Create a new user and save to database."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username in db:
                raise ValueError("Username already exists")
            if any(user.get('email') == email for user in db.values() if isinstance(user, dict)):
                raise ValueError("Email already in use")

            user = User(email, username, password, role)
            db[username] = user.to_dict()
            return user.id

    def get_user(self, username):
        """Retrieve user by username."""
        with shelve.open(self.db_path) as db:
            user_data = db.get(username)
            if user_data:
                return user_data
            return None

    def get_user_by_id(self, user_id):
        """Retrieve user by ID."""
        with shelve.open(self.db_path) as db:
            for user_data in db.values():
                if isinstance(user_data, dict) and user_data.get('id') == user_id:
                    return user_data
            return None

    def update_user(self, username, updates):
        """Update user information."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username not in db:
                raise ValueError("User not found")

            user_data = db[username]
            for key, value in updates.items():
                if key in user_data:
                    user_data[key] = value
            db[username] = user_data
            return True

    def add_ticket_to_user(self, username, ticket_id):
        """Add a ticket to user's owned tickets."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username not in db:
                raise ValueError("User not found")

            user_data = db[username]
            if ticket_id not in user_data['tickets']:
                user_data['tickets'].append(ticket_id)
                user_data['purchase_history'].append({
                    'ticket_id': ticket_id,
                    'purchase_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                db[username] = user_data
                return True
            return False

    def add_voucher_to_user(self, username, voucher_id):
        """Add a redeemed voucher to user."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username not in db:
                raise ValueError("User not found")

            user_data = db[username]
            if voucher_id not in user_data['redeemed_vouchers']:
                user_data['redeemed_vouchers'].append(voucher_id)
                db[username] = user_data
                return True
            return False

    def update_points(self, username, points_change):
        """Update user's points balance."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username not in db:
                raise ValueError("User not found")

            user_data = db[username]
            user_data['points'] += points_change
            if user_data['points'] < 0:
                raise ValueError("Insufficient points")
            db[username] = user_data
            return user_data['points']

    def list_all_users(self):
        """List all users (admin function)."""
        with shelve.open(self.db_path) as db:
            return {k: v for k, v in db.items() if isinstance(v, dict)}

    def get_user_tickets(self, username):
        """Get all tickets owned by user."""
        with shelve.open(self.db_path) as db:
            if username not in db:
                raise ValueError("User not found")
            return db[username]['tickets']

    def get_user_purchase_history(self, username):
        """Get user's purchase history."""
        with shelve.open(self.db_path) as db:
            if username not in db:
                raise ValueError("User not found")
            return db[username]['purchase_history']

    def delete_user(self, username):
        """Delete a user account."""
        with shelve.open(self.db_path, writeback=True) as db:
            if username in db:
                del db[username]
                return True
            return False


# Utility function to initialize the database
def initialize_db(db_path='users.db'):
    """Initialize the database with an admin user if it doesn't exist."""
    user_manager = UserManager(db_path)
    try:
        # Create admin user if it doesn't exist
        user_manager.create_user(
            email="admin@ticketmaster.com",
            username="admin",
            password="admin123",  # In production, use a secure password
            role="admin"
        )
    except ValueError:
        # Admin already exists
        pass


if __name__ == "__main__":
    # Initialize database
    initialize_db()

    # Example usage
    user_manager = UserManager()

    # Create a new user
    try:
        user_id = user_manager.create_user("john@example.com", "john_doe", "password123")
        print(f"Created user with ID: {user_id}")
    except ValueError as e:
        print(f"Error creating user: {str(e)}")