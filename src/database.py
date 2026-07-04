import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join("data", "extraction_data.db")


def init_db():
    """Initialize the database with flexible schema for dynamic headers."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ExtractionResults (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        headers TEXT,                -- JSON array: ["项目名称", "投资金额", ...]
        header_descriptions TEXT,    -- JSON object: {"表头名": "说明", ...}
        data TEXT,                   -- JSON array of row objects
        source_files TEXT,           -- JSON array of source file names
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS TableTemplates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,            -- Template name
        headers TEXT,                -- JSON array
        header_descriptions TEXT,    -- JSON object
        template_description TEXT,   -- General description of the template
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SystemSettings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CustomModels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT UNIQUE,
        base_url TEXT,
        api_key TEXT,
        model_names TEXT,           -- JSON array of strings
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Auto-migration: Check and add missing columns for backward compatibility
    # Check ExtractionResults table
    cursor.execute("PRAGMA table_info(ExtractionResults)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "header_descriptions" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE ExtractionResults ADD COLUMN header_descriptions TEXT")
        except sqlite3.OperationalError as e:
            print(f"Migration error on ExtractionResults: {e}")
            
    # Check TableTemplates table
    cursor.execute("PRAGMA table_info(TableTemplates)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "header_descriptions" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE TableTemplates ADD COLUMN header_descriptions TEXT")
        except sqlite3.OperationalError as e:
            print(f"Migration error on TableTemplates: {e}")
            
    conn.commit()
    conn.close()



def save_extraction(headers: list[str], rows: list[dict], source_files: list[str], header_descriptions: dict = None):
    """
    Save an extraction result to the database.
    
    Args:
        headers: List of header names
        rows: List of row dictionaries
        source_files: List of source file names
        header_descriptions: Optional dict mapping header names to descriptions
    """
    header_descriptions = header_descriptions or {}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ExtractionResults (headers, header_descriptions, data, source_files) VALUES (?, ?, ?, ?)",
        (json.dumps(headers, ensure_ascii=False),
         json.dumps(header_descriptions, ensure_ascii=False),
         json.dumps(rows, ensure_ascii=False),
         json.dumps(source_files, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def get_all_extractions():
    """Retrieve all extraction records from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, headers, header_descriptions, data, source_files, created_at FROM ExtractionResults ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        # Handle backward compatibility - old records won't have header_descriptions
        header_desc = row[2] if row[2] else '{}'
        results.append({
            'id': row[0],
            'headers': json.loads(row[1]),
            'header_descriptions': json.loads(header_desc),
            'data': json.loads(row[3]),
            'source_files': json.loads(row[4]),
            'created_at': row[5]
        })

    return results


def delete_extraction(record_id: int):
    """Delete a specific extraction record."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ExtractionResults WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def save_template(name: str, headers: list[str], header_descriptions: dict, template_description: str = ""):
    """Save a table template to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO TableTemplates (name, headers, header_descriptions, template_description) VALUES (?, ?, ?, ?)",
            (name, 
             json.dumps(headers, ensure_ascii=False),
             json.dumps(header_descriptions, ensure_ascii=False),
             template_description)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error saving template: {e}")
        return False
    finally:
        conn.close()


def get_all_templates():
    """Retrieve all table templates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, headers, header_descriptions, template_description, created_at FROM TableTemplates ORDER BY name ASC"
    )
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            'id': row[0],
            'name': row[1],
            'headers': json.loads(row[2]),
            'header_descriptions': json.loads(row[3]),
            'template_description': row[4],
            'created_at': row[5]
        })
    return results


def delete_template(template_id: int):
    """Delete a table template."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM TableTemplates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


def get_setting(key: str, default=None):
    """Retrieve a system setting by key."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM SystemSettings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def update_setting(key: str, value: str):
    """Update or insert a system setting."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO SystemSettings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def save_custom_model(provider_name: str, base_url: str, api_key: str, model_names: list[str]):
    """Save or update a custom model provider."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO CustomModels (provider_name, base_url, api_key, model_names) VALUES (?, ?, ?, ?)",
            (provider_name, base_url, api_key, json.dumps(model_names, ensure_ascii=False))
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error saving custom model: {e}")
        return False
    finally:
        conn.close()


def get_all_custom_models():
    """Retrieve all custom model providers."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, provider_name, base_url, api_key, model_names FROM CustomModels ORDER BY provider_name ASC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            'id': row[0],
            'provider_name': row[1],
            'base_url': row[2],
            'api_key': row[3],
            'model_names': json.loads(row[4])
        })
    return results


def delete_custom_model(model_id: int):
    """Delete a custom model provider."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM CustomModels WHERE id = ?", (model_id,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
