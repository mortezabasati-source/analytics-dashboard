import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import gc
import plotly.express as px
from datetime import datetime, timedelta
from db import load_data # Import the data loading function
from dateutil.relativedelta import relativedelta

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

force_ltr_css()

# --- Loading Animation ---
loading_animation_html = """
<style>
    .loader-container {
        display: flex;
        flex-direction: column; /* Stack text and progress bar */
        gap: 3rem; /* Space between text and bar */
        position: fixed; /* Position relative to the viewport */
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%); /* Center the container */
        justify-content: center; 
        align-items: center;
        width: 100%;
        font-family: 'Arial', sans-serif;
        font-weight: bold;
        font-size: 15rem; /* Increased font size */
        z-index: 9999; /* Ensure it's on top */
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
        0%, 100% {
            transform: scale(1);
            opacity: 0.5;
        }
        50% {
            transform: scale(1.1);
            opacity: 1;
        }
    }
    /* Stagger the animation for a wave effect */
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
    <div class="loader-text"><span class="loader-letter">E</span><span class="loader-letter">A</span><span class="loader-letter">T</span><span class="loader-letter">A</span><span class="loader-letter">W</span><span class="loader-letter">A</span><span class="loader-letter">Y</span></div>
    <div class="progress-bar-container"><div class="progress-bar-fill"></div></div>
</div>
"""

# --- Data Loading ---
loading_placeholder = st.empty()
loading_placeholder.markdown(loading_animation_html, unsafe_allow_html=True)
df = load_data()
loading_placeholder.empty()

# --- Sidebar Filters ---
st.sidebar.header("Filter")

min_date = df['order_date'].min()
max_date = df['order_date'].max()

# --- Dependent Filters: Location -> Store ---
# 1. Location Filter (Primary)
locations = ['All'] + sorted(df['location'].unique().tolist())
selected_location = st.sidebar.selectbox("Välj plats (ort)", options=locations)

# 2. Store Filter (Dependent on Location)
if selected_location == 'All':
    # If no specific location is chosen, show all stores
    stores = ['All'] + sorted(df['store_name'].unique().tolist())
else:
    # If a location is chosen, filter the stores for that location
    available_stores_df = df[df['location'] == selected_location]
    stores = ['All'] + sorted(available_stores_df['store_name'].unique().tolist())
selected_store = st.sidebar.selectbox("Välj butik (namn)", options=stores)

# Category Filter
categories = ['All'] + sorted(df['category'].unique().tolist())
selected_category = st.sidebar.selectbox("Välj produkttyp (typ)", options=categories)

# Status Filter
st.sidebar.markdown("---")
status_options = {
    'All': 'Visa alla',
    'Medal': '🥇 Endast Medalj',
    'Flag': '🚩 Endast Flagga',
    'Both': '🥇 & 🚩 Båda'
}
selected_status_key = st.sidebar.selectbox("Filtrera efter status", options=list(status_options.keys()), format_func=lambda x: status_options[x])

# --- New Filtering Logic ---
st.sidebar.markdown("---")
filter_mode = st.sidebar.radio(
    "Välj filtermetod",
    ('Datumintervall', 'Veckovis', 'Månadsvis'),
    horizontal=True,
    label_visibility="collapsed"
)

start_date, end_date = None, None

if filter_mode == 'Datumintervall':
    today = datetime.now().date()
    start_of_current_week = today - timedelta(days=(today.weekday() + 1) % 7)
    calculated_start_date = start_of_current_week - timedelta(weeks=4)
    default_start_date = max(min_date, calculated_start_date)
    default_end_date = min(today, max_date)

    date_range = st.sidebar.date_input(
        "Välj datumintervall",
        value=(default_start_date, default_end_date),
        min_value=min_date,
        max_value=max_date,
    )
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[(df['order_date'] >= start_date) & (df['order_date'] <= end_date)]
        prev_year_start_date = start_date - relativedelta(years=1)
        prev_year_end_date = end_date - relativedelta(years=1)
        prev_year_df = df[(df['order_date'] >= prev_year_start_date) & (df['order_date'] <= prev_year_end_date)]

