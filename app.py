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
    
    df['Year'] = df['Date'].dt.year

    return df

@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- [디자인] 컬러 팔레트 ---
COLOR_GAS = '#1f77b4'      # 진한 파랑 (가스레인지 / 실제 판매량)
COLOR_INDUCTION = '#a4c2f4' # 연한 하늘색 (인덕션 / 손실 추정량)
COLOR_LINE = '#d62728'     # 빨강 (비율/전환율/손실율)

# ---------------------------------------------------------
# 3. 데이터 로드 및 사이드바 구성
# ---------------------------------------------------------
github_url = "https://raw.githubusercontent.com/Han11112222/citygas-induction-dashboard/main/(ver4)%EA%B0%80%EC%A0%95%EC%9A%A9_%EA%B0%80%EC%8A%A4%EB%A0%88%EC%9D%B8%EC%A7%80_%EC%82%AC%EC%9A%A9%EC%9C%A0%EB%AC%B4(201501_202412).xlsx"
df_raw = load_data_from_github(github_url)

if df_raw.empty:
    st.stop()

with st.sidebar:
    st.title("🔥 분석 대시보드")
    
    # 메뉴 선택
    selected_menu = st.radio(
        "분석 메뉴 선택",
        ["1. 전환 추세 및 상세 분석", "2. 판매량 영향 분석", "3. 지역별 위험도 순위", "4. 주택 유형별 비교"]
    )
    
    st.markdown("---")
    st.header("🍳 취사 PPH 설정")
    st.info("※ 10m³는 임의 추정값입니다. 실제 8월(하절기) 평균 사용량 등을 참고하여 입력해주세요.")
    
    # PPH 입력 위젯
    input_pph = st.number_input(
        "세대당 월평균 취사량 (m³)", 
        min_value=0.0, 
        max_value=100.0, 
        value=10.0, 
        step=0.5
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

st.header(f"📊 {selected_menu}")

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
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("###### 📋 월별 상세 데이터")
    st.dataframe(df_m.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 월별 데이터 다운로드", convert_df(df_m), "월별_데이터.csv", "text/csv")

    st.divider()

    # [2] 연도별 수량 및 손실량
    st.subheader("2️⃣ 연도별 수량 및 손실 추정량 분석")
    st.info(f"💡 **적용된 취사 PPH:** {input_pph}m³")
    
    df_year = df.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)']].sum().reset_index()
    df_year['전환율'] = (df_year['인덕션_추정_수'] / df_year['총청구계량기수']) * 100
    
    # 손실량 및 손실률 계산
    # df_year 데이터는 '월별 합계'이므로, 단순히 (연간 총 인덕션 추정 수 * PPH)를 하면 과대계상될 수 있습니다.
    # 정확한 '연간 손실량' = (월별 인덕션 수 * PPH)의 합계입니다.
    # 따라서 원본 df에서 계산 후 합칩니다.
    
    df['월별손실추정'] = df['인덕션_추정_수'] * input_pph
    df_loss_year = df.groupby('Year')['월별손실추정'].sum().reset_index()
    df_year = pd.merge(df_year, df_loss_year, on='Year')
    
    # 손실 점유율(%) 계산 = 손실량 / (실제사용량 + 손실량) * 100
    df_year['잠재총사용량'] = df_year['사용량(m3)'] + df_year['월별손실추정']
    df_year['손실점유율'] = (df_year['월별손실추정'] / df_year['잠재총사용량']) * 100
    
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

    # (우) 연도별 사용량 + 손실량 + 손실점유율(%) [요청사항 반영]
    with col2:
        fig_u = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 막대 1: 실제 판매량
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['사용량(m3)'], name='실제 판매량', marker_color=COLOR_GAS), secondary_y=False)
        # 막대 2: 손실 추정량
        fig_u.add_trace(go.Bar(x=df_year['Year'], y=df_year['월별손실추정'], name='손실 추정량(이탈분)', marker_color=COLOR_INDUCTION), secondary_y=False)
        
        # 선: 손실 점유율(%)
        fig_u.add_trace(go.Scatter(
            x=df_year['Year'], y=df_year['손실점유율'],
            mode='lines+markers+text',
            text=df_year['손실점유율'].apply(lambda x: f"{x:.1f}%"),
            textposition="top center",
            name='손실 비중(%)',
            line=dict(color=COLOR_LINE, width=3)
        ), secondary_y=True)
        
        fig_u.update_layout(title=f"실제 판매량 vs 손실 추정량 (손실 비중%)", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_u.update_yaxes(title_text="사용량(m³)", secondary_y=False)
        fig_u.update_yaxes(title_text="손실 비중(%)", secondary_y=True, range=[0, df_year['손실점유율'].max()*1.5]) # 범위 넉넉하게
        st.plotly_chart(fig_u, use_container_width=True)
    
    st.markdown("###### 📋 연도별 상세 데이터")
    st.dataframe(df_year.style.format("{:,.0f}"), use_container_width=True)
    st.download_button("📥 연도별 데이터 다운로드", convert_df(df_year), "연도별_상세.csv", "text/csv")

    st.divider()

    # [3] Drill-down Step 1: 연도 선택 -> 구군 비교
    st.subheader("3️⃣ 상세 분석: 연도 선택 ➡️ 구군별 비교")
    
    sel_year = st.selectbox("📅 분석할 연도를 선택하세요:", sorted(df['Year'].unique(), reverse=True))
    
    df_gu = df[df['Year'] == sel_year].groupby('시군구')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수']].sum().reset_index()
    df_gu['전환율'] = (df_gu['인덕션_추정_수'] / df_gu['총청구계량기수']) * 100
    
    c3, c4 = st.columns(2)
    
    # (좌) 구군별 구성 + 전환율
    with c3:
        fig_gu1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_gu1.add_trace(go.Bar(x=df_gu['시군구'], y=df_gu['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_gu1.add_trace(go.Scatter(x=df_gu['시군구'], y=df_gu['전환율'], name='전환율(%)', mode='lines+markers+text',
                                     text=df_gu['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                     line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_gu1.update_layout(title=f"[{sel_year}년] 구군별 세대 구성 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_gu1.update_yaxes(title_text="세대수", secondary_y=False)
        fig_gu1.update_yaxes(title_text="전환율(%)", secondary_y=True, range=[0, df_gu['전환율'].max()*1.2])
        st.plotly_chart(fig_gu1, use_container_width=True)

    # (우) 인덕션 수량 단독
    with c4:
        df_gu_sort = df_gu.sort_values(by='인덕션_추정_수', ascending=False)
        fig_gu2 = px.bar(df_gu_sort, x='시군구', y='인덕션_추정_수', text_auto='.2s', 
                         title=f"[{sel_year}년] 구군별 인덕션 도입 수량 순위", 
                         color='인덕션_추정_수', color_continuous_scale='Blues')
        st.plotly_chart(fig_gu2, use_container_width=True)

    st.markdown("###### 📋 구군별 상세 데이터")
    st.dataframe(df_gu.style.format({'전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}', '가스레인지연결전수': '{:,.0f}', '인덕션_추정_수': '{:,.0f}'}), use_container_width=True)
    st.download_button(f"📥 {sel_year}_구군별_다운로드", convert_df(df_gu), f"{sel_year}_구군별.csv", "text/csv")

    st.divider()

    # [4] Drill-down Step 2: 지역 선택 -> 연도별 흐름
    st.subheader("4️⃣ 상세 분석: 지역(구군) 선택 ➡️ 연도별 흐름")
    
    sel_region = st.selectbox("🏙️ 지역(구군)을 선택하세요:", sorted(df['시군구'].unique()))
    
    # 지역 필터링
    df_r_sub = df[df['시군구'] == sel_region]
    
    # 손실량 계산 (월별 합산)
    df_r_sub['월별손실추정'] = df_r_sub['인덕션_추정_수'] * input_pph
    
    df_r = df_r_sub.groupby('Year')[['총청구계량기수', '가스레인지연결전수', '인덕션_추정_수', '사용량(m3)', '월별손실추정']].sum().reset_index()
    df_r['전환율'] = (df_r['인덕션_추정_수'] / df_r['총청구계량기수']) * 100
    
    # 손실 점유율 계산
    df_r['잠재총사용량'] = df_r['사용량(m3)'] + df_r['월별손실추정']
    df_r['손실점유율'] = (df_r['월별손실추정'] / df_r['잠재총사용량']) * 100

    c5, c6 = st.columns(2)
    
    # (좌) 선택 지역: 연도별 구성 + 전환율
    with c5:
        fig_r1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['가스레인지연결전수'], name='가스레인지', marker_color=COLOR_GAS), secondary_y=False)
        fig_r1.add_trace(go.Bar(x=df_r['Year'], y=df_r['인덕션_추정_수'], name='인덕션', marker_color=COLOR_INDUCTION), secondary_y=False)
        fig_r1.add_trace(go.Scatter(x=df_r['Year'], y=df_r['전환율'], name='전환율(%)', mode='lines+markers+text',
                                    text=df_r['전환율'].apply(lambda x: f"{x:.1f}%"), textposition='top center',
                                    line=dict(color=COLOR_LINE, width=3)), secondary_y=True)
        fig_r1.update_layout(title=f"[{sel_region}] 연도별 세대 구성 및 전환율", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_r1.update_yaxes(title_text="세대수", secondary_y=False)
        fig_r1.update_yaxes(title_text="전환율(%)", secondary_y=True, range=[0, df_r['전환율'].max()*1.2])
        st.plotly_chart(fig_r1, use_container_width=True)
    
    # (우) 선택 지역: 사용량 + 손실량 + 손실비중(%)
    with c6:
        fig_r2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_r2.add_trace(go.Bar(x=df_r['Year'], y=df_r['사용량(m3)'], name='실제 사용량', marker_color=COLOR_GAS), secondary_y=False)
        fig_r2.add_trace(go.Bar(x=df_r['Year'], y=df_r['월별손실추정'], name='손실 추정량', marker_color=COLOR_INDUCTION), secondary_y=False)
        
        fig_r2.add_trace(go.Scatter(
            x=df_r['Year'], y=df_r['손실점유율'],
            mode='lines+markers+text',
            text=df_r['손실점유율'].apply(lambda x: f"{x:.1f}%"),
            textposition="top center",
            name='손실 비중(%)',
            line=dict(color=COLOR_LINE, width=3)
        ), secondary_y=True)

        fig_r2.update_layout(title=f"[{sel_region}] 실제 사용량 vs 손실 추정량", barmode='stack', legend=dict(orientation="h", y=-0.2))
        fig_r2.update_yaxes(title_text="사용량(m³)", secondary_y=False)
        fig_r2.update_yaxes(title_text="손실 비중(%)", secondary_y=True, range=[0, df_r['손실점유율'].max()*1.5])
        st.plotly_chart(fig_r2, use_container_width=True)

    st.markdown(f"###### 📋 [{sel_region}] 상세 데이터")
    st.dataframe(df_r.style.format("{:,.0f}"), use_container_width=True)
    st.download_button(f"📥 {sel_region}_데이터 다운로드", convert_df(df_r), f"{sel_region}_데이터.csv", "text/csv")


# =========================================================
# [MENU 2~4] 기존 차트 유지
# =========================================================
elif selected_menu == "2. 판매량 영향 분석":
    st.markdown("#### 📉 인덕션 전환율 vs 세대당 사용량(PPH)")
    
    st.info(f"⚠️ 주의: 아래 산점도의 '세대당 사용량'은 데이터에 있는 **전체 사용량(난방 포함)**을 기준으로 합니다. (입력하신 취사 PPH {input_pph}와 다름)")
    
    df['Real_PPH'] = df.apply(lambda x: (x['사용량(m3)']/x['가스레인지연결전수']) if x['가스레인지연결전수']>0 else 0, axis=1)
    df_s = df.groupby(['시군구', 'Date'])[['인덕션_전환율', 'Real_PPH']].mean().reset_index().dropna()
    
    if not df_s.empty:
        fig2 = px.scatter(df_s, x='인덕션_전환율', y='Real_PPH', color='시군구', trendline="ols",
                          labels={'Real_PPH': '세대당 총 사용량(m³)'})
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(df_s.style.format({'인덕션_전환율': '{:.2f}%', 'Real_PPH': '{:.2f} m3'}), use_container_width=True)
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
    st.dataframe(df_l.style.format({'인덕션_전환율': '{:.2f}%', '총청구계량기수': '{:,.0f}'}), use_container_width=True)
    st.download_button("📥 순위 데이터 다운로드", convert_df(df_l), "지역별_순위.csv", "text/csv")

elif selected_menu == "4. 주택 유형별 비교":
    st.markdown("#### 🏢 공동주택(APT) vs 단독주택 패턴 비교")
    df_t = df.groupby(['Date', '용도'])[['총청구계량기수', '가스레인지연결전수']].sum().reset_index()
    df_t['전환율'] = (1 - df_t['가스레인지연결전수'] / df_t['총청구계량기수']) * 100
    
    fig4 = px.line(df_t, x='Date', y='전환율', color='용도', markers=True)
    st.plotly_chart(fig4, use_container_width=True)
    
    df_pivot = df_t.pivot(index='Date', columns='용도', values='전환율').reset_index()
    st.dataframe(df_pivot.style.format("{:.2f}%", subset=df_pivot.columns[1:]), use_container_width=True)
    st.download_button("📥 유형별 데이터 다운로드", convert_df(df_pivot), "유형별_비교.csv", "text/csv")
