import shelve
import uuid

# Path to the shelve database file
shelve_file = 'users.db'


def display_all():
    """Display all key-value pairs in the shelve database."""
    with shelve.open(shelve_file) as db:
        print("\nContents of the shelve database:")
        for key, value in db.items():
            print(f"Key: {key}, ID: {value['id']}, Value: {value}")
        print("\n")


def update_password_by_id(user_id, new_password):
    """Update the password for a user based on their unique ID."""
    with shelve.open(shelve_file, writeback=True) as db:
        for key, value in db.items():
            if value.get("id") == user_id:
                db[key]['password'] = new_password  # Only update the password
                print(f"Password updated for user with ID: {user_id}")
                return
        print(f"No entry found with ID: {user_id}")


def delete_item_by_id(user_id):
    """Delete an entry based on its unique ID."""
    with shelve.open(shelve_file, writeback=True) as db:
        for key, value in list(db.items()):  # Use list() to avoid runtime errors during iteration
            if value.get("id") == user_id:
                del db[key]
                print(f"Deleted entry with ID: {user_id}")
                return
        print(f"No entry found with ID: {user_id}")


# Example Usage
if __name__ == "__main__":
    # Add sample data (optional, for testing purposes)

    # Display current contents
    display_all()

    # Update password for a user by ID
    user_id_to_update = input("Enter the ID of the user to update the password: ")
    new_password = input("Enter the new password: ")
    update_password_by_id(user_id_to_update, new_password)

    # Delete an item by ID
    user_id_to_delete = input("Enter the ID of the user to delete: ")
    delete_item_by_id(user_id_to_delete)

    # Display contents after changes
    display_all()