elif filter_mode == 'Veckovis':
    all_weeks = sorted(df['year_week_key'].unique(), reverse=True)

    # Create a mapping from week key to a representative date for label generation
    week_key_to_date = df.groupby('year_week_key')['order_date'].first()

    def format_week_label(week_key):
        """Formats the week key 'YYYY-WUU' into a user-friendly label like 'V30/31, 2024'."""
        if week_key not in week_key_to_date:
            return week_key # Fallback
        
        date = pd.to_datetime(week_key_to_date[week_key])
        year = week_key.split('-W')[0]
        week_u = week_key.split('-W')[1] # From the key (Sunday-based)
        week_v = date.strftime('%V')     # ISO week
        
        week_label = f"V{week_u}" if week_u.lstrip('0') == week_v.lstrip('0') else f"V{week_u}/{week_v}"
        return f"{week_label}, {year}"

    # --- Default Selection Logic: Last 5 weeks from today ---
    today = datetime.now().date()
    # Generate the keys for the current week and the 4 previous ones
    target_weeks = [(today - timedelta(weeks=i)).strftime('%Y-W%U') for i in range(5)]
    # Filter these target weeks to only include those that actually exist in the data
    default_selection = [week for week in target_weeks if week in all_weeks]
    # If no target weeks are found in data (e.g., old data), fall back to the 5 most recent available weeks.
    default_selection = default_selection if default_selection else all_weeks[:5]

    selected_weeks = st.sidebar.multiselect("Välj vecka/veckor", options=all_weeks, default=default_selection, format_func=format_week_label)
    filtered_df = df[df['year_week_key'].isin(selected_weeks)]
    
    # Find corresponding previous year weeks
    prev_year_weeks = [f"{int(w.split('-W')[0]) - 1}-W{w.split('-W')[1]}" for w in selected_weeks]
    prev_year_df = df[df['year_week_key'].isin(prev_year_weeks)]
    
    if not filtered_df.empty:
        start_date, end_date = filtered_df['order_date'].min(), filtered_df['order_date'].max()

elif filter_mode == 'Månadsvis':
    all_months = sorted(df['year_month_key'].unique(), reverse=True)
    selected_months = st.sidebar.multiselect("Välj månad/månader", options=all_months, default=all_months[:3])
    filtered_df = df[df['year_month_key'].isin(selected_months)]

    # Find corresponding previous year months
    prev_year_months = [f"{int(m.split('-M')[0]) - 1}-M{m.split('-M')[1]}" for m in selected_months]
    prev_year_df = df[df['year_month_key'].isin(prev_year_months)]

    if not filtered_df.empty:
        start_date, end_date = filtered_df['order_date'].min(), filtered_df['order_date'].max()

if 'filtered_df' not in locals() or filtered_df.empty:
    st.warning("Ingen data tillgänglig för valda filter. Välj ett annat intervall.")
    st.stop()

# Apply other filters on the already time-filtered data
if selected_store != 'All':
    filtered_df = filtered_df[filtered_df['store_name'] == selected_store]
    # Also filter the previous year dataframe if it's not empty
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



# --- Main Page Content ---
st.title("Försäljningsöversikt")
if start_date and end_date:
    st.markdown(f"Data från **{start_date.strftime('%Y-%m-%d')}** till **{end_date.strftime('%Y-%m-%d')}**")

if not filtered_df.empty:
    # --- Current Period Calculations ---
    total_gross_sales = filtered_df['sales'].sum()
    total_quantity = filtered_df['quantity'].sum()
    total_return_sales = filtered_df['return_sales'].sum()
    total_net_sales = total_gross_sales - total_return_sales
    overall_return_rate = (total_return_sales / total_gross_sales) * 100 if total_gross_sales > 0 else 0

    # --- Previous Year Calculations ---
    total_gross_sales_prev_year = prev_year_df['sales'].sum()
    total_quantity_prev_year = prev_year_df['quantity'].sum()
    total_return_sales_prev_year = prev_year_df['return_sales'].sum()
    total_net_sales_prev_year = total_gross_sales_prev_year - total_return_sales_prev_year
    overall_return_rate_prev_year = (total_return_sales_prev_year / total_gross_sales_prev_year) * 100 if total_gross_sales_prev_year > 0 else 0

    # --- YoY Delta Calculations ---
    # A small value to avoid division by zero
    epsilon = 1e-9
    net_sales_delta = ((total_net_sales - total_net_sales_prev_year) / (total_net_sales_prev_year + epsilon)) * 100
    quantity_delta = ((total_quantity - total_quantity_prev_year) / (total_quantity_prev_year + epsilon)) * 100
    return_value_delta = ((total_return_sales - total_return_sales_prev_year) / (total_return_sales_prev_year + epsilon)) * 100
    return_rate_delta = overall_return_rate - overall_return_rate_prev_year

    # Use 4 columns for the main KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Nettoförsäljning", value=f"{(total_net_sales/1000):,.1f} kSEK", delta=f"{net_sales_delta:.2f}% vs Föregående År", delta_color="normal")
    col2.metric(label="Antal Ordrar", value=f"{int(total_quantity):,}", delta=f"{quantity_delta:.2f}% vs Föregående År", delta_color="normal")
    col3.metric(label="Returvärde", value=f"{(total_return_sales/1000):,.1f} kSEK", delta=f"{return_value_delta:.2f}% vs Föregående År", delta_color="inverse")
    col4.metric(label="Returandel (%)", value=f"{overall_return_rate:.2f}%", delta=f"{return_rate_delta:.2f} p.p. vs Föregående År", delta_color="inverse")

