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
        # 세대당 사용량 (PPH)
        df['세대당_사용량'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)
        
    df['Year'] = df['Date'].dt.year

    return df

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성 (에러 해결의 핵심!)
# ---------------------------------------------------------
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.stop()

# --- [사이드바] 메뉴 및 필터 ---
with st.sidebar:
    st.title("🔥 분석 대시보드")
    
    # [1] 요청하신 '좌측 화면 4가지 탭' (라디오 버튼 메뉴)
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

# [중요] 필터링을 여기서 미리 수행해서 'df' 변수를 전역으로 만듦 (에러 해결!)
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# ---------------------------------------------------------
# 4. 메인 화면 로직
# ---------------------------------------------------------

st.header(f"📊 {selected_menu}")

# =========================================================
# [MENU 1] 전환 추세 및 상세 분석
# =========================================================
if selected_menu == "1. 전환 추세 및 상세 분석":
    
    # 1. 상단: 월별 트렌드 (기존 유지)
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

    st.markdown("---")

    # 2. 중단: 연도별 상세 (요청사항 반영!)
    st.markdown("#### 2️⃣ 연도별 수량 및 손실 추정량 분석")
    st.info("""
    💡 **그래프 해석 가이드:**
    * **좌측 그래프:** 전체 세대 중 가스레인지 사용자와 인덕션 전환자의 **비율(%) 변화**를 보여줍니다.
    * **우측 그래프:** 인덕션 전환으로 인해 **사라진 가스 판매량(손실 추정)**을 시각화했습니다. (주황색 영역만큼 매출 기회 손실)
    """)
    
    # 데이터 집계
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    df_year['전환율'] = (df_year['인덕션_추정_수'] / df_year['총청구계량기수']) * 100
    
    # [손실량 계산 로직]
    # PPH(세대당평균사용량) = 총사용량 / 가스레인지세대수
    # 손실추정량 = 인덕션세대수 * PPH
    df_year['PPH'] = df_year['사용량(m3)'] / df_year['가스레인지연결전수']
    df_year['손실추정량'] = df_year['인덕션_추정_수'] * df_year['PPH']
    
    col1, col2 = st.columns(2)
    
    # (좌) 연도별 수량 + 비율(Line)
    with col1:
        fig_q = make_subplots(specs=[[{"secondary_y": True}]])
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지(세대)', marker_color='#1f77b4'), secondary_y=False)
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션(세대)', marker_color='#ff7f0e'), secondary_y=False)
        fig_q.add_trace(go.Scatter(x=df_year['Year'], y=df_year['전환율'], name='전환율(%)', mode='lines+markers+text', 
                                   text=df_year['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center', 
                                   line=dict(color='red', width=3)), secondary_y=True)
        fig_q.update_layout(title="연도별 세대 구성 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_q.update_yaxes(title_text="세대수", secondary_y=False)
        fig_q.update_yaxes(title_text="전환율(%)", secondary_y=True, range=[0, df_year['전환율'].max()*1.2])
        st.plotly_chart(fig_q, use_container_width=True)

    # (우) 연도별 사용량 + 손실량(Stacked)
    with col2:
        fig_u = go.Figure()
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['사용량(m3)'], name='실제 사용량', marker_color='#2ca02c'))
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['손실추정량'], name='손실 추정량(이탈분)', marker_color='#d62728'))
        fig_u.update_layout(title="실제 사용량 vs 이탈 손실 추정량 (m³)", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_u, use_container_width=True)
    
    # 데이터 표
    with st.expander("📄 연도별 상세 데이터 확인"):
        st.dataframe(df_year.style.format("{:,.0f}"), use_container_width=True)
        st.download_button("📥 연도별 데이터 다운로드", convert_df(df_year), "연도별_상세.csv", "text/csv")

    st.markdown("---")

    # 3. 하단: Drill-down (요청사항 반영: 우측 그래프에 비율 Line 추가)
    st.markdown("#### 3️⃣ 상세 분석 (Drill-down)")
    
    col_sel3, col_sel4 = st.columns([1, 3])
    with col_sel3:
        sel_region = st.selectbox("🏙️ 지역(구군) 선택", sorted(df['시군구'].unique()))
        
    df_r = df[df['시군구'] == sel_region].groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_r['전환율'] = (df_r['인덕션_추정_수'] / df_r['총청구계량기수']) * 100
    
    c5, c6 = st.columns(2)
    with c5:
        # (좌) 누적 막대
        fig_r1 = go.Figure()
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='가스레인지', marker_color='#1f77b4'))
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션', marker_color='#ff7f0e'))
        fig_r1.update_layout(title=f"[{sel_region}] 연도별 세대 구성", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_r1, use_container_width=True)
    
    with c6:
        # (우) 인덕션 수량 + 전환율 Line (요청사항!)
        fig_r2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r2.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션 수(세대)', marker_color='#ff7f0e'), secondary_y=False)
        fig_r2.add_trace(go.Scatter(x=df_r['Year'], y=df_r['전환율'], name='전환율(%)', mode='lines+markers+text',
                                    text=df_r['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    line=dict(color='red', width=3)), secondary_y=True)
        fig_r2.update_layout(title=f"[{sel_region}] 인덕션 도입 수 및 전환율", legend=dict(orientation="h", y=-0.2))
        fig_r2.update_yaxes(title_text="인덕션 세대수", secondary_y=False)
        fig_r2.update_yaxes(title_text="전환율(%)", secondary_y=True, range=[0, df_r['전환율'].max()*1.2])
        st.plotly_chart(fig_r2, use_container_width=True)

    st.dataframe(df_r.style.format("{:,.0f}"), use_container_width=True)
    st.download_button(f"📥 {sel_region}_데이터 다운로드", convert_df(df_r), f"{sel_region}_데이터.csv", "text/csv")


# =========================================================
# [MENU 2] 판매량 영향 분석
# =========================================================
elif selected_menu == "2. 판매량 영향 분석":
    
    st.markdown("#### 📉 인덕션 전환율 vs 세대당 사용량(PPH)")
    # [에러 해결] df는 위에서 이미 필터링되어 있으므로 바로 사용 가능
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index().dropna()
    
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='세대당_사용량', color='시군구', trendline="ols")
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df_s.style.format({'인덕션_전환율': '{:.2f}%', '세대당_사용량': '{:.2f} m3'}))
        st.download_button("📥 PPH 데이터 다운로드", convert_df(df_s), "PPH_데이터.csv", "text/csv")
    else:
        st.info("데이터가 부족하여 그래프를 그릴 수 없습니다.")

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
    st.dataframe(df_l.style.format({'인덕션_전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}))
    st.download_button("📥 순위 데이터 다운로드", convert_df(df_l), "지역별_순위.csv", "text/csv")

# =========================================================
# [MENU 4] 주택 유형별 비교
# =========================================================
elif selected_menu == "4. 주택 유형별 비교":
    
    st.markdown("#### 🏢 공동주택(APT) vs 단독주택 패턴 비교")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    st.dataframe(df_pivot.style.format("{:.2f}%", subset=df_pivot.columns[1:]))
    st.download_button("📥 유형별 데이터 다운로드", convert_df(df_pivot), "유형별_비교.csv", "text/csv")
