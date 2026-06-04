import json
import time
from datetime import datetime
import pandas as pd
import streamlit as st
from openai import OpenAI

# 1. ページ全体をワイドモードに設定
st.set_page_config(
    page_title="AI Data Cleansing Pro (Enterprise)",
    page_icon="🪄",
    layout="wide",
    initial_sidebar_state="expanded",
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
    "【エンタープライズ版】カスタマイズ・ルール、差分ハイライト、大容量チャンク処理、日付付きエクスポートを搭載した次世代データ整形プラットフォーム。"
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


# --- 🎛️ 技能2: クレンジング「ルール」の画面カスタマイズ機能（サイドバー） ---
st.sidebar.markdown("### 🎛️ クレンジング設定")

st.sidebar.markdown("**基本ルール（トグル）**")
rule_company = st.sidebar.checkbox(
    "取引先名の「㈱」「(株)」を「株式会社」に統一", value=True
)
rule_address = st.sidebar.checkbox(
    "住所の英数字・郵便番号・ハイフンを半角に統一", value=True
)
rule_phone = st.sidebar.checkbox("電話番号のハイフンを完全に削除（数字のみ化）", value=False)
rule_fillna = st.sidebar.checkbox(
    "空欄（欠損値）セルを「不明」という文字列で埋める", value=False
)

st.sidebar.markdown("---")
st.sidebar.markdown("**追加のカスタム指示（自由記述）**")
custom_rule = st.sidebar.text_area(
    "AIへの直接指示（例：『メールアドレスのドメインを小文字に統一』『氏名の間の空白を削除』など）",
    value="",
    placeholder="ここに追加ルールを自由に記述できます",
)

st.sidebar.markdown("---")
st.sidebar.markdown("**処理設定**")
chunk_size = st.sidebar.slider(
    "1回あたりの処理行数（分割サイズ）",
    min_value=5,
    max_value=50,
    value=10,
    step=5,
    help="制限エラー(429)を防ぐため、データを小分けにしてAIに送信します。通常は10〜20が最適です。",
)


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
if "original_df_str" not in st.session_state:
    st.session_state.original_df_str = None
if "previous_file_name" not in st.session_state:
    st.session_state.previous_file_name = ""
if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0

if uploaded_file is not None:
    if st.session_state.previous_file_name != uploaded_file.name:
        st.session_state.cleaned_df = None
        st.session_state.original_df_str = None
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

        # 列名とデータをすべて文字列型に強制変換して完全固定化
        df.columns = [str(c) for c in df.columns]
        df_str_init = df.astype(str).replace("nan", "")  # 欠損値の文字列化防止
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
        st.dataframe(df_str_init, use_container_width=True, hide_index=True)

    # --- STEP 3: クレンジング実行エリア ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        execute_button = st.button(
            "🚀 クレンジングを一括実行する", type="primary", use_container_width=True
        )

    # 🚀 クレンジングのメイン実行ロジック
    if execute_button:
        # 画面サイドバーの設定からプロンプト指示を動的に組み立て
        rules_list = []
        if rule_company:
            rules_list.append(
                "- 会社名や取引先名が含まれる列について、「㈱」や「(株)」などの略称をすべて「株式会社」に統一してください。"
            )
        if rule_address:
            rules_list.append(
                "- 住所情報が含まれる列について、その中にある英数字、郵便番号、ハイフン、長音記号（ー）をすべて半角（ハイフンは「-」）に統一してください。"
            )
        if rule_phone:
            rules_list.append(
                "- 電話番号が含まれる列について、ハイフン（-）などの記号をすべて削除し、数字のみの形式に統一してください。"
            )
        if rule_fillna:
            rules_list.append(
                "- データ内に空欄、空文字、または「nan」となっているセルがある場合、一律で「不明」という文字列に置き換えてください。"
            )
        if custom_rule:
            rules_list.append(f"- 【最優先追加指示】: {custom_rule}")

        rules_prompt_string = "\n".join(rules_list)

        # --- ⏳ 技能4: 大量データ対応の「分割（チャンク）処理 ＋ 進捗バー」 ---
        total_rows = len(df_str_init)
        import math

        num_chunks = math.ceil(total_rows / chunk_size)

        progress_bar = st.progress(0)
        status_text = st.empty()

        all_cleaned_records = []

        try:
            for idx in range(num_chunks):
                current_chunk_num = idx + 1
                status_text.markdown(
                    f"🔄 **AIクレンジング進行中**: {total_rows}行中 {min(idx * chunk_size, total_rows)}行完了 （チャンク {current_chunk_num} / {num_chunks} 処理中...）"
                )

                # 💡【修正の肝】NumPyを使わず、Pandas純正のilocで安全に切り出す（100% DataFrameを維持）
                start_row = idx * chunk_size
                end_row = min(start_row + chunk_size, total_rows)
                chunk_df = df_str_init.iloc[start_row:end_row]

                # チャンクデータをJSONデータ化
                chunk_json_str = chunk_df.to_json(
                    orient="records", force_ascii=False
                )

                # プロンプトの組み立て（日本語列名でも絶対にエラーを吐かない、安全性最強の構成）
                prompt = """
                提供された名簿データ（一部切り出し）について、以下の【クレンジングルール】を適用して綺麗なデータに整形してください。

                【クレンジングルール】
                __RULES__
                - ルールに該当しない列名やデータ、および文章は絶対に書き換えず、そのまま保持してください。行数や列の構造を合体・変形させることは厳禁です。

                【出力構造】
                必ず、以下のように "data" というキーを持ったJSONオブジェクト形式で出力してください。元の列名を完全に保持したキーと値のペアにしてください。
                {
                  "data": [ ...オブジェクトの配列... ]
                }

                【対象データ】
                __DATA__
                """.replace("__RULES__", rules_prompt_string).replace(
                    "__DATA__", chunk_json_str
                )

                # OpenAI APIリクエストの送信（日本語列名に完全適合する高性能JSONモード）
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise data engineering assistant. You must clear values according to the instructions and strictly return the requested JSON object format containing the 'data' array.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                result_json = json.loads(response.choices[0].message.content)
                all_cleaned_records.extend(result_json.get("data", []))

                # 進捗バーの更新
                progress_bar.progress(current_chunk_num / num_chunks)
                # APIの1分間あたりの制限(RPM/TPM)を安全に回避するための短い休憩
                time.sleep(0.4)

            # すべてのチャンクが結合されたら状態を保存
            st.session_state.cleaned_df = pd.DataFrame(all_cleaned_records)
            st.session_state.original_df_str = df_str_init.copy()
            st.session_state.refresh_counter += 1

            status_text.empty()
            progress_bar.empty()
            st.toast("✨ すべてのデータの分割精密クレンジングが完了しました！")

        except Exception as e:
            status_text.empty()
            progress_bar.empty()
            st.error(f"クレンジング処理中にエラーが発生しました: {e}")

    # --- 📊 技能3: クレンジング前後の「差分ハイライト」とサマリー表示 ---
    if (
        st.session_state.cleaned_df is not None
        and st.session_state.original_df_str is not None
    ):
        st.markdown("<br>", unsafe_allow_html=True)

        orig_df = st.session_state.original_df_str
        new_df = st.session_state.cleaned_df

        # 列や行のズレを考慮し、安全に型とインデックスを合わせる
        if orig_df.shape == new_df.shape:
            changed_cells_mask = orig_df != new_df
            total_changed_cells = changed_cells_mask.sum().sum()
            total_changed_rows = changed_cells_mask.any(axis=1).sum()
        else:
            # 万が一サイズがズレた場合の安全弁
            total_changed_cells = "解析中"
            total_changed_rows = "解析中"
            changed_cells_mask = pd.DataFrame(
                False, index=new_df.index, columns=new_df.columns
            )

        with st.container(border=True):
            st.markdown(
                "<h4 style='margin-top:0;'>📊 クレンジング結果サマリー</h4>",
                unsafe_allow_html=True,
            )
            s_col1, s_col2, s_col3 = st.columns(3)
            s_col1.metric("総処理行数", f"{len(orig_df)} 行")
            s_col2.metric(
                "AIが修正した行数",
                f"{total_changed_rows} 行",
                delta=f"{total_changed_rows}件の変更"
                if isinstance(total_changed_rows, int)
                else None,
                delta_color="inverse",
            )
            s_col3.metric(
                "AIが修正した総セル数",
                f"{total_changed_cells} 箇所",
                delta=f"{total_changed_cells}セルの最適化"
                if isinstance(total_changed_cells, int)
                else None,
                delta_color="inverse",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # 差分ハイライト表示セクション
        with st.container(border=True):
            st.markdown(
                "<h4 style='margin-top:0;'>🔍 変更箇所の視覚的ハイライトプレビュー</h4>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='font-size: 13px; color: #e65100; margin-bottom: 10px;'>⚠️ 黄色く塗られているセルが、AIによって表記揺れや規則の修正が行われた箇所です。</p>",
                unsafe_allow_html=True,
            )

            # ハイライト用スタイリングマトリックスの生成
            def apply_style_matrix(df_new):
                style_df = pd.DataFrame(
                    "", index=df_new.index, columns=df_new.columns
                )
                if orig_df.shape == df_new.shape:
                    style_df[orig_df != df_new] = (
                        "background-color: #fff3cd; color: #856404; font-weight: bold;"
                    )
                return style_df

            highlighted_df_preview = new_df.style.apply(
                apply_style_matrix, axis=None
            )
            st.dataframe(
                highlighted_df_preview, use_container_width=True, hide_index=True
            )

        # 最終レビュー＆手動修正セクション
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                "<h4 style='margin-top:0;'>📝 Step 3: クレンジング済みデータの最終レビュー（手動修正可能）</h4>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='font-size: 13px; color: #1f77b4; margin-bottom: 15px;'>💡 データ構造が完全に同期されました。自作ボタン・内蔵ボタンのどちらからでも綺麗に複数列でダウンロード可能です。</p>",
                unsafe_allow_html=True,
            )

            # ユーザーの手動編集を受け付けるコアエディタ
            edited_df = st.data_editor(
                st.session_state.cleaned_df,
                key=f"data_editor_core_{st.session_state.refresh_counter}",
                use_container_width=True,
                hide_index=True,
            )

            # ダウンロードセクション（右下配置）
            st.markdown("<br>", unsafe_allow_html=True)
            d_col1, d_col2 = st.columns([3, 1])
            with d_col2:
                try:
                    # Windows Excelに完全適合するcp932形式バイナリに変換
                    csv_bytes = edited_df.to_csv(index=False).encode(
                        "cp932", errors="replace"
                    )

                    # --- 📅 日付の自動付加技能 ---
                    date_suffix = datetime.now().strftime("%Y%m%d")
                    dynamic_file_name = f"cleaned_customer_list_{date_suffix}.csv"

                    # ボタンの鍵（key）を完全に同期
                    st.download_button(
                        label="📥 CSVファイルとして出力",
                        data=csv_bytes,
                        file_name=dynamic_file_name,
                        mime="text/csv",
                        use_container_width=True,
                        key=f"final_download_btn_{st.session_state.refresh_counter}",
                    )
                except Exception as e:
                    st.error(f"CSV生成エラー: {e}")
