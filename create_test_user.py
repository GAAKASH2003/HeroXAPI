#!/usr/bin/env python3
import bcrypt
from database import db

def create_test_user():
    """Create a test user for development"""
    # Check if test user already exists
    existing_user = db(db.users.email == "admin@herox.com").select().first()
    if existing_user:
        print("Test user already exists!")
        return
    
    # Hash password
    password = "admin123"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create user
    user_id = db.users.insert(
        username="admin",
        email="admin@herox.com",
        password=hashed_password,
        full_name="Admin User"
    )
    
    # Commit the transaction
    db.commit()
    
    print(f"Test user created with ID: {user_id}")
    print("Email: admin@herox.com")
    print("Password: admin123")

if __name__ == "__main__":
    create_test_user()
