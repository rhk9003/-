import streamlit as st
import pandas as pd
import plotly.express as px

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
        # 嘗試讀取 CSV
        df = pd.read_csv(file)
        
        # 定義需要數值化的欄位
        numeric_cols = [
            'CTR（連結點閱率）', '曝光次數', '連結點擊次數', 
            '連結頁面瀏覽次數', 'CPM（每千次廣告曝光成本）', '花費金額 (TWD)'
        ]
        
        def clean_val(x):
            if isinstance(x, str):
                x = x.replace(',', '').replace('%', '')
                if x.strip() == '-': return 0
            return pd.to_numeric(x, errors='coerce')

        # 檢查欄位是否存在並清洗
        available_cols = [c for c in numeric_cols if c in df.columns]
        for col in available_cols:
            df[col] = df[col].apply(clean_val)
            
        # 計算 LP View Rate (品質指標)
        # 需同時有 '連結頁面瀏覽次數' 與 '連結點擊次數' 才能計算
        if '連結頁面瀏覽次數' in df.columns and '連結點擊次數' in df.columns:
            df['LP_View_Rate'] = df.apply(
                lambda row: row['連結頁面瀏覽次數'] / row['連結點擊次數'] if row['連結點擊次數'] > 0 else 0, axis=1
            )
        else:
            # 若欄位不足，不阻擋程式執行，但無法計算此指標
            st.warning("注意：CSV 缺少 '連結頁面瀏覽次數' 或 '連結點擊次數'，將無法計算品質比率。")
            df['LP_View_Rate'] = 0

        # 過濾極低流量雜訊 (預設 > 10 曝光才納入分析)
        df_clean = df[df['曝光次數'] > 10].copy()
        return df_clean

    except Exception as e:
        st.error(f"檔案讀取錯誤: {e}")
        return None

# --- 側邊欄：參數控制 ---
st.sidebar.title("⚙️ 鑑識參數設定")

st.sidebar.subheader("1. 幽靈點擊偵測 (Ghost Clicks)")
# 修正處：確保這一行有閉合括號
threshold_ctr_high = st.sidebar.slider("CTR 異常高標 (%)", 2.0, 15.0, 4.0, 0.5)
threshold_quality_low = st.sidebar.slider("落地頁瀏覽率 低標 (Quality < X)", 0.1, 1.0, 0.5, 0.1)

st.sidebar.subheader("2. 展示灌水偵測 (Flooding)")
percentile_imp = st.sidebar.slider("高曝光定義 (PR值)", 50, 99, 75, 5)
# 修正處：確保這一行有閉合括號
threshold_ctr_low = st.sidebar.slider("CTR 異常低標 (%)", 0.1, 3.0, 1.5, 0.1)

# --- 主畫面 ---
st.title("🕵️‍♂️ 廣告流量異常鑑識系統")
st.markdown("""
此工具協助您快速診斷 **Facebook/Meta 廣告報表** 中的兩類惡意攻擊或設定疏失：
1. **幽靈點擊 (Ghost Clicks)**：疑似機器人刷點擊 (High CTR, Low Quality)
2. **展示灌水 (Impression Flooding)**：疑似被惡意爬蟲刷展示 (High Imp, Low CTR)
""")

uploaded_file = st.file_uploader("請上傳 CSV 報表檔案", type=['csv'])

if uploaded_file is not None:
    df = load_and_clean_data(uploaded_file)
    
    if df is not None:
        # --- 1. 幽靈點擊分析 ---
        st.markdown("---")
        st.header("🚩 異常類型 A：幽靈點擊 (Ghost Clicks)")
        
        ghost_clicks = df[
            (df['CTR（連結點閱率）'] > threshold_ctr_high) & 
            (df['LP_View_Rate'] < threshold_quality_low)
        ].sort_values(by='CTR（連結點閱率）', ascending=False)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric("疑似異常廣告數", f"{len(ghost_clicks)}")
            st.markdown(f"**判定標準：**\n- CTR > {threshold_ctr_high}%\n- 到頁率 < {int(threshold_quality_low*100)}%")
            
        with col2:
            # 檢查是否有數據可繪圖
            if not df.empty:
                fig_ghost = px.scatter(
                    df, 
                    x='連結點擊次數', 
                    y='連結頁面瀏覽次數',
                    size='曝光次數',
                    color='CTR（連結點閱率）',
                    hover_data=['廣告名稱', '天數', 'LP_View_Rate'],
                    title='點擊 vs. 到頁 (偏離對角線越遠越異常)',
                    color_continuous_scale='Bluered'
                )
                max_val = df['連結點擊次數'].max()
                if pd.notnull(max_val):
                     fig_ghost.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val, line=dict(color="Green", width=2, dash="dash"))
                st.plotly_chart(fig_ghost, use_container_width=True)
            else:
                st.info("無數據可供繪圖")

        if not ghost_clicks.empty:
            st.subheader("詳細清單：疑似幽靈點擊")
            st.dataframe(
                ghost_clicks[['天數', '廣告名稱', '曝光次數', '連結點擊次數', '連結頁面瀏覽次數', 'CTR（連結點閱率）', 'LP_View_Rate']]
                .style.format({'CTR（連結點閱率）': '{:.2f}%', 'LP_View_Rate': '{:.2%}'})
            )
        else:
            st.success("✅ 在當前標準下，未發現顯著的幽靈點擊異常。")

        # --- 2. 展示灌水分析 ---
        st.markdown("---")
        st.header("🚩 異常類型 B：展示灌水 (Flooding)")
        
        # 計算動態閾值
        imp_threshold_val = df['曝光次數'].quantile(percentile_imp / 100)
        
        flooding = df[
            (df['曝光次數'] > imp_threshold_val) & 
            (df['CTR（連結點閱率）'] < threshold_ctr_low)
        ].sort_values(by='曝光次數', ascending=False)
        
        col3, col4 = st.columns([1, 2])
        
        with col3:
            st.metric("疑似灌水廣告數", f"{len(flooding)}")
            st.markdown(f"**判定標準：**\n- 曝光 > {int(imp_threshold_val)} (PR{percentile_imp})\n- CTR < {threshold_ctr_low}%")
            
        with col4:
            if not df.empty:
                fig_flood = px.scatter(
                    df, 
                    x='曝光次數', 
                    y='CTR（連結點閱率）',
                    size='CPM（每千次廣告曝光成本）',
                    color='LP_View_Rate',
                    hover_data=['廣告名稱', '天數', 'CPM（每千次廣告曝光成本）'],
                    title='曝光 vs. CTR (右下角為高風險區)',
                    color_continuous_scale='RdYlGn'
                )
                fig_flood.add_hline(y=threshold_ctr_low, line_dash="dash", line_color="red", annotation_text="低 CTR 警戒線")
                st.plotly_chart(fig_flood, use_container_width=True)
            else:
                st.info("無數據可供繪圖")

        if not flooding.empty:
            st.subheader("詳細清單：疑似展示灌水")
            st.dataframe(
                flooding[['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'CPM（每千次廣告曝光成本）', '花費金額 (TWD)']]
                .style.format({'CTR（連結點閱率）': '{:.2f}%', 'CPM（每千次廣告曝光成本）': '{:.2f}'})
            )
        else:
            st.success("✅ 在當前標準下，未發現顯著的展示灌水異常。")

else:
    st.info("請從左方上傳您的 Meta 廣告 CSV 報表以開始分析。")
