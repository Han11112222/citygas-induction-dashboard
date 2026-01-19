import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# 1. 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="도시가스 인덕션 전환 분석 대시보드",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 도시가스 가정용 연료전환(인덕션) 추이 분석")

# ---------------------------------------------------------
# 2. 강력해진 데이터 로드 함수 (수정됨)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    # 1. 인코딩 자동 감지 시도 (cp949 우선, 실패시 utf-8)
    try:
        df = pd.read_csv(file, encoding='cp949')
    except UnicodeDecodeError:
        df = pd.read_csv(file, encoding='utf-8')
    
    # 2. 컬럼명 전처리: 앞뒤 공백 제거 (매우 중요!)
    # 엑셀에서 가져올 때 " 사용량 " 처럼 공백이 딸려오는 경우 방지
    df.columns = df.columns.str.strip()
    
    # 3. 숫자 데이터 변환 함수 (쉼표 제거 및 강제 형변환)
    def clean_numeric(value):
        if pd.isna(value):  # 빈 값은 0으로
            return 0
        if isinstance(value, str):
            # 쉼표 제거 후 공백 제거
            clean_str = value.replace(',', '').strip()
            if clean_str == '':
                return 0
            return float(clean_str)
        return float(value)

    # 변환 대상 컬럼 리스트
    target_cols = ['총 청구계량기수', '가스레인지 연결 전수', '사용량(m3)']
    
    for col in target_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
        else:
            # 혹시 컬럼명이 다를 경우를 대비해 에러 대신 경고를 띄움
            st.warning(f"⚠️ 경고: '{col}' 컬럼을 찾을 수 없습니다. CSV 파일의 헤더를 확인해주세요.")

    # 4. 날짜 변환
    if '년월' in df.columns:
        df['년월'] = df['년월'].astype(str).str.strip()
        df['Date'] = pd.to_datetime(df['년월'], format='%Y%m', errors='coerce')
        # 날짜 변환 실패한 행(Total 등) 제거
        df = df.dropna(subset=['Date'])
    
    # 5. 파생 변수 생성
    if '총 청구계량기수' in df.columns and '가스레인지 연결 전수' in df.columns:
        df['인덕션_추정_수'] = df['총 청구계량기수'] - df['가스레인지 연결 전수']
        df['인덕션_전환율'] = df.apply(
            lambda x: (x['인덕션_추정_수'] / x['총 청구계량기수'] * 100) if x['총 청구계량기수'] > 0 else 0, 
            axis=1
        )
    
    if '사용량(m3)' in df.columns and '가스레인지 연결 전수' in df.columns:
        df['세대당_사용량'] = df.apply(
            lambda x: (x['사용량(m3)'] / x['가스레인지 연결 전수']) if x['가스레인지 연결 전수'] > 0 else 0,
            axis=1
        )

    return df

