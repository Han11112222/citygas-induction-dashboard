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
        
    df['Year'] = df['Date'].dt.year

    return df

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 (기존 유지)
# ---------------------------------------------------------
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.stop()

# 사이드바 필터 (기존 유지)
with st.sidebar:
    st.title("🔥 분석 대시보드")
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
# 4. 탭 구성 (4개 탭 복구 완료)
# ---------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 1. 전환 추세 및 상세 분석", "📉 2. 판매량 영향", "🗺️ 3. 지역별 위험도", "🏢 4. 주택 유형별 비교"
])

# =========================================================
# [TAB 1] 전환 추세 및 상세 분석 (상단 유지 + 하단 신규 추가)
# =========================================================
with tab1:
    # 1. 상단: 월별 트렌드 (기존 내용 유지 - 손대지 않음)
    st.markdown("#### 1️⃣ 월별 트렌드 (Time Series)")
    df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_m['전환율'] = (df_m['인덕션_추정_수'] / df_m['총청구계량기수']) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='가스레인지', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['인덕션_추정_수'], name='인덕션(추정)', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['전환율'], name='전환율(%)', yaxis='y2', mode='lines+markers', line=dict(color='red')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("📄 월별 데이터 보기"):
        st.dataframe(df_m.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}))
        st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.markdown("---") # 구분선
    
    # 2. 중단: 연도별 수량 vs 사용량 (요청하신 1번째 사진 구성)
    st.markdown("#### 2️⃣ 연도별 수량 및 사용량 비교")
    
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    
    c1, c2 = st.columns(2)
    
    # (좌) 연도별 수량 (Stacked Bar)
    with c1:
        fig_q = go.Figure()
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_q.update_layout(title="연도별 세대수 구성", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_q, use_container_width=True)
        st.dataframe(df_year[['Year', '가스레인지연결전수', '인덕션_추정_수']].style.format("{:,.0f}"), use_container_width=True)
        st.download_button("📥 세대수 데이터 다운로드", convert_df(df_year[['Year', '가스레인지연결전수', '인덕션_추정_수']]), "연도별_세대수.csv", "text/csv")

    # (우) 연도별 사용량 (Bar + Trendline)
    with c2:
        fig_u = go.Figure()
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['사용량(m3)'], name='총 사용량', marker_color='#2ca02c'))
        fig_u.add_trace(go.Scatter(x=df_year['Year'], y=df_year['사용량(m3)'], name='추세', line=dict(color='red', dash='dot')))
        fig_u.update_layout(title="연도별 총 사용량(m³) 추이", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_u, use_container_width=True)
        st.dataframe(df_year[['Year', '사용량(m3)']].style.format("{:,.0f}"), use_container_width=True)
        st.download_button("📥 사용량 데이터 다운로드", convert_df(df_year[['Year', '사용량(m3)']]), "연도별_사용량.csv", "text/csv")

    st.markdown("---")

    # 3. 하단: Drill-down 분석 (요청하신 3번째 사진 구성)
    st.markdown("#### 3️⃣ 상세 분석 (Drill-down)")
    
    # [3-1] 연도 선택 -> 구군별 현황
    col_sel1, col_sel2 = st.columns([1, 3])
    with col_sel1:
        sel_year = st.selectbox("📅 연도 선택", sorted(df['Year'].unique(), reverse=True))
    
    df_gu = df[df['Year'] == sel_year].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    
    c3, c4 = st.columns(2)
    with c3:
        fig_gu1 = go.Figure()
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_gu1.update_layout(title=f"{sel_year}년 구군별 구성", barmode='stack')
        st.plotly_chart(fig_gu1, use_container_width=True)
        st.dataframe(df_gu.style.format("{:,.0f}", subset=['가스레인지연결전수', '인덕션_추정_수']), use_container_width=True)

    with c4:
        df_gu_sort = df_gu.sort_values(by='인덕션_추정_수', ascending=False)
        fig_gu2 = px.bar(df_gu_sort, x='시군구', y='인덕션_추정_수', text_auto='.2s', title=f"{sel_year}년 구군별 인덕션 수량", color='인덕션_추정_수', color_continuous_scale='Oranges')
        st.plotly_chart(fig_gu2, use_container_width=True)
        st.dataframe(df_gu_sort[['시군구', '인덕션_추정_수']].style.format("{:,.0f}"), use_container_width=True)

    st.divider()

    # [3-2] 구군 선택 -> 연도별 흐름
    col_sel3, col_sel4 = st.columns([1, 3])
    with col_sel3:
        sel_region = st.selectbox("🏙️ 지역(구군) 선택", sorted(df['시군구'].unique()))
        
    df_r = df[df['시군구'] == sel_region].groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    
    c5, c6 = st.columns(2)
    with c5:
        fig_r1 = go.Figure()
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_r1.update_layout(title=f"[{sel_region}] 연도별 구성 변화", barmode='stack')
        st.plotly_chart(fig_r1, use_container_width=True)
    
    with c6:
        # 우측: 인덕션 수량 변화 (단독)
        fig_r2 = px.line(df_r, x='Year', y='인덕션_추정_수', markers=True, title=f"[{sel_region}] 인덕션 도입 수량 추이")
        fig_r2.update_traces(line_color='#ff7f0e', line_width=3)
        st.plotly_chart(fig_r2, use_container_width=True)

    # 하단 통합 데이터 표
    st.dataframe(df_r.style.format("{:,.0f}"), use_container_width=True)
    st.download_button(f"📥 {sel_region}_데이터 다운로드", convert_df(df_r), f"{sel_region}_데이터.csv", "text/csv")


# =========================================================
# [TAB 2] 판매량 영향 분석 (기존 유지)
# =========================================================
with tab2:
    st.subheader("인덕션 전환율과 세대당 사용량(PPH) 관계")
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index().dropna()
    
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='세대당_사용량', color='시군구', trendline="ols")
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df_s.style.format({'인덕션_전환율': '{:.2f}%', '세대당_사용량': '{:.2f} m3'}))
        st.download_button("📥 PPH 데이터 다운로드", convert_df(df_s), "PPH_데이터.csv", "text/csv")
    else:
        st.info("데이터 부족")

# =========================================================
# [TAB 3] 지역별 위험도 순위 (기존 유지)
# =========================================================
with tab3:
    st.subheader("지역별 인덕션 전환율 순위")
    latest = df['Date'].max()
    df_l = df[df['Date'] == latest].groupby('시군구')[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_l['인덕션_전환율'] = (1 - df_l['가스레인지연결전수'] / df_l['총청구계량기수']) * 100
    df_l = df_l.sort_values('인덕션_전환율', ascending=False)
    
    fig3 = px.bar(df_l, x='시군구', y='인덕션_전환율', color='인덕션_전환율', text_auto='.1f', title=f"기준: {latest.strftime('%Y-%m')}")
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(df_l.style.format({'인덕션_전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}))
    st.download_button("📥 순위 데이터 다운로드", convert_df(df_l), "지역별_순위.csv", "text/csv")

# =========================================================
# [TAB 4] 주택 유형별 비교 (기존 유지)
# =========================================================
with tab4:
    st.subheader("공동주택 vs 단독주택")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    st.dataframe(df_pivot.style.format("{:.2f}%", subset=df_pivot.columns[1:]))
    st.download_button("📥 유형별 데이터 다운로드", convert_df(df_pivot), "유형별_비교.csv", "text/csv")
