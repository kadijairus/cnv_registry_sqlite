"""
Creates SQLite database using a pre-prepared SQL script (Registrid_cleaned.sql)
containing schema, triggers, and potentially sample data.
Also provides runtime data access functions for the GUI.
"""

import sqlite3
import os
import traceback # Keep for data access functions


# Working DB on local disk (SQLite on a network drive risks corruption); backups go to U: (see cnv_backup.py)
DB_FILE = os.path.join(os.path.expanduser("~"), "cnv_registry", "cnv_registry.db")
# Input file for creating the database structure and content
PREPARED_SQL_FILE = "Registrid_cleaned.sql"

# --- Database Creation Function ---
def create_database_from_prepared_sql(db_path, prepared_sql_path):
    """ Creates/overwrites SQLite DB using a single prepared SQL script. """
    print(f"\n--- Starting Database Creation from Prepared SQL ---")
    print(f"  Using SQL file: {prepared_sql_path}")
    print(f"  Target DB: {db_path}")

    # Check if the prepared SQL file exists
    if not os.path.exists(prepared_sql_path):
        print(f"ERROR: Prepared SQL file '{prepared_sql_path}' not found!")
        print("--- Database Creation Failed ---")
        return False

    # Attempt to delete existing DB file
    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"  - Removed existing database file: {db_path}")
    except OSError as e:
        print(f"ERROR: Could not delete existing database file '{db_path}': {e}")
        print("--- Database Creation Failed ---")
        return False

    conn = None
    try:
        # Read the entire prepared SQL script
        print(f"Reading combined SQL from: {prepared_sql_path}")
        with open(prepared_sql_path, 'r', encoding='utf-8') as f:
            sql_to_execute = f.read()
        print("  - Read prepared SQL successfully.")

        # Connect and execute the script
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;") # Enable FK constraints
        cursor = conn.cursor()

        print(f"Executing prepared script (schema, triggers, data)...")
        cursor.executescript(sql_to_execute) # Execute everything
        print(f"Script executed successfully.")

        # Commit might be implicit with executescript on success, but explicit is safe
        conn.commit()

        print(f"Database '{db_path}' created/populated successfully from '{prepared_sql_path}'.")
        print("--- Database Creation Finished ---")
        return True

    except Exception as e:
        print(f"\nERROR during database creation/population from prepared script: {e}")
        if isinstance(e, sqlite3.Error):
            print("  This might be an error in the SQL syntax within")
            print(f"  '{prepared_sql_path}' (schema, trigger, or data).")
        traceback.print_exc() # Show full traceback
        # Clean up potentially corrupted DB file
        if os.path.exists(db_path):
            try:
                if conn: conn.close(); conn = None
                os.remove(db_path)
                print("  - Removed potentially corrupted/incomplete database file.")
            except Exception as cleanup_err: print(f"  - Error during cleanup: {cleanup_err}")
        print("--- Database Creation Failed ---")
        return False
    finally:
        if conn:
            try: conn.close()
            except sqlite3.Error: pass # Ignore errors during close in finally


# --- Database Connection Handling for GUI (Keep as is) ---
def db_connect(db_path=DB_FILE):
    """Establishes a connection to the EXISTING SQLite database."""
    print(f"Connecting to database: {db_path}")
    if not os.path.exists(db_path):
        print(f"ERROR: Database file '{db_path}' not found.")
        print("       Run 'python cnv_registry_db.py' first.")
        return None, None
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        print(f"Successfully connected to database: {db_path}")
        return conn, cursor
    except sqlite3.Error as e:
        print(f"ERROR connecting to database '{db_path}': {e}")
        if conn: conn.close()
        return None, None

def db_disconnect(conn):
    """Closes the database connection."""
    if conn:
        try:
            conn.close(); print("Database connection closed.")
        except sqlite3.Error as e:
            print(f"ERROR closing database connection: {e}")

# --- GUI Data Fetching/Modification Functions ---
def get_active_classifications(cursor, table_name, code_col, name_col, other_cols=None):
    if not cursor: print(f"ERROR: No cursor for get_active_classifications({table_name})"); return []
    active_col = "is_active"
    cols_to_select = f"{code_col}, {name_col}";
    if other_cols and isinstance(other_cols, (list, tuple)): cols_to_select += f", {', '.join(other_cols)}"
    query = f"SELECT {cols_to_select} FROM {table_name} WHERE {active_col} = ? ORDER BY {name_col};"
    try: cursor.execute(query, (1,)); return cursor.fetchall()
    except sqlite3.Error as e: print(f"ERROR fetching classifications from '{table_name}': {e}"); return []

def get_active_cnvs_display(cursor):
    if not cursor: return []
    query = """ SELECT c.cnv_id, d.dna_code, k.chromosome_name, c.start_pos, c.end_pos, ko.copy_number_value, t.interpretation_name, p.inheritance_name, cs.cnv_status_name, ko.rgb_color FROM cnv c JOIN analysis a ON c.analysis_id = a.analysis_id JOIN dna d ON a.dna_id = d.dna_id JOIN chromosome k ON c.chromosome_code = k.chromosome_code JOIN copy_number ko ON c.copy_number_code = ko.copy_number_code JOIN interpretation t ON c.interpretation_code = t.interpretation_code JOIN inheritance p ON c.inheritance_code = p.inheritance_code JOIN cnv_status cs ON c.cnv_status_code = cs.cnv_status_code WHERE cs.cnv_status_name = 'aktiivne' ORDER BY d.dna_code, k.chromosome_code, c.start_pos; """
    try: cursor.execute(query); return cursor.fetchall()
    except sqlite3.Error as e: print(f"ERROR fetching active CNVs: {e}"); return []

