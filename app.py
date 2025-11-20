import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components

# --- 頁面基本設定 ---
st.set_page_config(
    page_title="流量異常鑑識儀表板",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# --- 核心邏輯：資料清洗與計算 ---
@st.cache_data
def load_and_clean_data(file):
    try:
        df = pd.read_csv(file)
        numeric_cols = [
            'CTR（連結點閱率）', '曝光次數', '連結點擊次數', 
            '連結頁面瀏覽次數', 'CPM（每千次廣告曝光成本）', '花費金額 (TWD)'
        ]
        
        def clean_val(x):
            if isinstance(x, str):
                x = x.replace(',', '').replace('%', '')
                if x.strip() == '-': return 0
            return pd.to_numeric(x, errors='coerce')

        available_cols = [c for c in numeric_cols if c in df.columns]
        for col in available_cols:
            df[col] = df[col].apply(clean_val)
            
        if '連結頁面瀏覽次數' in df.columns and '連結點擊次數' in df.columns:
            df['LP_View_Rate'] = df.apply(
                lambda row: row['連結頁面瀏覽次數'] / row['連結點擊次數'] if row['連結點擊次數'] > 0 else 0, axis=1
            )
        else:
            df['LP_View_Rate'] = 0

        df_clean = df[df['曝光次數'] > 10].copy()
        return df_clean

    except Exception as e:
        st.error(f"檔案讀取錯誤: {e}")
        return None

# --- 側邊欄：參數控制 ---
st.sidebar.title("⚙️ 鑑識參數設定")

# 加入列印按鈕的說明
st.sidebar.info("💡 想要保存報告？\n點擊右側主畫面的「列印」按鈕，並在目的地選擇「另存為 PDF」。")

st.sidebar.subheader("1. 幽靈點擊偵測 (Ghost Clicks)")
threshold_ctr_high = st.sidebar.slider("CTR 異常高標 (%)", 2.0, 15.0, 4.0, 0.5)
threshold_quality_low = st.sidebar.slider("落地頁瀏覽率 低標 (Quality < X)", 0.1, 1.0, 0.5, 0.1)

st.sidebar.subheader("2. 展示灌水偵測 (Flooding)")
percentile_imp = st.sidebar.slider("高曝光定義 (PR值)", 50, 99, 75, 5)
threshold_ctr_low = st.sidebar.slider("CTR 異常低標 (%)", 0.1, 3.0, 1.5, 0.1)

# --- 主畫面 ---
col_title, col_btn = st.columns([3, 1])
with col_title:
    st.title("🕵️‍♂️ 廣告流量異常鑑識系統")
with col_btn:
    st.write("") # Spacer
    st.write("")
    # 嵌入 JavaScript 按鈕來觸發瀏覽器列印
    components.html(
        """
        <button onclick="window.parent.print()" style="
            background-color: #FF4B4B; 
            color: white; 
            padding: 10px 24px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 16px; 
            font-weight: bold;">
            🖨️ 列印 / 存為 PDF
        </button>
        """,
        height=50
    )

st.markdown("上傳 CSV 報表，自動診斷流量異常。")

uploaded_file = st.file_uploader("請上傳 CSV 報表檔案", type=['csv'])

if uploaded_file is not None:
    df = load_and_clean_data(uploaded_file)
    
    if df is not None:
        # --- 運算區 ---
        ghost_clicks = df[
            (df['CTR（連結點閱率）'] > threshold_ctr_high) & 
            (df['LP_View_Rate'] < threshold_quality_low)
        ].sort_values(by='CTR（連結點閱率）', ascending=False)

        imp_threshold_val = df['曝光次數'].quantile(percentile_imp / 100)
        flooding = df[
            (df['曝光次數'] > imp_threshold_val) & 
            (df['CTR（連結點閱率）'] < threshold_ctr_low)
        ].sort_values(by='曝光次數', ascending=False)

        # --- 繪圖區 ---
        if not df.empty:
            fig_ghost = px.scatter(
                df, x='連結點擊次數', y='連結頁面瀏覽次數', size='曝光次數', color='CTR（連結點閱率）',
                hover_data=['廣告名稱', '天數', 'LP_View_Rate'], title='點擊 vs. 到頁診斷', color_continuous_scale='Bluered'
            )
            max_val = df['連結點擊次數'].max()
            if pd.notnull(max_val):
                fig_ghost.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val, line=dict(color="Green", width=2, dash="dash"))

            fig_flood = px.scatter(
                df, x='曝光次數', y='CTR（連結點閱率）', size='CPM（每千次廣告曝光成本）', color='LP_View_Rate',
                hover_data=['廣告名稱', '天數', 'CPM（每千次廣告曝光成本）'], title='曝光 vs. CTR 診斷', color_continuous_scale='RdYlGn'
            )
            fig_flood.add_hline(y=threshold_ctr_low, line_dash="dash", line_color="red", annotation_text="低 CTR 警戒線")

        # --- 顯示區 ---
        st.markdown("---")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.header("🚩 異常 A：幽靈點擊")
            st.metric("疑似異常數", f"{len(ghost_clicks)}")
        with col2:
            if not df.empty: st.plotly_chart(fig_ghost, use_container_width=True)
        if not ghost_clicks.empty:
            st.dataframe(ghost_clicks[['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'LP_View_Rate']].style.format({'CTR（連結點閱率）': '{:.2f}%', 'LP_View_Rate': '{:.2%}'}))

        st.markdown("---")
        col3, col4 = st.columns([1, 2])
        with col3:
            st.header("🚩 異常 B：展示灌水")
            st.metric("疑似灌水數", f"{len(flooding)}")
        with col4:
            if not df.empty: st.plotly_chart(fig_flood, use_container_width=True)
        if not flooding.empty:
            st.dataframe(flooding[['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'CPM（每千次廣告曝光成本）']].style.format({'CTR（連結點閱率）': '{:.2f}%', 'CPM（每千次廣告曝光成本）': '{:.2f}'}))

else:
    st.info("請上傳檔案以開始分析。")
