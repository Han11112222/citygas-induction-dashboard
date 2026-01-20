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
    [형님 요청 반영] 전체 도시가스 판매량 데이터 로드
    1. '실적_부피' 시트 사용
    2. 가정용(4개) + 업무/산업용 등(나머지) = 전체 판매량 합산
    3. 단위 보정 (천m³ -> m³)
    """
    try:
        # 1. '실적_부피' 시트 로드
        df = pd.read_excel(url, engine='openpyxl', sheet_name='실적_부피')
        
        # 2. 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(' ', '').str.strip()
        
        # 3. 날짜 및 연도 처리
        if '연' in df.columns and '월' in df.columns:
             df['Year'] = pd.to_numeric(df['연'], errors='coerce').fillna(0).astype(int)
             df['Date'] = pd.to_datetime(df['Year'].astype(str) + df['월'].astype(str).str.zfill(2) + '01', errors='coerce')
        
        # 4. [핵심] 전체 판매량 합산 대상 컬럼 정의 (소계~주한미군 포함 개념)
        # 가정용 4개
        household_cols = ['취사용', '개별난방용', '중앙난방용', '자가열전용']
        # 기타 용도 (파일에 있는 나머지 실적 컬럼들)
        other_cols = ['일반용', '업무난방용', '냉방용', '산업용', '수송용(CNG)', '수송용(BIO)', '열병합용', '연료전지용', '열전용설비용', '주한미군']
        
        all_target_cols = household_cols + other_cols
        
        # 5. 숫자 변환 (쉼표 제거 및 에러 방지)
        for col in all_target_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0 # 컬럼 없으면 0
        
        # 6. [핵심] 전체 합산 -> '전체_판매량'
        # 7. [단위 보정] x 1000 (천m³ -> m³)
        df['전체_판매량'] = df[all_target_cols].sum(axis=1) * 1000
        
        # 데이터 리턴
        return df[['Year', 'Date', '전체_판매량']]
             
    except Exception as e:
        st.error(f"⚠️ 판매량 엑셀 파일 로드 중 오류 발생: {e}") 
        return pd.DataFrame()

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 (형님 요청 반영) ---
COLOR_GAS = '#1f77b4'       # 진한 파랑 (전체 판매량 - 바닥)
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
    with st.expander("✅ 판매량 데이터(전체) 로드 확인 (단위: m³)"):
        st.write("아래는 [가정용+산업용+업무용+...] 전체 합계(m³ 환산) 결과입니다.")
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
    
    # [수정] 2017년부터 표시 + 소수점 1자리 + 첫번째 줄(인덱스) 숨김
    df_m_filtered = df_m[df_m['Date'].dt.year >= 2017].copy()
    st.dataframe(
        df_m_filtered.style.format({
            '전환율': '{:.1f}%',  # 소수점 1자리
            '총청구계량기수': '{:,.0f}',
            '가스레인지연결전수': '{:,.0f}',
            '인덕션_추정_수': '{:,.0f}'
        }), 
        use_container_width=True,
        hide_index=True  # 첫번째 줄(인덱스) 삭제 효과
    )
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
            max_value=100.0, 
            value=10.0, 
            step=0.5
        )
    # ---------------------------------------
    
    # 1. 연도별 인덕션 수량 집계
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_year['Year'] = df_year['Year'].astype(int)
    df_year['전환율'] = (df_year['인덕션_추정_수'] / df_year['총청구계량기수']) * 100
    
    # 2. [핵심] 전체 판매량 데이터 병합 (단위: m³)
    actual_sales_col = '전체_판매량'
    
    if not df_sales_raw.empty:
        # 판매량 데이터도 연도별로 합산
        df_sales_raw['Year'] = df_sales_raw['Year'].astype(int)
        df_sales_year = df_sales_raw.groupby('Year')[actual_sales_col].sum().reset_index()
        
        # 병합 (Year 기준)
        df_year = pd.merge(df_year, df_sales_year, on='Year', how='left')
        df_year[actual_sales_col] = df_year[actual_sales_col].fillna(0)
    else:
        df_year[actual_sales_col] = 0

    # 3. 손실 추정량 계산 (단위: m³)
    df['월별손실추정'] = df['인덕션_추정_수'] * input_pph
    df_loss_year = df.groupby('Year')['월별손실추정'].sum().reset_index()
    df_loss_year['Year'] = df_loss_year['Year'].astype(int)
    
    df_year = pd.merge(df_year, df_loss_year, on='Year', how='left')
    
    # 4. 손실 점유율 계산 (전체판매량 대비 손실 비중)
    df_year['잠재총사용량'] = df_year[actual_sales_col] + df_year['월별손실추정']
    df_year['손실점유율'] = df_year.apply(
        lambda x: (x['월별손실추정'] / x['잠재총사용량'] * 100) if x['잠재총사용량'] > 0 else 0, 
        axis=1
    )
    
    # 5. [필터링] 2017년 이후 데이터만 (판매량 있는 구간)
    df_year_filtered = df_year[df_year['Year'] >= 2017].copy()
    
    col1, col2 = st.columns(2)
    
    # (좌) 연도별 수량 + 비율
    with col1:
        fig_q = make_subplots(specs=[[{"secondary_y": True}]])
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['가스레인지연결전수'], name='가스레인지(누적)', marker_color=COLOR_GAS), secondary_y=False)
        fig_q.add_trace(go.Bar(x=df_year['Year'], y=df_year['인덕션_추정_수'], name='인덕션(누적)', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_q.add_trace(go.Scatter(x=df_year['Year'], y=df_year['전환율'], name='전환율(%)', mode='lines+markers+text', 
                                   text=df_year['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center', 
                                   line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_q.update_layout(title="연도별 세대 구성(월합계) 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_q.update_yaxes(title_text="연간 누적 세대수", secondary_y=False)
        fig_q.update_yaxes(title_text="전환율(%)", secondary_y=True, range=[0, df_year['전환율'].max()*1.2])
        st.plotly_chart(fig_q, use_container_width=True)

    # (우) 연도별 전체 판매량 vs 손실량 (2017년부터)
    with col2:
        fig_u = make_subplots(specs=[[{"secondary_y": True}]])
        
        # [핵심] 바닥: 전체 판매량 (진한 파랑)
        fig_u.add_trace(go.Bar(
            x=df_year_filtered['Year'], 
            y=df_year_filtered[actual_sales_col], 
            name='전체 판매량(가정+산업 등)', 
            marker_color=COLOR_GAS
        ), secondary_y=False)
        
        # [핵심] 위: 손실 추정량 (연한 하늘색)
        fig_u.add_trace(go.Bar(
            x=df_year_filtered['Year'], 
            y=df_year_filtered['월별손실추정'], 
            name='손실 추정량(이탈분)', 
            marker_color=COLOR_INDUCTION
        ), secondary_y=False)
        
        # 선: 손실 비중
        fig_u.add_trace(go.Scatter(
            x=df_year_filtered['Year'], y=df_year_filtered['손실점유율'],
            mode='lines+markers+text',
            text=df_year_filtered['손실점유율'].apply(lambda x: f"{x:.1f}%"),
            textposition="top center",
            name='손실 비중(%)',
            line=dict(color=COLOR_LINE, width=3)
        ), secondary_y=True)
        
        fig_u.update_layout(title=f"전체 판매량 vs 손실 추정량 (2017년~, 세대당 {input_pph}m³ 기준)", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_u.update_yaxes(title_text="사용량(m³)", secondary_y=False)
        fig_u.update_yaxes(title_text="손실 비중(%)", secondary_y=True, range=[0, df_year_filtered['손실점유율'].max()*1.5])
        st.plotly_chart(fig_u, use_container_width=True)
    
    # [수정] 테이블 포맷팅 (소수점 1자리, 인덱스 숨김)
    st.dataframe(
        df_year_filtered.style.format({
            '전환율': '{:.1f}%',
            '손실점유율': '{:.1f}%',
            '총청구계량기수': '{:,.0f}',
            actual_sales_col: '{:,.0f}',
            '월별손실추정': '{:,.0f}'
        }), 
        use_container_width=True,
        hide_index=True
    )
    st.download_button("📥 연도별 데이터 다운로드", convert_df(df_year_filtered), "연도별_상세.csv", "text/csv")

    st.divider()

    # [3] Drill-down Step 1: 연도 선택 -> 구군 비교
    st.subheader("3️⃣ 상세 분석: 연도 선택 ➡️ 구군별 비교")
    
    sel_year = st.selectbox("📅 분석할 연도를 선택하세요:", sorted(df['Year'].unique(), reverse=True))
    
    df_gu = df[df['Year'] == sel_year].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_gu['전환율'] = (df_gu['인덕션_추정_수'] / df_gu['총청구계량기수']) * 100
    
    c3, c4 = st.columns(2)
    
    with c3:
        fig_gu1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_gu1.add_trace(go.Scatter(x=df_gu['시군구'], y=df_gu['전환율'], name='전환율(%)', mode='lines+markers+text',
                                     text=df_gu['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                     line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_gu1.update_layout(title=f"[{sel_year}년] 구군별 세대 구성 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_gu1, use_container_width=True)

    with c4:
        df_gu_sort = df_gu.sort_values(by='인덕션_추정_수', ascending=False)
        fig_gu2 = px.bar(df_gu_sort, x='시군구', y='인덕션_추정_수', text_auto='.2s', 
                         title=f"[{sel_year}년] 구군별 인덕션 도입 수량 순위", 
                         color='인덕션_추정_수', color_continuous_scale='Blues')
        st.plotly_chart(fig_gu2, use_container_width=True)

    st.dataframe(df_gu.style.format({'전환율': '{:.1f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}'}), use_container_width=True, hide_index=True)
    st.download_button(f"📥 {sel_year}_구군별_다운로드", convert_df(df_gu), f"{sel_year}_구군별.csv", "text/csv")

    st.divider()

    # [4] Drill-down Step 2: 지역 선택 -> 연도별 흐름
    st.subheader("4️⃣ 상세 분석: 지역(구군) 선택 ➡️ 연도별 흐름")
    
    sel_region = st.selectbox("🏙️ 지역(구군)을 선택하세요:", sorted(df['시군구'].unique()))
    
    df_r_sub = df[df['시군구'] == sel_region].copy()
    
    # 손실량 계산 (월별 합산) -> 인덕션 추정 수 * PPH
    df_r_sub['월별손실추정'] = df_r_sub['인덕션_추정_수'] * input_pph
    
    df_r = df_r_sub.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '월별손실추정']].sum().reset_index()
    df_r['전환율'] = (df_r['인덕션_추정_수'] / df_r['총청구계량기수']) * 100
    
    c5, c6 = st.columns(2)
    
    with c5:
        fig_r1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_r1.add_trace(go.Scatter(x=df_r['Year'], y=df_r['전환율'], name='전환율(%)', mode='lines+markers+text',
                                    text=df_r['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_r1.update_layout(title=f"[{sel_region}] 연도별 세대 구성 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_r1, use_container_width=True)
    
    with c6:
        # [수정] 4번 상세분석: 전사 전체 판매량 vs 해당 지역 손실 추정량 비교
        # 판매량은 전사 데이터만 있으므로 이를 배경(참조)으로 깔고, 해당 지역 손실량을 보여줍니다.
        # 단, 스케일 차이가 클 수 있으므로 2축을 사용하거나 별도로 표시합니다.
        # 여기서는 형님 요청대로 "전체 판매량과 손실 추정량 그래프"를 추가합니다.
        
        fig_r2 = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 전체 판매량 (전사 기준) - 참조용
        fig_r2.add_trace(go.Bar(
            x=df_year_filtered['Year'], 
            y=df_year_filtered[actual_sales_col], 
            name='전사 전체 판매량(참조)', 
            marker_color='#e0e0e0', # 회색으로 배경 처리
            opacity=0.5
        ), secondary_y=False)
        
        # 해당 지역 손실 추정량
        fig_r2.add_trace(go.Bar(
            x=df_r['Year'], 
            y=df_r['월별손실추정'], 
            name=f'{sel_region} 손실 추정량', 
            marker_color=COLOR_INDUCTION,
            text=df_r['월별손실추정'].apply(lambda x: f"{x:,.0f}"),
            textposition='auto'
        ), secondary_y=True) # 스케일이 다르므로 보조축 사용
        
        fig_r2.update_layout(
            title=f"[{sel_region}] 손실 추정량 (vs 전사 전체 판매량)", 
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(title='전사 판매량 (m³)'),
            yaxis2=dict(title='지역 손실량 (m³)', overlaying='y', side='right')
        )
        st.plotly_chart(fig_r2, use_container_width=True)

    st.dataframe(df_r.style.format("{:,.0f}"), use_container_width=True, hide_index=True)
    st.download_button(f"📥 {sel_region}_데이터 다운로드", convert_df(df_r), f"{sel_region}_데이터.csv", "text/csv")


# =========================================================
# [MENU 2~4] 기존 차트 유지
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
