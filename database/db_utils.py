import os
import psycopg2
from psycopg2 import extras

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "order_management"),
            user=os.getenv("POSTGRES_USER", "user"),
            password=os.getenv("POSTGRES_PASSWORD", "password"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"""Error: Could not connect to the database. Please ensure it is running.
Details: {e}""")
        return None

def initialize_database():
    """
    Initializes the database by executing the schema.sql file.
    This will drop existing tables and recreate them.
    """
    conn = None
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        schema_path = os.path.join(script_dir, 'schema.sql')

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        conn = get_db_connection()
        if conn is None:
            return

        with conn.cursor() as cur:
            print("INFO: Executing schema.sql to initialize database...")
            cur.execute(schema_sql)
            conn.commit()
            print("SUCCESS: Database initialized successfully.")

    except FileNotFoundError:
        print(f"ERROR: schema.sql not found at {schema_path}")
    except Exception as e:
        print(f"ERROR: An error occurred during database initialization: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("--- Database Initializer ---")
    # This check ensures that the user confirms the destructive action
    confirm = input("Are you sure you want to drop all existing tables and re-initialize the database? (yes/no): ")
    if confirm.lower() == 'yes':
        initialize_database()
    else:
        print("INFO: Database initialization cancelled.")
    print("--- Finished ---")
