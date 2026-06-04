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
    "【プロトタイプ版: OpenAI駆動】高度なAIデータクレンジング・プラットフォーム。表記揺れや表記規則の統一をワンクリックで実行します。"
)
st.markdown("---")

# 6. OpenAI APIキーを st.secrets から取得しクライアントを初期化
try:
    if "OPENAI_API_KEY" not in st.secrets:
        st.error(
            "【システムエラー】 `OPENAI_API_KEY` が設定されていません。Streamlit Cloudの Advanced settings ➔ Secrets に登録してください。"
        )
        st.stop()

    # OpenAIクライアントの初期化
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

# セッション状態で整形後データを管理
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None

if uploaded_file is not None:
    # 3. ファイルの読み込み（拡張子自動判別）
    try:
        if uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            try:
                df = pd.read_csv(uploaded_file, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(uploaded_file, encoding="cp932")
    except Exception as e:
        st.error(
            f"ファイルの読み込みに失敗しました。ファイル形式を確認してください。エラー: {e}"
        )
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
            "<p style='text-align: center; color: gray; margin-bottom: 5px;'>ルール：取引先名の株式会社統一 / 住所の半角統一</p>",
            unsafe_allow_html=True,
        )
        execute_button = st.button(
            "🚀 クレンジングを一括実行する", type="primary", use_container_width=True
        )

    if execute_button:
        with st.spinner("OpenAI GPT が高度なデータモデリングと整形を実行中..."):
            try:
                # 表データをJSON形式のテキストに変換
                data_json_str = df.to_json(orient="records", force_ascii=False)

                # 指示ルールのプロンプト作成
                prompt = f"""
以下のJSON形式のデータを、指定された【指示ルール】に従ってクレンジングし、指定のJSONオブジェクト構造で返してください。

【指示ルール】
1. 「取引先名」の「㈱」や「(株)」はすべて「株式会社」に統一してください。
2. 「住所」の英数字や郵便番号、ハイフンはすべて半角に統一してください。
3. 必ず元の列名を完全に維持してください。

【出力構造】
必ず、以下のように "data" というキーを持ったJSONオブジェクト形式で出力してください。
{{
  "data": [ここにクレンジング済みのオブジェクトの配列が入る]
}}

【対象データ】
{data_json_str}
"""

                # OpenAI APIリクエストの送信
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional data cleansing assistant. You always output valid JSON adhering strictly to the requested schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                # 返ってきたJSONテキストをパース
                response_text = response.choices[0].message.content
                cleaned_json = json.loads(response_text)

                # DataFrame に再変換
                st.session_state.cleaned_df = pd.DataFrame(cleaned_json["data"])
                st.toast("✨ クレンジング処理が正常に完了しました！")

            except Exception as e:
                st.error(f"クレンジング処理中にエラーが発生しました: {e}")

    # --- STEP 4: 整形後データのレビューとエクスポート ---
    if st.session_state.cleaned_df is not None:
        st.markdown("