else:
    st.warning("Ingen data tillgänglig för valda filter.")
    st.stop()

st.markdown("---")

if filter_mode == 'Månadsvis' or filter_mode == 'Datumintervall':
    # --- YoY Monthly Trend Chart ---
    def prepare_monthly_data(df, period_name):
        if df.empty:
            return pd.DataFrame() # Return empty DataFrame if input is empty

        df_temp = df.copy()
        df_temp['order_date'] = pd.to_datetime(df_temp['order_date'])
        # Aggregate both gross sales and returns using 'ME' for Month End
        monthly_df = df_temp.set_index('order_date').resample('ME')[['sales', 'return_sales']].sum().reset_index()
        monthly_df['net_sales'] = monthly_df['sales'] - monthly_df['return_sales']
        monthly_df['net_sales_kSEK'] = monthly_df['net_sales'] / 1000
        monthly_df['return_sales_kSEK'] = monthly_df['return_sales'] / 1000
        # Calculate return rate as a percentage
        monthly_df['return_rate'] = (monthly_df['return_sales'] / monthly_df['sales'].replace(0, 1)) * 100
        monthly_df['Period'] = period_name
        # Use month number for alignment across years
        monthly_df['MånadNr'] = monthly_df['order_date'].dt.month
        return monthly_df

    monthly_current = prepare_monthly_data(filtered_df, "Nuvarande Period")
    monthly_previous = prepare_monthly_data(prev_year_df, "Föregående År")

    # Merge current and previous year data for a unified hover template
    monthly_combined = pd.merge(
        monthly_current,
        monthly_previous,
        on='MånadNr',
        suffixes=('_curr', '_prev'),
        how='left'
    )
    # Fill NaN for previous year data with 0 for display purposes
    monthly_combined.fillna({
        'sales_prev': 0, 'net_sales_kSEK_prev': 0, 'return_rate_prev': 0
    }, inplace=True)

    x_axis_labels = monthly_current.set_index('MånadNr')['order_date'].dt.strftime('%b').to_dict()
    monthly_combined['Månad'] = monthly_combined['MånadNr'].map(x_axis_labels)

    # Create figure with graph_objects for more control
    fig_line = go.Figure()

    # --- Custom Hover Template with Colors ---
    color_current_gross = '#1f77b4'
    color_previous_gross = '#aec7e8'
    color_current_return = '#d62728'
    color_previous_return = '#ff9896'

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
        "<extra></extra>" # Hides the secondary box
    )

    fig_line.add_trace(go.Bar(
        x=monthly_combined['Månad'], y=monthly_combined['sales_curr'] / 1000,
        name='Bruttoförsäljning (Nuvarande)', marker_color='#1f77b4',
        customdata=monthly_combined[['sales_curr', 'net_sales_kSEK_curr', 'return_rate_curr', 'sales_prev', 'net_sales_kSEK_prev', 'return_rate_prev']],
        hovertemplate=hovertemplate
    ))
    fig_line.add_trace(go.Bar(
        x=monthly_combined['Månad'], y=monthly_combined['sales_prev'] / 1000,
        name='Bruttoförsäljning (Föregående)', marker_color='#aec7e8',
        hoverinfo='none' # Disable hover for this trace as it's included in the main one
    ))

    fig_line.add_trace(go.Scatter(
        x=monthly_combined['Månad'], y=monthly_combined['return_rate_curr'],
        name='Returandel % (Nuvarande)', mode='lines+markers', line=dict(color='#d62728', width=2), yaxis='y2'
    ))
    fig_line.add_trace(go.Scatter(
        x=monthly_combined['Månad'], y=monthly_combined['return_rate_prev'],
        name='Returandel % (Föregående)', mode='lines+markers', line=dict(color='#ff9896', width=2, dash='dash'), yaxis='y2'
    ))

