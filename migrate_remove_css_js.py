#!/usr/bin/env python3
"""
Migration script to remove css_content and js_content columns from phishlets table.
This script should be run once to update existing databases.
"""

import os
import sqlite3
from pathlib import Path

def migrate_remove_css_js():
    """Remove css_content and js_content columns from phishlets table"""
    
    # Get database path
    database_dir = os.path.join(os.path.dirname(__file__), 'database')
    db_path = os.path.join(database_dir, 'app.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Nothing to migrate.")
        return
    
    print(f"Migrating database: {db_path}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(phishlets)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"Current columns in phishlets table: {columns}")
        
        # Check if css_content and js_content columns exist
        css_exists = 'css_content' in columns
        js_exists = 'js_content' in columns
        
        if not css_exists and not js_exists:
            print("CSS and JS content columns already removed. No migration needed.")
            return
        
        print("Starting migration...")
        
        # Create new table without css_content and js_content columns
        new_table_sql = """
        CREATE TABLE phishlets_new (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            user_id INTEGER NOT NULL,
            original_url VARCHAR NOT NULL,
            clone_url VARCHAR,
            html_content TEXT,
            form_fields TEXT,
            capture_credentials BOOLEAN DEFAULT 1,
            capture_other_data BOOLEAN DEFAULT 1,
            redirect_url VARCHAR,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
        
        # Create new table
        cursor.execute(new_table_sql)
        print("Created new phishlets table structure")
        
        # Copy data from old table to new table (excluding css_content and js_content)
        copy_sql = """
        INSERT INTO phishlets_new (
            id, name, description, user_id, original_url, clone_url, 
            html_content, form_fields, capture_credentials, capture_other_data, 
            redirect_url, is_active, created_at, updated_at
        )
        SELECT 
            id, name, description, user_id, original_url, clone_url, 
            html_content, form_fields, capture_credentials, capture_other_data, 
            redirect_url, is_active, created_at, updated_at
        FROM phishlets
        """
        
        cursor.execute(copy_sql)
        print("Copied data to new table")
        
        # Drop old table
        cursor.execute("DROP TABLE phishlets")
        print("Dropped old phishlets table")
        
        # Rename new table to original name
        cursor.execute("ALTER TABLE phishlets_new RENAME TO phishlets")
        print("Renamed new table to phishlets")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        
        # Verify the new structure
        cursor.execute("PRAGMA table_info(phishlets)")
        new_columns = [column[1] for column in cursor.fetchall()]
        print(f"New columns in phishlets table: {new_columns}")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_remove_css_js()


