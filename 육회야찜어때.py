import pandas as pd
import streamlit as st
import plotly.express as px
import datetime

# --- 1. 데이터 로드 및 전처리 ---
@st.cache_data
def load_data(url):
    csv_url = url.split('/edit')[0] + "/export?format=csv&gid=1085060193"
    try:
        df = pd.read_csv(csv_url, encoding='utf-8-sig')
    except:
        df = pd.read_csv(csv_url, encoding='cp949')
    
    df['주문금액'] = pd.to_numeric(df['주문금액'].astype(str).str.replace(r'[^\d]', '', regex=True), errors='coerce').fillna(0).astype(int)
    df = df[~df.astype(str).apply(lambda x: x.str.contains('취소')).any(axis=1)].copy()
    
    df['datetime'] = pd.to_datetime(df['일자'].str.split(' ').str[0] + ' ' + df['시간'], format='%y/%m/%d %H:%M', errors='coerce')
    df['연도'] = df['datetime'].dt.strftime('%y')
    df['날짜_date'] = df['datetime'].dt.date
    df['요일'] = df['일자'].str.extract(r'\((.*?)\)')
    df['영업시간대_라벨'] = df['datetime'].dt.hour.apply(lambda x: f"{x}시" if x >= 10 else f"익일 {x}시")
    return df

df = load_data("https://docs.google.com/spreadsheets/d/1zzNCiYyGO3BPCxEBScxxlfHmpN72a-_XCYEnx7TFTS8/edit?gid=1085060193#gid=1085060193")

# --- 2. 사이드바 구성 ---
st.set_page_config(layout="wide")
st.title('📊 매출 분석 대시보드')

st.sidebar.header('🔍 필터링 설정')

# 날짜 From-To
col_f, col_t = st.sidebar.columns(2)
s_date = col_f.date_input("① 시작일", st.session_state.get('start_dt', df['날짜_date'].min()), format="YYYY/MM/DD")
e_date = col_t.date_input("② 종료일", st.session_state.get('end_dt', df['날짜_date'].max()), format="YYYY/MM/DD")

# [수정된 배치] 연도/월 세로 배치 및 옆에 긴 적용 버튼 배치
st.sidebar.markdown("---")
row1, row2 = st.sidebar.columns([3, 1])

with row1:
    y_options = sorted(df['연도'].unique(), reverse=True)
    # format_func을 사용하여 선택지에 '20xx년' 식으로 표시
    y_sel = st.selectbox("연도", y_options, format_func=lambda x: f"20{x}년")
    m_sel = st.selectbox("월", range(1, 13), format_func=lambda x: f"{x}월")

with row2:
    # 버튼 높이 맞춤을 위한 빈 공간(st.write 사용 가능하지만 간편하게 처리)
    st.write("") # 간격
    st.write("") # 간격
    if st.button("적용"):
        st.session_state.start_dt = datetime.date(int("20"+y_sel), m_sel, 1)
        next_m = m_sel + 1 if m_sel < 12 else 1
        next_y = int("20"+y_sel) + (1 if m_sel == 12 else 0)
        st.session_state.end_dt = datetime.date(next_y, next_m, 1) - datetime.timedelta(days=1)
        st.rerun()

st.sidebar.markdown("---")
shop_sel = st.sidebar.multiselect('가게 선택', df['가게'].unique(), default=df['가게'].unique())
plat_sel = st.sidebar.multiselect('플랫폼 선택', df['플랫폼'].unique(), default=df['플랫폼'].unique())
search_txt = st.sidebar.text_input('📋 메뉴명 검색')

f_df = df[(df['날짜_date'] >= s_date) & (df['날짜_date'] <= e_date) & (df['가게'].isin(shop_sel)) & (df['플랫폼'].isin(plat_sel))].copy()
if search_txt: f_df = f_df[f_df['주문내역'].str.contains(search_txt, case=False, na=False)]
f_df['요일'] = pd.Categorical(f_df['요일'], categories=['월', '화', '수', '목', '금', '토', '일'], ordered=True)

# --- 3. 대시보드 메인 ---
f_df['매출_천원'] = f_df['주문금액'] / 1000
m1, m2, m3 = st.columns(3)
m1.metric("총 매출(천원)", f"{f_df['매출_천원'].sum():,.1f}")
m2.metric("총 주문", f"{len(f_df):,}건")
m3.metric("평균 객단가(천원)", f"{f_df['매출_천원'].mean():,.1f}")

st.markdown("---")
fig1 = px.bar(f_df.groupby('날짜_date')['매출_천원'].sum().reset_index(), x='날짜_date', y='매출_천원', title="전체 매출 추이(천원)")
st.plotly_chart(fig1, use_container_width=True)

row1_l, row1_r = st.columns(2)
row2_l, row2_r = st.columns(2)

with row1_l:
    st.subheader("📱 플랫폼별 매출")
    p_order = f_df.groupby('플랫폼')['매출_천원'].sum().sort_values(ascending=False).index.tolist()
    fig5 = px.bar(f_df.groupby(['플랫폼', '가게'])['매출_천원'].sum().reset_index(), x='플랫폼', y='매출_천원', color='가게', category_orders={"플랫폼": p_order})
    st.plotly_chart(fig5, use_container_width=True)

with row1_r:
    st.subheader("📋 메뉴별 매출 순위 (TOP 10)")
    top_menu = f_df.groupby(['주문내역', '가게'])['매출_천원'].sum().nlargest(10, keep='all').reset_index()
    fig4 = px.bar(top_menu, x='주문내역', y='매출_천원', color='가게')
    st.plotly_chart(fig4, use_container_width=True)

with row2_l:
    st.subheader("📅 요일별 매출")
    fig3 = px.bar(f_df.groupby(['요일', '가게'], observed=False)['매출_천원'].sum().reset_index(), x='요일', y='매출_천원', color='가게')
    st.plotly_chart(fig3, use_container_width=True)

with row2_r:
    st.subheader("⏰ 시간대별 매출")
    fig2 = px.bar(f_df.groupby(['영업시간대_라벨', '가게'])['매출_천원'].sum().reset_index(), x='영업시간대_라벨', y='매출_천원', color='가게')
    st.plotly_chart(fig2, use_container_width=True)

st.subheader('📋 상세 데이터')
d_df = f_df[['일자', '시간', '가게', '플랫폼', '주문내역', '매출_천원']].copy()
d_df['주문내역'] = d_df['주문내역'].str.replace(',', '\n')
st.dataframe(d_df, use_container_width=True, height=500)