else: # Veckovis
    # --- YoY Weekly Trend Chart ---
    def prepare_weekly_data(df, period_name):
        if df.empty:
            return pd.DataFrame() # Return empty DataFrame if input is empty

        df_temp = df.copy()
        df_temp['order_date'] = pd.to_datetime(df_temp['order_date'])
        # Resample by week, ending on Saturday (Sunday-Saturday week), using gross sales
        weekly_df = df_temp.set_index('order_date').resample('W-SAT')[['sales', 'return_sales']].sum().reset_index()
        weekly_df['net_sales'] = weekly_df['sales'] - weekly_df['return_sales']
        weekly_df['net_sales_kSEK'] = weekly_df['net_sales'] / 1000
        weekly_df['return_sales_kSEK'] = weekly_df['return_sales'] / 1000
        # Calculate return rate as a percentage
        weekly_df['return_rate'] = (weekly_df['return_sales'] / weekly_df['sales'].replace(0, 1)) * 100
        weekly_df['Period'] = period_name
        # Use week number for alignment across years
        weekly_df['VeckaNr'] = weekly_df['order_date'].dt.strftime('%U').astype(int)
        return weekly_df

    weekly_current = prepare_weekly_data(filtered_df, "Nuvarande Period")
    weekly_previous = prepare_weekly_data(prev_year_df, "Föregående År")

    # Merge current and previous year data for a unified hover template
    weekly_combined = pd.merge(
        weekly_current,
        weekly_previous,
        on='VeckaNr',
        suffixes=('_curr', '_prev'),
        how='left'
    )
    weekly_combined.fillna({
        'sales_prev': 0, 'net_sales_kSEK_prev': 0, 'return_rate_prev': 0
    }, inplace=True)

    x_axis_labels = {}
    for index, row in weekly_current.iterrows():
        date = row['order_date']
        week_u = date.strftime('%U')
        week_v = date.strftime('%V')
        year = date.strftime('%Y')
        week_label = f"V{week_u}" if week_u == week_v else f"V{week_u}/{week_v}"
        full_label = f"{week_label}, {year}"
        x_axis_labels[row['VeckaNr']] = full_label
    weekly_combined['Vecka'] = weekly_combined['VeckaNr'].map(x_axis_labels)
    weekly_combined.dropna(subset=['Vecka'], inplace=True) # Drop if no label exists

    # Create figure with graph_objects for more control
    fig_line = go.Figure()

    # --- Custom Hover Template with Colors (same as monthly) ---
    color_current_gross = '#1f77b4'
    color_previous_gross = '#aec7e8'
    color_current_return = '#d62728'
    color_previous_return = '#ff9896'

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
        x=weekly_combined['Vecka'], y=weekly_combined['sales_curr'] / 1000,
        name='Bruttoförsäljning (Nuvarande)', marker_color='#1f77b4',
        customdata=weekly_combined[['sales_curr', 'net_sales_kSEK_curr', 'return_rate_curr', 'sales_prev', 'net_sales_kSEK_prev', 'return_rate_prev']],
        hovertemplate=hovertemplate
    ))
    fig_line.add_trace(go.Bar(
        x=weekly_combined['Vecka'], y=weekly_combined['sales_prev'] / 1000,
        name='Bruttoförsäljning (Föregående)', marker_color='#aec7e8',
        hoverinfo='none'
    ))

    fig_line.add_trace(go.Scatter(
        x=weekly_combined['Vecka'], y=weekly_combined['return_rate_curr'],
        name='Returandel % (Nuvarande)', mode='lines+markers', line=dict(color='#d62728', width=2), yaxis='y2'
    ))
    fig_line.add_trace(go.Scatter(
        x=weekly_combined['Vecka'], y=weekly_combined['return_rate_prev'],
        name='Returandel % (Föregående)', mode='lines+markers', line=dict(color='#ff9896', width=2, dash='dash'), yaxis='y2'
    ))

