import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components

# --- 頁面基本設定 ---
st.set_page_config(
    page_title="流量異常鑑識儀表板 (Pro)",
    page_icon="⚖️",
    layout="wide"
)

# --- 核心邏輯：資料清洗 ---
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
            
        # 計算品質指標
        if '連結頁面瀏覽次數' in df.columns and '連結點擊次數' in df.columns:
            df['LP_View_Rate'] = df.apply(
                lambda row: row['連結頁面瀏覽次數'] / row['連結點擊次數'] if row['連結點擊次數'] > 0 else 0, axis=1
            )
        else:
            df['LP_View_Rate'] = 0

        # 過濾極小流量 (統計學上的雜訊)
        df_clean = df[df['曝光次數'] > 50].copy() 
        return df_clean

    except Exception as e:
        st.error(f"檔案讀取錯誤: {e}")
        return None

# --- 核心邏輯：自動計算統計閾值 & 基準值 ---
def calculate_dynamic_thresholds(df):
    stats = {}
    
    # 1. 計算基礎統計 (正常值 Reference)
    stats['mean_ctr'] = round(df['CTR（連結點閱率）'].mean(), 2)
    stats['median_ctr'] = round(df['CTR（連結點閱率）'].median(), 2)
    stats['mean_quality'] = round(df['LP_View_Rate'].mean(), 2)
    
    # 2. CTR 異常高標 (使用 IQR 法)
    q1_ctr = df['CTR（連結點閱率）'].quantile(0.25)
    q3_ctr = df['CTR（連結點閱率）'].quantile(0.75)
    iqr = q3_ctr - q1_ctr
    upper_bound = q3_ctr + 1.5 * iqr
    stats['ctr_high_threshold'] = round(float(upper_bound), 1)

    # 3. 品質低標 (使用平均值 - 0.5 標準差，或商業底線 0.3)
    mean_quality = df['LP_View_Rate'].mean()
    std_quality = df['LP_View_Rate'].std()
    suggested_quality = max(0.3, min(0.8, mean_quality - 0.5 * std_quality))
    stats['quality_low_threshold'] = round(float(suggested_quality), 2)

    # 4. CTR 異常低標 (使用 Q1)
    stats['ctr_low_threshold'] = round(max(0.5, float(q1_ctr)), 1)
    
    # 5. 灌水定義 (PR90)
    stats['imp_pr_threshold'] = 90

    return stats

# --- 介面佈局 ---
st.title("⚖️ 流量異常鑑識儀表板 (含基準參考)")
st.markdown("系統將自動分析此帳戶的 **正常平均值 (Normal Baseline)**，並據此建議 **
