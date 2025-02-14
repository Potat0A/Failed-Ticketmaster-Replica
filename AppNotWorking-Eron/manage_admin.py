import user_management


def menu():
    print("Admin User Management")
    print("1. Add Admin")
    print("2. Update Admin Password")
    print("3. Delete Admin")
    print("4. List Admins")
    print("5. Exit")


def add_admin():
    username = input("Enter new admin username: ")
    password = input("Enter new admin password: ")
    try:
        user_management.add_admin(username, password)
        print(f"Admin {username} added successfully.")
    except ValueError as e:
        print(e)


def update_admin_password():
    username = input("Enter admin username to update password: ")
    new_password = input("Enter new password: ")
    try:
        user_management.update_admin_password(username, new_password)
        print(f"Password for admin {username} updated successfully.")
    except ValueError as e:
        print(e)


def delete_admin():
    username = input("Enter admin username to delete: ")
    try:
        user_management.delete_admin(username)
        print(f"Admin {username} deleted successfully.")
    except ValueError as e:
        print(e)


def list_admins():
    admins = user_management.get_admins()
    if admins:
        print("Admin Users:")
        for username in admins:
            print(f"- {username}")
    else:
        print("No admin users found.")


def main():
    while True:
        menu()
        choice = input("Enter choice: ")
        if choice == '1':
            add_admin()
        elif choice == '2':
            update_admin_password()
        elif choice == '3':
            delete_admin()
        elif choice == '4':
            list_admins()
        elif choice == '5':
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()