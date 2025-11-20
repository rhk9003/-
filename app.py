import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

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

# --- Excel 生成邏輯 (新功能) ---
def generate_excel(ghost_df, flood_df, params_dict):
    output = BytesIO()
    # 使用 xlsxwriter 引擎來支援格式設定
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # Sheet 1: 異常A (幽靈點擊)
        if not ghost_df.empty:
            cols_ghost = ['天數', '廣告名稱', '曝光次數', '連結點擊次數', '連結頁面瀏覽次數', 'CTR（連結點閱率）', 'LP_View_Rate']
            ghost_df[cols_ghost].to_excel(writer, sheet_name='異常A_幽靈點擊', index=False)
        else:
            pd.DataFrame({'訊息': ['無符合條件的資料']}).to_excel(writer, sheet_name='異常A_幽靈點擊', index=False)

        # Sheet 2: 異常B (展示灌水)
        if not flood_df.empty:
            cols_flood = ['天數', '廣告名稱', '曝光次數', 'CTR（連結點閱率）', 'CPM（每千次廣告曝光成本）', '花費金額 (TWD)']
            flood_df[cols_flood].to_excel(writer, sheet_name='異常B_展示灌水', index=False)
        else:
            pd.DataFrame({'訊息': ['無符合條件的資料']}).to_excel(writer, sheet_name='異常B_展示灌水', index=False)

        # Sheet 3: 分析參數紀錄
        param_df = pd.DataFrame(list(params_dict.items()), columns=['參數名稱', '設定值'])
        param_df.to_excel(writer, sheet_name='分析參數紀錄', index=False)

        # --- 格式美化 (Auto-adjust columns width) ---
        workbook = writer.book
        # 定義百分比格式
        percent_fmt = workbook.add_format({'num_format': '0.00%'})
        
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            # 設定欄寬
            worksheet.set_column('A:A', 15) # 日期
            worksheet.set_column('B:B', 40) # 廣告名稱 (寬一點)
            worksheet.set_column('C:Z', 12) # 其他數據
            
            # 嘗試對特定欄位套用百分比格式 (簡單對應)
            # 注意：xlsxwriter 套用格式較複雜，這裡做基礎寬度調整即可，數據本身已是數值

    output.seek(0)
    return output

# --- 側邊欄：參數控制 ---
st.sidebar.title("⚙️ 鑑識參數設定")

st.sidebar.subheader("1. 幽靈點擊偵測 (Ghost Clicks)")
threshold_ctr_high = st.sidebar.slider("CTR 異常高標 (%)", 2.0, 15.0, 4.0, 0.5)
threshold_quality_low = st.sidebar.slider("落地頁瀏覽率 低標 (Quality < X)", 0.1, 1.0, 0.5, 0.1)

st.sidebar.subheader("2. 展示灌水偵測 (Flooding)")
percentile_imp = st.sidebar.slider("高曝光定義 (PR值)", 50, 99, 75, 5)
threshold_ctr_low = st.sidebar.slider("CTR 異常低標 (%)", 0.1, 3.0, 1.5, 0.1)

# --- 主畫面 ---
st.title("🕵️‍♂️ 廣告流量異常鑑識系統")
st.markdown("上傳 CSV 報表，自動診斷流量異常，並支援 **一鍵匯出 Excel 報告**。")

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
            # 圖表僅供網頁瀏覽，Excel 只輸出數據
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

        # --- 匯出按鈕區 ---
        st.markdown("---")
        st.header("📥 匯出報告")
        st.write("點擊下方按鈕，將當前的異常名單下載為 Excel 報表。")
        
        # 收集當前參數
        current_params = {
            'CTR 異常高標': f"{threshold_ctr_high}%",
            '落地頁瀏覽率 低標': f"{int(threshold_quality_low*100)}%",
            '高曝光定義 (PR值)': f"PR{percentile_imp}",
            'CTR 異常低標': f"{threshold_ctr_low}%"
        }

        if st.button('生成 Excel 分析報表'):
            with st.spinner('正在生成 Excel 中...'):
                try:
                    excel_file = generate_excel(ghost_clicks, flooding, current_params)
                    
                    st.download_button(
                        label="⬇️ 下載 Excel 檔案 (.xlsx)",
                        data=excel_file,
                        file_name="Meta廣告異常分析報表.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("報表生成完畢！請點擊上方按鈕下載。")
                except Exception as e:
                    st.error(f"生成失敗: {e}")
else:
    st.info("請上傳檔案以開始分析。")
