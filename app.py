import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="인덕션 전환 추세 분석",
    page_icon="🔥",
    layout="wide"
)

# ---------------------------------------------------------
# 2. 데이터 로드 및 유틸리티
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def load_data_final_v19(url):
    try:
        df = pd.read_excel(url, engine='openpyxl')
    except Exception as e:
        st.error(f"⚠️ 가스레인지 데이터 로드 실패: {e}")
        return pd.DataFrame()

    df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
    
    target_cols = ['총청구계량기수', '가스레인지연결전수', '사용량(m3)']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if '년월' in df.columns:
        df['년월'] = df['년월'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df['Date'] = pd.to_datetime(df['년월'], format='%Y%m', errors='coerce')
        df = df.dropna(subset=['Date'])
    
    # 파생 변수
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    # [연도 정수형 변환]
    df['Year'] = df['Date'].dt.year.astype(int)

    return df

@st.cache_data(ttl=60)
def load_sales_data_final_v19():
    """
    [판매량 데이터 로드]
    단위: 천m³ -> m³ (* 1000)
    """
    url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/%ED%8C%90%EB%A7%A4%EB%9F%89(%EA%B3%84%ED%9A%8D_%EC%8B%A4%EC%A0%81).xlsx"
    
    try:
        df = pd.read_excel(url, engine='openpyxl', sheet_name='실적_부피')
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # 합산 대상 컬럼
        household_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        other_cols = ['일반용', '업무난방용', '냉방용', '산업용', '수송용(CNG)', '수송용(BIO)', '열병합용', '연료전지용', '열전용설비용', '주한미군']
        all_cols = household_cols + other_cols
        
        # 숫자 변환
        for col in all_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # [단위 보정] 천m³ -> m³ (무조건 * 1000)
        df['가정용_판매량_전체'] = df[household_cols].sum(axis=1) * 1000
        df['기타_판매량_전체'] = df[other_cols].sum(axis=1) * 1000
        df['전체_판매량'] = df['가정용_판매량_전체'] + df['기타_판매량_전체']
        
        return df[['Year', 'Date', '가정용_판매량_전체', '전체_판매량']]
             
    except Exception as e:
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 ---
COLOR_GAS = '#1f77b4'       # 기본 파랑
COLOR_INDUCTION = '#a4c2f4' # 연한 하늘색
COLOR_LINE = '#d62728'      # 빨강 (비율 선)
COLOR_LOSS_BLUE = '#115f9a' # 손실량 (딥 블루)
COLOR_HIGHLIGHT_BG = '#a4c2f4' # 하이라이트 배경
COLOR_HIGHLIGHT_LINE = '#1f77b4' # 하이라이트 선/텍스트
# [신규] 텍스트 색상 (연한 회색)
COLOR_TEXT_LIGHTGREY = 'lightgrey' 

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성
# ---------------------------------------------------------
gas_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

df_raw = load_data_final_v19(gas_url)
df_sales_raw = load_sales_data_final_v19()

if df_raw.empty:
    st.error("🚨 기본 데이터 로드 실패. 잠시 후 다시 시도해주세요.")
    st.stop()

# 대제목
st.title("🔥 인덕션 전환 추세 분석")

# [데이터 로드 확인창]
if not df_sales_raw.empty:
    with st.expander("✅ 판매량 데이터 로드 확인 (단위: m³로 변환됨)"):
        st.write("아래 수치는 **천m³ 단위에 1,000을 곱하여 m³로 변환된** 결과입니다.")
        check_df = df_sales_raw[df_sales_raw['Year'] >= 2024].sort_values('Date', ascending=False).head(5)
        st.dataframe(check_df, use_container_width=True)
else:
    st.warning("⚠️ 판매량 데이터를 불러오는 중입니다.")

with st.sidebar:
    st.header("🔥 분석 메뉴")
    selected_menu = st.radio(
        "분석 메뉴 선택",
        ["1. 전환 추세 및 상세 분석"]
    )
    
    st.markdown("---")
    st.header("🔍 데이터 필터")
    
    input_pph = st.number_input(
        "적용할 세대당 월평균 가스 사용량 (m³)", 
        min_value=0.0, 
        max_value=100.0, 
        value=5.0, 
        step=0.5
    )
    st.caption("※ PPH: 난방을 제외한 순수 취사 전용 사용량")
    
    st.divider()
    
    min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()
    start_date, end_date = st.slider("조회 기간", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    
    regions = st.multiselect("지역 선택", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.multiselect("용도 선택", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))

# 전역 필터 적용
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# ---------------------------------------------------------
# 4. 메인 화면 로직
# ---------------------------------------------------------

st.markdown(f"### 📊 {selected_menu}")

# =========================================================
# [MENU 1] 전환 추세 및 상세 분석
# =========================================================
if selected_menu == "1. 전환 추세 및 상세 분석":
    
    st.info("""
    **[인덕션 사용가구 추정 방법]**
    1. **인덕션 사용가구 추정** : 총 청구 계량기 수 (12월 기준) - 가스레인지 연결 전수 (12월 기준)
    2. **연간 손실 추정량** : 인덕션 사용가구 추정 × 세대당 월평균 가스 사용량(PPH) × 12개월
    """)

    # 1. 월별 트렌드 (Time Series)
    st.subheader("1️⃣ 월별 트렌드 (Time Series)")
    df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_m['전환율'] = (df_m['인덕션_추정_수'] / df_m['총청구계량기수']) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='가스레인지', stackgroup='one', line=dict(color=COLOR_GAS)))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['인덕션_추정_수'], name='인덕션(추정)', stackgroup='one', line=dict(color=COLOR_INDUCTION)))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['전환율'], name='전환율(%)', yaxis='y2', mode='lines+markers', line=dict(color=COLOR_LINE)))
    
    fig.update_layout(
        yaxis2=dict(overlaying='y', side='right'), 
        hovermode="x unified", 
        legend=dict(orientation="h", y=1.1),
        height=600 
    )
    st.plotly_chart(fig, use_container_width=True)
    
    df_m_filtered = df_m[df_m['Date'].dt.year >= 2017].copy()
    st.dataframe(df_m_filtered.style.format({'전환율': '{:.1f}%','총청구계량기수': '{:,.0f}','가스레인지연결전수': '{:,.0f}','인덕션_추정_수': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.divider()

    # [2] 연도별 분석
    st.subheader("2️⃣ 연도별 수량 및 손실 추정량 분석")
    
    # --- 데이터 처리 ---
    df_dec = df[df['Date'].dt.month == 12].copy()
    df_year_stock = df_dec.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_year_stock['Year'] = df_year_stock['Year'].astype(int)
    df_year_stock['전환율'] = (df_year_stock['인덕션_추정_수'] / df_year_stock['총청구계량기수']) * 100
    df_year_stock['연간손실추정_m3'] = df_year_stock['인덕션_추정_수'] * input_pph * 12
    
    if not df_sales_raw.empty:
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[['가정용_판매량_전체', '전체_판매량']].sum().reset_index()
    else:
        df_sales_year = pd.DataFrame(columns=['Year', '가정용_판매량_전체', '전체_판매량'])

    df_year = pd.merge(df_year_stock, df_sales_year, on='Year', how='left')
    if not df_sales_year.empty:
        df_year['가정용_판매량_전체'] = df_year['가정용_판매량_전체'].fillna(0)
        df_year['전체_판매량'] = df_year['전체_판매량'].fillna(0)
    else:
        df_year['가정용_판매량_전체'] = 0
        df_year['전체_판매량'] = 0
        
    df_year['잠재_가정용'] = df_year['가정용_판매량_전체'] + df_year['연간손실추정_m3']
    df_year['손실점유율_가정'] = df_year.apply(lambda x: (x['연간손실추정_m3'] / x['잠재_가정용'] * 100) if x['잠재_가정용'] > 0 else 0, axis=1)
    df_year['잠재_전체'] = df_year['전체_판매량'] + df_year['연간손실추정_m3']
    df_year['손실점유율_전체'] = df_year.apply(lambda x: (x['연간손실추정_m3'] / x['잠재_전체'] * 100) if x['잠재_전체'] > 0 else 0, axis=1)

    df_year_filtered = df_year[df_year['Year'] >= 2017].copy()
    
    highlight_condition = df_year_filtered['전환율'] > 10.0
    start_highlight_year = df_year_filtered.loc[highlight_condition, 'Year'].min() if highlight_condition.any() else None
    end_highlight_year = df_year_filtered['Year'].max()

    # ----------------------------------------------------
    # [형님 요청] 그래프 1: 텍스트 사이즈 2배 & 연한 회색
    # ----------------------------------------------------
    st.markdown("##### 1. 연도별 세대 구성(12월) 및 전환율")
    fig_q = make_subplots(specs=[[{"secondary_y": True}]])
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지(12월)', marker_color=COLOR_GAS), secondary_y=False)
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션(12월)', marker_color=COLOR_INDUCTION), secondary_y=False)
    
    # [수정] 텍스트 폰트 사이즈 2배(24px) 및 색상(연한 회색) 적용
    fig_q.add_trace(go.Scatter(
        x=df_year['Year'], y=df_year['전환율'], name='전환율(%)', mode='lines+markers+text', 
        text=df_year['전환율'].apply(lambda x: f"{x:.1f}%"), 
        textposition='top center',
        textfont=dict(size=24, color=COLOR_TEXT_LIGHTGREY), # 폰트 수정
        line=dict(color=COLOR_LINE, width=3)
    ), secondary_y=True)
    
    if start_highlight_year:
        fig_q.add_vrect(
            x0=start_highlight_year-0.5, x1=end_highlight_year+0.5, 
            fillcolor=COLOR_HIGHLIGHT_BG, opacity=0.2, layer="below", line_width=0
        )
        fig_q.add_vline(
            x=start_highlight_year-0.5, line_width=2, line_dash="dash", line_color=COLOR_HIGHLIGHT_LINE,
            annotation_text="🚀 전환 가속화", 
            annotation_position="top left",
            annotation_font=dict(size=14, color=COLOR_HIGHLIGHT_LINE, family="Arial Black")
        )

    fig_q.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500, hovermode="x unified")
    fig_q.update_yaxes(title_text="세대수 (12월 기준)", secondary_y=False)
    fig_q.update_yaxes(title_text="전환율 (%)", secondary_y=True, range=[0, df_year['전환율'].max()*1.2])
    st.plotly_chart(fig_q, use_container_width=True)

    st.markdown("---") 

    # ----------------------------------------------------
    # [형님 요청] 그래프 2: 텍스트 사이즈 2배 & 연한 회색 (막대 안)
    # ----------------------------------------------------
    st.markdown("##### 2. 연간 가정용 손실량 추정 및 비중")
    fig_loss = make_subplots(specs=[[{"secondary_y": True}]])
    
    latest_year_val = df_year_filtered['Year'].max()
    latest_loss_val = df_year_filtered[df_year_filtered['Year'] == latest_year_val]['연간손실추정_m3'].values[0] if pd.notna(latest_year_val) else 0

    # 1축: 손실량 (막대) - [수정] 텍스트 폰트 수정
    fig_loss.add_trace(go.Bar(
        x=df_year_filtered['Year'],
        y=df_year_filtered['연간손실추정_m3'],
        name='연간 손실량(m³)',
        marker_color=COLOR_LOSS_BLUE,
        text=df_year_filtered['손실점유율_가정'].apply(lambda x: f"{x:.1f}%"),
        textposition='inside',
        # [수정] 폰트 사이즈 2배(20px) 및 색상(연한 회색) 적용
        textfont=dict(size=20, color=COLOR_TEXT_LIGHTGREY) 
    ), secondary_y=False)
    
    # 최신 연도 라벨
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

    # 2축: 비중 (선)
    fig_loss.add_trace(go.Scatter(
        x=df_year_filtered['Year'],
        y=df_year_filtered['손실점유율_가정'],
        name='손실 비중(%, 가정용 대비)',
        mode='lines+markers', 
        line=dict(color=COLOR_LINE, width=3)
    ), secondary_y=True)

    fig_loss.update_layout(height=500, legend=dict(orientation="h", y=1.1), hovermode="x unified")
    fig_loss.update_yaxes(title_text="연간 손실량 (m³)", secondary_y=False)
    fig_loss.update_yaxes(title_text="손실 비중 (%)", secondary_y=True, range=[0, df_year_filtered['손실점유율_가정'].max()*1.2], showticklabels=False)
    st.plotly_chart(fig_loss, use_container_width=True)

    # [계산기]
    with st.expander("💰 손실 매출 시뮬레이터 (계산기)", expanded=True):
        if pd.notna(latest_year_val):
            c_calc1, c_calc2 = st.columns([1, 2])
            with c_calc1:
                input_price = st.number_input("소매단가(원/m³)", value=950, step=10)
            with c_calc2:
                loss_revenue = latest_loss_val * input_price
                st.metric(
                    label=f"{latest_year_val}년 추정 손실 매출액", 
                    value=f"{loss_revenue/100000000:.2f} 억원",
                    delta=f"손실량: {latest_loss_val:,.0f} m³"
                )
        else:
            st.write("데이터가 없습니다.")

    st.divider()

    # ----------------------------------------------------
    # [하단 그래프] 판매량 비교 (유지)
    # ----------------------------------------------------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### ① 가정용 판매량 vs 손실 추정량")
        fig_u1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['가정용_판매량_전체'], name='가정용 판매량', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['연간손실추정_m3'], name='손실량(우측)', marker_color=COLOR_LOSS_BLUE), secondary_y=False)
        fig_u1.add_trace(go.Scatter(x=df_year_filtered['Year'], y=df_year_filtered['손실점유율_가정'], name='손실 비중', mode='lines+markers+text', text=df_year_filtered['손실점유율_가정'].apply(lambda x: f"{x:.2f}%"), textposition='top center', line=dict(color=COLOR_LINE, width=2)), secondary_y=True)
        fig_u1.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        fig_u1.update_yaxes(title_text="사용량 (m³)", secondary_y=False)
        fig_u1.update_yaxes(title_text="손실 비중 (%)", secondary_y=True, showticklabels=False) 
        st.plotly_chart(fig_u1, use_container_width=True)

    with col2:
        st.markdown("##### ② 전체 판매량 vs 손실 추정량")
        fig_u2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['전체_판매량'], name='전체 판매량', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['연간손실추정_m3'], name='손실량(우측)', marker_color=COLOR_LOSS_BLUE), secondary_y=False)
        fig_u2.add_trace(go.Scatter(x=df_year_filtered['Year'], y=df_year_filtered['손실점유율_전체'], name='손실 비중', mode='lines+markers+text', text=df_year_filtered['손실점유율_전체'].apply(lambda x: f"{x:.2f}%"), textposition='top center', line=dict(color=COLOR_LINE, width=2)), secondary_y=True)
        fig_u2.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        fig_u2.update_yaxes(title_text="사용량 (m³)", secondary_y=False)
        fig_u2.update_yaxes(title_text="손실 비중 (%)", secondary_y=True, showticklabels=False)
        st.plotly_chart(fig_u2, use_container_width=True)
    
    # ----------------------------------------------------
    # [형님 요청] 표 하이라이트 (핵심 컬럼 세로 강조)
    # ----------------------------------------------------
    st.dataframe(
        df_year_filtered.style
        .format({
            '전환율': '{:.1f}%', '손실점유율_가정': '{:.2f}%', '손실점유율_전체': '{:.2f}%',
            '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}',
            '가정용_판매량_전체': '{:,.0f}', '전체_판매량': '{:,.0f}', '연간손실추정_m3': '{:,.0f}',
            '잠재_가정용': '{:,.0f}', '잠재_전체': '{:,.0f}'
        })
        # [핵심 수정] 특정 컬럼(인덕션_추정_수, 전환율) 세로 하이라이트 적용
        .set_properties(
            subset=['인덕션_추정_수', '전환율'], 
            **{'background-color': '#ffffcc', 'font-weight': 'bold', 'color': 'black'}
        ),
        use_container_width=True, hide_index=True
    )
    st.download_button("📥 상세 데이터 다운로드", convert_df(df_year_filtered), "상세_데이터.csv", "text/csv")

    st.divider()

    # [3] Drill-down Step 1: 연도 선택 -> 구군별 비교 (12월 기준)
    st.subheader("3️⃣ 상세 분석: 연도 선택 ➡️ 구군별 비교")
    sel_year = st.selectbox("📅 분석할 연도를 선택하세요:", sorted(df['Year'].unique(), reverse=True))
    
    df_gu_stock = df[(df['Year'] == sel_year) & (df['Date'].dt.month == 12)].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    if df_gu_stock.empty:
         last_month = df[df['Year'] == sel_year]['Date'].max().month
         df_gu_stock = df[(df['Year'] == sel_year) & (df['Date'].dt.month == last_month)].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()

    df_gu_stock['전환율'] = (df_gu_stock['인덕션_추정_수'] / df_gu_stock['총청구계량기수']) * 100
    
    c3, c4 = st.columns(2)
    with c3:
        fig_gu1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_gu1.add_trace(go.Bar(x=df_gu_stock['시군구'], y=df_gu_stock['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_gu1.add_trace(go.Bar(x=df_gu_stock['시군구'], y=df_gu_stock['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_gu1.add_trace(go.Scatter(x=df_gu_stock['시군구'], y=df_gu_stock['전환율'], name='전환율(%)', mode='lines+markers+text',
                                     text=df_gu_stock['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                     line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_gu1.update_layout(title=f"[{sel_year}년] 구군별 세대 구성 (12월 기준)", barmode='stack', legend=dict(orientation="h", y=-0.2), height=500)
        st.plotly_chart(fig_gu1, use_container_width=True)

    with c4:
        df_gu_sort = df_gu_stock.sort_values(by='인덕션_추정_수', ascending=False)
        fig_gu2 = px.bar(df_gu_sort, x='시군구', y='인덕션_추정_수', text_auto='.2s', 
                         title=f"[{sel_year}년] 구군별 인덕션 도입 수량 순위 (12월 기준)", 
                         color='인덕션_추정_수', color_continuous_scale='Blues')
        fig_gu2.update_layout(height=500)
        st.plotly_chart(fig_gu2, use_container_width=True)

    st.dataframe(df_gu_stock.style.format({'전환율': '{:.1f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button(f"📥 {sel_year}_구군별_다운로드", convert_df(df_gu_stock), f"{sel_year}_구군별.csv", "text/csv")

    st.divider()

    # [4] 상세분석: 지역별 흐름
    st.subheader("4️⃣ 상세 분석: 지역(구군) 선택 ➡️ 연도별 흐름")
    sel_region = st.selectbox("🏙️ 지역(구군)을 선택하세요:", sorted(df['시군구'].unique()))
    
    df_r_stock = df[(df['시군구'] == sel_region) & (df['Date'].dt.month == 12)].copy()
    df_r = df_r_stock.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_r['전환율'] = (df_r['인덕션_추정_수'] / df_r['총청구계량기수']) * 100
    df_r['연간손실추정_m3'] = df_r['인덕션_추정_수'] * input_pph * 12
    
    df_r_filtered = df_r[df_r['Year'] >= 2017].copy()

    c5, c6 = st.columns(2)
    with c5:
        fig_r1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_r1.add_trace(go.Scatter(x=df_r['Year'], y=df_r['전환율'], name='전환율(%)', mode='lines+markers+text',
                                    text=df_r['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_r1.update_layout(title=f"[{sel_region}] 연도별 세대 구성 (12월 기준)", barmode='stack', legend=dict(orientation="h", y=-0.2), height=500)
        st.plotly_chart(fig_r1, use_container_width=True)
    with c6:
        fig_r2 = make_subplots(specs=[[{"secondary_y": True}]])
        # [수정] 딥 블루 적용
        fig_r2.add_trace(go.Bar(
            x=df_r_filtered['Year'], 
            y=df_r_filtered['연간손실추정_m3'], 
            name=f'[{sel_region}] 손실 추정량', 
            marker_color=COLOR_LOSS_BLUE, # 딥 블루
            text=df_r_filtered['연간손실추정_m3'].apply(lambda x: f"{x:,.0f}"),
            textposition='auto'
        ), secondary_y=False) 
        fig_r2.update_layout(
            title=f"[{sel_region}] 연간 손실 추정량 추이 (단위: m³)", 
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(title="손실량 (m³)"),
            height=500
        )
        st.plotly_chart(fig_r2, use_container_width=True)
    st.dataframe(df_r_filtered.style.format({'전환율': '{:.1f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}', '연간손실추정_m3': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button(f"📥 {sel_region}_데이터 다운로드", convert_df(df_r), f"{sel_region}_데이터.csv", "text/csv")
