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
        # [수정] URL 따옴표 추가하여 에러 해결
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
        # 개별 행에 대한 전환율 계산
        df['인덕션_전환율'] = df.apply(lambda x: (x['인덕션_추정_수']/x['총청구계량기수']*100) if x['총청구계량기수']>0 else 0, axis=1)
    
    # [연도 정수형 변환]
    df['Year'] = df['Date'].dt.year.astype(int)

    return df

@st.cache_data(ttl=60)
def load_sales_data():
    """
    [판매량 데이터 로드]
    단위: 천m³ -> m³ (* 1000)
    """
    # [수정] URL 따옴표 추가
    url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/%ED%8C%90%EB%A7%A4%EB%9F%89(%EA%B3%84%ED%9A%8D_%EC%8B%A4%EC%A0%81).xlsx"
    
    try:
        df = pd.read_excel(url, engine='openpyxl', sheet_name='실적_부피')
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # 합산 대상 컬럼
        household_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        other_cols = ['일반용', '업무난방용', '냉방용', '산업용', '수송용(CNG)', '수송용(BIO)', '열병합용', '연료전지용', '열전용설비용', '주한미군']
        all_cols = household_cols + other_cols
        
        # 숫자 변환
        for col in all_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0
        
        # [단위 보정] 천m³ -> m³ (무조건 * 1000)
        df['가정용_판매량_전체'] = df[household_cols].sum(axis=1) * 1000
        df['기타_판매량_전체'] = df[other_cols].sum(axis=1) * 1000
        df['전체_판매량'] = df['가정용_판매량_전체'] + df['기타_판매량_전체']
        
        return df[['Year', 'Date', '가정용_판매량_전체', '전체_판매량']]
             
    except Exception as e:
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 ---
COLOR_GAS = '#1f77b4'       # 진한 파랑 (판매량)
COLOR_INDUCTION = '#a4c2f4' # 연한 하늘색 (손실량)
COLOR_LINE = '#d62728'      # 빨강 (비율)

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성
# ---------------------------------------------------------
gas_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"

df_raw = load_data_from_github(gas_url)
df_sales_raw = load_sales_data()

if df_raw.empty:
    st.error("🚨 기본 데이터 로드 실패. 잠시 후 다시 시도해주세요.")
    st.stop()

# 대제목
st.title("🔥 인덕션 전환 추세 분석")

# [데이터 로드 확인창]
if not df_sales_raw.empty:
    with st.expander("✅ 판매량 데이터 로드 확인 (단위: m³로 변환됨)"):
        st.write("아래 수치는 **천m³ 단위에 1,000을 곱하여 m³로 변환된** 결과입니다.")
        check_df = df_sales_raw[df_sales_raw['Year'] >= 2024].sort_values('Date', ascending=False).head(5)
        st.dataframe(check_df, use_container_width=True)
else:
    st.warning("⚠️ 판매량 데이터를 불러오는 중입니다.")

