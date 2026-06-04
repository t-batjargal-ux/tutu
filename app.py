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
    "【プロトタイプ版: OpenAI駆動】高度なAIデータクレンジング・プラットフォーム。古いキャッシュを完全に排除した安全なエクスポートが可能です。"
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

# セッション状態の完全な初期化
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
if "previous_file_name" not in st.session_state:
    st.session_state.previous_file_name = ""
if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0

# 🔥【最重要リセットロジック】新しいファイルがドロップされたら、過去の記憶を完全に抹消する
if uploaded_file is not None:
    if st.session_state.previous_file_name != uploaded_file.name:
        st.session_state.cleaned_df = None  # 古いデータを消去
        st.session_state.previous_file_name = uploaded_file.name
        st.session_state.refresh_counter += (
            1  # カウンターを増やしてコンポーネントを強制リフレッシュ
        )

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
            "<p style='text-align: center; color: gray; margin-bottom: 5px;'>AIが「会社名」や「住所」に該当する列を自動判定して整形します</p>",
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
以下のJSON形式のデータを、指定された【指示ルール】に従ってインテリジェントにクレンジングし、指定のJSONオブジェクト構造で返してください。

【指示ルール】
1. 列名が何であれ（例：「取引先名」「会社名」「企業名」「顧客名」など）、【会社名や組織名】が格納されていると判断できる列のデータについて、「㈱」や「(株)」などの略称をすべて「株式会社」に統一してください。
2. 列名が何であれ（例：「住所」「所在地」「送付先」「住所１」など）、【住所情報】が格納されていると判断できる列のデータについて、その中にある英数字、郵便番号、ハイフン、長音記号（ー）をすべて半角（ハイフンは「-」）に統一してください。
3. 元のデータ構造、列名は完全に維持してください。また、上記に該当しない列（例：担当者名、電話番号、あるいはデータに関係のない文章など）のデータは絶対に改変せず、そのまま維持してください。
4. もし、データ全体が会社名や住所とは全く関係のない内容（例：マニュアル、仕様書、タスク一覧など）である場合は、データを一切変更せず、そのままの形で返してください。

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
                            "content": "You are an expert data architect. You analyze the semantic meaning of columns and perform robust data cleansing according to the rules, while strictly preserving untouched columns and schema.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                # 返ってきたJSONテキストをパース
                response_text = response.choices[0].message.content
                cleaned_json = json.loads(response_text)

                # DataFrame に再変換し、リフレッシュカウンターを更新
                st.session_state.cleaned_df = pd.DataFrame(cleaned_json["data"])
                st.session_state.refresh_counter += 1

                st.toast("✨ クレンジング処理が正常に完了しました！")

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

            # 🔥 表（データエディタ）自体もIDを動的に変えて、古いキャッシュを完全に殺す
            edited_df = st.data_editor(
                st.session_state.cleaned_df,
                key=f"data_editor_core_{st.session_state.refresh_counter}",
                use_container_width=True,
                hide_index=True,
            )

            # ダウンロードセクションを右下にスマートに配置
            st.markdown("<br>", unsafe_allow_html=True)
            d_col1, d_col2 = st.columns([3, 1])
            with d_col2:
                try:
                    # 最新のエディタ状態からCSVデータを生成
                    csv_data = edited_df.to_csv(index=False, encoding="utf-8-sig")

                    # 🔥 ダウンロードボタンの鍵（key）を完全に同期させ、最新CSVを強制的に抱え直させる
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
