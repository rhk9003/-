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
        
        # 數值化處理
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
        # 避免分母為 0
        if '連結頁面瀏覽次數' in df.columns and '連結點擊次數' in df.columns:
            df['LP_View_Rate'] = df.apply(
                lambda row: row['連結頁面瀏覽次數'] / row['連結點擊次數'] if row['連結點擊次數'] > 0 else 0, axis=1
            )
        else:
            st.error("缺少關鍵欄位：需包含 '連結頁面瀏覽次數' 與 '連結點擊次數'")
            return None

        # 過濾極低流量雜訊 (預設 > 10 曝光才納入分析)
        df_clean = df[df['曝光次數'] > 10].copy()
        return df_clean

    except Exception as e:
        st.error(f"檔案讀取錯誤: {e}")
        return None

# --- 側邊欄：參數控制 ---
st.sidebar.title("⚙️ 鑑識參數設定")

st.sidebar.subheader("1. 幽靈點擊偵測 (Ghost Clicks)")
threshold_ctr_high = st.sidebar.slider("CTR 異常高標 (%)", 2.0, 15.0, 4.0, 0.5)
threshold_quality_low = st.sidebar.slider("落地頁瀏覽率 低標 (Quality < X)", 0.1, 1.0, 0.5, 0.1)

st.sidebar.subheader("2. 展示灌水偵測 (Flooding)")
percentile_imp = st.sidebar.slider("高曝光定義 (PR值)", 50, 99, 75, 5)
threshold_ctr_low = st.sidebar.slider("CTR 異常低標 (%)", 0.1, 3.0, 1.5, 0.1