# ---------------------------------------------------------
# 3. 사이드바 및 메인 로직
# ---------------------------------------------------------
st.sidebar.header("📂 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("CSV 파일을 업로드해주세요", type=['csv'])

if uploaded_file is not None:
    # 데이터 로드
    df_raw = load_data(uploaded_file)
    
    # [디버깅용] 데이터 확인 옵션
    with st.expander("🔍 데이터가 제대로 들어왔는지 확인하기 (클릭)"):
        st.write("데이터 미리보기 (상위 5개 행):")
        st.dataframe(df_raw.head())
        st.write("컬럼 목록:", df_raw.columns.tolist())
    
    # 필수 컬럼 체크
    required_cols = ['Date', '시군구', '용도']
    if not all(col in df_raw.columns for col in required_cols):
        st.error(f"데이터에 필수 컬럼이 누락되었습니다. 현재 컬럼: {df_raw.columns.tolist()}")
        st.stop()

    # --- 필터링 로직 ---
    min_date = df_raw['Date'].min()
    max_date = df_raw['Date'].max()
    
    start_date, end_date = st.sidebar.slider(
        "조회 기간",
        min_value=min_date.date(),
        max_value=max_date.date(),
        value=(min_date.date(), max_date.date()),
        format="YYYY.MM"
    )
    
    region_list = sorted(df_raw['시군구'].unique())
    selected_regions = st.sidebar.multiselect("지역 선택", region_list, default=region_list)
    
    type_list = sorted(df_raw['용도'].unique())
    selected_types = st.sidebar.multiselect("용도 선택", type_list, default=type_list)
    
    # 필터 적용
    mask = (
        (df_raw['Date'].dt.date >= start_date) &
        (df_raw['Date'].dt.date <= end_date) &
        (df_raw['시군구'].isin(selected_regions)) &
        (df_raw['용도'].isin(selected_types))
    )
    df = df_raw.loc[mask]

    # --- 탭 구성 ---
    tab1, tab2, tab3, tab4 = st.tabs(["📈 전환 추세", "📉 판매량 영향", "🗺️ 지역 분석", "🏢 유형별 비교"])
    
    # [Tab 1] 인덕션 전환 추세
    with tab1:
        st.subheader("인덕션 전환 추세")
        df_monthly = df.groupby('Date')[['총 청구계량기수', '가스레인지 연결 전수', '인덕션_추정_수']].sum().reset_index()
        df_monthly['전환율'] = (df_monthly['인덕션_추정_수'] / df_monthly['총 청구계량기수']) * 100
        
        # 차트
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_monthly['Date'], y=df_monthly['가스레인지 연결 전수'], mode='lines', name='가스레인지', stackgroup='one'))
        fig1.add_trace(go.Scatter(x=df_monthly['Date'], y=df_monthly['인덕션_추정_수'], mode='lines', name='인덕션(추정)', stackgroup='one'))
        fig1.add_trace(go.Scatter(x=df_monthly['Date'], y=df_monthly['전환율'], mode='lines+markers', name='전환율(%)', yaxis='y2', line=dict(color='red', width=2)))
        fig1.update_layout(yaxis2=dict(overlaying='y', side='right'), title="가스레인지 잔존 vs 인덕션 이탈 추이")
        st.plotly_chart(fig1, use_container_width=True)

    # [Tab 2] 판매량 영향
    with tab2:
        st.subheader("인덕션 전환율과 세대당 사용량(PPH) 상관관계")
        # 시군구/년월별 집계
        df_scatter = df.groupby(['시군구', 'Date'])[['인덕션_전환율', '세대당_사용량']].mean().reset_index()
        # Nan 값 제거 (계산 오류 방지)
        df_scatter = df_scatter.dropna()
        
        if not df_scatter.empty:
            fig2 = px.scatter(
                df_scatter, x='인덕션_전환율', y='세대당_사용량', color='시군구',
                trendline="ols", title="인덕션 전환율이 높을수록 사용량은 줄어드는가?"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("데이터가 충분하지 않아 상관관계 차트를 그릴 수 없습니다.")

    # [Tab 3] 지역 분석
    with tab3:
        st.subheader("최근 월 기준 지역별 전환율")
        latest_date = df['Date'].max()
        df_latest = df[df['Date'] == latest_date].groupby('시군구')[['총 청구계량기수', '가스레인지 연결 전수']].sum().reset_index()
        df_latest['인덕션_전환율'] = (1 - df_latest['가스레인지 연결 전수'] / df_latest['총 청구계량기수']) * 100
        
        fig4 = px.bar(df_latest.sort_values('인덕션_전환율', ascending=False), x='시군구', y='인덕션_전환율', color='인덕션_전환율', title="지역별 위험도 순위")
        st.plotly_chart(fig4, use_container_width=True)

    # [Tab 4] 유형별 비교
    with tab4:
        st.subheader("공동주택 vs 단독주택")
        df_type = df.groupby(['Date', '용도'])[['총 청구계량기수', '가스레인지 연결 전수']].sum().reset_index()
        df_type['전환율'] = (1 - df_type['가스레인지 연결 전수'] / df_type['총 청구계량기수']) * 100
        fig5 = px.line(df_type, x='Date', y='전환율', color='용도', title="주택 용도별 이탈 가속화 비교")
        st.plotly_chart(fig5, use_container_width=True)

else:
    st.info("👈 왼쪽 사이드바에서 CSV 파일을 업로드해주세요.")
