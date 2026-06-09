import os
import pandas as pd
from threading import Lock

_cache = {}
_lock = Lock()

# update these paths to match your deployment
DATA_DIR = os.environ.get('SALES_DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))

DATA_FILES = {
    'sales_orders': 'Sales Order - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Date Wise Sales Order.xlsx',
    'sales_order_details': 'Sales Order Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16__Submitted + Draft_Date Wise Sales Order.xlsx',
    'sales_invoice': 'Sales Invoice Details - DynaRep_Best Marine Private Limited__2026-04-01_2026-05-16_Sales Invoice_Submitted + Draft__Date Wise Sales Invoice.xlsx',
}


def _clean(df, date_col, required='Customer Name'):
    df = df.copy()
    df.dropna(subset=[required], inplace=True)
    df[date_col] = pd.to_datetime(df[date_col], format='%d-%b-%y', errors='coerce')
    df['week'] = df[date_col].dt.isocalendar().week.astype(int)
    df['month'] = df[date_col].dt.month
    df['half'] = df['week'].apply(lambda w: 'first' if w <= 15 else 'second')
    return df


def load_data():
    global _cache
    with _lock:
        if _cache:
            return _cache['so'], _cache['sod'], _cache['inv']

        so = pd.read_excel(os.path.join(DATA_DIR, DATA_FILES['sales_orders']))
        sod = pd.read_excel(os.path.join(DATA_DIR, DATA_FILES['sales_order_details']))
        inv = pd.read_excel(os.path.join(DATA_DIR, DATA_FILES['sales_invoice']))

        so.dropna(subset=['Customer Name'], inplace=True)
        so['Date'] = pd.to_datetime(so['Date'], format='%d-%b-%y', errors='coerce')
        so['week'] = so['Date'].dt.isocalendar().week.astype(int)
        so['half'] = so['week'].apply(lambda w: 'first' if w <= 15 else 'second')

        sod = _clean(sod, 'Posting Date')
        inv = _clean(inv, 'Posting Date')

        for df in [sod, inv]:
            df['category'] = df['Item Name'].str.split('-').str[0].str.strip()

        _cache = {'so': so, 'sod': sod, 'inv': inv}
        return so, sod, inv


def reload_data():
    """Force reload - call when Excel files are updated"""
    global _cache
    with _lock:
        _cache = {}
    return load_data()