fig_line.update_layout(
    barmode='overlay',
    title_text='Bruttoförsäljning & Returandel vs Föregående År',
    title_x=0, margin=dict(l=0, r=0, t=30, b=0),
    yaxis=dict(
        title='Bruttoförsäljning (kSEK)'
    ),
    yaxis2=dict(
        title='Returandel (%)',
        overlaying='y',
        side='right',
        showgrid=False,
        ticksuffix='%',
        dtick=1 # Set tick increment to 1%
    ),
    legend_title_text='Period & Mått'
)
st.plotly_chart(fig_line, use_container_width=True)

# --- Centralized Safe Resample Function ---
def safe_weekly_resample(df):
    """
    Safely resamples a DataFrame weekly, returning an empty DataFrame if the input is empty
    or if the resample operation results in an empty DataFrame.
    """
    if df.empty:
        return pd.DataFrame()
    
    df_temp = df.copy()
    df_temp['order_date'] = pd.to_datetime(df_temp['order_date'])
    return df_temp.set_index('order_date').resample('W-SAT')[['sales', 'return_sales']].sum()

# --- Correlated Return Analysis Section (Weekly only) ---
if filter_mode == 'Veckovis' and not filtered_df.empty:
    st.markdown("---")
    st.markdown("### Analys av Korrelerad Retur (Veckobaserad)")
    st.info(
        "I denna analys kopplas returer från en vecka till försäljningen från föregående vecka "
        "för att ge en mer rättvisande bild av returandelen.",
        icon="💡"
    )

    # 1. Prepare data by resampling weekly
    weekly_agg = safe_weekly_resample(filtered_df)
    
    # 2. Shift sales data to get previous week's sales
    weekly_agg['sales_prev_week'] = weekly_agg['sales'].shift(1)

    # 3. Calculate the correlated return rate
    weekly_agg['correlated_return_rate'] = (weekly_agg['return_sales'] / weekly_agg['sales_prev_week'].replace(0, 1)) * 100

    # 4. Prepare for plotting
    plot_df = weekly_agg.dropna(subset=['sales_prev_week']).reset_index()
    # Use the same label formatting as the main chart
    plot_df['Vecka'] = plot_df['order_date'].apply(lambda d: format_week_label(d.strftime('%Y-W%U')))

    # 5. Create the chart
    fig_corr_return = go.Figure()

    # --- Custom Hover Template with Colors for Correlated Chart ---
    color_sales = '#1f77b4'
    color_return = '#d62728'
    corr_hovertemplate = (
        "<b>%{x}</b><br><br>" +
        f"<span style='color:{color_sales};'>Föreg. Veckas Försäljning: %{{y:,.1f}} kSEK</span><br>" +
        f"<span style='color:{color_return};'>Returbelopp: %{{customdata[0]:,.1f}} kSEK</span><br>" +
        f"<span style='color:{color_return};'>Korrelerad Returandel: %{{customdata[1]:.2f}}%</span><br>" +
        "<extra></extra>"
    )

    # Add Bar for Previous Week's Sales
    fig_corr_return.add_trace(go.Bar(
        x=plot_df['Vecka'],
        y=plot_df['sales_prev_week'] / 1000,
        name='Föregående Veckas Försäljning',
        marker_color='#1f77b4',
        customdata=plot_df[['return_sales', 'correlated_return_rate']],
        hovertemplate=corr_hovertemplate
    ))

    # Add overlaid Bar for Current Week's Return Amount
    fig_corr_return.add_trace(go.Bar(
        x=plot_df['Vecka'],
        y=plot_df['return_sales'] / 1000,
        name='Returbelopp (Nuvarande Vecka)',
        marker_color='#d62728', # Red color to match the return rate line
        hoverinfo='none' # Hover is handled by the main bar
    ))

    # Add Line for Correlated Return Rate
    fig_corr_return.add_trace(go.Scatter(
        x=plot_df['Vecka'],
        y=plot_df['correlated_return_rate'],
        name='Korrelerad Returandel',
        mode='lines+markers',
        line=dict(color='#d62728', width=2),
        yaxis='y2',
        hoverinfo='none' # Hover is handled by the main bar
    ))

    fig_corr_return.update_layout(
        title_text='Korrelerad Retur',
        barmode='overlay', # Overlay the bars
        title_x=0, margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(title='Bruttoförsäljning (kSEK)'),
        yaxis2=dict(title='Korrelerad Returandel (%)', overlaying='y', side='right', showgrid=False, ticksuffix='%', dtick=1),
        legend_title_text='Mått'
    )
    st.plotly_chart(fig_corr_return, use_container_width=True)

