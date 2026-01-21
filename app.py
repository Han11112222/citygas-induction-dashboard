import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Induction Transition Trend Analysis",
    page_icon="🔥",
    layout="wide"
)

# ---------------------------------------------------------
# 2. Data Loading and Utilities
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def load_data_final_v22(url):
    try:
        df = pd.read_excel(url, engine='openpyxl')
    except Exception as e:
        st.error(f"⚠️ Failed to load gas range data: {e}")
        return pd.DataFrame()

    df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
    
    target_cols = ['TotalBillingMeters', 'GasRangeConnectedCount', 'Usage(m3)'] # Translated columns for internal use if needed, but keeping original Korean names in dataframe logic based on user code
    # Actual Korean column names from user code:
    korean_cols = ['총청구계량기수', '가스레인지연결전수', '사용량(m3)']

    for col in korean_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if '년월' in df.columns:
        df['년월'] = df['년월'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df['Date'] = pd.to_datetime(df['년월'], format='%Y%m', errors='coerce')
        df = df.dropna(subset=['Date'])
    
    # Derived variables
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['Induction_Est_Count'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['Induction_Conversion_Rate'] = df.apply(lambda x: (x['Induction_Est_Count']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    # [Year Integer Conversion]
    df['Year'] = df['Date'].dt.year.astype(int)

    return df

@st.cache_data(ttl=60)
def load_sales_data_final_v22():
    """
    [Load Sales Data]
    Unit: 1000m³ -> m³ (* 1000)
    """
    url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/%ED%8C%90%EB%A7%A4%EB%9F%89(%EA%B3%84%ED%9A%8D_%EC%8B%A4%EC%A0%81).xlsx"
    
    try:
        df = pd.read_excel(url, engine='openpyxl', sheet_name='실적_부피')
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # Columns to aggregate
        household_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        other_cols = ['일반용', '업무난방용', '냉방용', '산업용', '수송용(CNG)', '수송용(BIO)', '열병합용', '연료전지용', '열전용설비용', '주한미군']
        all_cols = household_cols + other_cols
        
        # Numeric conversion
        for col in all_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # [Unit Correction] 1000m³ -> m³ (unconditionally * 1000)
        df['Household_Sales_Total'] = df[household_cols].sum(axis=1) * 1000
        df['Other_Sales_Total'] = df[other_cols].sum(axis=1) * 1000
        df['Total_Sales'] = df['Household_Sales_Total'] + df['Other_Sales_Total']
        
        return df[['Year', 'Date', 'Household_Sales_Total', 'Total_Sales']]
             
    except Exception as e:
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [Design] Color Palette (Unified Blue Theme) ---
COLOR_GAS = '#1f77b4'       # Basic Blue (Gas Range)
COLOR_INDUCTION = '#a4c2f4' # Light Sky Blue (Induction)
COLOR_LINE = '#d62728'      # Red (Ratio Line)
COLOR_LOSS_BLUE = '#115f9a' # Loss Amount (Deep Blue)
COLOR_HIGHLIGHT_BG = '#a4c2f4' # Highlight Background
COLOR_HIGHLIGHT_LINE = '#1f77b4' # Highlight Line/Text
COLOR_TEXT_LIGHTGREY = 'lightgrey' # Graph Internal Text Color

# ---------------------------------------------------------
# 3. Data Loading and Sidebar Configuration
# ---------------------------------------------------------
gas_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

df_raw = load_data_final_v22(gas_url)
df_sales_raw = load_sales_data_final_v22()

if df_raw.empty:
    st.error("🚨 Failed to load basic data. Please try again later.")
    st.stop()

# Main Title
st.title("🔥 Induction Transition Trend Analysis")

# [Data Load Confirmation Window]
if not df_sales_raw.empty:
    with st.expander("✅ Check Sales Data Load (Converted to m³)"):
        st.write("The figures below are **converted from 1000m³ units to m³**.")
        check_df = df_sales_raw[df_sales_raw['Year'] >= 2024].sort_values('Date', ascending=False).head(5)
        st.dataframe(check_df, use_container_width=True)
else:
    st.warning("⚠️ Loading sales data.")

with st.sidebar:
    st.header("🔥 Analysis Menu")
    selected_menu = st.radio(
        "Select Analysis Menu",
        ["One Page Review", "1. Transition Trends & Detailed Analysis"] # Added One Page Review tab
    )
    
    st.markdown("---")
    st.header("🔍 Data Filter")
    
    # [Removed PPH term and set default to 5.0]
    input_monthly_usage = st.number_input(
        "Applicable Monthly Average Gas Usage per Household (m³)", 
        min_value=0.0, 
        max_value=100.0, 
        value=5.0, 
        step=0.5
    )
    st.caption("※ Pure cooking usage excluding heating")
    
    st.divider()
    
    min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()
    start_date, end_date = st.slider("Query Period", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    
    regions = st.multiselect("Select Region", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.multiselect("Select Type", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))

# Apply Global Filter
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# ---------------------------------------------------------
# 4. Main Screen Logic
# ---------------------------------------------------------

st.markdown(f"### 📊 {selected_menu}")

# =========================================================
# [MENU 0] One Page Review
# =========================================================
if selected_menu == "One Page Review":
    st.subheader("📋 One Page Review")
    
    # 1. Data Preparation (Comparison: Latest Year vs Previous Year)
    # Using December data for accurate household counts
    df_dec = df[df['Date'].dt.month == 12].copy()
    
    # Annual aggregation
    df_summary = df_dec.groupby('Year')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()
    df_summary['Conversion_Rate'] = (df_summary['Induction_Est_Count'] / df_summary['총청구계량기수']) * 100
    df_summary['Annual_Loss_m3'] = df_summary['Induction_Est_Count'] * input_monthly_usage * 12
    
    # Extract latest and previous year data
    latest_year = df_summary['Year'].max()
    prev_year = latest_year - 1
    
    if not df_summary.empty:
        curr_data = df_summary[df_summary['Year'] == latest_year].iloc[0]
        prev_data = df_summary[df_summary['Year'] == prev_year].iloc[0] if prev_year in df_summary['Year'].values else None
        
        # Unit price for revenue calculation (Temporary: 950 KRW/m3 - can be linked to input if needed)
        unit_price = 950 
        
        # 2. Display KPI Metrics (3 Columns)
        kpi1, kpi2, kpi3 = st.columns(3)
        
        with kpi1:
            delta_val = (curr_data['Conversion_Rate'] - prev_data['Conversion_Rate']) if prev_data is not None else 0
            st.metric(
                label=f"🔥 {latest_year} Induction Conversion Rate",
                value=f"{curr_data['Conversion_Rate']:.1f}%",
                delta=f"{delta_val:+.1f}%p (vs Prev Year)",
                delta_color="inverse" # Increasing conversion rate is negative for city gas ('inverse' makes it red)
            )
            
        with kpi2:
            loss_vol = curr_data['Annual_Loss_m3']
            prev_loss = prev_data['Annual_Loss_m3'] if prev_data is not None else 0
            delta_loss = loss_vol - prev_loss
            st.metric(
                label=f"📉 Annual Est. Loss (m³)",
                value=f"{loss_vol:,.0f} m³",
                delta=f"{delta_loss:,.0f} m³ (Increase vs Prev Year)",
                delta_color="inverse"
            )

        with kpi3:
            loss_rev = loss_vol * unit_price
            prev_rev = prev_loss * unit_price
            delta_rev = loss_rev - prev_rev
            st.metric(
                label=f"💰 Annual Est. Revenue Loss (Based on {unit_price} KRW)",
                value=f"{loss_rev/100000000:.2f} Billion KRW",
                delta=f"{delta_rev/100000000:.2f} Billion KRW (Increase vs Prev Year)",
                delta_color="inverse"
            )

        # 3. Analysis Logic and Conclusion (One-Line Insight)
        st.success(f"""
        **💡 [Analysis Insight]** As of **December {latest_year}**, out of a total of **{curr_data['총청구계량기수']:,.0f} households**, approximately **{curr_data['Induction_Est_Count']:,.0f} households** are estimated to be using induction.
        This results in an annual sales volume decrease of approximately **{loss_vol:,.0f}m³**, which is an expansion of **{delta_loss:,.0f}m³** compared to the previous year.
        *(Calculation Basis: Est. Induction Households as of End of Dec × Monthly Avg {input_monthly_usage}m³ × 12 Months)*
        """)
        
        # 4. Key Graphs for Review
        col1, col2 = st.columns(2)
        
        # Graph 1: Conversion Trend (Line Chart)
        with col1:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=df_summary['Year'], y=df_summary['Conversion_Rate'], mode='lines+markers+text',
                                        name='Conversion Rate', text=df_summary['Conversion_Rate'].apply(lambda x: f"{x:.1f}%"),
                                        textposition='top center', line=dict(color=COLOR_LINE, width=3)))
            fig_trend.update_layout(title="Annual Induction Conversion Rate Trend", height=400)
            st.plotly_chart(fig_trend, use_container_width=True)
            
        # Graph 2: Loss Volume Trend (Bar Chart)
        with col2:
            fig_loss_trend = go.Figure()
            fig_loss_trend.add_trace(go.Bar(x=df_summary['Year'], y=df_summary['Annual_Loss_m3'],
                                            name='Loss Volume', marker_color=COLOR_LOSS_BLUE,
                                            text=df_summary['Annual_Loss_m3'].apply(lambda x: f"{x:,.0f}"), textposition='auto'))
            fig_loss_trend.update_layout(title="Annual Estimated Loss Volume Trend (m³)", height=400)
            st.plotly_chart(fig_loss_trend, use_container_width=True)

    else:
        st.info("No data available for the selected period.")


# =========================================================
# [MENU 1] Transition Trends & Detailed Analysis
# =========================================================
elif selected_menu == "1. Transition Trends & Detailed Analysis":
    
    st.info("""
    **[Induction Household Estimation Method]**
    1. **Est. Induction Households** : Total Billing Meters (Dec) - Gas Range Connected Count (Dec)
    2. **Annual Est. Loss** : Est. Induction Households × Monthly Avg Gas Usage per Household × 12 Months
    """)

    # 1. Monthly Trend (Time Series)
    st.subheader("1️⃣ Monthly Trend (Time Series)")
    df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()
    df_m['Conversion_Rate'] = (df_m['Induction_Est_Count'] / df_m['총청구계량기수']) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='Gas Range', stackgroup='one', line=dict(color=COLOR_GAS)))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['Induction_Est_Count'], name='Induction (Est)', stackgroup='one', line=dict(color=COLOR_INDUCTION)))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['Conversion_Rate'], name='Conversion Rate (%)', yaxis='y2', mode='lines+markers', line=dict(color=COLOR_LINE)))
    
    fig.update_layout(
        yaxis2=dict(overlaying='y', side='right'), 
        hovermode="x unified", 
        legend=dict(orientation="h", y=1.1),
        height=600 
    )
    st.plotly_chart(fig, use_container_width=True)
    
    df_m_filtered = df_m[df_m['Date'].dt.year >= 2017].copy()
    st.dataframe(df_m_filtered.style.format({'Conversion_Rate': '{:.1f}%','총청구계량기수': '{:,.0f}','가스레인지연결전수': '{:,.0f}','Induction_Est_Count': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button("📥 Download Monthly Data", convert_df(df_m), "monthly_data.csv", "text/csv")

    st.divider()

    # [2] Annual Analysis
    st.subheader("2️⃣ Annual Quantity and Estimated Loss Analysis")
    
    # --- Data Processing ---
    df_dec = df[df['Date'].dt.month == 12].copy()
    df_year_stock = df_dec.groupby('Year')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()
    df_year_stock['Year'] = df_year_stock['Year'].astype(int)
    df_year_stock['Conversion_Rate'] = (df_year_stock['Induction_Est_Count'] / df_year_stock['총청구계량기수']) * 100
    
    # Annual Total Loss = Dec Est. Induction Count * Monthly Avg Usage * 12 Months
    df_year_stock['Annual_Loss_Est_m3'] = df_year_stock['Induction_Est_Count'] * input_monthly_usage * 12
    
    if not df_sales_raw.empty:
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[['Household_Sales_Total', 'Total_Sales']].sum().reset_index()
    else:
        df_sales_year = pd.DataFrame(columns=['Year', 'Household_Sales_Total', 'Total_Sales'])

    df_year = pd.merge(df_year_stock, df_sales_year, on='Year', how='left')
    if not df_sales_year.empty:
        df_year['Household_Sales_Total'] = df_year['Household_Sales_Total'].fillna(0)
        df_year['Total_Sales'] = df_year['Total_Sales'].fillna(0)
    else:
        df_year['Household_Sales_Total'] = 0
        df_year['Total_Sales'] = 0
        
    df_year['Potential_Household'] = df_year['Household_Sales_Total'] + df_year['Annual_Loss_Est_m3']
    df_year['Loss_Share_Household'] = df_year.apply(lambda x: (x['Annual_Loss_Est_m3'] / x['Potential_Household'] * 100) if x['Potential_Household'] > 0 else 0, axis=1)
    df_year['Potential_Total'] = df_year['Total_Sales'] + df_year['Annual_Loss_Est_m3']
    df_year['Loss_Share_Total'] = df_year.apply(lambda x: (x['Annual_Loss_Est_m3'] / x['Potential_Total'] * 100) if x['Potential_Total'] > 0 else 0, axis=1)

    df_year_filtered = df_year[df_year['Year'] >= 2017].copy()
    
    highlight_condition = df_year_filtered['Conversion_Rate'] > 10.0
    start_highlight_year = df_year_filtered.loc[highlight_condition, 'Year'].min() if highlight_condition.any() else None
    end_highlight_year = df_year_filtered['Year'].max()

    # --- Draw Graphs ---
    st.markdown("##### 1. Annual Household Composition (Dec) & Conversion Rate")
    fig_q = make_subplots(specs=[[{"secondary_y": True}]])
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='Gas Range (Dec)', marker_color=COLOR_GAS), secondary_y=False)
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['Induction_Est_Count'], name='Induction (Dec)', marker_color=COLOR_INDUCTION), secondary_y=False)
    
    # [Modified] Text location to 'bottom center'
    fig_q.add_trace(go.Scatter(
        x=df_year['Year'], y=df_year['Conversion_Rate'], name='Conversion Rate (%)', mode='lines+markers+text', 
        text=df_year['Conversion_Rate'].apply(lambda x: f"{x:.1f}%"), 
        textposition='bottom center', # [Changed] top center -> bottom center
        textfont=dict(size=20, color=COLOR_TEXT_LIGHTGREY), 
        line=dict(color=COLOR_LINE, width=3)
    ), secondary_y=True)
    
    if start_highlight_year:
        # [Modified] Highlight opacity 0.2 -> 0.4
        fig_q.add_vrect(
            x0=start_highlight_year-0.5, x1=end_highlight_year+0.5, 
            fillcolor=COLOR_HIGHLIGHT_BG, opacity=0.4, layer="below", line_width=0
        )
        fig_q.add_vline(
            x=start_highlight_year-0.5, line_width=2, line_dash="dash", line_color=COLOR_HIGHLIGHT_LINE,
            annotation_text="🚀 Conversion Acceleration", 
            annotation_position="top left",
            annotation_font=dict(size=14, color=COLOR_HIGHLIGHT_LINE, family="Arial Black")
        )

    fig_q.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500, hovermode="x unified")
    fig_q.update_yaxes(title_text="Households (Dec)", secondary_y=False)
    fig_q.update_yaxes(title_text="Conversion Rate (%)", secondary_y=True, range=[0, df_year['Conversion_Rate'].max()*1.2])
    st.plotly_chart(fig_q, use_container_width=True)

    st.markdown("---") 

    st.markdown("##### 2. Annual Household Estimated Loss & Share")
    fig_loss = make_subplots(specs=[[{"secondary_y": True}]])
    
    latest_year_val = df_year_filtered['Year'].max()
    latest_loss_val = df_year_filtered[df_year_filtered['Year'] == latest_year_val]['Annual_Loss_Est_m3'].values[0] if pd.notna(latest_year_val) else 0

    # 1st Axis: Loss Amount (Bar) - [Modified] Text removed (Moved to line graph)
    fig_loss.add_trace(go.Bar(
        x=df_year_filtered['Year'],
        y=df_year_filtered['Annual_Loss_Est_m3'],
        name='Annual Loss (m³)',
        marker_color=COLOR_LOSS_BLUE,
        # text and textposition removed
    ), secondary_y=False)
    
    # Latest year label
    if pd.notna(latest_year_val):
        fig_loss.add_trace(go.Scatter(
            x=[latest_year_val],
            y=[latest_loss_val],
            mode='text',
            text=[f"{latest_loss_val:,.0f} m³"],
            textposition="top center",
            textfont=dict(size=15, color=COLOR_LOSS_BLUE, family="Arial Black"),
            showlegend=False,
            hoverinfo='skip'
        ), secondary_y=False)

    # 2nd Axis: Share (Line) - [Modified] Text added, position 'bottom center', color 'lightgrey'
    fig_loss.add_trace(go.Scatter(
        x=df_year_filtered['Year'],
        y=df_year_filtered['Loss_Share_Household'],
        name='Loss Share (vs Household)',
        mode='lines+markers+text', # [Changed] text mode added
        text=df_year_filtered['Loss_Share_Household'].apply(lambda x: f"{x:.1f}%"), # [Added] text data
        textposition='bottom center', # [Added] position setting
        textfont=dict(size=16, color=COLOR_TEXT_LIGHTGREY), # [Added] font setting (light grey)
        line=dict(color=COLOR_LINE, width=3)
    ), secondary_y=True)

    fig_loss.update_layout(height=500, legend=dict(orientation="h", y=1.1), hovermode="x unified")
    fig_loss.update_yaxes(title_text="Annual Loss (m³)", secondary_y=False)
    fig_loss.update_yaxes(title_text="Loss Share (%)", secondary_y=True, range=[0, df_year_filtered['Loss_Share_Household'].max()*1.2], showticklabels=False)
    st.plotly_chart(fig_loss, use_container_width=True)

    # [Calculator]
    with st.expander("💰 Loss Revenue Simulator (Calculator)", expanded=True):
        if pd.notna(latest_year_val):
            c_calc1, c_calc2 = st.columns([1, 2])
            with c_calc1:
                input_price = st.number_input("Retail Price (KRW/m³)", value=950, step=10)
            with c_calc2:
                loss_revenue = latest_loss_val * input_price
                st.metric(
                    label=f"{latest_year_val} Est. Loss Revenue", 
                    value=f"{loss_revenue/100000000:.2f} Billion KRW",
                    delta=f"Loss Volume: {latest_loss_val:,.0f} m³"
                )
        else:
            st.write("No data available.")

    st.divider()

    # ----------------------------------------------------
    # [Bottom Graphs] Sales Comparison (Maintained)
    # ----------------------------------------------------
    col1, col2 = st.columns(2)
    
    # (Left) Household Sales vs Loss
    with col1:
        st.markdown("##### ① Household Sales vs Est. Loss")
        fig_u1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['Household_Sales_Total'], name='Household Sales', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['Annual_Loss_Est_m3'], name='Loss (Right Axis)', marker_color=COLOR_LOSS_BLUE), secondary_y=False)
        fig_u1.add_trace(go.Scatter(x=df_year_filtered['Year'], y=df_year_filtered['Loss_Share_Household'], name='Loss Share', mode='lines+markers+text', text=df_year_filtered['Loss_Share_Household'].apply(lambda x: f"{x:.2f}%"), textposition='top center', line=dict(color=COLOR_LINE, width=2)), secondary_y=True)
        fig_u1.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        fig_u1.update_yaxes(title_text="Usage (m³)", secondary_y=False)
        fig_u1.update_yaxes(title_text="Loss Share (%)", secondary_y=True, showticklabels=False) 
        st.plotly_chart(fig_u1, use_container_width=True)

    # (Right) Total Sales vs Loss
    with col2:
        st.markdown("##### ② Total Sales vs Est. Loss")
        fig_u2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['Total_Sales'], name='Total Sales', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['Annual_Loss_Est_m3'], name='Loss (Right Axis)', marker_color=COLOR_LOSS_BLUE), secondary_y=False)
        fig_u2.add_trace(go.Scatter(x=df_year_filtered['Year'], y=df_year_filtered['Loss_Share_Total'], name='Loss Share', mode='lines+markers+text', text=df_year_filtered['Loss_Share_Total'].apply(lambda x: f"{x:.2f}%"), textposition='top center', line=dict(color=COLOR_LINE, width=2)), secondary_y=True)
        fig_u2.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        fig_u2.update_yaxes(title_text="Usage (m³)", secondary_y=False)
        fig_u2.update_yaxes(title_text="Loss Share (%)", secondary_y=True, showticklabels=False)
        st.plotly_chart(fig_u2, use_container_width=True)
    
    # [Table Highlight]
    st.dataframe(
        df_year_filtered.style
        .format({
            'Conversion_Rate': '{:.1f}%', 'Loss_Share_Household': '{:.2f}%', 'Loss_Share_Total': '{:.2f}%',
            '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', 'Induction_Est_Count': '{:,.0f}',
            'Household_Sales_Total': '{:,.0f}', 'Total_Sales': '{:,.0f}', 'Annual_Loss_Est_m3': '{:,.0f}',
            'Potential_Household': '{:,.0f}', 'Potential_Total': '{:,.0f}'
        })
        .set_properties(
            subset=['Induction_Est_Count', 'Conversion_Rate'], 
            **{'background-color': '#ffffcc', 'font-weight': 'bold', 'color': 'black'}
        ),
        use_container_width=True, hide_index=True
    )
    st.download_button("📥 Download Detailed Data", convert_df(df_year_filtered), "detailed_data.csv", "text/csv")

    st.divider()

    # [3] Drill-down Step 1: Select Year -> District Comparison (Dec Data)
    st.subheader("3️⃣ Detailed Analysis: Select Year ➡️ District Comparison")
    sel_year = st.selectbox("📅 Select Year for Analysis:", sorted(df['Year'].unique(), reverse=True))
    
    df_gu_stock = df[(df['Year'] == sel_year) & (df['Date'].dt.month == 12)].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()
    if df_gu_stock.empty:
         last_month = df[df['Year'] == sel_year]['Date'].max().month
         df_gu_stock = df[(df['Year'] == sel_year) & (df['Date'].dt.month == last_month)].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()

    df_gu_stock['Conversion_Rate'] = (df_gu_stock['Induction_Est_Count'] / df_gu_stock['총청구계량기수']) * 100
    
    c3, c4 = st.columns(2)
    with c3:
        fig_gu1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_gu1.add_trace(go.Bar(x=df_gu_stock['시군구'], y=df_gu_stock['가스레인지연결전수'], name='Gas Range', marker_color=COLOR_GAS), secondary_y=False)
        fig_gu1.add_trace(go.Bar(x=df_gu_stock['시군구'], y=df_gu_stock['Induction_Est_Count'], name='Induction', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_gu1.add_trace(go.Scatter(x=df_gu_stock['시군구'], y=df_gu_stock['Conversion_Rate'], name='Conversion Rate (%)', mode='lines+markers+text',
                                     text=df_gu_stock['Conversion_Rate'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                     line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_gu1.update_layout(title=f"[{sel_year}] District Household Composition (Dec)", barmode='stack', legend=dict(orientation="h", y=-0.2), height=500)
        st.plotly_chart(fig_gu1, use_container_width=True)

    with c4:
        df_gu_sort = df_gu_stock.sort_values(by='Induction_Est_Count', ascending=False)
        fig_gu2 = px.bar(df_gu_sort, x='시군구', y='Induction_Est_Count', text_auto='.2s', 
                         title=f"[{sel_year}] District Induction Introduction Rank (Dec)", 
                         color='Induction_Est_Count', color_continuous_scale='Blues')
        fig_gu2.update_layout(height=500)
        st.plotly_chart(fig_gu2, use_container_width=True)

    st.dataframe(df_gu_stock.style.format({'Conversion_Rate': '{:.1f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', 'Induction_Est_Count': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button(f"📥 Download {sel_year} District Data", convert_df(df_gu_stock), f"{sel_year}_district.csv", "text/csv")

    st.divider()

    # [4] Detailed Analysis: Regional Trend
    st.subheader("4️⃣ Detailed Analysis: Select Region ➡️ Annual Trend")
    sel_region = st.selectbox("🏙️ Select Region:", sorted(df['시군구'].unique()))
    
    df_r_stock = df[(df['시군구'] == sel_region) & (df['Date'].dt.month == 12)].copy()
    df_r = df_r_stock.groupby('Year')[['총청구계량기수', '가스레인지연결전수', 'Induction_Est_Count']].sum().reset_index()
    df_r['Conversion_Rate'] = (df_r['Induction_Est_Count'] / df_r['총청구계량기수']) * 100
    df_r['Annual_Loss_Est_m3'] = df_r['Induction_Est_Count'] * input_monthly_usage * 12
    
    df_r_filtered = df_r[df_r['Year'] >= 2017].copy()

    c5, c6 = st.columns(2)
    with c5:
        fig_r1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='Gas Range', marker_color=COLOR_GAS), secondary_y=False)
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['Induction_Est_Count'], name='Induction', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_r1.add_trace(go.Scatter(x=df_r['Year'], y=df_r['Conversion_Rate'], name='Conversion Rate (%)', mode='lines+markers+text',
                                    text=df_r['Conversion_Rate'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_r1.update_layout(title=f"[{sel_region}] Annual Household Composition (Dec)", barmode='stack', legend=dict(orientation="h", y=-0.2), height=500)
        st.plotly_chart(fig_r1, use_container_width=True)
    with c6:
        fig_r2 = make_subplots(specs=[[{"secondary_y": True}]])
        # [Modified] Deep Blue applied
        fig_r2.add_trace(go.Bar(
            x=df_r_filtered['Year'], 
            y=df_r_filtered['Annual_Loss_Est_m3'], 
            name=f'[{sel_region}] Est. Loss Volume', 
            marker_color=COLOR_LOSS_BLUE, 
            text=df_r_filtered['Annual_Loss_Est_m3'].apply(lambda x: f"{x:,.0f}"),
            textposition='auto'
        ), secondary_y=False) 
        fig_r2.update_layout(
            title=f"[{sel_region}] Annual Est. Loss Volume Trend (m³)", 
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(title="Loss Volume (m³)"),
            height=500
        )
        st.plotly_chart(fig_r2, use_container_width=True)
    st.dataframe(df_r_filtered.style.format({'Conversion_Rate': '{:.1f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', 'Induction_Est_Count': '{:,.0f}', 'Annual_Loss_Est_m3': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button(f"📥 Download {sel_region} Data", convert_df(df_r), f"{sel_region}_data.csv", "text/csv")
