import numpy as np
import pandas as pd
from .data_loader import load_data

# ── helpers ──────────────────────────────────────────────────────────────────

def _slope_label(series: pd.Series, threshold=0.15) -> str:
    """Return GROWING / DECLINING / STABLE based on linear slope."""
    if len(series) < 2:
        return 'INSUFFICIENT_DATA'
    x = np.arange(len(series))
    y = series.values.astype(float)
    if y.sum() == 0:
        return 'NO_ACTIVITY'
    slope = np.polyfit(x, y, 1)[0]
    pct_change = slope / (y.mean() + 1e-9)
    if pct_change > threshold:
        return 'GROWING'
    if pct_change < -threshold:
        return 'DECLINING'
    return 'STABLE'


def _r(val):
    return round(float(val), 2) if pd.notna(val) else 0.0


# ── tool 1: top N ─────────────────────────────────────────────────────────────

def get_top_n(entity: str, n: int, metric: str = 'revenue') -> dict:
    """Top N customers or products by revenue / qty / orders."""
    _, sod, inv = load_data()

    entity = entity.lower()
    metric = metric.lower()

    group_col = 'Customer Name' if entity == 'customer' else 'Item Name'
    metric_map = {
        'revenue': ('Amount', 'sum'),
        'qty':     ('Qty',    'sum'),
        'orders':  ('Doc.No.', 'nunique'),
    }
    if metric not in metric_map:
        metric = 'revenue'

    agg_col, agg_fn = metric_map[metric]
    total = inv[agg_col].agg(agg_fn)
    ranked = (
        inv.groupby(group_col)[agg_col]
        .agg(agg_fn)
        .sort_values(ascending=False)
        .head(n)
    )

    results = []
    for rank, (name, val) in enumerate(ranked.items(), 1):
        share = _r((val / total) * 100) if total else 0
        results.append({'rank': rank, 'name': name, metric: _r(val), 'share_pct': share})

    return {
        'entity': entity,
        'metric': metric,
        'top_n': n,
        'total': _r(total),
        'results': results,
    }


# ── tool 2: customer health score ─────────────────────────────────────────────

def get_customer_health_scores(customer_name: str = None) -> dict:
    """
    Weighted health score per customer (0-100).
    Revenue 40% | Frequency 30% | Product diversity 20% | Recency 10%
    Only returns scores for customers with issues unless customer_name specified.
    """
    _, sod, inv = load_data()

    agg = inv.groupby('Customer Name').agg(
        revenue=('Amount', 'sum'),
        orders=('Doc.No.', 'nunique'),
        unique_products=('Item Name', 'nunique'),
        last_date=('Posting Date', 'max'),
        qty=('Qty', 'sum'),
    ).reset_index()

    max_rev = agg['revenue'].max()
    max_ord = agg['orders'].max()
    max_prod = agg['unique_products'].max()
    latest = agg['last_date'].max()

    scores = []
    for _, row in agg.iterrows():
        rev_score  = (row['revenue']          / max_rev)  * 40
        freq_score = (row['orders']            / max_ord)  * 30
        div_score  = (row['unique_products']   / max_prod) * 20
        days_since = (latest - row['last_date']).days if pd.notna(row['last_date']) else 30
        rec_score  = max(0, (1 - days_since / 30)) * 10

        total_score = _r(rev_score + freq_score + div_score + rec_score)

        scores.append({
            'customer': row['Customer Name'],
            'score': total_score,
            'revenue': _r(row['revenue']),
            'orders': int(row['orders']),
            'unique_products': int(row['unique_products']),
            'days_since_last_order': int(days_since),
            'rating': 'HIGH' if total_score >= 60 else ('MEDIUM' if total_score >= 30 else 'LOW'),
        })

    scores.sort(key=lambda x: x['score'], reverse=True)

    if customer_name:
        match = [s for s in scores if customer_name.lower() in s['customer'].lower()]
        return {'scores': match or [{'error': f'Customer {customer_name!r} not found'}]}

    return {'scores': scores}


