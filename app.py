import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import anthropic

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

# 사이드바
st.sidebar.header("⚙️ 설정")
period_options = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=3)
selected_period = period_options[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "종목 선택",
    list(STOCKS.keys()),
    default=list(STOCKS.keys())[:5]
)

st.sidebar.markdown("---")
st.sidebar.header("🤖 AI 챗봇 설정")
api_key = st.sidebar.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")

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
            info_data[name] = stock.info
        except Exception:
            pass
    return data, info_data

with st.spinner("📡 주식 데이터를 불러오는 중..."):
    stock_histories, stock_infos = load_stock_data(
        {k: v for k, v in STOCKS.items() if k in selected_stocks},
        selected_period
    )

if not stock_histories:
    st.error("데이터를 불러오지 못했습니다.")
    st.stop()

# 현재가 요약 카드
st.subheader("💹 현재가 요약")
cols = st.columns(min(len(selected_stocks), 5))
for i, name in enumerate(selected_stocks):
    if name not in stock_histories:
        continue
    hist = stock_histories[name]
    current = hist["Close"].iloc[-1]
    prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
    change = current - prev
    pct = (change / prev) * 100
    icon = "🔴" if change >= 0 else "🔵"
    cols[i % 5].metric(f"{icon} {name}", f"{current:,.0f}원", f"{change:+,.0f}원 ({pct:+.2f}%)")

st.markdown("---")

# 탭 구성 — 챗봇 포함
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 주가 차트", "📉 수익률 비교", "📋 종목 상세", "🔥 거래량", "🤖 AI 챗봇"])

