import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide"
)

STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "POSCO홀딩스": "005490.KS",
    "카카오": "035720.KS",
    "네이버": "035420.KS",
    "기아": "000270.KS",
    "셀트리온": "068270.KS",
}

st.title("📈 국내 주식 대시보드")
st.markdown("---")

# 사이드바 설정
st.sidebar.header("⚙️ 설정")
period_options = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=3)
selected_period = period_options[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "종목 선택",
    list(STOCKS.keys()),
    default=list(STOCKS.keys())[:5]
)

if not selected_stocks:
    st.warning("종목을 하나 이상 선택해주세요.")
    st.stop()

@st.cache_data(ttl=300)
def load_stock_data(tickers: dict, period: str):
    data = {}
    info_data = {}
    for name, ticker in tickers.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if not hist.empty:
                data[name] = hist
            info = stock.info
            info_data[name] = info
        except Exception:
            pass
    return data, info_data

with st.spinner("📡 주식 데이터를 불러오는 중..."):
    stock_histories, stock_infos = load_stock_data(
        {k: v for k, v in STOCKS.items() if k in selected_stocks},
        selected_period
    )

if not stock_histories:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
    st.stop()

# 현재가 요약 카드
st.subheader("💹 현재가 요약")
cols = st.columns(min(len(selected_stocks), 5))
for i, name in enumerate(selected_stocks):
    if name not in stock_histories:
        continue
    hist = stock_histories[name]
    current_price = hist["Close"].iloc[-1]
    prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
    change = current_price - prev_price
    change_pct = (change / prev_price) * 100
    col = cols[i % 5]
    delta_color = "🔴" if change >= 0 else "🔵"
    col.metric(
        label=f"{delta_color} {name}",
        value=f"{current_price:,.0f}원",
        delta=f"{change:+,.0f}원 ({change_pct:+.2f}%)"
    )

st.markdown("---")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📊 주가 차트", "📉 수익률 비교", "📋 종목 상세", "🔥 거래량"])