# ── tool 3: discontinuation candidates ────────────────────────────────────────

def get_discontinuation_candidates(entity_type: str = 'both') -> dict:
    """
    Identify products or customers to discontinue.
    Criteria: bottom-10th-percentile revenue AND ≤2 orders AND no activity in final week.
    """
    _, sod, inv = load_data()
    results = {'products': [], 'customers': []}

    latest_week = inv['week'].max()

    # products
    if entity_type in ('product', 'both'):
        p = inv.groupby('Item Name').agg(
            revenue=('Amount', 'sum'),
            orders=('Doc.No.', 'nunique'),
            qty=('Qty', 'sum'),
            last_week=('week', 'max'),
        ).reset_index()

        threshold = p['revenue'].quantile(0.10)

        for _, row in p.iterrows():
            if row['revenue'] <= threshold and row['orders'] <= 2 and row['last_week'] < latest_week:
                results['products'].append({
                    'name': row['Item Name'],
                    'revenue': _r(row['revenue']),
                    'orders': int(row['orders']),
                    'qty_sold': int(row['qty']),
                    'last_active_week': int(row['last_week']),
                    'reason': (
                        f"Revenue ₹{_r(row['revenue'])} is in bottom 10% of all products, "
                        f"only {int(row['orders'])} order(s), no activity after week {int(row['last_week'])}. "
                        "Holding this SKU adds inventory cost with minimal return."
                    ),
                })

    # customers
    if entity_type in ('customer', 'both'):
        c = inv.groupby('Customer Name').agg(
            revenue=('Amount', 'sum'),
            orders=('Doc.No.', 'nunique'),
            last_week=('week', 'max'),
        ).reset_index()

        med_rev = c['revenue'].median()

        for _, row in c.iterrows():
            if row['orders'] == 1 and row['revenue'] < med_rev / 2 and row['last_week'] < latest_week:
                results['customers'].append({
                    'name': row['Customer Name'],
                    'revenue': _r(row['revenue']),
                    'orders': int(row['orders']),
                    'last_active_week': int(row['last_week']),
                    'reason': (
                        f"Only 1 order in the entire period, revenue ₹{_r(row['revenue'])} is below "
                        f"half the median (₹{_r(med_rev / 2)}), no repeat. "
                        "Low relationship value — consider deprioritising unless strategic reason exists."
                    ),
                })

    results['summary'] = {
        'discontinue_products_count': len(results['products']),
        'discontinue_customers_count': len(results['customers']),
    }
    return results


# ── tool 4: volume growth alerts ──────────────────────────────────────────────

def get_volume_growth_alerts(entity_type: str = 'both', threshold_pct: float = 20.0) -> dict:
    """
    Compare first-half vs second-half revenue/qty.
    Flags entities growing > threshold_pct% — recommended for increased focus.
    """
    _, sod, inv = load_data()
    results = {'growing_customers': [], 'growing_products': []}

    def _alerts(df, group_col):
        alerts = []
        for name, grp in df.groupby(group_col):
            h1 = grp[grp['half'] == 'first']['Amount'].sum()
            h2 = grp[grp['half'] == 'second']['Amount'].sum()
            if h1 == 0 and h2 == 0:
                continue
            if h1 == 0:
                pct = 100.0
            else:
                pct = ((h2 - h1) / h1) * 100

            if pct >= threshold_pct:
                alerts.append({
                    'name': name,
                    'first_half_revenue': _r(h1),
                    'second_half_revenue': _r(h2),
                    'growth_pct': _r(pct),
                    'recommendation': (
                        f"Revenue grew {_r(pct)}% from first half to second half. "
                        "Increase focus — prioritise stock, relationship, and upsell opportunities."
                    ),
                })
        return sorted(alerts, key=lambda x: x['growth_pct'], reverse=True)

    if entity_type in ('customer', 'both'):
        results['growing_customers'] = _alerts(inv, 'Customer Name')

    if entity_type in ('product', 'both'):
        results['growing_products'] = _alerts(inv, 'Item Name')

    results['threshold_pct'] = threshold_pct
    results['summary'] = {
        'growing_customers': len(results['growing_customers']),
        'growing_products': len(results['growing_products']),
    }
    return results


