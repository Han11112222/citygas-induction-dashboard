import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="도시가스 인덕션 전환 분석",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 도시가스 가정용 연료전환(인덕션) 추이 분석")

# ---------------------------------------------------------
# 2. 깃허브 데이터 자동 로드 함수
# ---------------------------------------------------------
@st.cache_data
def load_data_from_github(url):
    try:
        # 엑셀 파일 읽기 (openpyxl 엔진 사용)
        df = pd.read_excel(url, engine='openpyxl')
            
    except Exception as e:
        st.error(f"⚠️ 데이터를 불러오지 못했습니다. 에러 메시지: {e}")
        return pd.DataFrame()

    # [전처리] 컬럼 공백 제거 (안전장치)
    df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
    
    # 숫자 변환 (쉼표 제거)
    target_cols = ['총청구계량기수', '가스레인지연결전수', '사용량(m3)']
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 날짜 변환
    if '년월' in df.columns:
        df['년월'] = df['년월'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df['Date'] = pd.to_datetime(df['년월'], format='%Y%m', errors='coerce')
        df = df.dropna(subset=['Date'])
    
    # 파생 변수 생성
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    if '사용량(m3)' in df.columns and '가스레인지연결전수' in df.columns:
        df['세대당_사용량'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)

    return df

# ---------------------------------------------------------
# 3. 메인 로직 (자동 실행)
# ---------------------------------------------------------

# 👇 Han형님의 깃허브 엑셀 파일 주소 (자동으로 추출해서 넣었습니다!)
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

# 데이터 로드
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.warning("데이터 로딩 실패. GitHub URL이나 파일 형식을 확인해주세요.")
    st.stop()

# 성공 메시지 (잠깐 떴다 사라짐)
st.toast("✅ GitHub에서 최신 데이터를 성공적으로 가져왔습니다!")

# --- 이하 분석 로직 ---
min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()

# 사이드바 필터
with st.sidebar:
    st.header("🔍 분석 필터")
    start_date, end_date = st.slider("조회 기간", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    
    # 지역/용도 필터 (전체 선택 기본값)
    all_regions = sorted(df_raw['시군구'].unique())
    all_types = sorted(df_raw['용도'].unique())
    
    regions = st.multiselect("지역", all_regions, default=all_regions)
    types = st.multiselect("용도", all_types, default=all_types)

# 데이터 필터링
df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📈 전환 추세", "📉 판매량 영향", "🗺️ 지역 위험도", "🏢 유형별 비교"])

with tab1:
    st.subheader("가스레인지 잔존 vs 인덕션 이탈 추이")
    df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_m['전환율'] = (df_m['인덕션_추정_수'] / df_m['총청구계량기수']) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='가스레인지', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['인덕션_추정_수'], name='인덕션(추정)', stackgroup='one'))
    fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['전환율'], name='전환율(%)', yaxis='y2', mode='lines+markers', line=dict(color='red')))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("인덕션 전환율과 세대당 사용량(PPH) 관계")
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index().dropna()
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='세대당_사용량', color='시군구', trendline="ols")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("데이터 부족으로 상관관계를 표시할 수 없습니다.")

with tab3:
    st.subheader("지역별 인덕션 전환율 순위")
    latest = df['Date'].max()
    df_l = df[df['Date'] == latest].groupby('시군구')[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_l['인덕션_전환율'] = (1 - df_l['가스레인지연결전수'] / df_l['총청구계량기수']) * 100
    fig3 = px.bar(df_l.sort_values('인덕션_전환율', ascending=False), x='시군구', y='인덕션_전환율', color='인덕션_전환율', text_auto='.1f')
    st.plotly_chart(fig3, use_container_width=True)

with tab4:
    st.subheader("공동주택 vs 단독주택")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
