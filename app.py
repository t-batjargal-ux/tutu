import json
import pandas as pd
import streamlit as st
from openai import OpenAI

# 1. ページ全体をワイドモードに設定
st.set_page_config(
    page_title="AI Data Cleansing Pro (Final)",
    page_icon="🪄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 視覚的な微調整
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
    "【プロトタイプ版: OpenAI駆動】列構造を完全保護。エディタ内蔵のエクスポート機能を利用する高安定性プラットフォーム。"
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

        # 過去の壊れた1列CSVの自動サルベージ
        if len(df.columns) == 1 and "," in str(df.columns[0]):
            raw_col = df.columns[0]
            new_columns = [
                c.strip().strip('"').strip("'") for c in raw_col.split(",")
            ]
            fixed_rows = []
            for val in df[raw_col]:
                row_vals = [
                    str(v).strip().strip('"').strip("'")
                    for v in str(val).split(",")
                ]
                if len(row_vals) < len(new_columns):
                    row_vals += [""] * (len(new_columns) - len(row_vals))
                elif len(row_vals) > len(new_columns):
                    row_vals = row_vals[: len(new_columns)]
                fixed_rows.append(row_vals)
            df = pd.DataFrame(fixed_rows, columns=new_columns)

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
            "<p style='text-align: center; color: gray; margin-bottom: 5px;'>AIが列構造を完全に維持したまま、値を精密にクレンジングします</p>",
            unsafe_allow_html=True,
        )
        execute_button = st.button(
            "🚀 クレンジングを一括実行する", type="primary", use_container_width=True
        )

    if execute_button:
        with st.spinner("AI が列構造を固定したまま精密クレンジングを実行中..."):
            try:
                # 表データをJSON形式のテキストに変換
                data_json_str = df.to_json(orient="records", force_ascii=False)

                # 【確実】AIに変な嘘をつかせず、元のキー（列名）を1ミリも弄らせない最強のプロンプト
                prompt = f"""
You are a precise data cleansing engine. Clean the following JSON array of objects based on these strict rules:

1. Identify the column containing company/client names. Replace abbreviations like "㈱" or "(株)" with "株式会社".
2. Identify the column containing addresses. Convert all full-width alphanumeric characters, zip codes, and hyphens to half-width characters.
3. Keep all other columns and the original keys/schema EXACTLY as they are. Do not merge or combine any columns.

Input Data:
{data_json_str}

Respond ONLY with a valid JSON object in this format, reusing the exact keys from the input data:
{{
  "data": [ ...cleaned objects... ]
}}
"""

                # OpenAI APIリクエストの送信
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional data architect. You only output valid JSON adhering strictly to the schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                cleaned_json = json.loads(response.choices[0].message.content)

                # DataFrame に再変換し画面を更新
                st.session_state.cleaned_df = pd.DataFrame(
                    cleaned_json["data"]
                )
                st.session_state.refresh_counter += 1
                st.toast("✨ 精密クレンジングが完了しました！")

            except Exception as e:
                st.error(f"クレンジング処理中にエラーが発生しました: {e}")

    # --- STEP 4: 整形後データのレビューとエクスポート ---
    if st.session_state.cleaned_df is not None:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                "<h4 style='margin-top:0;'>📝 Step 3: クレンジング済みデータの最終レビュー</h4>",
                unsafe_allow_html=True,
            )

            # 🛠️【最大改善】迷わせないUI：自作ボタンを完全に撤去し、最強の内蔵ボタンへユーザーを誘導
            st.info(
                "💡 クレンジングが完了しました！ダウンロードは、**下の表の右上**にマウスを乗せると表示される **「Download as CSV」(下矢印のアイコン)** をクリックしてください。一番綺麗に出力されます。"
            )

            # データエディタの表示
            st.data_editor(
                st.session_state.cleaned_df,
                key=f"data_editor_core_{st.session_state.refresh_counter}",
                use_container_width=True,
                hide_index=True,
            )