# ── tool 5: trend direction ───────────────────────────────────────────────────

def get_trend_direction(entity_type: str = 'both', entity_name: str = None) -> dict:
    """
    Weekly revenue trend per customer or product.
    Returns only GROWING and DECLINING — silent on STABLE/INSUFFICIENT.
    """
    _, sod, inv = load_data()
    results = {'growing': [], 'declining': []}

    def _trends(df, group_col):
        all_weeks = sorted(df['week'].unique())
        for name, grp in df.groupby(group_col):
            weekly = grp.groupby('week')['Amount'].sum().reindex(all_weeks, fill_value=0)
            label = _slope_label(weekly)
            if label in ('GROWING', 'DECLINING'):
                w_dict = {f'week_{w}': _r(weekly[w]) for w in all_weeks}
                entry = {
                    'name': name,
                    'trend': label,
                    'weekly_revenue': w_dict,
                    'total_revenue': _r(grp['Amount'].sum()),
                }
                if label == 'GROWING':
                    entry['action'] = "Increasing trend — deepen relationship, ensure stock availability, explore upsell."
                else:
                    entry['action'] = "Declining trend — investigate: satisfaction issue, competition, seasonal, or at-risk customer/product."
                results['growing' if label == 'GROWING' else 'declining'].append(entry)

    if entity_type in ('customer', 'both'):
        df = inv
        if entity_name:
            df = inv[inv['Customer Name'].str.contains(entity_name, case=False, na=False)]
        _trends(df, 'Customer Name')

    if entity_type in ('product', 'both'):
        df = inv
        if entity_name:
            df = inv[inv['Item Name'].str.contains(entity_name, case=False, na=False)]
        _trends(df, 'Item Name')

    results['summary'] = {
        'growing_count': len(results['growing']),
        'declining_count': len(results['declining']),
    }
    return results


# ── tool 6: order-to-invoice analysis ─────────────────────────────────────────

def get_order_to_invoice_analysis(customer_name: str = None) -> dict:
    """
    Compare SO customer revenue vs invoiced revenue.
    Detects customers with large order-to-invoice gaps (unfulfilled or pending orders).
    """
    so, sod, inv = load_data()

    so_rev = sod.groupby('Customer Name')['Amount'].sum().reset_index()
    so_rev.columns = ['Customer Name', 'so_revenue']

    inv_rev = inv.groupby('Customer Name')['Amount'].sum().reset_index()
    inv_rev.columns = ['Customer Name', 'invoiced_revenue']

    merged = pd.merge(so_rev, inv_rev, on='Customer Name', how='outer').fillna(0)
    merged['gap'] = merged['so_revenue'] - merged['invoiced_revenue']
    merged['gap_pct'] = ((merged['gap'] / (merged['so_revenue'] + 1e-9)) * 100).round(1)

    if customer_name:
        merged = merged[merged['Customer Name'].str.contains(customer_name, case=False, na=False)]

    records = []
    for _, row in merged.iterrows():
        status = 'MATCHED' if abs(row['gap_pct']) < 5 else ('UNDER_INVOICED' if row['gap'] > 0 else 'OVER_INVOICED')
        records.append({
            'customer': row['Customer Name'],
            'so_revenue': _r(row['so_revenue']),
            'invoiced_revenue': _r(row['invoiced_revenue']),
            'gap': _r(row['gap']),
            'gap_pct': _r(row['gap_pct']),
            'status': status,
            'note': (
                f"₹{_r(row['gap'])} ({_r(row['gap_pct'])}%) ordered but not yet invoiced — "
                "check fulfilment or pending delivery." if status == 'UNDER_INVOICED'
                else ('Revenue matches orders.' if status == 'MATCHED'
                      else f"Invoiced ₹{_r(abs(row['gap']))} more than ordered — check for manual invoices.")
            ),
        })

    records.sort(key=lambda x: abs(x['gap']), reverse=True)
    return {'analysis': records, 'total_so_revenue': _r(merged['so_revenue'].sum()),
            'total_invoiced': _r(merged['invoiced_revenue'].sum())}