# 탭 1: 주가 차트
with tab1:
    st.subheader("주가 추이")
    chart_type = st.radio("차트 유형", ["라인 차트", "캔들스틱"], horizontal=True)

    if chart_type == "라인 차트":
        fig = go.Figure()
        for name in selected_stocks:
            if name not in stock_histories:
                continue
            hist = stock_histories[name]
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist["Close"],
                mode="lines",
                name=name,
                hovertemplate=f"{name}<br>날짜: %{{x}}<br>종가: %{{y:,.0f}}원<extra></extra>"
            ))
        fig.update_layout(
            xaxis_title="날짜",
            yaxis_title="주가 (원)",
            hovermode="x unified",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        selected_for_candle = st.selectbox("캔들스틱 종목 선택", selected_stocks)
        if selected_for_candle in stock_histories:
            hist = stock_histories[selected_for_candle]
            fig = go.Figure(data=[go.Candlestick(
                x=hist.index,
                open=hist["Open"],
                high=hist["High"],
                low=hist["Low"],
                close=hist["Close"],
                name=selected_for_candle,
                increasing_line_color="#FF4B4B",
                decreasing_line_color="#1F77B4"
            )])
            fig.update_layout(
                title=f"{selected_for_candle} 캔들스틱 차트",
                xaxis_title="날짜",
                yaxis_title="주가 (원)",
                height=500,
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)

# 탭 2: 수익률 비교
with tab2:
    st.subheader("기간 누적 수익률 비교")
    fig = go.Figure()
    for name in selected_stocks:
        if name not in stock_histories:
            continue
        hist = stock_histories[name]
        returns = (hist["Close"] / hist["Close"].iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=returns,
            mode="lines",
            name=name,
            hovertemplate=f"{name}<br>수익률: %{{y:.2f}}%<extra></extra>"
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        xaxis_title="날짜",
        yaxis_title="누적 수익률 (%)",
        hovermode="x unified",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 수익률 바 차트
    st.subheader("전체 기간 수익률 순위")
    returns_summary = []
    for name in selected_stocks:
        if name not in stock_histories:
            continue
        hist = stock_histories[name]
        total_return = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        returns_summary.append({"종목": name, "수익률(%)": round(total_return, 2)})

    if returns_summary:
        df_returns = pd.DataFrame(returns_summary).sort_values("수익률(%)", ascending=True)
        fig_bar = px.bar(
            df_returns, x="수익률(%)", y="종목", orientation="h",
            color="수익률(%)",
            color_continuous_scale=["#1F77B4", "#AAAAAA", "#FF4B4B"],
            color_continuous_midpoint=0,
            text="수익률(%)"
        )
        fig_bar.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_bar.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# 탭 3: 종목 상세
with tab3:
    st.subheader("종목 상세 정보")
    selected_detail = st.selectbox("종목 선택", selected_stocks, key="detail_select")

    if selected_detail in stock_infos and selected_detail in stock_histories:
        info = stock_infos[selected_detail]
        hist = stock_histories[selected_detail]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**기본 정보**")
            detail_rows = {
                "현재가": f"{hist['Close'].iloc[-1]:,.0f}원",
                "시가총액": f"{info.get('marketCap', 0):,.0f}원" if info.get('marketCap') else "N/A",
                "52주 최고": f"{info.get('fiftyTwoWeekHigh', 0):,.0f}원" if info.get('fiftyTwoWeekHigh') else "N/A",
                "52주 최저": f"{info.get('fiftyTwoWeekLow', 0):,.0f}원" if info.get('fiftyTwoWeekLow') else "N/A",
                "PER": f"{info.get('trailingPE', 'N/A')}",
                "PBR": f"{info.get('priceToBook', 'N/A')}",
                "배당수익률": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "N/A",
            }
            for k, v in detail_rows.items():
                st.markdown(f"- **{k}**: {v}")

        with col2:
            st.markdown("**기간 통계**")
            stats = {
                "기간 최고가": f"{hist['High'].max():,.0f}원",
                "기간 최저가": f"{hist['Low'].min():,.0f}원",
                "평균 거래량": f"{hist['Volume'].mean():,.0f}주",
                "평균 종가": f"{hist['Close'].mean():,.0f}원",
                "기간 변동성(σ)": f"{hist['Close'].pct_change().std() * 100:.2f}%",
                "기간 수익률": f"{(hist['Close'].iloc[-1]/hist['Close'].iloc[0]-1)*100:.2f}%",
            }
            for k, v in stats.items():
                st.markdown(f"- **{k}**: {v}")

        # 볼린저 밴드
        st.subheader(f"{selected_detail} 볼린저 밴드")
        window = 20
        if len(hist) >= window:
            hist = hist.copy()
            hist["MA20"] = hist["Close"].rolling(window=window).mean()
            hist["STD"] = hist["Close"].rolling(window=window).std()
            hist["Upper"] = hist["MA20"] + 2 * hist["STD"]
            hist["Lower"] = hist["MA20"] - 2 * hist["STD"]

            fig_bb = go.Figure()
            fig_bb.add_trace(go.Scatter(x=hist.index, y=hist["Upper"], name="상단 밴드",
                                        line=dict(color="rgba(255,75,75,0.3)"), showlegend=True))
            fig_bb.add_trace(go.Scatter(x=hist.index, y=hist["Lower"], name="하단 밴드",
                                        line=dict(color="rgba(31,119,180,0.3)"),
                                        fill="tonexty", fillcolor="rgba(128,128,128,0.1)", showlegend=True))
            fig_bb.add_trace(go.Scatter(x=hist.index, y=hist["MA20"], name="20일 이평선",
                                        line=dict(color="orange", dash="dash")))
            fig_bb.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="종가",
                                        line=dict(color="white")))
            fig_bb.update_layout(height=400, xaxis_title="날짜", yaxis_title="주가 (원)",
                                  hovermode="x unified")
            st.plotly_chart(fig_bb, use_container_width=True)

# 탭 4: 거래량
with tab4:
    st.subheader("거래량 분석")
    selected_vol = st.selectbox("종목 선택", selected_stocks, key="vol_select")

    if selected_vol in stock_histories:
        hist = stock_histories[selected_vol]
        colors = ["#FF4B4B" if c >= o else "#1F77B4"
                  for c, o in zip(hist["Close"], hist["Open"])]

        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(
            x=hist.index, y=hist["Volume"],
            marker_color=colors,
            name="거래량",
            hovertemplate="날짜: %{x}<br>거래량: %{y:,.0f}주<extra></extra>"
        ))
        ma_vol = hist["Volume"].rolling(window=20).mean()
        fig_vol.add_trace(go.Scatter(
            x=hist.index, y=ma_vol,
            line=dict(color="yellow", width=2),
            name="20일 평균 거래량"
        ))
        fig_vol.update_layout(
            height=400,
            xaxis_title="날짜",
            yaxis_title="거래량 (주)",
            hovermode="x unified"
        )
        st.plotly_chart(fig_vol, use_container_width=True)

    # 거래량 비교 (최근 평균)
    st.subheader("종목별 평균 거래량 비교")
    vol_data = []
    for name in selected_stocks:
        if name not in stock_histories:
            continue
        avg_vol = stock_histories[name]["Volume"].mean()
        vol_data.append({"종목": name, "평균 거래량": avg_vol})

    if vol_data:
        df_vol = pd.DataFrame(vol_data).sort_values("평균 거래량", ascending=True)
        fig_vol_bar = px.bar(
            df_vol, x="평균 거래량", y="종목", orientation="h",
            color="평균 거래량", color_continuous_scale="Blues",
            text="평균 거래량"
        )
        fig_vol_bar.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_vol_bar.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_vol_bar, use_container_width=True)

st.markdown("---")
st.caption(f"데이터 출처: Yahoo Finance (yfinance) | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
