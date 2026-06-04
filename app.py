import json
import pandas as pd
import streamlit as st
from openai import OpenAI

# 1. ページ全体をワイドモードに設定
st.set_page_config(
    page_title="AI Data Cleansing Pro (Prototype)",
    page_icon="🪄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 視覚的な微調整（コンテナの上部パディングを最適化）
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; padding-bottom: 2.5rem; }
    </style>
""",
    unsafe_allow_html=True,
)

# ヘッダーエリア
st.title("🪄 AI Data Cleansing Professional")
st.caption(
    "【プロトタイプ版: OpenAI駆動】列構造を100%保護し、内蔵エクスポートと自作ボタンを完全に同期したデータクレンジング・プラットフォーム。"
)
st.markdown("---")

# OpenAI APIキーを st.secrets から取得しクライアントを初期化
try:
    if "OPENAI_API_KEY" not in st.secrets:
        st.error(
            "【システムエラー】 `OPENAI_API_KEY` が設定されていません。Streamlit Cloudの Advanced settings ➔ Secrets に登録してください。"
        )
        st.stop()
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"OpenAIクライアントの初期化中にエラーが発生しました: {e}")
    st.stop()

# --- STEP 1: ファイルのインポート ---
with st.container(border=True):
    st.markdown(
        "<h4 style='margin-top:0;'>📥 Step 1: 対象ファイルのインポート</h4>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "CSVまたはExcelファイルをここにドロップしてください（UTF-8 / cp932 / .xlsx 対応）",
        type=["csv", "xlsx"],
        label_visibility="collapsed",
    )

# セッション状態の管理
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "previous_file_name" not in st.session_state:
    st.session_state.previous_file_name = ""
if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0

if uploaded_file is not None:
    if st.session_state.previous_file_name != uploaded_file.name:
        st.session_state.cleaned_df = None
        st.session_state.previous_file_name = uploaded_file.name
        st.session_state.refresh_counter += 1

    # ファイルの読み込み（拡張子自動判別）
    try:
        if uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            try:
                df = pd.read_csv(uploaded_file, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, encoding="cp932")
    except Exception as e:
        st.error(f"ファイルの読み込みに失敗しました: {e}")
        st.stop()

    # --- STEP 2: アップロードデータのプレビュー ---
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            f"<h4 style='margin-top:0;'>📋 Step 2: アップロードデータの確認 <span style='font-size:14px; font-weight:normal; color:gray;'>({uploaded_file.name})</span></h4>",
            unsafe_allow_html=True,
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- STEP 3: クレンジング実行エリア ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown(
            "<p style='text-align: center; color: gray; margin-bottom: 5px;'>元の列構造を完全に維持したまま、指定列の値のみを精密に書き換えます</p>",
            unsafe_allow_html=True,
        )
        execute_button = st.button(
            "🚀 クレンジングを一括実行する", type="primary", use_container_width=True
        )

    if execute_button:
        with st.spinner("AI が列構造を固定したまま値の精密クレンジングを実行中..."):
            try:
                # 完全に独立した複数列を持つDataFrameのコピーを作成
                df_cleaned = df.copy()
                columns_list = [str(c) for c in df.columns]

                # 1. クレンジング対象の列名を特定
                mapping_prompt = f"""
                以下の列名リストから、【会社名・取引先名】が格納されている列名と、【住所・所在地】が格納されている列名をそれぞれ1つずつ特定してください。
                列名リスト: {columns_list}

                必ず以下のJSON構造のみで返答してください。該当する列がない場合はnullにしてください。
                {{
                  "company_column": "特定した列名またはnull",
                  "address_column": "特定した列名またはnull"
                }}