# ── tool 7: low volume analysis ───────────────────────────────────────────────

def get_low_volume_analysis(top_n: int = 20) -> dict:
    """
    Bottom N products by qty sold. Helps identify slow-moving inventory.
    """
    _, sod, inv = load_data()

    prod = inv.groupby('Item Name').agg(
        qty=('Qty', 'sum'),
        revenue=('Amount', 'sum'),
        orders=('Doc.No.', 'nunique'),
        customers=('Customer Name', 'nunique'),
    ).reset_index().sort_values('qty')

    results = []
    for _, row in prod.head(top_n).iterrows():
        results.append({
            'product': row['Item Name'],
            'qty_sold': int(row['qty']),
            'revenue': _r(row['revenue']),
            'orders': int(row['orders']),
            'customers': int(row['customers']),
            'verdict': (
                'DEAD_STOCK' if row['qty'] == 0
                else ('VERY_LOW' if row['qty'] <= 5 else 'LOW')
            ),
        })

    return {'low_volume_products': results, 'count': len(results)}


# ── tool 8: revenue summary ───────────────────────────────────────────────────

def get_revenue_summary() -> dict:
    """Overall business summary: total revenue, orders, customers, products, weekly breakdown."""
    so, sod, inv = load_data()

    weekly = inv.groupby('week')['Amount'].sum().to_dict()
    top_cat = inv.groupby('category')['Amount'].sum().sort_values(ascending=False)

    return {
        'period': '01-Apr-2026 to 30-Apr-2026',
        'total_invoiced_revenue': _r(inv['Amount'].sum()),
        'total_so_value': _r(so['Grand Total'].sum()),
        'total_invoice_line_items': len(inv),
        'unique_customers': int(inv['Customer Name'].nunique()),
        'unique_products': int(inv['Item Name'].nunique()),
        'unique_orders': int(inv['Doc.No.'].nunique()),
        'weekly_revenue': {f'week_{k}': _r(v) for k, v in weekly.items()},
        'top_categories': [
            {'category': cat, 'revenue': _r(rev), 'share_pct': _r(rev / inv['Amount'].sum() * 100)}
            for cat, rev in top_cat.head(8).items()
        ],
        'avg_order_value': _r(inv.groupby('Doc.No.')['Amount'].sum().mean()),
        'peak_week': int(max(weekly, key=weekly.get)),
    }


# ── tool 9: customer deep dive ────────────────────────────────────────────────

def get_customer_deep_dive(customer_name: str) -> dict:
    """Full breakdown for a single customer: orders, products, trend, health."""
    _, sod, inv = load_data()

    c_inv = inv[inv['Customer Name'].str.contains(customer_name, case=False, na=False)]
    c_sod = sod[sod['Customer Name'].str.contains(customer_name, case=False, na=False)]

    if c_inv.empty and c_sod.empty:
        return {'error': f'No data found for customer matching {customer_name!r}'}

    weekly = c_inv.groupby('week')['Amount'].sum()
    trend = _slope_label(weekly)

    top_products = (
        c_inv.groupby('Item Name')['Amount'].sum()
        .sort_values(ascending=False).head(5)
        .to_dict()
    )

    return {
        'customer': customer_name,
        'total_revenue': _r(c_inv['Amount'].sum()),
        'total_orders': int(c_inv['Doc.No.'].nunique()),
        'total_qty': int(c_inv['Qty'].sum()),
        'unique_products': int(c_inv['Item Name'].nunique()),
        'so_value': _r(c_sod['Amount'].sum()),
        'trend': trend,
        'weekly_revenue': {f'week_{k}': _r(v) for k, v in weekly.to_dict().items()},
        'top_products': [{
            'product': p,
            'revenue': _r(r),
        } for p, r in top_products.items()],
        'action': (
            "Priority customer — growing. Increase stock depth for their top products, strengthen relationship."
            if trend == 'GROWING'
            else (
                "Declining activity — investigate satisfaction, pending orders, or competitive loss."
                if trend == 'DECLINING'
                else "Stable customer."
            )
        ),
    }


