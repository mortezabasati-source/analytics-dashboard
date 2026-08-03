import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# --- Robust .env loading ---
# Construct the path to the .env file in the project root directory.
# This is more reliable than using a relative path like '../.env'.
project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / '.env')

def get_db_connection_string():
    """Constructs the database connection string from environment variables."""
    return (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

def create_mock_data():
    """Generates a mock DataFrame if the database connection fails."""
    st.warning("⚠️ Database connection failed. Using mock data for demonstration.", icon="🔥")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=18 * 30)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    data = {
        'order_date': np.random.choice(date_range, 500),
        'category': np.random.choice(['Typ A', 'Typ B', 'Typ C'], 500),
        'product_name': [f'Sort {i}' for i in np.random.randint(1, 20, 500)],
        'sales': np.random.uniform(50, 1000, 500),
        'quantity': np.random.randint(1, 10, 500),
        'store_name': np.random.choice(['Butik X', 'Butik Y'], 500),
        'location': np.random.choice(['Ort A', 'Ort B'], 500),
        'return_sales': np.random.uniform(0, 100, 500),
        'return_quantity': np.random.randint(0, 2, 500),
    }
    df = pd.DataFrame(data)
    
    # --- Apply Optimizations to Mock Data ---
    df['order_date'] = pd.to_datetime(df['order_date'])
    
    # Downcast numeric types
    for col in ['sales', 'return_sales']:
        df[col] = df[col].astype('float32')
    for col in ['quantity', 'return_quantity']:
        df[col] = df[col].astype('int32')
        
    # Convert object types to category for memory efficiency
    for col in ['category', 'product_name', 'store_name', 'location']:
        df[col] = df[col].astype('category')

    df['year_month_key'] = df['order_date'].dt.strftime('%Y-M%m')
    df['year_week_key'] = df['order_date'].dt.strftime('%Y-W%U')
    df['order_date'] = df['order_date'].dt.date # Convert to date object
    return df

@st.cache_data(ttl="1h", max_entries=2)
def load_data():
    """Loads data from the MySQL view with a fallback to mock data."""
    try:
        # --- Pre-connection Check ---
        # Verify that all required environment variables are loaded before attempting to connect.
        required_vars = [
            'DB_USER', 'DB_PASS', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'VIEW_NAME',
            'DATE_COLUMN_NAME',
            'SALES_COLUMN_NAME',
            'QUANTITY_COLUMN_NAME',
            'CATEGORY_COLUMN_NAME',
            'PRODUCT_NAME_COLUMN_NAME',
            'STORE_NAME_COLUMN_NAME',
            'LOCATION_COLUMN_NAME',
            'RETURN_SALES_COLUMN_NAME',
            'RETURN_QUANTITY_COLUMN_NAME'
        ]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            # If variables are missing, check if the .env file itself exists and report back to the user.
            dotenv_path = project_root / '.env'
            if not dotenv_path.is_file():
                raise FileNotFoundError(f"The .env file was not found. The app is looking for it at: {dotenv_path}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        view_name = os.getenv('VIEW_NAME')
        engine = create_engine(get_db_connection_string())
        
        # The 'connect()' method is where the actual connection attempt happens.
        # Most credential/network errors will be caught here.
        with engine.connect() as connection:
            query = text(f"SELECT * FROM {view_name}")
            df = pd.read_sql(query, connection)

        # --- Memory Usage Logging (Before Optimization) ---
        mem_usage_before = df.memory_usage(deep=True).sum() / 1e6
        print(f"--- Memory Usage Before Optimization: {mem_usage_before:.2f} MB ---")

        # --- Data Type Conversion ---
        # Create a mapping from actual DB column names (from .env) to standard app column names
        column_mapping = {
            os.getenv('DATE_COLUMN_NAME'): 'order_date',
            os.getenv('SALES_COLUMN_NAME'): 'sales',
            os.getenv('QUANTITY_COLUMN_NAME'): 'quantity',
            os.getenv('CATEGORY_COLUMN_NAME'): 'category',
            os.getenv('PRODUCT_NAME_COLUMN_NAME'): 'product_name',
            os.getenv('STORE_NAME_COLUMN_NAME'): 'store_name',
            os.getenv('LOCATION_COLUMN_NAME'): 'location',
            os.getenv('RETURN_SALES_COLUMN_NAME'): 'return_sales',
            os.getenv('RETURN_QUANTITY_COLUMN_NAME'): 'return_quantity',
        }

        # Check if all source columns exist in the DataFrame
        source_columns = list(column_mapping.keys())
        missing_db_cols = [col for col in source_columns if col not in df.columns]
        if missing_db_cols:
            raise ValueError(f"The following columns specified in .env were not found in the database view: {', '.join(missing_db_cols)}")
            
        # Rename all columns at once for efficiency and consistency
        df.rename(columns=column_mapping, inplace=True)

        # --- Data Cleaning: Strip whitespace from key categorical columns ---
        # This prevents merge/join issues later due to leading/trailing spaces.
        df['store_name'] = df['store_name'].astype(str).str.strip()

        # Convert data types on standardized column names
        df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
        
        # --- Business Logic Calculations (before final type conversion) ---
        df['net_sales'] = pd.to_numeric(df['sales'], errors='coerce').fillna(0) - pd.to_numeric(df['return_sales'], errors='coerce').fillna(0)
        
        # --- Memory Optimization: Downcasting and Category Conversion ---
        for col in ['sales', 'return_sales']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')
        df['net_sales'] = df['net_sales'].astype('float32') # Downcast calculated column

        for col in ['quantity', 'return_quantity']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int32')
        
        # Drop rows with critical missing data after initial numeric conversion
        # This step is crucial and might be why some stores appear to have no data if their core metrics are missing.
        df.dropna(subset=['order_date', 'sales', 'quantity'], inplace=True)

        # Calculate return rate after cleaning and before converting to category
        df['return_rate'] = (df['return_sales'] / df['sales'].replace(0, np.nan)).replace([np.inf, -np.inf], 0).fillna(0).astype('float32')

        # --- Add Time-Based Keys for Robust Filtering ---
        df['year_month_key'] = df['order_date'].dt.strftime('%Y-M%m')
        df['year_week_key'] = df['order_date'].dt.strftime('%Y-W%U')

        # Convert low-cardinality string/object columns to 'category'
        for col in ['category', 'product_name', 'store_name', 'location']:
            if col in df.columns:
                df[col] = df[col].astype('category')
        df['year_month_key'] = df['year_month_key'].astype('category')
        df['year_week_key'] = df['year_week_key'].astype('category')

        mem_usage_after = df.memory_usage(deep=True).sum() / 1e6
        print(f"--- Memory Usage After Optimization: {mem_usage_after:.2f} MB ---")
        print(f"--- Optimization Complete. Memory saved: {(mem_usage_before - mem_usage_after):.2f} MB ---")

        df['order_date'] = df['order_date'].dt.date # Convert back to date object for filtering
        return df
    except Exception as e:
        # Improved error logging to show the type of exception and the message.
        st.error(f"An error occurred while connecting to the database. Please check credentials and network.")
        st.error(f"Error Type: `{type(e).__name__}`")
        st.error(f"Error Details: `{e}`")
        return create_mock_data()
