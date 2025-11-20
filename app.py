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
st.markdown("系統將自動分析此帳戶的 **正常平均值 (Normal Baseline)**，並據此建議 **異常判定紅線 (Threshold)**。")

# 加入列印按鈕
components.html(
    """<button onclick="window.parent.print()" style="background-color:#FF4B4B;color:white;padding:8px 20px;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">🖨️ 列印報告 / 另存 PDF</button>""",
    height=45
)

# 檔案上傳區
uploaded_file = st.file_uploader("請上傳 CSV 報表檔案", type=['csv'])

# --- 狀態管理 ---
if 'stats' not in st.session_state:
    # 預設空值 (還沒上傳檔案時)
    st.session_state['stats'] = {
        'mean_ctr': 0, 'median_ctr': 0, 'mean_quality': 0,
        'ctr_high_threshold': 4.0, 'quality_low_threshold': 0.5,
        'imp_pr_threshold': 75, 'ctr_low_threshold': 1.5
    }

df = None
if uploaded_file is not None:
    # 讀取數據
    df = load_and_clean_data(uploaded_file)
    if df is not None:
        # 若是新檔案，重新計算基準值與建議閾值
        current_file_id = getattr(uploaded_file, 'id', uploaded_file.name) # 簡單的 ID 檢查
        if st.session_state.get('last_file_id') != current_file_id:
            new_stats = calculate_dynamic_thresholds(df)
            st.session_state['stats'] = new_stats
            st.session_state['last_file_id'] = current_file_id
            st.toast("已計算帳戶基準值，並更新異常建議閾值！", icon="✅")

# --- 側邊欄：顯示「正常值」與「異常設定」 ---
st.sidebar.title("⚙️ 判定標準設定")

# 取出當前統計值
s = st.session_state['stats']

# [區塊 1] 幽靈點擊設定
st.sidebar.header("1. 幽靈點擊 (Ghost Clicks)")

if df is not None:
    st.sidebar.info(f"""
    **📊 帳戶正常基準 (Baseline)**
    - 平均 CTR： **{s['mean_ctr']}%**
    - 平均到頁率： **{int(s['mean_quality']*100)}%**
    """)
else:
    st.sidebar.text("等待數據計算基準值...")

ctr_high = st.sidebar.slider(
    "🔴 設定 CTR 異常高標 (%)", 
    2.0, 15.0, 
    value=s['ctr_high_threshold'],
    help="建議設為：平均值 + 2倍標準差 或 IQR 離群值"
)

quality_low = st.sidebar.slider(
    "🔴 設定 到頁率 異常低標", 
    0.1, 1.0, 
    value=s['quality_low_threshold'],
    help="建議設為：平均到頁率的 70% 以下"
)

st.sidebar.markdown("---")

# [區塊 2] 展示灌水設定
st.sidebar.header("2. 展示灌水 (Flooding)")

if df is not None:
    # 計算 PR90 的實際曝光數值給使用者看，更有感
    imp_val_disp = int(df['曝光次數'].quantile(s['imp_pr_threshold']/100))
    st.sidebar.info(f"""
    **📊 流量基準**
    - 中位數 CTR： **{s['median_ctr']}%**
    - 頂部流量門檻： **> {imp_val_disp} 次**
    """)

imp_pr = st.sidebar.slider(
    "🔴 高曝光定義 (PR值)", 
    50, 99, 
    value=s['imp_pr_threshold'],
    help="PR90 代表只檢查流量最大的前 10% 廣告"
)

ctr_low = st.sidebar.slider(
    "🔴 設定 CTR 異常低標 (%)", 
    0.1, 5.0, 
    value=s['ctr_low_threshold'],
    help="建議設為：第一四分位數 (Q1) 或更低"
)

# --- 主畫面分析結果 ---
if df is not None:
    # 運算
    ghost_clicks = df[
        (df['CTR（連結點閱率）'] > ctr_high) & 
        (df['LP_View_Rate'] < quality_low)
    ].sort_values(by='CTR（連結點閱率）', ascending=False)

    imp_threshold_val = df['曝光次數'].quantile(imp_pr / 100)
    flooding = df[
        (df['曝光次數'] > imp_threshold_val) & 
        (df['CTR（連結點閱率）'] < ctr_low)
    ].sort_values(by='曝光次數', ascending=False)

    # 顯示圖表
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("🚩 幽靈點擊名單")
        st.metric("異常數量", f"{len(ghost_clicks)}", delta="High CTR & Low Quality", delta_color="inverse")
        st.caption(f"判定標準：CTR > {ctr_high}% 且 到頁率 < {int(quality_low*100)}%")
    with col2:
        fig_ghost = px.scatter(
            df, x='連結點擊次數', y='連結頁面瀏覽次數', size='曝光次數', color='CTR（連結點閱率）',
            hover_data=['廣告名稱', '天數', 'LP_View_Rate'], 
            title=f'幽靈點擊診斷 (平均 CTR: {s["mean_ctr"]}%)', 
            color_continuous_scale='Bluered'
        )
        limit_xy = max(df['連結點擊次數'].max(), df['連結頁面瀏覽次數'].max())
        fig_ghost.add_shape(type="line", x0=0, y0=0, x1=limit_xy, y1=limit_xy, line=dict(color="Green", width=2, dash="dash"))
        st.plotly_chart(fig_ghost, use_container_width=True)

    if not ghost_clicks.empty:
        st.dataframe(ghost_clicks[['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'LP_View_Rate']].style.format({'CTR（連結點閱率）': '{:.2f}%', 'LP_View_Rate': '{:.2%}'}))

    st.markdown("---")

    col3, col4 = st.columns([1, 2])
    with col3:
        st.subheader("🚩 展示灌水名單")
        st.metric("異常數量", f"{len(flooding)}", delta="High Imp & Low CTR", delta_color="inverse")
        st.caption(f"判定標準：曝光 > {int(imp_threshold_val)} (PR{imp_pr}) 且 CTR < {ctr_low}%")
    with col4:
        fig_flood = px.scatter(
            df, x='曝光次數', y='CTR（連結點閱率）', size='CPM（每千次廣告曝光成本）', color='LP_View_Rate',
            hover_data=['廣告名稱', '天數', 'CPM（每千次廣告曝光成本）'], 
            title=f'展示灌水診斷 (中位數 CTR: {s["median_ctr"]}%)', 
            color_continuous_scale='RdYlGn'
        )
        fig_flood.add_hline(y=ctr_low, line_dash="dash", line_color="red")
        fig_flood.add_vline(x=imp_threshold_val, line_dash="dash", line_color="orange")
        st.plotly_chart(fig_flood, use_container_width=True)

    if not flooding.empty:
        st.dataframe(flooding[['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'CPM（每千次廣告曝光成本）']].style.format({'CTR（連結點閱率）': '{:.2f}%', 'CPM（每千次廣告曝光成本）': '{:.2f}'}))

else:
    st.info("👈 請從左側上傳 CSV 檔案。系統將自動計算帳戶平均值供您參考。")