# ── tool 10: product deep dive ────────────────────────────────────────────────

def get_product_deep_dive(product_name: str) -> dict:
    """Full breakdown for a product: customers, revenue, qty, trend."""
    _, sod, inv = load_data()

    p_inv = inv[inv['Item Name'].str.contains(product_name, case=False, na=False)]

    if p_inv.empty:
        return {'error': f'No data found for product matching {product_name!r}'}

    weekly = p_inv.groupby('week')['Amount'].sum()
    trend = _slope_label(weekly)

    top_customers = (
        p_inv.groupby('Customer Name')['Amount'].sum()
        .sort_values(ascending=False).head(5)
        .to_dict()
    )

    return {
        'product': product_name,
        'total_revenue': _r(p_inv['Amount'].sum()),
        'total_qty': int(p_inv['Qty'].sum()),
        'unique_customers': int(p_inv['Customer Name'].nunique()),
        'avg_rate': _r(p_inv['Rate'].mean()),
        'trend': trend,
        'weekly_revenue': {f'week_{k}': _r(v) for k, v in weekly.to_dict().items()},
        'top_customers': [{
            'customer': c,
            'revenue': _r(r),
        } for c, r in top_customers.items()],
        'action': (
            "Growing product — ensure stock, explore new customers for this item."
            if trend == 'GROWING'
            else (
                "Declining product — check if customer-specific or market-wide. Consider promotion or phase-out."
                if trend == 'DECLINING'
                else "Stable product."
            )
        ),
    }


# ── tool 11: payment behavior stub ───────────────────────────────────────────

def get_payment_behavior(customer_name: str = None) -> dict:
    """Stub — requires Payment Entries data not yet uploaded."""
    return {
        'status': 'DATA_NOT_AVAILABLE',
        'message': (
            'Payment behavior analysis requires Payment Entries data. '
            'Please upload the payment ledger Excel from your ERP. '
            'Once available, this tool will show: avg payment delay days, '
            'number of part-payments per invoice, outstanding amounts, '
            'and customers with chronic late payment behavior.'
        ),
        'required_columns': ['Customer', 'Invoice Ref', 'Payment Date', 'Amount Paid', 'Invoice Date'],
    }


# ── tool 12: returns analysis stub ────────────────────────────────────────────

def get_return_analysis(customer_name: str = None) -> dict:
    """Stub — requires Sales Returns data not yet uploaded."""
    return {
        'status': 'DATA_NOT_AVAILABLE',
        'message': (
            'Returns analysis requires Sales Return/Credit Note data. '
            'Please upload returns ledger from your ERP. '
            'Once available this tool will show: return rate per product, '
            'customers with high return frequency, and return-correlated discontinuation signals.'
        ),
        'required_columns': ['Customer', 'Item', 'Return Date', 'Qty Returned', 'Reason'],
    }


# ── registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    'get_top_n':                      get_top_n,
    'get_customer_health_scores':     get_customer_health_scores,
    'get_discontinuation_candidates': get_discontinuation_candidates,
    'get_volume_growth_alerts':       get_volume_growth_alerts,
    'get_trend_direction':            get_trend_direction,
    'get_order_to_invoice_analysis':  get_order_to_invoice_analysis,
    'get_low_volume_analysis':        get_low_volume_analysis,
    'get_revenue_summary':            get_revenue_summary,
    'get_customer_deep_dive':         get_customer_deep_dive,
    'get_product_deep_dive':          get_product_deep_dive,
    'get_payment_behavior':           get_payment_behavior,
    'get_return_analysis':            get_return_analysis,
}