def get_analysis_details_by_dna(cursor, dna_code):
    if not cursor: return None
    query = "SELECT a.analysis_id, a.analysis_status_code, a_s.analysis_status_name FROM analysis a JOIN dna d ON a.dna_id = d.dna_id JOIN analysis_status a_s ON a.analysis_status_code = a_s.analysis_status_code WHERE d.dna_code = ?;"
    try: cursor.execute(query, (dna_code,)); return cursor.fetchone()
    except sqlite3.Error as e: print(f"ERROR fetching analysis details for DNA '{dna_code}': {e}"); return None

def get_cnvs_for_analysis_display(cursor, analysis_id):
    if not cursor: return []
    query = "SELECT c.cnv_id, k.chromosome_name, c.start_pos, c.end_pos, ko.copy_number_value, t.interpretation_name, p.inheritance_name, cs.cnv_status_name FROM cnv c JOIN chromosome k ON c.chromosome_code = k.chromosome_code JOIN copy_number ko ON c.copy_number_code = ko.copy_number_code JOIN interpretation t ON c.interpretation_code = t.interpretation_code JOIN inheritance p ON c.inheritance_code = p.inheritance_code JOIN cnv_status cs ON c.cnv_status_code = cs.cnv_status_code WHERE c.analysis_id = ? ORDER BY k.chromosome_code, c.start_pos;"
    try: cursor.execute(query, (analysis_id,)); return cursor.fetchall()
    except sqlite3.Error as e: print(f"ERROR fetching CNVs for analysis ID {analysis_id}: {e}"); return []

def get_cnv_details_for_edit(cursor, cnv_id):
     if not cursor: return None
     query = "SELECT c.*, d.dna_code FROM cnv c JOIN analysis a ON c.analysis_id = a.analysis_id JOIN dna d ON a.dna_id = d.dna_id WHERE c.cnv_id = ?;"
     try: cursor.execute(query, (cnv_id,)); return cursor.fetchone()
     except sqlite3.Error as e: print(f"ERROR fetching details for CNV ID {cnv_id}: {e}"); return None

def add_cnv(cursor, conn, analysis_id, chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code):
    if not cursor or not conn: return None
    query = "INSERT INTO cnv (analysis_id, chromosome_code, start_pos, end_pos, copy_number_code, interpretation_code, inheritance_code) VALUES (?, ?, ?, ?, ?, ?, ?);"
    try: cursor.execute(query, (analysis_id, chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code)); conn.commit(); return cursor.lastrowid
    except sqlite3.Error as e: print(f"ERROR adding CNV: {e}"); conn.rollback(); return None

def update_cnv(cursor, conn, cnv_id, chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code):
    if not cursor or not conn: return False
    query = "UPDATE cnv SET chromosome_code=?, start_pos=?, end_pos=?, copy_number_code=?, interpretation_code=?, inheritance_code=? WHERE cnv_id=?;"
    try: cursor.execute(query, (chrom_code, start, end, copy_number_code, interpretation_code, inheritance_code, cnv_id)); updated = cursor.rowcount; conn.commit(); return updated > 0
    except sqlite3.Error as e: print(f"ERROR updating CNV ID {cnv_id}: {e}"); conn.rollback(); return False

def update_cnv_state(cursor, conn, cnv_id, target_state_code):
    if not cursor or not conn: return False
    query = "UPDATE cnv SET cnv_status_code = ? WHERE cnv_id = ?;"
    try: cursor.execute(query, (target_state_code, cnv_id)); updated = cursor.rowcount; conn.commit(); return updated > 0
    except sqlite3.Error as e: print(f"ERROR updating state for CNV ID {cnv_id}: {e}"); conn.rollback(); return False

def get_analysis_status_name(cursor, analysis_id):
    if not cursor: return None
    query = "SELECT a_s.analysis_status_name FROM analysis a JOIN analysis_status a_s ON a.analysis_status_code = a_s.analysis_status_code WHERE a.analysis_id = ?;"
    try: cursor.execute(query, (analysis_id,)); result = cursor.fetchone(); return result['analysis_status_name'] if result else None
    except sqlite3.Error as e: print(f"ERROR fetching analysis state for ID {analysis_id}: {e}"); return None


# --- Main execution block ---
if __name__ == "__main__":
    import sys
    import cnv_backup
    print("=" * 60)
    if os.path.exists(DB_FILE):
        print(f"WARNING: Database '{DB_FILE}' already exists and will be DELETED and rebuilt.")
        if input("Type YES to continue: ").strip() != "YES":
            print("Cancelled. Database was not changed.")
            sys.exit(1)
        if not cnv_backup.backup_database(DB_FILE, reason="before-rebuild"):
            print("Backup failed - rebuild cancelled. Database was not changed.")
            sys.exit(1)
    success = create_database_from_prepared_sql(DB_FILE, PREPARED_SQL_FILE)
    print("-" * 60)
    if success:
        print(f"Database '{DB_FILE}' created/updated successfully using '{PREPARED_SQL_FILE}'.")
        print("Ready to run the GUI (cnv_admin_gui.py).")
    else:
        print(f"Database creation failed. Check errors above and ensure '{PREPARED_SQL_FILE}' exists and is valid.")
        print("You might need to run 'python prepare_database_sql.py' first.")
    print("=" * 60)