# ── 탭 1: 주가 차트 ──────────────────────────────────────────────────
with tab1:
    st.subheader("주가 추이")
    chart_type = st.radio("차트 유형", ["라인 차트", "캔들스틱"], horizontal=True)

    if chart_type == "라인 차트":
        fig = go.Figure()
        for name in selected_stocks:
            if name not in stock_histories:
                continue
            hist = stock_histories[name]
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name=name,
                                     hovertemplate=f"{name}<br>날짜: %{{x}}<br>종가: %{{y:,.0f}}원<extra></extra>"))
        fig.update_layout(xaxis_title="날짜", yaxis_title="주가 (원)",
                          hovermode="x unified", height=500,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    else:
        sel = st.selectbox("종목 선택", selected_stocks)
        if sel in stock_histories:
            hist = stock_histories[sel]
            fig = go.Figure(data=[go.Candlestick(
                x=hist.index, open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"],
                increasing_line_color="#FF4B4B", decreasing_line_color="#1F77B4"
            )])
            fig.update_layout(title=f"{sel} 캔들스틱", xaxis_title="날짜", yaxis_title="주가 (원)",
                               height=500, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

# ── 탭 2: 수익률 비교 ────────────────────────────────────────────────
with tab2:
    st.subheader("기간 누적 수익률 비교")
    fig = go.Figure()
    for name in selected_stocks:
        if name not in stock_histories:
            continue
        hist = stock_histories[name]
        returns = (hist["Close"] / hist["Close"].iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(x=hist.index, y=returns, mode="lines", name=name,
                                 hovertemplate=f"{name}<br>수익률: %{{y:.2f}}%<extra></extra>"))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(xaxis_title="날짜", yaxis_title="누적 수익률 (%)",
                      hovermode="x unified", height=500,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("전체 기간 수익률 순위")
    rows = []
    for name in selected_stocks:
        if name not in stock_histories:
            continue
        hist = stock_histories[name]
        rows.append({"종목": name, "수익률(%)": round((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100, 2)})
    if rows:
        df_r = pd.DataFrame(rows).sort_values("수익률(%)", ascending=True)
        fig_bar = px.bar(df_r, x="수익률(%)", y="종목", orientation="h",
                         color="수익률(%)", color_continuous_scale=["#1F77B4", "#AAAAAA", "#FF4B4B"],
                         color_continuous_midpoint=0, text="수익률(%)")
        fig_bar.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_bar.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

# ── 탭 3: 종목 상세 ──────────────────────────────────────────────────
with tab3:
    st.subheader("종목 상세 정보")
    sel_d = st.selectbox("종목 선택", selected_stocks, key="detail")
    if sel_d in stock_infos and sel_d in stock_histories:
        info = stock_infos[sel_d]
        hist = stock_histories[sel_d]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**기본 정보**")
            for k, v in {
                "현재가": f"{hist['Close'].iloc[-1]:,.0f}원",
                "시가총액": f"{info.get('marketCap', 0):,.0f}원" if info.get('marketCap') else "N/A",
                "52주 최고": f"{info.get('fiftyTwoWeekHigh', 0):,.0f}원" if info.get('fiftyTwoWeekHigh') else "N/A",
                "52주 최저": f"{info.get('fiftyTwoWeekLow', 0):,.0f}원" if info.get('fiftyTwoWeekLow') else "N/A",
                "PER": f"{info.get('trailingPE', 'N/A')}",
                "PBR": f"{info.get('priceToBook', 'N/A')}",
                "배당수익률": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
            }.items():
                st.markdown(f"- **{k}**: {v}")
        with c2:
            st.markdown("**기간 통계**")
            for k, v in {
                "기간 최고가": f"{hist['High'].max():,.0f}원",
                "기간 최저가": f"{hist['Low'].min():,.0f}원",
                "평균 거래량": f"{hist['Volume'].mean():,.0f}주",
                "평균 종가": f"{hist['Close'].mean():,.0f}원",
                "기간 변동성(σ)": f"{hist['Close'].pct_change().std()*100:.2f}%",
                "기간 수익률": f"{(hist['Close'].iloc[-1]/hist['Close'].iloc[0]-1)*100:.2f}%",
            }.items():
                st.markdown(f"- **{k}**: {v}")

        st.subheader(f"{sel_d} 볼린저 밴드")
        if len(hist) >= 20:
            h = hist.copy()
            h["MA20"] = h["Close"].rolling(20).mean()
            h["STD"] = h["Close"].rolling(20).std()
            h["Upper"] = h["MA20"] + 2 * h["STD"]
            h["Lower"] = h["MA20"] - 2 * h["STD"]
            fig_bb = go.Figure()
            fig_bb.add_trace(go.Scatter(x=h.index, y=h["Upper"], name="상단 밴드", line=dict(color="rgba(255,75,75,0.3)")))
            fig_bb.add_trace(go.Scatter(x=h.index, y=h["Lower"], name="하단 밴드",
                                        line=dict(color="rgba(31,119,180,0.3)"),
                                        fill="tonexty", fillcolor="rgba(128,128,128,0.1)"))
            fig_bb.add_trace(go.Scatter(x=h.index, y=h["MA20"], name="20일 이평선", line=dict(color="orange", dash="dash")))
            fig_bb.add_trace(go.Scatter(x=h.index, y=h["Close"], name="종가", line=dict(color="white")))
            fig_bb.update_layout(height=400, xaxis_title="날짜", yaxis_title="주가 (원)", hovermode="x unified")
            st.plotly_chart(fig_bb, use_container_width=True)

# ── 탭 4: 거래량 ─────────────────────────────────────────────────────
with tab4:
    st.subheader("거래량 분석")
    sel_v = st.selectbox("종목 선택", selected_stocks, key="vol")
    if sel_v in stock_histories:
        hist = stock_histories[sel_v]
        colors = ["#FF4B4B" if c >= o else "#1F77B4" for c, o in zip(hist["Close"], hist["Open"])]
        fig_v = go.Figure()
        fig_v.add_trace(go.Bar(x=hist.index, y=hist["Volume"], marker_color=colors, name="거래량",
                               hovertemplate="날짜: %{x}<br>거래량: %{y:,.0f}주<extra></extra>"))
        fig_v.add_trace(go.Scatter(x=hist.index, y=hist["Volume"].rolling(20).mean(),
                                   line=dict(color="yellow", width=2), name="20일 평균"))
        fig_v.update_layout(height=400, xaxis_title="날짜", yaxis_title="거래량 (주)", hovermode="x unified")
        st.plotly_chart(fig_v, use_container_width=True)

    st.subheader("종목별 평균 거래량 비교")
    vd = [{"종목": n, "평균 거래량": stock_histories[n]["Volume"].mean()}
          for n in selected_stocks if n in stock_histories]
    if vd:
        df_v = pd.DataFrame(vd).sort_values("평균 거래량", ascending=True)
        fig_vb = px.bar(df_v, x="평균 거래량", y="종목", orientation="h",
                        color="평균 거래량", color_continuous_scale="Blues", text="평균 거래량")
        fig_vb.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_vb.update_layout(height=400, coloraxis_showscale=False)
        st.plotly_chart(fig_vb, use_container_width=True)

# ── 탭 5: AI 챗봇 ────────────────────────────────────────────────────
with tab5:
    st.subheader("🤖 주식 AI 챗봇")
    st.markdown("현재 로드된 주식 데이터를 바탕으로 AI에게 질문하세요.")

    if not api_key:
        st.info("👈 사이드바에서 Anthropic API Key를 입력하세요. [발급 받기](https://console.anthropic.com/)")
    else:
        # 주식 데이터 요약 — 시스템 컨텍스트로 제공
        def build_stock_context():
            lines = [f"오늘 날짜: {datetime.now().strftime('%Y-%m-%d')}"]
            lines.append(f"조회 기간: {selected_period_label}")
            lines.append("\n현재 로드된 종목 데이터 요약:")
            for name in selected_stocks:
                if name not in stock_histories:
                    continue
                hist = stock_histories[name]
                current = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
                pct = (current - prev) / prev * 100
                total_ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
                vol = hist["Close"].pct_change().std() * 100
                lines.append(
                    f"- {name}: 현재가 {current:,.0f}원, 전일대비 {pct:+.2f}%, "
                    f"기간수익률 {total_ret:+.2f}%, 변동성 {vol:.2f}%"
                )
            return "\n".join(lines)

        SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 AI 어시스턴트입니다.
사용자가 제공한 주식 데이터를 분석하고 투자에 관한 인사이트를 제공합니다.

중요 사항:
- 제공된 데이터를 기반으로 객관적인 분석을 제공하세요.
- 투자 권유가 아닌 정보 제공 목적임을 명심하세요.
- 한국어로 친절하고 전문적으로 답변하세요.
- 구체적인 수치와 근거를 들어 설명하세요.

현재 주식 데이터:
{context}"""

        # 대화 기록 초기화
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # 대화 기록 표시
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                    st.markdown(msg["content"])

        # 빠른 질문 버튼
        st.markdown("**빠른 질문:**")
        quick_cols = st.columns(3)
        quick_questions = [
            "가장 수익률이 높은 종목은?",
            "변동성이 가장 낮은 안정적인 종목은?",
            "현재 데이터 기반으로 투자 전략을 추천해줘",
        ]
        quick_input = None
        for i, q in enumerate(quick_questions):
            if quick_cols[i].button(q, use_container_width=True):
                quick_input = q

        # 사용자 입력
        user_input = st.chat_input("주식에 대해 무엇이든 물어보세요...")
        final_input = quick_input or user_input

        if final_input:
            st.session_state.chat_history.append({"role": "user", "content": final_input})
            with st.chat_message("user", avatar="🧑"):
                st.markdown(final_input)

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("AI가 분석 중입니다..."):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        context = build_stock_context()
                        system = SYSTEM_PROMPT.format(context=context)

                        # 대화 기록을 API 형식으로 변환
                        messages = [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.chat_history
                        ]

                        # 스트리밍 응답
                        response_text = ""
                        response_placeholder = st.empty()

                        with client.messages.stream(
                            model="claude-opus-4-8",
                            max_tokens=2048,
                            system=system,
                            messages=messages,
                        ) as stream:
                            for text in stream.text_stream:
                                response_text += text
                                response_placeholder.markdown(response_text + "▌")

                        response_placeholder.markdown(response_text)
                        st.session_state.chat_history.append(
                            {"role": "assistant", "content": response_text}
                        )

                    except anthropic.AuthenticationError:
                        st.error("❌ API Key가 올바르지 않습니다. 사이드바에서 확인해주세요.")
                    except Exception as e:
                        st.error(f"❌ 오류가 발생했습니다: {str(e)}")

        # 대화 초기화 버튼
        if st.session_state.chat_history:
            if st.button("🗑️ 대화 초기화"):
                st.session_state.chat_history = []
                st.rerun()

st.markdown("---")
st.caption(f"데이터 출처: Yahoo Finance (yfinance) | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
