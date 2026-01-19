import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="도시가스 인덕션 전환 분석",
    page_icon="🔥",
    layout="wide"
)

# ---------------------------------------------------------
# 2. 깃허브 데이터 로드 & 유틸리티
# ---------------------------------------------------------
@st.cache_data
def load_data_from_github(url):
    try:
        df = pd.read_excel(url, engine='openpyxl')
    except Exception as e:
        st.error(f"⚠️ 데이터를 불러오지 못했습니다. 에러 메시지: {e}")
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
    
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    if '사용량(m3)' in df.columns and '가스레인지연결전수' in df.columns:
        df['세대당_사용량'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)

    return df

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성 (핵심 변경!)
# ---------------------------------------------------------

github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.stop()

# --- [사이드바] 메뉴 및 필터 ---
with st.sidebar:
    st.title("🔥 분석 대시보드")
    
    # 1. 메인 메뉴 (라디오 버튼으로 탭 대체)
    selected_menu = st.radio(
        "분석 메뉴 선택",
        ["1. 전환 추세 및 상세 분석", "2. 판매량 영향 분석", "3. 지역별 위험도 순위", "4. 주택 유형별 비교"]
    )
    
    st.markdown("---")
    st.header("🔍 데이터 필터")
    
    min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()
    start_date, end_date = st.slider("조회 기간", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    
    regions = st.multiselect("지역 선택", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.multiselect("용도 선택", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))

# 필터링 적용
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# ---------------------------------------------------------
# 4. 메인 화면 로직 (메뉴 선택에 따라 화면 전환)
# ---------------------------------------------------------

st.header(f"📊 {selected_menu}")

# =========================================================
# [MENU 1] 전환 추세 및 상세 분석
# =========================================================
if selected_menu == "1. 전환 추세 및 상세 분석":
    
    st.markdown("#### 1️⃣ 월별 트렌드 (Time Series)")
    df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_m['전환율'] = (df_m['인덕션_추정_수'] / df_m['총청구계량기수']) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='가스레인지', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['인덕션_추정_수'], name='인덕션(추정)', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['전환율'], name='전환율(%)', yaxis='y2', mode='lines+markers', line=dict(color='red')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    
    # [데이터 표]
    st.markdown("###### 📋 월별 상세 데이터")
    st.dataframe(df_m.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.divider()

    st.markdown("#### 2️⃣ 연도별 & 지역별 상세 현황 (Dual Axis)")
    df['Year'] = df['Date'].dt.year
    col1, col2 = st.columns(2)
    
    # [차트 A] 연도별
    with col1:
        st.markdown("##### 연도별 추이")
        df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
        df_year['전환율'] = (df_year['인덕션_추정_수'] / df_year['총청구계량기수']) * 100
        
        fig_y = make_subplots(specs=[[{"secondary_y": True}]])
        fig_y.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'), secondary_y=False)
        fig_y.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'), secondary_y=False)
        fig_y.add_trace(go.Scatter(x=df_year['Year'], y=df_year['전환율'], name='전환율(%)', mode='lines+markers+text', text=df_year['전환율'].apply(lambda x: f"{x:.1f}%"), textposition="top center", marker_color='red'), secondary_y=True)
        fig_y.update_layout(barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_y, use_container_width=True)
        
        # [데이터 표]
        st.dataframe(df_year.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
        st.download_button("📥 연도별 데이터 다운로드", convert_df(df_year), "연도별_데이터.csv", "text/csv")

    # [차트 B] 지역별
    with col2:
        st.markdown(f"##### {df['Year'].max()}년 지역별 현황")
        current_year = df['Year'].max()
        df_region = df[df['Year'] == current_year].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
        df_region['전환율'] = (df_region['인덕션_추정_수'] / df_region['총청구계량기수']) * 100
        df_region = df_region.sort_values(by='전환율', ascending=False)
        
        fig_r = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r.add_trace(go.Bar(x=df_region['시군구'], y=df_region['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4', showlegend=False), secondary_y=False)
        fig_r.add_trace(go.Bar(x=df_region['시군구'], y=df_region['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e', showlegend=False), secondary_y=False)
        fig_r.add_trace(go.Scatter(x=df_region['시군구'], y=df_region['전환율'], name='전환율(%)', mode='lines+markers+text', text=df_region['전환율'].apply(lambda x: f"{x:.1f}%"), textposition="top center", marker_color='red', showlegend=False), secondary_y=True)
        fig_r.update_layout(barmode='stack')
        st.plotly_chart(fig_r, use_container_width=True)
        
        # [데이터 표]
        st.dataframe(df_region.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
        st.download_button("📥 지역별 데이터 다운로드", convert_df(df_region), "지역별_데이터.csv", "text/csv")

# =========================================================
# [MENU 2] 판매량 영향 분석
# =========================================================
elif selected_menu == "2. 판매량 영향 분석":
    
    st.markdown("#### 📉 인덕션 전환율 vs 세대당 사용량(PPH)")
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index().dropna()
    
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='세대당_사용량', color='시군구', trendline="ols", hover_data=['Date'])
        st.plotly_chart(fig2, use_container_width=True)
        
        # [데이터 표]
        st.markdown("###### 📋 상관관계 분석 원본 데이터")
        # 날짜 포맷 정리해서 보여주기
        df_s['Date'] = df_s['Date'].dt.strftime('%Y-%m')
        st.dataframe(df_s.style.format({'인덕션_전환율': '{:.2f}%', '세대당_사용량': '{:.2f} m3'}), use_container_width=True)
        st.download_button("📥 PPH 분석 데이터 다운로드", convert_df(df_s), "PPH_분석_데이터.csv", "text/csv")
    else:
        st.info("데이터 부족으로 상관관계를 표시할 수 없습니다.")

# =========================================================
# [MENU 3] 지역별 위험도 순위
# =========================================================
elif selected_menu == "3. 지역별 위험도 순위":
    
    st.markdown("#### 🗺️ 최근 월 기준 이탈 위험도")
    latest = df['Date'].max()
    df_l = df[df['Date'] == latest].groupby('시군구')[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_l['인덕션_전환율'] = (1 - df_l['가스레인지연결전수'] / df_l['총청구계량기수']) * 100
    df_l = df_l.sort_values('인덕션_전환율', ascending=False)
    
    fig3 = px.bar(df_l, x='시군구', y='인덕션_전환율', color='인덕션_전환율', text_auto='.1f', title=f"기준월: {latest.strftime('%Y-%m')}")
    st.plotly_chart(fig3, use_container_width=True)
    
    # [데이터 표]
    st.markdown("###### 📋 지역별 순위 데이터")
    st.dataframe(df_l.style.format({'인덕션_전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 지역별 순위 다운로드", convert_df(df_l), "지역별_위험도.csv", "text/csv")

# =========================================================
# [MENU 4] 주택 유형별 비교
# =========================================================
elif selected_menu == "4. 주택 유형별 비교":
    
    st.markdown("#### 🏢 공동주택(APT) vs 단독주택 패턴 비교")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    
    # [데이터 표] (피벗으로 보기 좋게 변형)
    st.markdown("###### 📋 유형별 전환율 데이터 비교")
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    df_pivot['Date'] = df_pivot['Date'].dt.strftime('%Y-%m')
    
    st.dataframe(df_pivot.style.format("{:.2f}%", subset=df_pivot.columns[1:]), use_container_width=True)
    st.download_button("📥 유형별 비교 데이터 다운로드", convert_df(df_pivot), "유형별_비교_데이터.csv", "text/csv")
