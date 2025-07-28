import sqlite3
import os
from getpass import getpass
from flask_bcrypt import Bcrypt

# Ensure this matches the path in your app.py
DATABASE_SUBDIR = 'data'
DATABASE_FILENAME = 'chore_chart.db'
DATABASE = os.path.join(DATABASE_SUBDIR, DATABASE_FILENAME)

def create_admin_user():
    print("--- Create Admin User ---")
    
    # Check if the database directory exists
    if not os.path.exists(DATABASE_SUBDIR):
        print(f"Database directory '{DATABASE_SUBDIR}' not found. Please run the main application first to create it.")
        return

    # Check if the database file exists
    if not os.path.exists(DATABASE):
        print(f"Database file '{DATABASE}' not found. Please run the main application first to create it.")
        return

    username = input("Enter admin username: ").strip()
    
    # Use getpass to hide password input
    password = getpass("Enter admin password: ")
    password_confirm = getpass("Confirm admin password: ")

    if not username:
        print("Username cannot be empty.")
        return
        
    if not password:
        print("Password cannot be empty.")
        return

    if password != password_confirm:
        print("Passwords do not match.")
        return

    bcrypt = Bcrypt()
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            print(f"Error: Username '{username}' already exists.")
            conn.close()
            return

        # Insert new user
        cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        conn.close()
        print(f"Admin user '{username}' created successfully!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print("Please ensure the database has been initialized by running the main app first.")

if __name__ == '__main__':
    create_admin_user()