with st.sidebar:
    st.header("🔥 분석 메뉴")
    selected_menu = st.radio(
        "분석 메뉴 선택",
        ["1. 전환 추세 및 상세 분석 (Ver 2.0)", "2. 판매량 영향 분석", "3. 지역별 위험도 순위", "4. 주택 유형별 비교"]
    )
    
    st.markdown("---")
    st.header("🔍 데이터 필터")
    
    # [형님 요청] PPH 입력
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
# [MENU 1] 전환 추세 및 상세 분석 (Ver 2.0 로직 적용)
# =========================================================
if selected_menu == "1. 전환 추세 및 상세 분석 (Ver 2.0)":
    
    # 설명 추가
    st.info("""
    💡 **분석 기준 (Ver 2.0):**
    1. **세대수(Stock):** 누적 오류를 방지하기 위해 매년 **'12월(연말) 데이터'**를 기준으로 합니다.
    2. **손실량(Flow):** 12월 기준 인덕션 세대수에 **PPH**와 **12개월**을 곱하여 **'연간 총 손실량'**을 추정합니다.
    """)

    # -------------------------------------------------------------
    # [1] 데이터 전처리 (12월 기준 집계 + 연간 손실량 계산)
    # -------------------------------------------------------------
    
    # 1. 12월 데이터만 필터링 (Stock Data: 세대수)
    df_dec = df[df['Date'].dt.month == 12].copy()
    
    # 2. 데이터 집계 (세대수: 12월 기준)
    df_ver2_stock = df_dec.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_ver2_stock['Year'] = df_ver2_stock['Year'].astype(int)
    df_ver2_stock['전환율'] = (df_ver2_stock['인덕션_추정_수'] / df_ver2_stock['총청구계량기수']) * 100
    
    # 3. [핵심] 연간 총 손실량 계산 (12월 기준 인덕션 수 * PPH * 12개월)
    df_ver2_stock['연간손실추정_m3'] = df_ver2_stock['인덕션_추정_수'] * input_pph * 12
    
    # 4. 판매량 데이터 (전체 월 합계 - 기존 로직)
    if not df_sales_raw.empty:
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[['가정용_판매량_전체', '전체_판매량']].sum().reset_index()
    else:
        df_sales_year = pd.DataFrame(columns=['Year', '가정용_판매량_전체', '전체_판매량'])

    # 5. 병합 (Stock + Flow)
    df_ver2 = pd.merge(df_ver2_stock, df_sales_year, on='Year', how='left')
    
    if not df_sales_year.empty:
        df_ver2['가정용_판매량_전체'] = df_ver2['가정용_판매량_전체'].fillna(0)
        df_ver2['전체_판매량'] = df_ver2['전체_판매량'].fillna(0)
    else:
        df_ver2['가정용_판매량_전체'] = 0
        df_ver2['전체_판매량'] = 0
        
    # 점유율 계산 (연간 총량 기준)
    df_ver2['잠재_가정용'] = df_ver2['가정용_판매량_전체'] + df_ver2['연간손실추정_m3']
    df_ver2['손실점유율_가정'] = df_ver2.apply(lambda x: (x['연간손실추정_m3'] / x['잠재_가정용'] * 100) if x['잠재_가정용'] > 0 else 0, axis=1)

    # 필터링 (2017~)
    df_ver2_filtered = df_ver2[df_ver2['Year'] >= 2017].copy()
    
    # 하이라이트 조건 (전환율 10% 돌파 시점부터 끝까지)
    highlight_condition = df_ver2_filtered['전환율'] > 10.0
    start_highlight_year = df_ver2_filtered.loc[highlight_condition, 'Year'].min() if highlight_condition.any() else None
    end_highlight_year = df_ver2_filtered['Year'].max()

    # -------------------------------------------------------------
    # [2] 그래프 그리기 (좌우 배치)
    # -------------------------------------------------------------
    col_left, col_right = st.columns(2)
    
    # (좌) 세대 구성 및 전환율 (12월 기준)
    with col_left:
        st.markdown("##### 1️⃣ 연도별 세대 구성 (12월 기준) 및 전환율")
        fig_q = make_subplots(specs=[[{"secondary_y": True}]])
        fig_q.add_trace(go.Bar(x=df_ver2['Year'], y=df_ver2['가스레인지연결전수'], name='가스레인지(12월)', marker_color=COLOR_GAS), secondary_y=False)
        fig_q.add_trace(go.Bar(x=df_ver2['Year'], y=df_ver2['인덕션_추정_수'], name='인덕션(12월)', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_q.add_trace(go.Scatter(x=df_ver2['Year'], y=df_ver2['전환율'], name='전환율(%)', mode='lines+markers+text', 
                                   text=df_ver2['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center', 
                                   line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        
        # [하이라이트] 10% 이상부터 끝까지
        if start_highlight_year:
            fig_q.add_vrect(x0=start_highlight_year-0.5, x1=end_highlight_year+0.5, 
                            fillcolor="yellow", opacity=0.15, layer="below", line_width=0,
                            annotation_text="🚀10% 돌파", annotation_position="top left")

        fig_q.update_layout(barmode='stack', legend=dict(orientation="h", y=1.1), height=500, hovermode="x unified")
        fig_q.update_yaxes(title_text="세대수 (12월 기준)", secondary_y=False)
        fig_q.update_yaxes(title_text="전환율 (%)", secondary_y=True, range=[0, df_ver2['전환율'].max()*1.2])
        st.plotly_chart(fig_q, use_container_width=True)

    # (우) 연간 손실 추정량 및 비중
    with col_right:
        st.markdown("##### 2️⃣ 연도별 추정 손실량 및 비중 (단위: m³, %)")
        fig_loss = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 1축: 손실량 (막대)
        fig_loss.add_trace(go.Bar(
            x=df_ver2_filtered['Year'],
            y=df_ver2_filtered['연간손실추정_m3'],
            name='연간 손실량(m³)',
            marker_color=COLOR_INDUCTION,
            text=df_ver2_filtered['연간손실추정_m3'].apply(lambda x: f"{x:,.0f}"),
            textposition='auto'
        ), secondary_y=False)
        
        # 2축: 손실 비중 (선)
        fig_loss.add_trace(go.Scatter(
            x=df_ver2_filtered['Year'],
            y=df_ver2_filtered['손실점유율_가정'],
            name='손실 비중(%)',
            mode='lines+markers+text',
            text=df_ver2_filtered['손실점유율_가정'].apply(lambda x: f"{x:.2f}%"),
            textposition='top center',
            line=dict(color=COLOR_LINE, width=3)
        ), secondary_y=True)

        fig_loss.update_layout(height=500, legend=dict(orientation="h", y=1.1), hovermode="x unified")
        fig_loss.update_yaxes(title_text="연간 손실량 (m³)", secondary_y=False)
        fig_loss.update_yaxes(title_text="가정용 대비 비중 (%)", secondary_y=True, range=[0, df_ver2_filtered['손실점유율_가정'].max()*1.2])
        st.plotly_chart(fig_loss, use_container_width=True)

    st.divider()
    
    # 상세 데이터 표
    st.dataframe(
        df_ver2_filtered.style.format({
            '전환율': '{:.1f}%',
            '손실점유율_가정': '{:.2f}%',
            '총청구계량기수': '{:,.0f}',
            '가스레인지연결전수': '{:,.0f}',
            '인덕션_추정_수': '{:,.0f}',
            '가정용_판매량_전체': '{:,.0f}',
            '전체_판매량': '{:,.0f}',
            '연간손실추정_m3': '{:,.0f}',
            '잠재_가정용': '{:,.0f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    st.download_button("📥 상세 데이터 다운로드", convert_df(df_ver2_filtered), "Ver2_데이터.csv", "text/csv")


# =========================================================
# [MENU 2~4] 기존 차트 유지 (2, 3, 4번 등)
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
        st.download_button("📥 PPH 데이터 다운로드", convert_df(df_s), "PPH_데이터.csv", "text/csv")
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
    st.download_button("📥 순위 데이터 다운로드", convert_df(df_l), "지역별_순위.csv", "text/csv")

elif selected_menu == "4. 주택 유형별 비교":
    st.markdown("#### 🏢 공동주택(APT) vs 단독주택 패턴 비교")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    st.dataframe(df_pivot.style.format("{:.1f}%", subset=df_pivot.columns[1:]), use_container_width=True, hide_index=True)
    st.download_button("📥 유형별 데이터 다운로드", convert_df(df_pivot), "유형별_비교.csv", "text/csv")
