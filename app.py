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
def load_sales_data(url):
    """
    [수정됨] 가정용 판매량 데이터 로드
    - 시트 이름을 유연하게 찾음 ('실적_부피'가 포함된 시트 우선)
    - ['취사용', '개별난방용', '중앙난방용', '자가열전용'] 4개 항목 직접 합산
    """
    try:
        # 1. 엑셀 파일 객체 로드 (시트 이름 확인용)
        xls = pd.ExcelFile(url, engine='openpyxl')
        
        # 2. 시트 찾기 ('실적'과 '부피'가 들어간 시트 우선)
        target_sheet = None
        for sheet in xls.sheet_names:
            if '실적' in sheet and '부피' in sheet:
                target_sheet = sheet
                break
        
        # 없으면 첫 번째 시트 사용
        if target_sheet is None:
            target_sheet = xls.sheet_names[0]
            # st.warning(f"⚠️ '실적_부피' 시트를 못 찾아 '{target_sheet}' 시트를 사용합니다.")

        # 3. 데이터 읽기
        df = pd.read_excel(url, sheet_name=target_sheet, engine='openpyxl')
        
        # 4. 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        # 5. 날짜 및 연도 처리
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # 6. 합산할 4개 항목 정의
        target_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        
        # 7. 숫자 변환 (쉼표 제거 및 에러 방지)
        for col in target_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # 8. [핵심] 4개 항목 직접 합산 -> '가정용_판매량_전체' (단위 보정 x 1000)
        df['가정용_판매량_전체'] = df[target_cols].sum(axis=1) * 1000
        
        # 데이터 리턴
        return df[['Year', 'Date', '가정용_판매량_전체']]
             
    except Exception as e:
        st.error(f"⚠️ 판매량 엑셀 파일 로드 중 오류 발생: {e}") 
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 (형님 요청 반영) ---
COLOR_GAS = '#1f77b4'       # 진한 파랑 (실제 판매량 - 바닥)
COLOR_INDUCTION = '#a4c2f4' # 연한 하늘색 (손실 추정량 - 위)
COLOR_LINE = '#d62728'      # 빨강 (비율/전환율/손실율)

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성
# ---------------------------------------------------------
gas_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
sales_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/판매량(계획_실적).xlsx"

df_raw = load_data_from_github(gas_url)
df_sales_raw = load_sales_data(sales_url)

if df_raw.empty:
    st.stop()

# 대제목
st.title("🔥 인덕션 전환 추세 분석")

# [데이터 로드 확인]
if not df_sales_raw.empty:
    with st.expander("✅ 판매량 데이터 로드 확인 (단위: m³)"):
        st.write("아래는 [취사용+개별+중앙+자가열] 합계에 **1000을 곱한(m³ 환산)** 결과입니다.")
        # 최근 2025년 데이터만 필터링해서 보여줌
        check_df = df_sales_raw[df_sales_raw['Year'] >= 2024].sort_values('Date', ascending=False).head(5)
        st.dataframe(check_df, use_container_width=True)
else:
    st.error("🚨 판매량 데이터를 불러오지 못했습니다. Github URL을 확인해주세요.")

with st.sidebar:
    st.header("🔥 분석 메뉴")
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
    
    st.dataframe(df_m.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.divider()

    # [2] 연도별 수량 및 손실량
    st.subheader("2️⃣ 연도별 수량 및 손실 추정량 분석")
    
    pph_col1, pph_col2 = st.columns([3, 1])
    
    with pph_col1:
        st.info("""
        ##### 📘 인덕션 전환 추정근거
        1. **추정 인덕션 세대수** = 가정용 총 청구 계량기수 − 가스렌지연결 청구 계량기수
        2. **추정 사용량 감소** = 추정 인덕션 세대수 × 3y평균 취사용 사용량 (우측 입력값 적용)
        
        ※ '세대당 월평균 가스 사용량'은 난방을 제외한 **순수 취사 전용 사용량**을 의미합니다.
        """)
        
    with pph_col2:
        input_pph = st.number_input(
            "🔻 적용할 세대당 월평균 가스 사용량 (m³)", 
            min_value=0.0,