# --- Store Performance Leaderboard ---
st.markdown("### Butikernas Prestation")

# --- 1. Unified Store List Generation ---
current_stores = set(filtered_df['store_name'].astype(str).unique())
previous_stores = set()
if not prev_year_df.empty:
    previous_stores = set(prev_year_df['store_name'].astype(str).unique())

all_unique_stores = sorted(list(current_stores.union(previous_stores)))
store_performance = pd.DataFrame({'store_name': all_unique_stores})

# --- 2. Isolated Metric Aggregation ---
# Current Period Metrics
current_agg = filtered_df.groupby('store_name').agg(
    gross_sales=('sales', 'sum'),
    return_sales=('return_sales', 'sum'),
    quantity=('quantity', 'sum')
).reset_index()

# Previous Period Metrics
prev_agg = pd.DataFrame()
if not prev_year_df.empty:
    prev_agg = prev_year_df.groupby('store_name').agg(
        gross_sales_prev=('sales', 'sum'),
        return_sales_prev=('return_sales', 'sum'),
        quantity_prev=('quantity', 'sum')
    ).reset_index()

# Correlated Returns
corr_agg = pd.DataFrame()
df_corr_stores = filtered_df.copy()
if not df_corr_stores.empty:
    df_corr_stores['order_date'] = pd.to_datetime(df_corr_stores['order_date'])
    weekly_store_agg = df_corr_stores.groupby('store_name').apply(safe_weekly_resample).reset_index(level=1, drop=True)
    weekly_store_agg['sales_prev_week'] = weekly_store_agg.groupby(level=0)['sales'].shift(1)
    store_corr_totals = weekly_store_agg.groupby(level=0)[['return_sales', 'sales_prev_week']].sum()
    store_corr_totals['correlated_return_rate'] = (store_corr_totals['return_sales'] / store_corr_totals['sales_prev_week'].replace(0, 1)) * 100
    corr_agg = store_corr_totals.reset_index()

# --- 3. Safe Merge & YoY Calculation ---
# Merge all aggregated metrics into the master DataFrame
store_performance = pd.merge(store_performance, current_agg, on='store_name', how='left')
if not prev_agg.empty:
    store_performance = pd.merge(store_performance, prev_agg, on='store_name', how='left')
if not corr_agg.empty:
    store_performance = pd.merge(store_performance, corr_agg[['store_name', 'correlated_return_rate']], on='store_name', how='left')

# Fill NaNs for metrics with 0 after merging
fill_zeros_cols = [
    'gross_sales', 'return_sales', 'quantity',
    'gross_sales_prev', 'return_sales_prev', 'quantity_prev',
    'correlated_return_rate'
]
for col in fill_zeros_cols:
    if col in store_performance.columns:
        store_performance[col] = store_performance[col].fillna(0)

# Calculate derived metrics
store_performance['net_sales'] = store_performance['gross_sales'] - store_performance['return_sales']
store_performance['return_rate'] = (store_performance['return_sales'] / store_performance['gross_sales'].replace(0, np.nan)) * 100

if 'gross_sales_prev' in store_performance.columns:
    store_performance['net_sales_prev'] = store_performance['gross_sales_prev'] - store_performance['return_sales_prev']
    store_performance['return_rate_prev'] = (store_performance['return_sales_prev'] / store_performance['gross_sales_prev'].replace(0, np.nan)) * 100

# Safely calculate YoY metrics
store_performance['net_sales_yoy'] = np.where(
    store_performance.get('net_sales_prev', 0) > 0,
    (store_performance['net_sales'] - store_performance['net_sales_prev']) / store_performance['net_sales_prev'] * 100,
    pd.NA
)
store_performance['quantity_yoy'] = np.where(
    store_performance.get('quantity_prev', 0) > 0,
    (store_performance['quantity'] - store_performance['quantity_prev']) / store_performance['quantity_prev'] * 100,
    pd.NA
)
store_performance['return_rate_yoy'] = np.where(
    store_performance.get('gross_sales_prev', 0) > 0,
    store_performance['return_rate'] - store_performance['return_rate_prev'],
    pd.NA
)

# --- 4. Status Flagging & Display ---
store_performance['Status'] = ''

# Add Gold Medal for Top 20 stores by Current Net Sales
top_20_sales_stores = store_performance.nlargest(20, 'net_sales')['store_name'].tolist()
store_performance.loc[store_performance['store_name'].isin(top_20_sales_stores), 'Status'] += '🥇'

