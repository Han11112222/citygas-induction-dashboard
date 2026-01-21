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
def load_data_from_github(url):
    try:
        # [수정] URL에 따옴표("") 추가하여 SyntaxError 해결
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
def load_sales_data():
    """
    [핵심 수정] 판매량 데이터 로드
    1. '실적_부피' 시트 사용
    2. [단위 보정] 엑셀 데이터(천m³) * 1000 -> m³
    """
    # [수정] URL에 따옴표("") 추가
    url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/%ED%8C%90%EB%A7%A4%EB%9F%89(%EA%B3%84%ED%9A%8D_%EC%8B%A4%EC%A0%81).xlsx"
    
    try:
        # 1. '실적_부피' 시트 로드
        df = pd.read_excel(url, engine='openpyxl', sheet_name='실적_부피')
        
        # 2. 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        # 3. 날짜 및 연도 처리
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # 4. 합산 대상 컬럼 정의
        household_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        other_cols = ['일반용', '업무난방용', '냉방용', '산업용', '수송용(CNG)', '수송용(BIO)', '열병합용', '연료전지용', '열전용설비용', '주한미군']
        all_cols = household_cols + other_cols
        
        # 5. 숫자 변환
        for col in all_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # 6. [단위 보정] 엑셀(천m³) -> m³ (x 1000)
        df['가정용_판매량_전체'] = df[household_cols].sum(axis=1) * 1000
        df['기타_판매량_전체'] = df[other_cols].sum(axis=1) * 1000
        df['전체_판매량'] = df['가정용_판매량_전체'] + df['기타_판매량_전체']
        
        return df[['Year', 'Date', '가정용_판매량_전체', '전체_판매량']]
             
    except Exception as e:
        # st.error(f"⚠️ 판매량 데이터 로드 중 에러: {e}") 
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 ---
COLOR_GAS = '#1f77b4'       # 진한 파랑 (판매량 - 바닥)
COLOR_INDUCTION = '#a4c2f4' # 연한 하늘색 (손실 추정량 - 위)
COLOR_LINE = '#d62728'      # 빨강 (비율/전환율/손실율)

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성
# ---------------------------------------------------------
# [수정] URL에 따옴표("") 추가
gas_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

df_raw = load_data_from_github(gas_url)
df_sales_raw = load_sales_data()

if df_raw.empty:
    st.stop()

# 대제목
st.title("🔥 인덕션 전환 추세 분석")

# [데이터 로드 확인]
if not df_sales_raw.empty:
    with st.expander("✅ 판매량 데이터 로드 확인 (단위: m³로 변환 완료)"):
        check_df = df_sales_raw[df_sales_raw['Year'] >= 2024].sort_values('Date', ascending=False).head(5)
        st.dataframe(check_df, use_container_width=True)
else:
    st.error("🚨 판매량 데이터를 불러오지 못했습니다. URL 인코딩 문제를 확인해주세요.")

