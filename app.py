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
    "【プロトタイプ版: OpenAI駆動】データ破損自動修復ロジックを搭載した、絶対に列構造を崩さない完全版プラットフォーム。"
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

        # 🔥【超強力：過去の壊れたファイル自動サルベージ機能】
        # もしCSVが1列に潰れて、列名にカンマが含まれていたら、強制的に複数列に分解・修復する
        if len(df.columns) == 1 and "," in str(df.columns[0]):
            raw_col = df.columns[0]
            # 潰れた列名を綺麗にバラす
            new_columns = [
                c.strip().strip('"').strip("'") for c in raw_col.split(",")
            ]

            fixed_rows = []
            for val in df[raw_col]:
                # 潰れた行データを綺麗にバラす
                row_vals = [
                    str(v).strip().strip('"').strip("'")
                    for v in str(val).split(",")
                ]
                # 列数のズレを安全に補正
                if len(row_vals) < len(new_columns):
                    row_vals += [""] * (len(new_columns) - len(row_vals))
                elif len(row_vals) > len(new_columns):
                    row_vals = row_vals[: len(new_columns)]
                fixed_rows.append(row_vals)

            # 正常な複数列のデータフレームとして完全復活
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

                # 絶対に列を合体させないよう、厳格なFew-shot（お手本）をプロンプトに注入
                prompt = f"""
以下のJSON形式のデータを、指定された【指示ルール】に従ってクレンジングし、指定のJSONオブジェクト構造で返してください。

【指示ルール】
1. 「取引先名」などの会社名が入った列の「㈱」や「(株)」はすべて「株式会社」に統一してください。
2. 「住所」などの住所が入った列の英数字や郵便番号、ハイフンはすべて半角に統一してください。
3. 元のデータ構造（行数、すべての列名、キー）は完全に維持してください。関係のない列（電話番号、担当者名など）の値は絶対に改変せず、そのまま戻してください。複数の列を1つに合体させるような行為は厳禁とします。

【出力構造】
必ず、以下のように "data" というキーを持ったJSONオブジェクト形式で出力してください。各オブジェクトは元の列名を完全に保持したキーと値のペアにしてください。
{{
  "data": [
    {{
      "取引先名": "クレンジング後の値",
      "住所": "クレンジング後の値",
      "電話番号": "元の値",
      "担当者名": "元の値"
    }}
  ]
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
                            "content": "You are a precise data engineering assistant. You clean values while strictly preserving the horizontal columns and vertical row structure without any fusion.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                # 返ってきたJSONテキストをパース
                response_text = response.choices[0].message.content
                cleaned_json = json.loads(response_text)

                # DataFrame に再変換し、キャッシュを殺すためにカウンターを回す
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
            st.markdown(
                "<p style='font-size: 13px; color: #1f77b4; margin-bottom: 15px;'>💡 必要に応じて、セルをダブルクリックして手動で修正を加えることができます。</p>",
                unsafe_allow_html=True,
            )

            # 動的キーにより、メモリ内の古いゴーストデータを完全に抹消
            edited_df = st.data_editor(
                st.session_state.cleaned_df,
                key=f"data_editor_core_{st.session_state.refresh_counter}",
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)
            d_col1, d_col2 = st.columns([3, 1])
            with d_col2:
                try:
                    # 最新のエディタ状態から、Excel対応のBOM付きCSVデータをクリーンに生成
                    csv_data = edited_df.to_csv(index=False, encoding="utf-8-sig")

                    # ボタンの鍵（key）を完全に同期させ、最新CSVを強制的にダウンロード
                    st.download_button(
                        label="📥 CSVファイルとして出力",
                        data=csv_data,
                        file_name="cleaned_customer_list.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key=f"final_download_btn_{st.session_state.refresh_counter}",
                    )
                except Exception as e:
                    st.error(f"CSV生成エラー: {e}")