# Add Red Flag for Top 20 stores by Correlated Return Rate
if 'correlated_return_rate' in store_performance.columns:
    top_20_return_stores = store_performance.nlargest(20, 'correlated_return_rate')['store_name'].tolist()
    store_performance.loc[store_performance['store_name'].isin(top_20_return_stores), 'Status'] += '🚩'

# --- Apply Status Filter ---
if selected_status_key == 'Medal':
    store_performance = store_performance[store_performance['Status'].str.contains('🥇')]
elif selected_status_key == 'Flag':
    store_performance = store_performance[store_performance['Status'].str.contains('🚩')]
elif selected_status_key == 'Both':
    store_performance = store_performance[store_performance['Status'].str.contains('🥇') & store_performance['Status'].str.contains('🚩')]
# 'All' requires no filtering

# Sort by net sales by default
store_performance.sort_values('net_sales', ascending=False, inplace=True)

# Prepare the dataframe for display (renaming and formatting)
store_performance_display = store_performance.rename(columns={    
    'store_name': 'Butik',
    'net_sales': 'Nettoförsäljning (kSEK)',
    'net_sales_yoy': 'Nettoförsäljning YoY (%)',
    'return_rate': 'Returandel (%)',
    'return_rate_yoy': 'Returandel YoY (p.p.)',
    'quantity': 'Antal Ordrar',
    'quantity_yoy': 'Antal Ordrar YoY (%)'
})

# Convert sales to kSEK for display
store_performance_display['Nettoförsäljning (kSEK)'] /= 1000

# Determine which columns to display based on filter mode
display_columns = ['Status', 'Butik', 'Nettoförsäljning (kSEK)', 'Nettoförsäljning YoY (%)', 'Returandel (%)', 'Returandel YoY (p.p.)', 'Antal Ordrar', 'Antal Ordrar YoY (%)']

# --- Styling function for YoY columns ---
def color_yoy(val):
    if pd.isna(val):
        return ''
    color = 'red' if val < 0 else 'green'
    return f'color: {color}'

def color_return_yoy(val):
    if pd.isna(val):
        return ''
    color = 'green' if val < 0 else 'red' # Inverse logic for returns
    return f'color: {color}'

# Display the styled dataframe with bar charts inside for better visualization
st.dataframe(store_performance_display[display_columns].style.format({
                'Nettoförsäljning (kSEK)': '{:,.1f}',
                'Nettoförsäljning YoY (%)': '{:+.1f}%',
                'Returandel (%)': '{:.2f}%',
                'Returandel YoY (p.p.)': '{:+.2f}',
                'Antal Ordrar YoY (%)': '{:+.1f}%'}, na_rep="-")
             .map(color_yoy, subset=['Nettoförsäljning YoY (%)', 'Antal Ordrar YoY (%)'])
             .map(color_return_yoy, subset=['Returandel YoY (p.p.)'])
             .bar(subset=['Nettoförsäljning (kSEK)'], color='#aec7e8', vmin=0),
             use_container_width=True)

# --- Cleanup ---
del store_performance, store_performance_display
if 'current_agg' in locals(): del current_agg
if 'prev_agg' in locals(): del prev_agg
if 'corr_agg' in locals(): del corr_agg
gc.collect()

