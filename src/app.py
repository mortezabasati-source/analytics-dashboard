from datetime import datetime, timedelta
import pandas as pd  # type: ignore
import plotly.express as px  # type: ignore
import plotly.graph_objects as go  # type: ignore
import streamlit as st  # type: ignore
from dateutil.relativedelta import relativedelta  # type: ignore

from db import load_data  # Import the data loading function

# --- Page Configuration ---
st.set_page_config(
    page_title="Försäljningsöversikt",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for LTR Layout ---
def force_ltr_css():
    st.markdown(
        """
        <style>
            body, .stApp, .stSidebar, .stMetric, .stDateInput, .stSelectbox { direction: ltr !important; }
            div, p, h1, h2, h3, h4, h5, h6, .stMarkdown, .stMetric-label, .stMetric-value { text-align: left !important; }
            .stSidebar .st-emotion-cache-16txtl3 { text-align: left !important; }

            /* Reduce font size for metric values to prevent truncation */
            div[data-testid="stMetricValue"] {
                font-size: 1.8rem !important;
            }
            div[data-testid="stMetricLabel"] p {
                font-size: 0.9rem !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- Loading Animation HTML ---
loading_animation_html = """
<style>
    .loader-container {
        display: flex;
        flex-direction: column;
        gap: 3rem;
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        justify-content: center; 
        align-items: center;
        width: 100%;
        font-family: 'Arial', sans-serif;
        font-weight: bold;
        font-size: 6rem;
        z-index: 9999;
    }
    .loader-text {
        display: flex;
        justify-content: center;
    }
    .loader-letter {
        color: #1f77b4;
        opacity: 0.5;
        animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
    }
    .loader-letter:nth-child(1) { animation-delay: 0.1s; }
    .loader-letter:nth-child(2) { animation-delay: 0.2s; }
    .loader-letter:nth-child(3) { animation-delay: 0.3s; }
    .loader-letter:nth-child(4) { animation-delay: 0.4s; }
    .loader-letter:nth-child(5) { animation-delay: 0.5s; }
    .loader-letter:nth-child(6) { animation-delay: 0.6s; }
    .loader-letter:nth-child(7) { animation-delay: 0.7s; }

    .progress-bar-container {
        width: 50%;
        max-width: 800px;
        height: 25px;
        background-color: #e0e0e0;
        border-radius: 15px;
        border: 2px solid #1f77b4;
        overflow: hidden;
    }
    .progress-bar-fill {
        width: 100%;
        height: 100%;
        background-color: #1f77b4;
        animation: fill-progress 2.5s infinite linear;
    }
    @keyframes fill-progress {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
</style>
<div class="loader-container">
    <div class="loader-text">
        <span class="loader-letter">E</span><span class="loader-letter">A</span><span class="loader-letter">T</span>
        <span class="loader-letter">A</span><span class="loader-letter">W</span><span class="loader-letter">A</span>
        <span class="loader-letter">Y</span>
    </div>
    <div class="progress-bar-container"><div class="progress-bar-fill"></div></div>
</div>
"""

def safe_weekly_resample(df):
    """Safely resamples DataFrame on a weekly basis."""
    if df.empty:
        return pd.DataFrame()
    df_temp = df.copy()
    df_temp['order_date'] = pd.to_datetime(df_temp['order_date'])
    return df_temp.set_index('order_date').resample('W-SAT')[['sales', 'return_sales']].sum()

def display_correlated_return_analysis(filtered_df):
    """Displays weekly correlated return analysis."""
    st.markdown("---")
    st.markdown("### Analys av Korrelerad Retur (Veckobaserad)")
    st.info("I denna analys kopplas returer från en vecka till försäljningen från föregående vecka för att ge en mer rättvisande bild av returandelen.", icon="💡")

    if filtered_df.empty:
        return

    weekly_agg = safe_weekly_resample(filtered_df)
    weekly_agg['sales_prev_week'] = weekly_agg['sales'].shift(1)
    weekly_agg['correlated_return_rate'] = (weekly_agg['return_sales'] / weekly_agg['sales_prev_week'].replace(0, 1)) * 100

    plot_df = weekly_agg.dropna(subset=['sales_prev_week']).reset_index()

    # Shifted label logic for Correlated Returns (V29/30)
    def format_corr_week_label(date_val):
        curr_week = int(date_val.strftime('%U'))
        prev_week = curr_week - 1
        year = date_val.strftime('%Y')
        return f"V{prev_week}/{curr_week}, {year}"

    plot_df['Vecka'] = plot_df['order_date'].apply(format_corr_week_label)

    fig_corr_return = go.Figure()
    color_sales, color_return = '#1f77b4', '#d62728'

    corr_hovertemplate = (
        "<b>%{x}</b><br><br>" +
        f"<span style='color:{color_sales};'>Föreg. Veckas Försäljning: %{{y:,.1f}} kSEK</span><br>" +
        f"<span style='color:{color_return};'>Returbelopp: %{{customdata[0]:,.1f}} kSEK</span><br>" +
        f"<span style='color:{color_return};'>Korrelerad Returandel: %{{customdata[1]:.2f}}%</span><br>" +
        "<extra></extra>"
    )

    fig_corr_return.add_trace(go.Bar(
        x=plot_df['Vecka'],
        y=plot_df['sales_prev_week'] / 1000,
        name='Föregående Veckas Försäljning',
        marker_color=color_sales,
        customdata=plot_df[['return_sales', 'correlated_return_rate']],
        hovertemplate=corr_hovertemplate
    ))

    fig_corr_return.add_trace(go.Bar(
        x=plot_df['Vecka'],
        y=plot_df['return_sales'] / 1000,
        name='Returbelopp (Nuvarande Vecka)',
        marker_color=color_return,
        hoverinfo='none'
    ))

    fig_corr_return.add_trace(go.Scatter(
        x=plot_df['Vecka'],
        y=plot_df['correlated_return_rate'],
        name='Korrelerad Returandel',
        mode='lines+markers',
        line=dict(color=color_return, width=2),
        yaxis='y2',
        hoverinfo='none'
    ))

    fig_corr_return.update_layout(
        title_text='Korrelerad Retur',
        barmode='overlay',
        title_x=0, margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(title='Bruttoförsäljning (kSEK)'),
        yaxis2=dict(title='Korrelerad Returandel (%)', overlaying='y', side='right', showgrid=False, ticksuffix='%', dtick=1),
        legend_title_text='Mått'
    )
    st.plotly_chart(fig_corr_return, use_container_width=True)

def display_store_performance(filtered_df, prev_year_df):
    """Displays the Store Performance Leaderboard using robust explicit joins."""
    st.markdown("### Butikernas Prestation")

    # Master list of store names
    all_stores = set(filtered_df['store_name'].dropna().unique())
    if not prev_year_df.empty:
        all_stores.update(prev_year_df['store_name'].dropna().unique())

    store_perf = pd.DataFrame({'store_name': list(all_stores)})
    # Ensure all store names are strings and strip whitespace. Use map to avoid Series.str typing issues.
    store_perf['store_name'] = store_perf['store_name'].map(lambda x: (str(x) if x is not None else '').strip())
    store_perf = store_perf[store_perf['store_name'] != '']

    # Current period metrics
    curr_metrics = filtered_df.groupby('store_name', observed=False).agg(
        gross_sales=('sales', 'sum'),
        return_sales=('return_sales', 'sum'),
        quantity=('quantity', 'sum')
    ).reset_index()
    curr_metrics['net_sales'] = curr_metrics['gross_sales'] - curr_metrics['return_sales']
    curr_metrics['return_rate'] = (curr_metrics['return_sales'] / curr_metrics['gross_sales'].replace(0, 1)) * 100
    curr_metrics[['gross_sales', 'return_sales', 'quantity', 'net_sales', 'return_rate']] = curr_metrics[
        ['gross_sales', 'return_sales', 'quantity', 'net_sales', 'return_rate']
    ].apply(pd.to_numeric, errors='coerce').fillna(0)

    store_perf = pd.merge(store_perf, curr_metrics, on='store_name', how='left').fillna(0)

    # Previous year metrics & YoY logic
    store_perf['net_sales_yoy'] = pd.NA
    store_perf['quantity_yoy'] = pd.NA
    store_perf['return_rate_yoy'] = pd.NA

    if not prev_year_df.empty:
        prev_metrics = prev_year_df.groupby('store_name', observed=False).agg(
            gross_sales_prev=('sales', 'sum'),
            return_sales_prev=('return_sales', 'sum'),
            quantity_prev=('quantity', 'sum')
        ).reset_index()
        prev_metrics['net_sales_prev'] = prev_metrics['gross_sales_prev'] - prev_metrics['return_sales_prev']
        prev_metrics['return_rate_prev'] = (prev_metrics['return_sales_prev'] / prev_metrics['gross_sales_prev'].replace(0, 1)) * 100
        prev_metrics[['gross_sales_prev', 'return_sales_prev', 'quantity_prev', 'net_sales_prev', 'return_rate_prev']] = prev_metrics[
            ['gross_sales_prev', 'return_sales_prev', 'quantity_prev', 'net_sales_prev', 'return_rate_prev']
        ].apply(pd.to_numeric, errors='coerce')

        store_perf = pd.merge(store_perf, prev_metrics, on='store_name', how='left')

        # Ensure numeric types for calculations
        for col in ['net_sales', 'net_sales_prev', 'quantity', 'quantity_prev', 'return_rate', 'return_rate_prev']:
            if col in store_perf.columns:
                store_perf[col] = pd.to_numeric(store_perf[col], errors='coerce')

        # Calculate YoY only if previous year sales exist
        has_prev_sales = store_perf['net_sales_prev'].notna() & (store_perf['net_sales_prev'] > 0)
        has_prev_qty = store_perf['quantity_prev'].notna() & (store_perf['quantity_prev'] > 0)

        # Ensure numeric types explicitly before arithmetic to avoid type errors
        store_perf['net_sales'] = pd.to_numeric(store_perf['net_sales'], errors='coerce')
        store_perf['net_sales_prev'] = pd.to_numeric(store_perf['net_sales_prev'], errors='coerce')

        # Avoid division by zero by treating zeros as NaN for the ratio, compute YoY and fill NaN with 0
        numer = pd.to_numeric(store_perf.loc[has_prev_sales, 'net_sales'], errors='coerce')
        denom = pd.to_numeric(store_perf.loc[has_prev_sales, 'net_sales_prev'], errors='coerce')
        if not isinstance(numer, pd.Series):
            numer = pd.Series(numer, index=store_perf.loc[has_prev_sales].index)
        if not isinstance(denom, pd.Series):
            denom = pd.Series(denom, index=store_perf.loc[has_prev_sales].index)
        denom = denom.where(denom != 0, pd.NA).fillna(1)
        store_perf.loc[has_prev_sales, 'net_sales_yoy'] = ((numer - denom) / denom) * 100
        store_perf['net_sales_yoy'] = store_perf['net_sales_yoy'].fillna(0)

        store_perf['quantity'] = pd.to_numeric(store_perf['quantity'], errors='coerce')
        store_perf['quantity_prev'] = pd.to_numeric(store_perf['quantity_prev'], errors='coerce')
        qty_numer = pd.to_numeric(store_perf.loc[has_prev_qty, 'quantity'], errors='coerce')
        qty_denom = pd.to_numeric(store_perf.loc[has_prev_qty, 'quantity_prev'], errors='coerce')
        if not isinstance(qty_numer, pd.Series):
            qty_numer = pd.Series(qty_numer, index=store_perf.loc[has_prev_qty].index)
        if not isinstance(qty_denom, pd.Series):
            qty_denom = pd.Series(qty_denom, index=store_perf.loc[has_prev_qty].index)
        qty_denom = qty_denom.where(qty_denom != 0, pd.NA).fillna(1)
        store_perf.loc[has_prev_qty, 'quantity_yoy'] = ((qty_numer - qty_denom) / qty_denom) * 100
        store_perf['quantity_yoy'] = store_perf['quantity_yoy'].fillna(0)

        # Ensure return rates are numeric to avoid unsupported operand errors during subtraction
        rr = pd.to_numeric(store_perf['return_rate'], errors='coerce')
        if not isinstance(rr, pd.Series):
            rr = pd.Series(rr, index=store_perf.index)
        store_perf['return_rate'] = rr.fillna(0)

        rr_prev = pd.to_numeric(store_perf['return_rate_prev'], errors='coerce')
        if not isinstance(rr_prev, pd.Series):
            rr_prev = pd.Series(rr_prev, index=store_perf.index)
        store_perf['return_rate_prev'] = rr_prev.fillna(0)
        # Coerce to numeric to avoid unsupported operand types during subtraction
        left = pd.to_numeric(store_perf.loc[has_prev_sales, 'return_rate'], errors='coerce')
        if not isinstance(left, pd.Series):
            left = pd.Series(left, index=store_perf.loc[has_prev_sales].index)
        left = left.fillna(0)
        right = pd.to_numeric(store_perf.loc[has_prev_sales, 'return_rate_prev'], errors='coerce')
        if not isinstance(right, pd.Series):
            right = pd.Series(right, index=store_perf.loc[has_prev_sales].index)
        right = right.fillna(0)
        store_perf.loc[has_prev_sales, 'return_rate_yoy'] = left - right

    # Correlated returns flagging
    store_perf['Status'] = ''
    top_20_sales = store_perf.nlargest(20, 'net_sales')['store_name'].tolist()
    top_20_sales_mask = store_perf['store_name'].isin(top_20_sales)
    store_perf.loc[top_20_sales_mask, 'Status'] = (
        store_perf.loc[top_20_sales_mask, 'Status'].astype(str) + '🥇'
    )

    if not filtered_df.empty:
        weekly_store = filtered_df.groupby('store_name', observed=False).apply(safe_weekly_resample).reset_index()
        if not weekly_store.empty and 'store_name' in weekly_store.columns:
            weekly_store['sales_prev_week'] = weekly_store.groupby('store_name', observed=False)['sales'].shift(1)
            corr_totals = weekly_store.groupby('store_name', observed=False)[['return_sales', 'sales_prev_week']].sum().reset_index()
            corr_totals['correlated_return_rate'] = (corr_totals['return_sales'] / corr_totals['sales_prev_week'].replace(0, 1)) * 100

            store_perf = pd.merge(store_perf, corr_totals[['store_name', 'correlated_return_rate']], on='store_name', how='left').fillna({'correlated_return_rate': 0})
            top_20_returns = store_perf.nlargest(20, 'correlated_return_rate')['store_name'].tolist()
            top_20_returns_mask = store_perf['store_name'].isin(top_20_returns)
            store_perf.loc[top_20_returns_mask, 'Status'] = (
                store_perf.loc[top_20_returns_mask, 'Status'].astype(str) + '🚩'
            )

    store_perf = store_perf.sort_values('net_sales', ascending=False)

    display_df = store_perf.rename(columns={
        'store_name': 'Butik',
        'net_sales': 'Nettoförsäljning (kSEK)',
        'net_sales_yoy': 'Nettoförsäljning YoY (%)',
        'return_rate': 'Returandel (%)',
        'return_rate_yoy': 'Returandel YoY (p.p.)',
        'quantity': 'Antal Ordrar',
        'quantity_yoy': 'Antal Ordrar YoY (%)'
    })

    display_df['Nettoförsäljning (kSEK)'] /= 1000

    cols = ['Status', 'Butik', 'Nettoförsäljning (kSEK)', 'Nettoförsäljning YoY (%)', 'Returandel (%)', 'Returandel YoY (p.p.)', 'Antal Ordrar', 'Antal Ordrar YoY (%)']

    def color_yoy(val):
        if pd.isna(val): return ''
        return 'color: red' if val < 0 else 'color: #228B22' # Darker green for better contrast

    def color_return_yoy(val):
        if pd.isna(val): return ''
        return 'color: #228B22' if val < 0 else 'color: red' # Darker green for better contrast

    st.dataframe(
        display_df[cols].style.format({
            'Nettoförsäljning (kSEK)': '{:,.1f}',
            'Nettoförsäljning YoY (%)': '{:+.1f}%',
            'Returandel (%)': '{:.2f}%',
            'Returandel YoY (p.p.)': '{:+.2f}',
            'Antal Ordrar YoY (%)': '{:+.1f}%'
        }, na_rep="-")
        .map(color_yoy, subset=['Nettoförsäljning YoY (%)', 'Antal Ordrar YoY (%)'])
        .map(color_return_yoy, subset=['Returandel YoY (p.p.)'])
        .bar(subset=['Nettoförsäljning (kSEK)'], color='#aec7e8', vmin=0),
        use_container_width=True
    )

def display_new_churned_stores(filtered_df, prev_year_df):
    """Displays New and Churned stores with Actual Total Net Sales."""
    st.markdown("---")
    st.markdown("### Analys av Nya och Förlorade Butiker")
    st.info("Här visas butiker som tillkommit eller försvunnit i den valda perioden jämfört med samma period föregående år. Prestationen mäts som total nettoförsäljning.", icon="💡")

    curr_stores = set(filtered_df[filtered_df['sales'] > 0]['store_name'].dropna().astype(str).str.strip().unique())
    prev_stores = set(prev_year_df[prev_year_df['sales'] > 0]['store_name'].dropna().astype(str).str.strip().unique())

    new_stores_set = curr_stores - prev_stores
    churned_stores_set = prev_stores - curr_stores

    col_new, col_churned = st.columns(2)

    with col_new:
        st.markdown("#### Nya Butiker")
        if new_stores_set:
            new_df = filtered_df[filtered_df['store_name'].isin(new_stores_set)].copy()
            total_sales = new_df.groupby('store_name')['net_sales'].sum().reset_index().rename(
                columns={'store_name': 'Butik', 'net_sales': 'Total Nettoförsäljning (SEK)'}
            )
            total_sales = total_sales[total_sales['Total Nettoförsäljning (SEK)'] > 0]
            if not total_sales.empty:
                st.markdown(f"**Totalt:** `{total_sales['Total Nettoförsäljning (SEK)'].sum():,.0f} SEK`")
                total_sales = total_sales.sort_values('Total Nettoförsäljning (SEK)', ascending=False)
                st.dataframe(total_sales.style.format({'Total Nettoförsäljning (SEK)': '{:,.0f}'}), use_container_width=True)
            else:
                st.success("Inga nya butiker med positiv försäljning under denna period.", icon="✅")
        else:
            st.success("Inga nya butiker under denna period.", icon="✅")

    with col_churned:
        st.markdown("#### Förlorade Butiker")
        if churned_stores_set:
            churned_df = prev_year_df[prev_year_df['store_name'].isin(churned_stores_set)].copy()
            total_sales_ch = churned_df.groupby('store_name')['net_sales'].sum().reset_index().rename(
                columns={'store_name': 'Butik', 'net_sales': 'Total Nettoförsäljning (SEK)'}
            )
            total_sales_ch = total_sales_ch[total_sales_ch['Total Nettoförsäljning (SEK)'] > 0]
            if not total_sales_ch.empty:
                st.markdown(f"**Totalt:** `{total_sales_ch['Total Nettoförsäljning (SEK)'].sum():,.0f} SEK`")
                total_sales_ch = total_sales_ch.sort_values('Total Nettoförsäljning (SEK)', ascending=False)
                st.dataframe(total_sales_ch.style.format({'Total Nettoförsäljning (SEK)': '{:,.0f}'}), use_container_width=True)
            else:
                st.success("Inga förlorade butiker med positiv försäljning under denna period.", icon="✅")
        else:
            st.success("Inga butiker förlorade under denna period.", icon="✅")

def display_product_charts(filtered_df):
    """Displays Category Pie chart and Top 10 Products Bar chart."""
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        category_sales = filtered_df.groupby('category', observed=False)['sales'].sum().reset_index()
        category_sales['sales'] /= 1000
        fig_pie = px.pie(category_sales, names='category', values='sales', title='Försäljningsandel per Produkttyp', hole=0.4)
        fig_pie.update_traces(hovertemplate='<b>%{label}</b><br>Försäljning: %{value:,.1f} kSEK<br>Andel: %{percent}')
        fig_pie.update_layout(title_x=0, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        top_products = (
            filtered_df.assign(full_product_name=filtered_df['category'].astype(str) + ' - ' + filtered_df['product_name'].astype(str))
            .groupby('full_product_name')['sales'].sum().nlargest(10).sort_values(ascending=True).reset_index()
        )
        top_products['sales'] /= 1000
        fig_bar = px.bar(top_products, x='sales', y='full_product_name', orientation='h', title='Topp 10 Produkter', labels={'full_product_name': 'Produkt (Typ - Sort)', 'sales': 'Bruttoförsäljning (kSEK)'})
        fig_bar.update_layout(title_x=0, margin=dict(l=0, r=0, t=30, b=0), yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)

def display_smart_insights(filtered_df, prev_year_df):
    """Calculates and displays a set of dynamic, actionable insights."""
    st.markdown("---")
    with st.expander("💡 Snabbinsikter & Varningar", expanded=True):
        col1, col2, col3 = st.columns(3)

        # --- Insight 1: Best Performing Store (YoY Growth) ---
        with col1:
            best_store_name, best_yoy = None, None
            if not prev_year_df.empty:
                curr_sales = filtered_df.groupby('store_name', observed=False)['net_sales'].sum().reset_index()
                prev_sales = prev_year_df.groupby('store_name', observed=False)['net_sales'].sum().reset_index()

                yoy_df = pd.merge(curr_sales, prev_sales, on='store_name', suffixes=('_curr', '_prev'))
                yoy_df = yoy_df[yoy_df['net_sales_prev'] > 0] # Avoid division by zero and new stores

                if not yoy_df.empty:
                    yoy_df['yoy_growth'] = ((yoy_df['net_sales_curr'] - yoy_df['net_sales_prev']) / yoy_df['net_sales_prev']) * 100
                    best_performer_idx = yoy_df['yoy_growth'].idxmax()
                    best_store_name = yoy_df.loc[best_performer_idx, 'store_name']
                    best_yoy = yoy_df.loc[best_performer_idx, 'yoy_growth']

            if best_store_name:
                st.success(
                    f"**Top Growth:** Butik **{best_store_name}** har störst ökning i nettoförsäljning "
                    f"(**+{best_yoy:.1f}%** vs föregående år).",
                    icon="🟢"
                )
            else:
                st.info("Ingen YoY-data för att identifiera butik med högst tillväxt.", icon="ℹ️")

        # --- Insight 2: Store Needing Attention (High Returns) ---
        with col2:
            worst_store_name, worst_rate = None, None
            # Use correlated return rate if available (weekly view)
            weekly_store = filtered_df.groupby('store_name', observed=False).apply(safe_weekly_resample).reset_index()
            if not weekly_store.empty and 'store_name' in weekly_store.columns:
                weekly_store['sales_prev_week'] = weekly_store.groupby('store_name', observed=False)['sales'].shift(1)
                corr_totals = weekly_store.groupby('store_name', observed=False)[['return_sales', 'sales_prev_week']].sum().reset_index()
                corr_totals = corr_totals[corr_totals['sales_prev_week'] > 0]
                if not corr_totals.empty:
                    corr_totals['corr_rate'] = (corr_totals['return_sales'] / corr_totals['sales_prev_week']) * 100
                    worst_performer_idx = corr_totals['corr_rate'].idxmax()
                    worst_store_name = corr_totals.loc[worst_performer_idx, 'store_name']
                    worst_rate = corr_totals.loc[worst_performer_idx, 'corr_rate']

            if worst_store_name:
                st.warning(
                    f"**High Return Alert:** Butik **{worst_store_name}** har högst korrelerad returandel "
                    f"(**{worst_rate:.1f}%**).",
                    icon="🔴"
                )
            else:
                st.info("Ingen data för korrelerad returandel. Kontrollera i veckovyn.", icon="ℹ️")

        # --- Insight 3: Top Product Category by Sales ---
        with col3:
            if not filtered_df.empty:
                category_sales = filtered_df.groupby('category', observed=False)['sales'].sum().reset_index()
                total_sales = filtered_df['sales'].sum()

                if total_sales > 0 and not category_sales.empty:
                    top_category_idx = category_sales['sales'].idxmax()
                    top_category_name = category_sales.loc[top_category_idx, 'category']
                    top_category_share = (category_sales['sales'].max() / total_sales) * 100
                    st.info(
                        f"**Top Category:** Produkttypen **{top_category_name}** står för störst andel av "
                        f"försäljningen (**{top_category_share:.1f}%**).",
                        icon="📦"
                    )
                else:
                    st.info("Ingen försäljningsdata för att analysera produktkategorier.", icon="ℹ️")
            else:
                st.info("Ingen data för att analysera produktkategorier.", icon="ℹ️")


def main():
    """Main application execution flow."""
    force_ltr_css()

    # --- Loading Animation Placeholder (Placed at top before load_data) ---
    loading_placeholder = st.empty()
    loading_placeholder.markdown(loading_animation_html, unsafe_allow_html=True)
    
    df = load_data()
    loading_placeholder.empty()

    week_key_to_date = df.groupby('year_week_key')['order_date'].first()

    def format_week_label(week_key):
        if week_key not in week_key_to_date:
            return week_key
        year, week_u_str = week_key.split('-W')
        current_week = int(week_u_str)
        next_week = current_week + 1
        return f"V{current_week}/{next_week}, {year}"

    # --- Sidebar Filters ---
    st.sidebar.header("Filter")
    min_date, max_date = df['order_date'].min(), df['order_date'].max()

    locations = ['All'] + sorted(df['location'].dropna().unique().tolist())
    selected_location = st.sidebar.selectbox("Välj plats (ort)", options=locations)

    if selected_location == 'All':
        stores = ['All'] + sorted(df['store_name'].dropna().unique().tolist())
    else:
        available_stores_df = df[df['location'] == selected_location]
        stores = ['All'] + sorted(available_stores_df['store_name'].dropna().unique().tolist())
    selected_store = st.sidebar.selectbox("Välj butik (namn)", options=stores)

    categories = ['All'] + sorted(df['category'].dropna().unique().tolist())
    selected_category = st.sidebar.selectbox("Välj produkttyp (typ)", options=categories)

    st.sidebar.markdown("---")
    filter_mode = st.sidebar.radio("Välj filtermetod", ('Datumintervall', 'Veckovis', 'Månadsvis'), index=1, horizontal=True, label_visibility="collapsed")

    start_date, end_date = None, None
    filtered_df, prev_year_df = pd.DataFrame(), pd.DataFrame()

    if filter_mode == 'Datumintervall':
        today = datetime.now().date()
        start_of_current_week = today - timedelta(days=(today.weekday() + 1) % 7)
        calculated_start_date = start_of_current_week - timedelta(weeks=4)
        default_start_date = max(min_date, calculated_start_date)
        default_end_date = min(today, max_date)
        date_range = st.sidebar.date_input("Välj datumintervall", value=(default_start_date, default_end_date), min_value=min_date, max_value=max_date)
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = df[(df['order_date'] >= start_date) & (df['order_date'] <= end_date)]
            prev_year_start_date = start_date - relativedelta(years=1)
            prev_year_end_date = end_date - relativedelta(years=1)
            prev_year_df = df[(df['order_date'] >= prev_year_start_date) & (df['order_date'] <= prev_year_end_date)]

    elif filter_mode == 'Veckovis':
        all_weeks = sorted(df['year_week_key'].unique(), reverse=True)
        today = datetime.now().date()
        target_weeks = [(today - timedelta(weeks=i)).strftime('%Y-W%U') for i in range(5)]
        default_selection = [week for week in target_weeks if week in all_weeks] or all_weeks[:5]
        selected_weeks = st.sidebar.multiselect("Välj vecka/veckor", options=all_weeks, default=default_selection, format_func=format_week_label)
        filtered_df = df[df['year_week_key'].isin(selected_weeks)]
        prev_year_weeks = [f"{int(w.split('-W')[0]) - 1}-W{w.split('-W')[1]}" for w in selected_weeks]
        prev_year_df = df[df['year_week_key'].isin(prev_year_weeks)]

    elif filter_mode == 'Månadsvis':
        all_months = sorted(df['year_month_key'].unique(), reverse=True)
        selected_months = st.sidebar.multiselect("Välj månad/månader", options=all_months, default=all_months[:3])
        filtered_df = df[df['year_month_key'].isin(selected_months)]
        prev_year_months = [f"{int(m.split('-M')[0]) - 1}-M{m.split('-M')[1]}" for m in selected_months]
        prev_year_df = df[df['year_month_key'].isin(prev_year_months)]

    if not filtered_df.empty and start_date is None:
        start_date, end_date = filtered_df['order_date'].min(), filtered_df['order_date'].max()

    if selected_store != 'All':
        filtered_df = filtered_df[filtered_df['store_name'] == selected_store]
        if not prev_year_df.empty:
            prev_year_df = prev_year_df[prev_year_df['store_name'] == selected_store]
    if selected_location != 'All':
        filtered_df = filtered_df[filtered_df['location'] == selected_location]
        if not prev_year_df.empty:
            prev_year_df = prev_year_df[prev_year_df['location'] == selected_location]
    if selected_category != 'All':
        filtered_df = filtered_df[filtered_df['category'] == selected_category]
        if not prev_year_df.empty:
            prev_year_df = prev_year_df[prev_year_df['category'] == selected_category]

    st.title("Försäljningsöversikt")
    if start_date and end_date:
        st.markdown(f"Data från **{start_date.strftime('%Y-%m-%d')}** till **{end_date.strftime('%Y-%m-%d')}**")

    # --- Store Group KPI Section ---
    def categorize_store_group(store_name):
        """Categorizes a store name into ICA, Coop, Hemköp, or Övrig."""
        name_lower = str(store_name).lower()
        if name_lower.startswith('ica'):
            return 'ICA'
        elif name_lower.startswith('coop'):
            return 'Coop'
        elif name_lower.startswith('hemköp'):
            return 'Hemköp'
        else:
            return 'Övrig'

    filtered_df['store_group'] = filtered_df['store_name'].apply(categorize_store_group)
    if not prev_year_df.empty:
        prev_year_df['store_group'] = prev_year_df['store_name'].apply(categorize_store_group)

    group_sales_current = filtered_df.groupby('store_group', observed=False)['net_sales'].sum()
    group_sales_prev = prev_year_df.groupby('store_group', observed=False)['net_sales'].sum() if not prev_year_df.empty else pd.Series(dtype='float64')

    all_groups = ['ICA', 'Coop', 'Hemköp', 'Övrig']
    group_sales_current = group_sales_current.reindex(all_groups, fill_value=0)
    group_sales_prev = group_sales_prev.reindex(all_groups, fill_value=0)

    epsilon = 1e-9
    group_yoy_delta = ((group_sales_current - group_sales_prev) / (group_sales_prev.abs() + epsilon)) * 100

    st.markdown("#### Försäljning per Butikskedja")

    # --- Custom CSS for KPI Card Backgrounds ---
    st.markdown("""
    <style>
    /* Target the columns that hold the KPI cards */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) > div {
        background-color: #ffcccc; /* Light Red for ICA */
        border-radius: 10px; padding: 15px;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(2) > div {
        background-color: #ccffcc; /* Light Green for Coop */
        border-radius: 10px; padding: 15px;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(3) > div {
        background-color: #ffebcc; /* Light Orange for Hemköp */
        border-radius: 10px; padding: 15px;
    }
    div[data-testid="stHorizontalBlock"] > div:nth-child(4) > div {
        background-color: #ffffcc; /* Light Yellow for Övrig */
        border-radius: 10px; padding: 15px;
    }

    /* Change the color of the positive delta in all metric cards to blue */
    div[data-testid="stMetricDelta"] > div {
        color: #004080 !important; /* Darker blue for positive delta */
    }

    </style>
    """, unsafe_allow_html=True)

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("ICA Nettoförsäljning", f"{(group_sales_current.get('ICA', 0)/1000):,.1f} kSEK", f"{group_yoy_delta.get('ICA', 0):.2f}% vs Föregående År")
    kpi_cols[1].metric("Coop Nettoförsäljning", f"{(group_sales_current.get('Coop', 0)/1000):,.1f} kSEK", f"{group_yoy_delta.get('Coop', 0):.2f}% vs Föregående År")
    kpi_cols[2].metric("Hemköp Nettoförsäljning", f"{(group_sales_current.get('Hemköp', 0)/1000):,.1f} kSEK", f"{group_yoy_delta.get('Hemköp', 0):.2f}% vs Föregående År")
    kpi_cols[3].metric("Övrig Nettoförsäljning", f"{(group_sales_current.get('Övrig', 0)/1000):,.1f} kSEK", f"{group_yoy_delta.get('Övrig', 0):.2f}% vs Föregående År")
    st.markdown("---") # Visual separator

    if filtered_df.empty:
        st.warning("Ingen data tillgänglig för valda filter. Välj ett annat intervall.")
        st.stop()

    # --- KPI Calculations ---
    total_net_sales = filtered_df['net_sales'].sum()
    total_quantity = filtered_df['quantity'].sum()
    total_return_sales = filtered_df['return_sales'].sum()
    overall_return_rate = (total_return_sales / filtered_df['sales'].sum()) * 100 if filtered_df['sales'].sum() > 0 else 0

    total_net_sales_prev_year = prev_year_df['net_sales'].sum() if not prev_year_df.empty else 0
    total_quantity_prev_year = prev_year_df['quantity'].sum() if not prev_year_df.empty else 0
    total_return_sales_prev_year = prev_year_df['return_sales'].sum() if not prev_year_df.empty else 0
    overall_return_rate_prev_year = (total_return_sales_prev_year / prev_year_df['sales'].sum()) * 100 if not prev_year_df.empty and prev_year_df['sales'].sum() > 0 else 0

    epsilon = 1e-9
    net_sales_delta = ((total_net_sales - total_net_sales_prev_year) / (total_net_sales_prev_year + epsilon)) * 100
    quantity_delta = ((total_quantity - total_quantity_prev_year) / (total_quantity_prev_year + epsilon)) * 100
    return_value_delta = ((total_return_sales - total_return_sales_prev_year) / (total_return_sales_prev_year + epsilon)) * 100
    return_rate_delta = overall_return_rate - overall_return_rate_prev_year

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nettoförsäljning", f"{(total_net_sales/1000):,.1f} kSEK", f"{net_sales_delta:.2f}% vs Föregående År")
    col2.metric("Antal Ordrar", f"{int(total_quantity):,}", f"{quantity_delta:.2f}% vs Föregående År")
    col3.metric("Returvärde", f"{(total_return_sales/1000):,.1f} kSEK", f"{return_value_delta:.2f}% vs Föregående År", "inverse")
    col4.metric("Returandel (%)", f"{overall_return_rate:.2f}%", f"{return_rate_delta:.2f} p.p. vs Föregående År", "inverse")

    # --- Smart Insights Section ---
    display_smart_insights(filtered_df, prev_year_df)


    # --- YoY Trend Chart ---
    def prepare_yoy_data(df_curr, df_prev, mode):
        if df_curr.empty:
            return pd.DataFrame()

        freq, time_key_col, time_key_format = ('ME', 'MånadNr', '%m') if mode != 'Veckovis' else ('W-SAT', 'VeckaNr', '%U')

        def aggregate_data(df_in):
            df_temp = df_in.copy()
            df_temp['order_date'] = pd.to_datetime(df_temp['order_date'])
            agg_df = df_temp.set_index('order_date').resample(freq)[['sales', 'return_sales']].sum().reset_index()
            agg_df['net_sales_kSEK'] = (agg_df['sales'] - agg_df['return_sales']) / 1000
            agg_df['return_rate'] = (agg_df['return_sales'] / agg_df['sales'].replace(0, 1)) * 100
            agg_df[time_key_col] = agg_df['order_date'].dt.strftime(time_key_format).astype(int)
            return agg_df

        current_agg = aggregate_data(df_curr)
        previous_agg = aggregate_data(df_prev) if not df_prev.empty else pd.DataFrame(columns=current_agg.columns)

        yoy_data = pd.merge(current_agg, previous_agg, on=time_key_col, suffixes=('_curr', '_prev'), how='left')
        yoy_data = yoy_data.fillna({'sales_prev': 0, 'net_sales_kSEK_prev': 0, 'return_rate_prev': 0})

        if mode == 'Veckovis':
            yoy_data['AxisLabel'] = yoy_data['order_date_curr'].dt.strftime('%Y-W%U').apply(format_week_label)
        else:
            x_axis_labels = current_agg.set_index(time_key_col)['order_date'].dt.strftime('%b').to_dict()
            yoy_data['AxisLabel'] = yoy_data[time_key_col].map(x_axis_labels)

        return yoy_data.dropna(subset=['AxisLabel'])

    yoy_data = prepare_yoy_data(filtered_df, prev_year_df, filter_mode)

    if not yoy_data.empty:
        fig_line = go.Figure()
        color_current_gross, color_previous_gross = '#1f77b4', '#aec7e8'
        color_current_return, color_previous_return = '#d62728', '#ff9896'

        hovertemplate = (
            "<b>%{x}</b><br><br>" +
            "<b>Nuvarande Period:</b><br>" +
            f"<span style='color:{color_current_gross};'>Bruttoförsäljning: %{{customdata[0]:,.1f}} kSEK</span><br>" +
            "Nettoförsäljning: %{customdata[1]:,.1f} kSEK<br>" +
            f"<span style='color:{color_current_return};'>Returandel: %{{customdata[2]:.2f}}%</span><br>" +
            "<br><b>Föregående År:</b><br>" +
            f"<span style='color:{color_previous_gross};'>Bruttoförsäljning: %{{customdata[3]:,.1f}} kSEK</span><br>" +
            "Nettoförsäljning: %{customdata[4]:,.1f} kSEK<br>" +
            f"<span style='color:{color_previous_return};'>Returandel: %{{customdata[5]:.2f}}%</span><br>" +
            "<extra></extra>"
        )

        fig_line.add_trace(go.Bar(
            x=yoy_data['AxisLabel'], y=yoy_data['sales_curr'] / 1000,
            name='Bruttoförsäljning (Nuvarande)', marker_color=color_current_gross,
            customdata=yoy_data[['sales_curr', 'net_sales_kSEK_curr', 'return_rate_curr', 'sales_prev', 'net_sales_kSEK_prev', 'return_rate_prev']],
            hovertemplate=hovertemplate
        ))
        fig_line.add_trace(go.Bar(
            x=yoy_data['AxisLabel'], y=yoy_data['sales_prev'] / 1000,
            name='Bruttoförsäljning (Föregående)', marker_color=color_previous_gross,
            hoverinfo='none'
        ))
        fig_line.add_trace(go.Scatter(
            x=yoy_data['AxisLabel'], y=yoy_data['return_rate_curr'],
            name='Returandel % (Nuvarande)', mode='lines+markers', line=dict(color=color_current_return, width=2), yaxis='y2'
        ))
        fig_line.add_trace(go.Scatter(
            x=yoy_data['AxisLabel'], y=yoy_data['return_rate_prev'],
            name='Returandel % (Föregående)', mode='lines+markers', line=dict(color=color_previous_return, width=2, dash='dash'), yaxis='y2'
        ))

        fig_line.update_layout(
            barmode='overlay', title_text='Bruttoförsäljning & Returandel vs Föregående År',
            title_x=0, margin=dict(l=0, r=0, t=30, b=0),
            yaxis=dict(title='Bruttoförsäljning (kSEK)'),
            yaxis2=dict(title='Returandel (%)', overlaying='y', side='right', showgrid=False, ticksuffix='%', dtick=1),
            legend_title_text='Period & Mått'
        )
        st.plotly_chart(fig_line, use_container_width=True)

    # --- Display Sections ---
    if filter_mode == 'Veckovis':
        display_correlated_return_analysis(filtered_df)

    display_store_performance(filtered_df, prev_year_df)

    if not prev_year_df.empty:
        display_new_churned_stores(filtered_df, prev_year_df)

    display_product_charts(filtered_df)

if __name__ == "__main__":
    main()