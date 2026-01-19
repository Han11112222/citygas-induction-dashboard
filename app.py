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
        df = pd.read_excel(url, engine='openpyxl')
    except Exception as e:
        st.error(f"⚠️ 데이터를 불러오지 못했습니다. 에러 메시지: {e}")
        return pd.DataFrame()

    # 컬럼 공백 제거 및 전처리
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
    
    # 파생 변수 생성
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    if '사용량(m3)' in df.columns and '가스레인지연결전수' in df.columns:
        df['세대당_사용량'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)

    return df

# ---------------------------------------------------------
# 3. 메인 로직
# ---------------------------------------------------------

# 👇 Han형님의 깃허브 파일 주소
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.warning("데이터 로딩 실패. GitHub URL을 확인해주세요.")
    st.stop()

# 필터링
min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()

with st.sidebar:
    st.header("🔍 분석 필터")
    start_date, end_date = st.slider("조회 기간", min_date.date(), max_date.date(), (min_date.date(), max_date.date()), format="YYYY.MM")
    regions = st.multiselect("지역", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.multiselect("용도", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))

df = df_raw[
    (df_raw['Date'].dt.date >= start_date) & 
    (df_raw['Date'].dt.date <= end_date) & 
    (df_raw['시군구'].isin(regions)) & 
    (df_raw['용도'].isin(types))
]

# ---------------------------------------------------------
# 4. 탭 구성 (Tab 5 추가됨!)
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 전환 추세", "📉 판매량 영향", "🗺️ 지역 위험도", "🏢 유형별 비교", "📊 구성비 상세 분석"
])

# [Tab 1~4: 기존 코드와 동일]
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

# ---------------------------------------------------------
# [Tab 5: 새로 추가된 그래프 4종 세트]
# ---------------------------------------------------------
with tab5:
    st.subheader("📊 연도별 & 지역별 구성비 상세 분석")
    st.markdown("전체 청구 세대(Total)를 **가스레인지**와 **인덕션(추정)**으로 나누어 시각화했습니다.")
    
    # 데이터 가공 (Plotly Bar차트용 포맷 변환)
    # 연도 추출
    df['Year'] = df['Date'].dt.year
    
    # 1. 연도별 데이터 집계
    df_year = df.groupby('Year')[['가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    # Long Format으로 변환 (범례 처리를 위해)
    df_year_long = df_year.melt(id_vars='Year', value_vars=['가스레인지연결전수', '인덕션_추정_수'], var_name='유형', value_name='세대수')
    
    # 2. 지역별 데이터 집계 (최신 연도 기준)
    current_year = df['Year'].max()
    df_region = df[df['Year'] == current_year].groupby('시군구')[['가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_region_long = df_region.melt(id_vars='시군구', value_vars=['가스레인지연결전수', '인덕션_추정_수'], var_name='유형', value_name='세대수')

    # --- 화면 배치 (2x2 Grid) ---
    col1, col2 = st.columns(2)
    
    # [1] 연도별 누적 막대 (절대값)
    with col1:
        st.markdown("##### 1️⃣ 연도별 세대수 변화 (절대값)")
        fig_y1 = px.bar(df_year_long, x='Year', y='세대수', color='유형', 
                        title="연도별 가스 vs 인덕션 세대수",
                        text_auto='.2s', # 숫자 표시
                        color_discrete_map={'가스레인지연결전수': '#1f77b4', '인덕션_추정_수': '#ff7f0e'})
        st.plotly_chart(fig_y1, use_container_width=True)

    # [2] 연도별 100% 누적 막대 (비중)
    with col2:
        st.markdown("##### 2️⃣ 연도별 비중 변화 (%)")
        # 100% 스택 바 차트를 만들기 위해 groupnorm 사용 불필요 (px.bar에서 기본 지원 안함 -> 데이터 처리 필요없음, layout 설정으로 가능)
        # 하지만 명확하게 하기 위해 normalization 옵션 활용
        fig_y2 = px.bar(df_year_long, x='Year', y='세대수', color='유형', 
                        title="연도별 점유율 변화 (100% 기준)",
                        text_auto='.1f', 
                        color_discrete_map={'가스레인지연결전수': '#1f77b4', '인덕션_추정_수': '#ff7f0e'})
        # bar mode를 'relative'가 아닌 '100% stacked'로 변경하려면 update_layout 필요하지만, 
        # Plotly Express에서는 barnorm='percent'를 지원하지 않는 경우가 있어 직접 계산하거나 layout 수정.
        # 가장 쉬운 방법: layout 업데이트
        fig_y2.update_layout(barmode='stack', yaxis=dict(tickformat=".0%"), barnorm='percent')
        st.plotly_chart(fig_y2, use_container_width=True)

    col3, col4 = st.columns(2)

    # [3] 구군별 누적 막대 (절대값)
    with col3:
        st.markdown(f"##### 3️⃣ {current_year}년 지역별 세대수 (절대값)")
        # 세대수 많은 순서로 정렬
        df_region_long = df_region_long.sort_values(by='세대수', ascending=False)
        fig_r1 = px.bar(df_region_long, x='시군구', y='세대수', color='유형',
                        title="지역별 가스 vs 인덕션 규모 비교",
                        text_auto='.2s',
                        color_discrete_map={'가스레인지연결전수': '#1f77b4', '인덕션_추정_수': '#ff7f0e'})
        st.plotly_chart(fig_r1, use_container_width=True)

    # [4] 구군별 100% 누적 막대 (비중)
    with col4:
        st.markdown(f"##### 4️⃣ {current_year}년 지역별 전환율 비교 (%)")
        fig_r2 = px.bar(df_region_long, x='시군구', y='세대수', color='유형',
                        title="지역별 인덕션 침투율 비교",
                        text_auto='.1f',
                        color_discrete_map={'가스레인지연결전수': '#1f77b4', '인덕션_추정_수': '#ff7f0e'})
        fig_r2.update_layout(barmode='stack', yaxis=dict(tickformat=".0%"), barnorm='percent')
        st.plotly_chart(fig_r2, use_container_width=True)