with st.sidebar:
    st.header("🔥 분석 메뉴")
    selected_menu = st.radio(
        "분석 메뉴 선택",
        ["1. 전환 추세 및 상세 분석", "ver2.0 분석 (12월 기준)", "2. 판매량 영향 분석", "3. 지역별 위험도 순위", "4. 주택 유형별 비교"]
    )
    
    st.markdown("---")
    st.header("🔍 데이터 필터")
    
    # [형님 요청] PPH 입력 버튼
    input_pph = st.number_input(
        "적용할 세대당 월평균 가스 사용량 (m³)", 
        min_value=0.0, 
        max_value=100.0, 
        value=10.0, 
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
# [MENU 1] 전환 추세 및 상세 분석 (기존 유지)
# =========================================================
if selected_menu == "1. 전환 추세 및 상세 분석":
    
    # [1] 월별 트렌드
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
    st.dataframe(
        df_m_filtered.style.format({
            '전환율': '{:.1f}%',
            '총청구계량기수': '{:,.0f}',
            '가스레인지연결전수': '{:,.0f}',
            '인덕션_추정_수': '{:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.divider()

    # [2] 연도별 수량 (단순 합산)
    st.subheader("2️⃣ 연도별 수량 및 손실 추정량 분석 (단순 월 누적)")
    
    # 1. 데이터 집계 (단순 Sum)
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_year['Year'] = df_year['Year'].astype(int)
    df_year['전환율'] = (df_year['인덕션_추정_수'] / df_year['총청구계량기수']) * 100
    
    # 2. 판매량 데이터 병합 (단위: m³)
    if not df_sales_raw.empty:
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[['가정용_판매량_전체', '전체_판매량']].sum().reset_index()
        df_year = pd.merge(df_year, df_sales_year, on='Year', how='left')
        df_year['가정용_판매량_전체'] = df_year['가정용_판매량_전체'].fillna(0)
        df_year['전체_판매량'] = df_year['전체_판매량'].fillna(0)
    else:
        df_year['가정용_판매량_전체'] = 0
        df_year['전체_판매량'] = 0

    # 3. 손실량 계산 (m³)
    df['월별손실추정_m3'] = df['인덕션_추정_수'] * input_pph
    df_loss_year = df.groupby('Year')['월별손실추정_m3'].sum().reset_index()
    df_loss_year['Year'] = df_loss_year['Year'].astype(int)
    df_year = pd.merge(df_year, df_loss_year, on='Year', how='left')
    
    # 4. 필터링 & 하이라이트
    df_year_filtered = df_year[df_year['Year'] >= 2017].copy()
    df_year_filtered = df_year_filtered.sort_values('Year')
    highlight_condition = df_year_filtered['전환율'] > 10.0
    start_highlight_year = df_year_filtered.loc[highlight_condition, 'Year'].min() if highlight_condition.any() else None
    
    # 그래프
    st.markdown("##### 📊 연도별 세대 구성 (월합계) 및 전환율")
    fig_q = make_subplots(specs=[[{"secondary_y": True}]])
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지(누적)', marker_color=COLOR_GAS), secondary_y=False)
    fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션(누적)', marker_color=COLOR_INDUCTION), secondary_y=False)
    fig_q.add_trace(go.Scatter(x=df_year['Year'], y=df_year['전환율'], name='전환율(%)', mode='lines+markers+text', 
                               text=df_year['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center', 
                               line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
    
    if start_highlight_year:
        fig_q.add_vrect(x0=start_highlight_year-0.5, x1=df_year['Year'].max()+0.5, 
                        fillcolor="yellow", opacity=0.15, layer="below", line_width=0,
                        annotation_text="🚀전환율 10% 돌파", annotation_position="top left")

    fig_q.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
    st.plotly_chart(fig_q, use_container_width=True)

    st.divider()

    # 우측 그래프 등 나머지 1번 메뉴 요소들 (생략 없이 원래 코드 유지)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### ① 가정용 판매량 vs 손실 추정량 (단위: m³)")
        fig_u1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['가정용_판매량_전체'], name='가정용 판매량', marker_color=COLOR_GAS), secondary_y=False)
        fig_u1.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['월별손실추정_m3'], name='손실량', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_u1.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        st.plotly_chart(fig_u1, use_container_width=True)
    with col2:
        st.markdown("##### ② 전체 판매량 vs 손실 추정량 (단위: m³)")
        fig_u2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['전체_판매량'], name='전체 판매량', marker_color=COLOR_GAS), secondary_y=False)
        fig_u2.add_trace(go.Bar(x=df_year_filtered['Year'], y=df_year_filtered['월별손실추정_m3'], name='손실량', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_u2.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        st.plotly_chart(fig_u2, use_container_width=True)

# =========================================================
# [MENU 2] Ver 2.0 분석 (12월 기준)
# =========================================================
elif selected_menu == "ver2.0 분석 (12월 기준)":
    
    st.info("💡 **Ver 2.0 분석:** 연도별 데이터 합산 시, 세대수는 **'12월 데이터(기말)'**만 사용하고, 판매량/손실량은 **'연간 총합'**을 사용하여 정확도를 높였습니다.")

    # 1. [핵심] 12월 데이터만 필터링 (Stock Data: 세대수)
    df_dec = df[df['Date'].dt.month == 12].copy()
    
    # 2. 데이터 집계 (세대수: 12월 기준)
    df_ver2_stock = df_dec.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_ver2_stock['Year'] = df_ver2_stock['Year'].astype(int)
    df_ver2_stock['전환율'] = (df_ver2_stock['인덕션_추정_수'] / df_ver2_stock['총청구계량기수']) * 100
    
    # 3. 판매량/손실량 데이터 (Flow Data: 연간 합계는 전체 월 합산이 맞음)
    # 손실량 계산 (전체 월 기준)
    df['월별손실추정_m3'] = df['인덕션_추정_수'] * input_pph
    df_flow_loss = df.groupby('Year')['월별손실추정_m3'].sum().reset_index()
    
    # 판매량 데이터 (전체 월 기준)
    if not df_sales_raw.empty:
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[['가정용_판매량_전체', '전체_판매량']].sum().reset_index()
    else:
        df_sales_year = pd.DataFrame(columns=['Year', '가정용_판매량_전체', '전체_판매량'])

    # 4. 병합 (Stock + Flow)
    df_ver2 = pd.merge(df_ver2_stock, df_flow_loss, on='Year', how='left')
    if not df_sales_year.empty:
        df_ver2 = pd.merge(df_ver2, df_sales_year, on='Year', how='left')
        df_ver2['가정용_판매량_전체'] = df_ver2['가정용_판매량_전체'].fillna(0)
        df_ver2['전체_판매량'] = df_ver2['전체_판매량'].fillna(0)
    else:
        df_ver2['가정용_판매량_전체'] = 0
        df_ver2['전체_판매량'] = 0
        
    # 필터링 (2017~)
    df_ver2_filtered = df_ver2[df_ver2['Year'] >= 2017].copy()
    
    # 하이라이트
    highlight_condition = df_ver2_filtered['전환율'] > 10.0
    start_highlight_year = df_ver2_filtered.loc[highlight_condition, 'Year'].min() if highlight_condition.any() else None

    # ----------------------------------------------------
    # 그래프 1: 세대 구성 (12월 기준)
    # ----------------------------------------------------
    col_v2_1, col_v2_2 = st.columns(2)
    
    with col_v2_1:
        st.markdown("##### 📊 연도별 세대 구성 (12월 기준) 및 전환율")
        fig_q = make_subplots(specs=[[{"secondary_y": True}]])
        fig_q.add_trace(go.Bar(x=df_ver2['Year'], y=df_ver2['가스레인지연결전수'], name='가스레인지(12월)', marker_color=COLOR_GAS), secondary_y=False)
        fig_q.add_trace(go.Bar(x=df_ver2['Year'], y=df_ver2['인덕션_추정_수'], name='인덕션(12월)', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_q.add_trace(go.Scatter(x=df_ver2['Year'], y=df_ver2['전환율'], name='전환율(%)', mode='lines+markers+text', 
                                   text=df_ver2['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center', 
                                   line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        
        if start_highlight_year:
            fig_q.add_vrect(x0=start_highlight_year-0.5, x1=df_ver2['Year'].max()+0.5, 
                            fillcolor="yellow", opacity=0.15, layer="below", line_width=0,
                            annotation_text="🚀10% 돌파", annotation_position="top left")

        fig_q.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500)
        fig_q.update_yaxes(title_text="세대수 (12월 기준)", secondary_y=False)
        st.plotly_chart(fig_q, use_container_width=True)

    with col_v2_2:
        st.markdown("##### 📉 연간 손실 추정량 (단위: m³)")
        fig_loss = go.Figure()
        fig_loss.add_trace(go.Bar(
            x=df_ver2['Year'],
            y=df_ver2['월별손실추정_m3'],
            name='연간 손실량',
            marker_color=COLOR_INDUCTION,
            text=df_ver2['월별손실추정_m3'].apply(lambda x: f"{x:,.0f}"),
            textposition='auto'
        ))
        fig_loss.update_layout(height=500, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_loss, use_container_width=True)

    st.divider()

    # ----------------------------------------------------
    # 그래프 2 & 3: 판매량 비교 (이중축 적용)
    # ----------------------------------------------------
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### ① 가정용 판매량 vs 손실 추정량 (이중축)")
        fig_u1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u1.add_trace(go.Bar(x=df_ver2_filtered['Year'], y=df_ver2_filtered['가정용_판매량_전체'], name='가정용 판매량', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u1.add_trace(go.Bar(x=df_ver2_filtered['Year'], y=df_ver2_filtered['월별손실추정_m3'], name='손실량', marker_color=COLOR_INDUCTION), secondary_y=True)
        fig_u1.update_layout(barmode='group', legend=dict(orientation="h", y=1.1), height=500)
        fig_u1.update_yaxes(title_text="판매량 (m³)", secondary_y=False)
        fig_u1.update_yaxes(title_text="손실량 (m³)", secondary_y=True)
        st.plotly_chart(fig_u1, use_container_width=True)

    with col2:
        st.markdown("##### ② 전체 판매량 vs 손실 추정량 (이중축)")
        fig_u2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_u2.add_trace(go.Bar(x=df_ver2_filtered['Year'], y=df_ver2_filtered['전체_판매량'], name='전체 판매량', marker_color=COLOR_GAS, opacity=0.7), secondary_y=False)
        fig_u2.add_trace(go.Bar(x=df_ver2_filtered['Year'], y=df_ver2_filtered['월별손실추정_m3'], name='손실량', marker_color=COLOR_INDUCTION), secondary_y=True)
        fig_u2.update_layout(barmode='group', legend=dict(orientation="h", y=1.1), height=500)
        fig_u2.update_yaxes(title_text="전체 판매량 (m³)", secondary_y=False)
        fig_u2.update_yaxes(title_text="손실량 (m³)", secondary_y=True)
        st.plotly_chart(fig_u2, use_container_width=True)
    
    st.dataframe(df_ver2_filtered.style.format("{:,.0f}"), use_container_width=True)


# =========================================================
# [MENU 2~4] 기존 차트 유지 (3, 4, 5번 등)
# =========================================================
elif selected_menu == "2. 판매량 영향 분석":
    st.markdown("#### 📉 인덕션 전환율 vs 세대당 사용량(PPH)")
    st.info("⚠️ 주의: 아래 산점도의 '세대당 사용량'은 데이터에 있는 **전체 사용량(난방 포함)**을 기준으로 합니다.")
    df['Real_PPH'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', 'Real_PPH']].mean().reset_index().dropna()
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='Real_PPH', color='시군구', trendline="ols", labels={'Real_PPH': '세대당 총 사용량(m³)'})
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df_s.style.format({'인덕션_전환율': '{:.1f}%', 'Real_PPH': '{:.1f} m3'}), use_container_width=True, hide_index=True)
    else:
        st.info("데이터 부족")

elif selected_menu == "3. 지역별 위험도 순위":
    st.markdown("#### 🗺️ 최근 월 기준 이탈 위험도")
    latest = df['Date'].max()
    df_l = df[df['Date'] == latest].groupby('시군구')[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_l['인덕션_전환율'] = (1 - df_l['가스레인지연결전수'] / df_l['총청구계량기수']) * 100
    df_l = df_l.sort_values('인덕션_전환율', ascending=False)
    fig3 = px.bar(df_l, x='시군구', y='인덕션_전환율', color='인덕션_전환율', text_auto='.1f', 
                  title=f"기준월: {latest.strftime('%Y-%m')}", color_continuous_scale='Blues')
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(df_l.style.format({'인덕션_전환율': '{:.1f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True, hide_index=True)

elif selected_menu == "4. 주택 유형별 비교":
    st.markdown("#### 🏢 공동주택(APT) vs 단독주택 패턴 비교")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    st.dataframe(df_pivot.style.format("{:.1f}%", subset=df_pivot.columns[1:]), use_container_width=True, hide_index=True)
