import shelve
import uuid

# Path to the shelve database file
shelve_file = 'users.db'


def initialize_last_id():
    """Ensure the last_id value is set in the shelve database."""
    with shelve.open(shelve_file, writeback=True) as db:
        if 'last_id' not in db:
            db['last_id'] = 0  # Initialize last_id to 0 or any starting value
            print("Initialized last_id to 0.")
        else:
            print(f"last_id already initialized to: {db['last_id']}")


def display_all():
    """Display all key-value pairs in the shelve database."""
    with shelve.open(shelve_file) as db:
        print("\nContents of the shelve database:")

        # Print the last_id value separately
        print(f"last_id: {db.get('last_id', 'Not Set')}")  # Display last_id

        # Iterate through and display all user records
        for key, value in db.items():
            if key != 'last_id':  # Skip the 'last_id' entry itself
                print(
                    f"Key: {key}, ID: {value['id']}, Email: {value['email']}, Role: {value['role']}, Points: {value['points']}, Redeemed Vouchers: {value['redeemed_vouchers']}")
        print("\n")


def update_password_by_id(user_id, new_password):
    """Update the password for a user based on their unique ID."""
    with shelve.open(shelve_file, writeback=True) as db:
        for key, value in db.items():
            if isinstance(value, dict) and value.get("id") == user_id:
                db[key]['password'] = new_password  # Only update the password
                print(f"Password updated for user with ID: {user_id}")
                return
        print(f"No entry found with ID: {user_id}")


def delete_item_by_id(user_id):
    """Delete an entry based on its unique ID."""
    with shelve.open(shelve_file, writeback=True) as db:
        for key, value in list(db.items()):  # Use list() to avoid runtime errors during iteration
            if isinstance(value, dict) and value.get("id") == user_id:
                del db[key]
                print(f"Deleted entry with ID: {user_id}")
                return
        print(f"No entry found with ID: {user_id}")


# Example Usage
if __name__ == "__main__":
    initialize_last_id()  # Ensure last_id is set
    while True:
        display_all()
        ans = int(input("Select what you want to do:\n"
                        "1. Update password\n"
                        "2. Delete users\n"
                        "3. Exit\n"))
        if ans == 1:
            user_id_to_update = input("Enter the ID of the user to update the password: ")
            new_password = input("Enter the new password: ")
            update_password_by_id(user_id_to_update, new_password)

        elif ans == 2:
            user_id_to_delete = input("Enter the ID of the user to delete: ")
            delete_item_by_id(user_id_to_delete)
        else:
            break
