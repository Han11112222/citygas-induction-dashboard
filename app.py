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
# 2. 데이터 로드 함수 (공백 없는 컬럼 전용)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # 1. 파일 읽기 (인코딩 자동 대응)
    try:
        df = pd.read_csv(file, encoding='cp949')
    except:
        df = pd.read_csv(file, encoding='utf-8')
    
    # [핵심] 혹시 모를 잔여 공백까지 완벽 제거 (안전장치)
    df.columns = df.columns.str.replace(' ', '').str.strip()
    
    # 2. 숫자 변환 (쉼표 제거 -> 숫자형)
    # 형님이 수정한 컬럼명 기준: 총청구계량기수, 가스레인지연결전수
    target_cols = ['총청구계량기수', '가스레인지연결전수', '사용량(m3)']
    
    for col in target_cols:
        if col in df.columns:
            # 문자열로 변환 후 쉼표 제거, 다시 숫자로
            df[col] = df[col].astype(str).str.replace(',', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 3. 날짜 변환
    if '년월' in df.columns:
        df['년월'] = df['년월'].astype(str).str.strip()
        df['Date'] = pd.to_datetime(df['년월'], format='%Y%m', errors='coerce')
        df = df.dropna(subset=['Date'])
    
    # 4. 파생 변수 생성 (공백 없는 이름 사용)
    if '총청구계량기수' in df.columns and '가스레인지연결전수' in df.columns:
        # 인덕션 추정 = 총청구 - 가스레인지
        df['인덕션_추정_수'] = df['총청구계량기수'] - df['가스레인지연결전수']
        
        # 전환율 계산 (분모 0 방지)
        df['인덕션_전환율'] = df.apply(
            lambda x: (x['인덕션_추정_수'] / x['총청구계량기수'] * 100) 
            if x['총청구계량기수'] > 0 else 0, 
            axis=1
        )
    
    if '사용량(m3)' in df.columns and '가스레인지연결전수' in df.columns:
        # 세대당 사용량 (PPH)
        df['세대당_사용량'] = df.apply(
            lambda x: (x['사용량(m3)'] / x['가스레인지연결전수']) 
            if x['가스레인지연결전수'] > 0 else 0,
            axis=1
        )

    return df

# ---------------------------------------------------------
# 3. 메인 대시보드 로직
# ---------------------------------------------------------
st.sidebar.header("📂 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

if uploaded_file is not None:
    df_raw = load_data(uploaded_file)
    
    # 필수 컬럼 체크 (공백 없는 버전)
    required = ['Date', '시군구', '용도', '총청구계량기수', '가스레인지연결전수']
    if not all(col in df_raw.columns for col in required):
        st.error(f"필수 컬럼이 없습니다. 현재 컬럼: {list(df_raw.columns)}")
        st.stop()

    # --- 필터링 ---
    min_date, max_date = df_raw['Date'].min(), df_raw['Date'].max()
    
    start_date, end_date = st.sidebar.slider(
        "조회 기간", 
        min_date.date(), max_date.date(), 
        (min_date.date(), max_date.date()), 
        format="YYYY.MM"
    )
    
    regions = st.sidebar.multiselect("지역", sorted(df_raw['시군구'].unique()), default=sorted(df_raw['시군구'].unique()))
    types = st.sidebar.multiselect("용도", sorted(df_raw['용도'].unique()), default=sorted(df_raw['용도'].unique()))
    
    df = df_raw[
        (df_raw['Date'].dt.date >= start_date) & 
        (df_raw['Date'].dt.date <= end_date) & 
        (df_raw['시군구'].isin(regions)) & 
        (df_raw['용도'].isin(types))
    ]

    # --- 시각화 탭 ---
    tab1, tab2, tab3, tab4 = st.tabs(["📈 전환 추세", "📉 판매량 영향", "🗺️ 지역 위험도", "🏢 유형별 비교"])
    
    # [Tab 1] 추세 분석
    with tab1:
        st.subheader("가스레인지 잔존 vs 인덕션 이탈 추이")
        df_m = df.groupby('Date')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
        df_m['전환율'] = (df_m['인덕션_추정_수'] / df_m['총청구계량기수']) * 100
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['가스레인지연결전수'], name='가스레인지', stackgroup='one'))
        fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['인덕션_추정_수'], name='인덕션(추정)', stackgroup='one'))
        fig.add_trace(go.Scatter(x=df_m['Date'], y=df_m['전환율'], name='전환율(%)', yaxis='y2', mode='lines+markers', line=dict(color='red')))
        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
    # [Tab 2] 판매량 영향 (PPH)
    with tab2:
        st.subheader("인덕션 전환율과 세대당 사용량(PPH) 관계")
        df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index().dropna()
        if not df_s.empty:
            fig2 = px.scatter(df_s, x='인덕션_전환율', y='세대당_사용량', color='시군구', trendline="ols", 
                              title="전환율이 높을수록 사용량(PPH)이 줄어드는가?")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("데이터가 부족하여 상관관계를 분석할 수 없습니다.")

    # [Tab 3] 지역별 순위
    with tab3:
        st.subheader("지역별 인덕션 전환율 순위 (최신 월 기준)")
        latest = df['Date'].max()
        df_l = df[df['Date'] == latest].groupby('시군구')[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
        df_l['인덕션_전환율'] = (1 - df_l['가스레인지연결전수'] / df_l['총청구계량기수']) * 100
        
        fig3 = px.bar(df_l.sort_values('인덕션_전환율', ascending=False), x='시군구', y='인덕션_전환율', 
                      color='인덕션_전환율', text_auto='.1f', title=f"{latest.strftime('%Y-%m')} 기준")
        st.plotly_chart(fig3, use_container_width=True)

    # [Tab 4] 용도별 비교
    with tab4:
        st.subheader("공동주택 vs 단독주택 전환율 비교")
        df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
        df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
        
        fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
        st.plotly_chart(fig4, use_container_width=True)

else:
    st.info("👈 수정하신 CSV 파일을 업로드해주세요! (띄어쓰기 없는 버전)")