# --- New and Churned Stores Analysis (Refactored) ---
if not prev_year_df.empty:
    st.markdown("---")
    st.markdown("### Analys av Nya och Förlorade Butiker")
    st.info(
        "Här visas butiker som tillkommit eller försvunnit i den valda perioden jämfört med samma period föregående år. "
        "Prestationen mäts som medianen av nettoförsäljningen per vecka.",
        icon="💡"
    )

    # 1. Clean Store Names and 2. Robust New/Churned Identification
    def get_active_stores(df):
        """Cleans store names and returns a set of stores with sales > 0."""
        if df.empty:
            return set()
        
        # Filter for positive sales first, then clean and get unique names
        active_df = df[df['sales'] > 0].copy()
        cleaned_names = active_df['store_name'].astype(str).str.strip()
        # Filter out any names that became empty strings after stripping
        return set(cleaned_names[cleaned_names != ''])

    current_stores_set = get_active_stores(filtered_df)
    previous_stores_set = get_active_stores(prev_year_df)

    new_stores_set = current_stores_set - previous_stores_set
    churned_stores_set = previous_stores_set - current_stores_set

    col_new, col_churned = st.columns(2)

    with col_new:
        st.markdown("#### Nya Butiker")
        if new_stores_set:
            # 3. Safe Weekly Median Calculation for New Stores
            new_stores_df = filtered_df[filtered_df['store_name'].isin(new_stores_set)].copy()
            weekly_sales = new_stores_df.groupby(['store_name', 'year_week_key'])['net_sales'].sum()
            median_weekly_sales = weekly_sales.groupby('store_name').median().reset_index()
            median_weekly_sales.rename(columns={'store_name': 'Butik', 'net_sales': 'Median Veckoförsäljning (SEK)'}, inplace=True)
            median_weekly_sales = median_weekly_sales[median_weekly_sales['Median Veckoförsäljning (SEK)'] > 0] # Filter out non-positive median sales

            if not median_weekly_sales.empty:
                total_median_sales_new = median_weekly_sales['Median Veckoförsäljning (SEK)'].sum()
                st.markdown(f"**Totalt:** `{total_median_sales_new:,.0f} SEK`")
                median_weekly_sales.sort_values('Median Veckoförsäljning (SEK)', ascending=False, inplace=True)
                st.dataframe(median_weekly_sales.style.format({'Median Veckoförsäljning (SEK)': '{:,.0f}'}), use_container_width=True)
            else:
                st.success("Inga nya butiker med positiv försäljning under denna period.", icon="✅")
        else:
            st.success("Inga nya butiker under denna period.", icon="✅")

    with col_churned:
        st.markdown("#### Förlorade Butiker")
        if churned_stores_set:
            # 3. Safe Weekly Median Calculation for Churned Stores
            churned_stores_df = prev_year_df[prev_year_df['store_name'].isin(churned_stores_set)].copy()
            weekly_sales_churned = churned_stores_df.groupby(['store_name', 'year_week_key'])['net_sales'].sum()
            median_weekly_sales_churned = weekly_sales_churned.groupby('store_name').median().reset_index()
            median_weekly_sales_churned.rename(columns={'store_name': 'Butik', 'net_sales': 'Median Veckoförsäljning (SEK)'}, inplace=True)
            median_weekly_sales_churned = median_weekly_sales_churned[median_weekly_sales_churned['Median Veckoförsäljning (SEK)'] > 0] # Filter out non-positive median sales

            if not median_weekly_sales_churned.empty:
                total_median_sales_churned = median_weekly_sales_churned['Median Veckoförsäljning (SEK)'].sum()
                st.markdown(f"**Totalt:** `{total_median_sales_churned:,.0f} SEK`")
                median_weekly_sales_churned.sort_values('Median Veckoförsäljning (SEK)', ascending=False, inplace=True)
                st.dataframe(median_weekly_sales_churned.style.format({'Median Veckoförsäljning (SEK)': '{:,.0f}'}), use_container_width=True)
            else:
                st.success("Inga förlorade butiker med positiv försäljning under denna period.", icon="✅")
        else:
            st.success("Inga butiker förlorade under denna period.", icon="✅")


col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    category_sales = filtered_df.groupby('category')['sales'].sum().reset_index()
    category_sales['sales'] = category_sales['sales'] / 1000 # Convert to thousands
    fig_pie = px.pie(category_sales, names='category', values='sales', title='Försäljningsandel per Produkttyp', hole=0.4)
    fig_pie.update_traces(hovertemplate='<b>%{label}</b><br>Försäljning: %{value:,.1f} kSEK<br>Andel: %{percent}')
    fig_pie.update_layout(title_x=0, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_chart2:
    # Create a new key combining category (typ) and product_name (sort) for unique identification
    # No need to copy, we can create the new column on a temporary view
    top_products = (
        filtered_df.assign(full_product_name=filtered_df['category'].astype(str) + ' - ' + filtered_df['product_name'].astype(str))
        .groupby('full_product_name')['sales'].sum().nlargest(10).sort_values(ascending=True).reset_index()
    )
    top_products['sales'] = top_products['sales'] / 1000 # Convert to thousands
    fig_bar = px.bar(top_products, x='sales', y='full_product_name', orientation='h', title='Topp 10 Produkter', labels={'full_product_name': 'Produkt (Typ - Sort)', 'sales': 'Bruttoförsäljning (kSEK)'})
    fig_bar.update_layout(title_x=0, margin=dict(l=0, r=0, t=30, b=0), yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)
