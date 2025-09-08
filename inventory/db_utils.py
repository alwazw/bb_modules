import os
import sys
import json
import psycopg2
from psycopg2 import extras

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_utils import get_db_connection

# =====================================================================================
# --- Inventory Database Functions (Phase 3 Scaffolding) ---
# =====================================================================================

def create_component(conn, name, component_type, specs=None):
    """
    Adds a new component to the 'components' table.

    Args:
        conn: An active psycopg2 database connection object.
        name (str): The name of the component (e.g., '16GB DDR4 RAM Stick').
        component_type (str): The type of component (e.g., 'RAM', 'SSD').
        specs (dict, optional): A JSON-compatible dict of specifications.

    Returns:
        The integer ID of the new component, or None on failure.
    """
    component_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO components (name, type, specs) VALUES (%s, %s, %s) RETURNING component_id;",
                (name, component_type, json.dumps(specs) if specs else None)
            )
            component_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        print(f"ERROR: Could not create component '{name}'. Reason: {e}")
        conn.rollback()
    return component_id

def get_component_by_name(conn, name):
    """
    Retrieves a component by its name.

    Args:
        conn: An active psycopg2 database connection object.
        name (str): The name of the component to find.

    Returns:
        A dictionary representing the component, or None if not found.
    """
    component = None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM components WHERE name = %s;", (name,))
            component = cur.fetchone()
    except Exception as e:
        print(f"ERROR: Could not get component '{name}'. Reason: {e}")
    return dict(component) if component else None

def create_base_product(conn, model_name, brand=None):
    """
    Adds a new base product (e.g., a laptop model) to the 'base_products' table.

    Args:
        conn: An active psycopg2 database connection object.
        model_name (str): The model name of the product (e.g., 'Dell Inspiron 15').
        brand (str, optional): The brand of the product (e.g., 'Dell').

    Returns:
        The integer ID of the new base product, or None on failure.
    """
    product_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO base_products (model_name, brand) VALUES (%s, %s) RETURNING product_id;",
                (model_name, brand)
            )
            product_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        print(f"ERROR: Could not create base product '{model_name}'. Reason: {e}")
        conn.rollback()
    return product_id

# TODO: Add more functions as the inventory module is built out:
# - create_product_variant
# - add_component_to_variant
# - map_shop_sku_to_variant
# - get_variant_by_shop_sku
# - etc.
