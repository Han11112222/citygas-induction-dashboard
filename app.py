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
# 2. 데이터 로드 및 유틸리티
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
    
    # 파생 변수
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    if '사용량(m3)' in df.columns and '가스레인지연결전수' in df.columns:
        df['세대당_사용량'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)
        
    # 연도 컬럼 미리 생성
    df['Year'] = df['Date'].dt.year

    return df

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바
# ---------------------------------------------------------
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.stop()

with st.sidebar:
    st.title("🔥 분석 대시보드")
    
    # 메뉴 선택 (직관적인 탭 이동)
    selected_menu = st.radio("메뉴 선택", ["1. 심층 분석 (Drill-down)", "2. 원본 데이터 검색"])
    
    st.markdown("---")
    st.header("🔍 기본 필터")
    
    # 기간 필터
    min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()
    start_date, end_date = st.slider("조회 기간", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    
    # 지역/용도 필터 (Drill-down에서도 기본 범위로 작동)
    regions = st.multiselect("지역 포함", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.multiselect("용도 포함", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))

# 필터 적용된 기본 데이터
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

st.header(f"📊 {selected_menu}")

# =========================================================
# [MENU 1] 심층 분석 (Drill-down) - 요청하신 핵심 기능
# =========================================================
if selected_menu == "1. 심층 분석 (Drill-down)":

    # --- PART 1. 전체 연도별 추세 (수량 vs 사용량) ---
    st.subheader("1️⃣ 연도별 구성 및 사용량 변화 (Total Trend)")
    
    # 데이터 집계
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    
    col1, col2 = st.columns(2)
    
    # (좌) 연도별 가스레인지 vs 인덕션 수량
    with col1:
        fig_q = go.Figure()
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_q.update_layout(title="연도별 세대수 구성 (Stacked)", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_q, use_container_width=True)
        
        # 데이터 표
        st.dataframe(df_year[['Year', '가스레인지연결전수', '인덕션_추정_수']].style.format("{:,.0f}"), use_container_width=True)
        st.download_button("📥 세대수 데이터 다운로드", convert_df(df_year[['Year', '가스레인지연결전수', '인덕션_추정_수']]), "연도별_세대수.csv", "text/csv")

    # (우) 연도별 사용량 추이
    with col2:
        fig_u = go.Figure()
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['사용량(m3)'], name='총 사용량', marker_color='#2ca02c'))
        # 추세선 추가
        fig_u.add_trace(go.Scatter(x=df_year['Year'], y=df_year['사용량(m3)'], name='추세선', mode='lines+markers', line=dict(color='red', width=2, dash='dot')))
        fig_u.update_layout(title="연도별 총 가스 사용량(m³) 변화", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_u, use_container_width=True)
        
        # 데이터 표
        st.dataframe(df_year[['Year', '사용량(m3)']].style.format("{:,.0f}"), use_container_width=True)
        st.download_button("📥 사용량 데이터 다운로드", convert_df(df_year[['Year', '사용량(m3)']]), "연도별_사용량.csv", "text/csv")

    st.markdown("---") # 구분선

    # --- PART 2. 연도 선택 -> 구군별 상세 ---
    st.subheader("2️⃣ [Drill-down] 특정 연도 상세 분석")
    
    # 연도 선택 Selectbox
    year_list = sorted(df['Year'].unique(), reverse=True)
    selected_year = st.selectbox("📅 분석할 연도를 선택하세요:", year_list, index=0)
    
    # 선택된 연도 데이터 필터링
    df_y_target = df[df['Year'] == selected_year]
    df_gu = df_y_target.groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    
    col3, col4 = st.columns(2)
    
    # (좌) 해당 연도 구군별 구성 (Stacked)
    with col3:
        fig_gu1 = go.Figure()
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_gu1.update_layout(title=f"{selected_year}년 구군별 세대 구성", barmode='stack')
        st.plotly_chart(fig_gu1, use_container_width=True)
        
        st.dataframe(df_gu.style.format("{:,.0f}", subset=['가스레인지연결전수', '인덕션_추정_수']), use_container_width=True)
        st.download_button(f"📥 {selected_year}_구군별_구성_다운로드", convert_df(df_gu), f"{selected_year}_구군별_구성.csv", "text/csv")

    # (우) 해당 연도 구군별 인덕션 수량 (단독)
    with col4:
        df_gu_sorted = df_gu.sort_values(by='인덕션_추정_수', ascending=False)
        fig_gu2 = px.bar(df_gu_sorted, x='시군구', y='인덕션_추정_수', text_auto='.2s', 
                         title=f"{selected_year}년 구군별 인덕션 도입 수량", color='인덕션_추정_수', color_continuous_scale='Oranges')
        st.plotly_chart(fig_gu2, use_container_width=True)
        
        st.dataframe(df_gu_sorted[['시군구', '인덕션_추정_수']].style.format("{:,.0f}"), use_container_width=True)
        st.download_button(f"📥 {selected_year}_인덕션_순위_다운로드", convert_df(df_gu_sorted), f"{selected_year}_인덕션_순위.csv", "text/csv")

    st.markdown("---") # 구분선

    # --- PART 3. 구군 선택 -> 연도별 흐름 ---
    st.subheader("3️⃣ [Drill-down] 특정 지역 연도별 흐름")
    
    # 구군 선택 Selectbox
    region_list = sorted(df['시군구'].unique())
    selected_region = st.selectbox("🏙️ 분석할 지역(구/군)을 선택하세요:", region_list, index=0)
    
    # 선택된 지역 데이터 필터링
    df_r_target = df[df['시군구'] == selected_region]
    df_r_year = df_r_target.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    df_r_year['전환율'] = (df_r_year['인덕션_추정_수'] / df_r_year['총청구계량기수']) * 100

    col5, col6 = st.columns(2)
    
    # (좌) 선택 지역 연도별 구성
    with col5:
        fig_r1 = go.Figure()
        fig_r1.add_trace(go.Bar(x=df_r_year['Year'], y=df_r_year['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_r1.add_trace(go.Bar(x=df_r_year['Year'], y=df_r_year['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_r1.update_layout(title=f"[{selected_region}] 연도별 세대 구성 변화", barmode='stack')
        st.plotly_chart(fig_r1, use_container_width=True)

    # (우) 선택 지역 연도별 전환율 꺾은선
    with col6:
        fig_r2 = go.Figure()
        fig_r2.add_trace(go.Scatter(x=df_r_year['Year'], y=df_r_year['전환율'], mode='lines+markers+text',
                                    text=df_r_year['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    name='전환율', line=dict(color='red', width=3)))
        fig_r2.update_layout(title=f"[{selected_region}] 연도별 인덕션 전환율 추이")
        st.plotly_chart(fig_r2, use_container_width=True)
    
    # 하단 통합 데이터 표
    st.markdown(f"###### 📋 [{selected_region}] 상세 데이터")
    st.dataframe(df_r_year.style.format({'전환율': '{:.2f}%', '사용량(m3)': '{:,.0f}', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
    st.download_button(f"📥 {selected_region}_상세데이터_다운로드", convert_df(df_r_year), f"{selected_region}_데이터.csv", "text/csv")


# =========================================================
# [MENU 2] 원본 데이터 검색 (기존 기능 유지)
# =========================================================
elif selected_menu == "2. 원본 데이터 검색":
    st.subheader("💾 원본 데이터 조회")
    st.dataframe(df)
    st.download_button("📥 전체 원본 데이터 다운로드", convert_df(df), "전체_원본_데이터.csv", "text/csv")
