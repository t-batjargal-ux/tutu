import json
import google.generativeai as genai
import pandas as pd
import streamlit as st

# 1. ページ全体をワイドモードに設定
st.set_page_config(layout="wide")

st.title("✨ AIデータクレンジング・アシスタント")
st.write("アップロードされたCSVデータを、Gemini APIを利用して自動で表記揺れの修正や整形を行います。")

# 6. APIキーを st.secrets から取得し設定
try:
    if "GEMINI_API_KEY" not in st.secrets:
        st.error(
            "エラー: `GEMINI_API_KEY` が設定されていません。`.streamlit/secrets.toml` ファイルを確認してください。"
        )
        st.stop()

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"APIの初期化中にエラーが発生しました: {e}")
    st.stop()

# 2. CSVファイルのみをアップロードできるように設定
uploaded_file = st.file_uploader(
    "クレンジングしたいCSVファイル（Shift_JIS / cp932）を選択してください",
    type=["csv"],
)

# Streamlitの再実行によるデータ消失を防ぐため、セッション状態で整形後データを管理
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None

if uploaded_file is not None:
    # 3. ファイルを cp932 で読み込み、プレビュー表示
    try:
        # 毎回再読み込みされるのを防ぐ、または常に最新の状態を参照
        df = pd.read_csv(uploaded_file, encoding="cp932")
        st.subheader("📋 アップロードデータのプレビュー")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(
            f"CSVファイルの読み込みに失敗しました。エンコーディングが「cp932（Shift_JIS）」であることを確認してください。エラー: {e}"
        )
        st.stop()

    # 4. クレンジング一括実行ボタンの配置
    if st.button("🚀 クレンジングを一括実行する", type="primary"):
        # 4. ボタン押下時にスピナーを表示
        with st.spinner("Geminiがデータを整形中..."):
            try:
                # 7. モデル（gemini-1.5-flash）の呼び出し
                model = genai.GenerativeModel("gemini-1.5-flash")

                # 8. 表データをJSON形式のテキストに変換 (orient='records' で扱いやすい配列に変換)
                data_json_str = df.to_json(orient="records", force_ascii=False)

                # 指示ルールのプロンプト作成
                prompt = f"""
以下のJSON形式のデータを、指定された【指示ルール】に従ってクレンジングし、元の構造（オブジェクトの配列）を維持したままJSON形式で返してください。

【指示ルール】
1. 「取引先名」の「㈱」や「(株)」はすべて「株式会社」に統一してください。
2. 「住所」の英数字や郵便番号、ハイフンはすべて半角に統一してください。
3. 必ず元の列名を完全に維持してください。
4. 出力は指定されたJSONデータのみとし、説明文やマークダウンの装飾（```json など）は含めないでください。

【対象データ】
{data_json_str}
"""

                # 9. 構造化出力を確実にするための generation_config 設定
                generation_config = {"response_mime_type": "application/json"}

                # APIリクエストの送信
                response = model.generate_content(
                    prompt, generation_config=generation_config
                )

                # 10. 返ってきたJSONテキストをパースしてDataFrameに再変換
                cleaned_json = json.loads(response.text)
                st.session_state.cleaned_df = pd.DataFrame(cleaned_json)

                st.success("✨ クレンジング処理が正常に完了しました！")

            except json.JSONDecodeError as json_err:
                st.error(
                    f"Geminiからの応答をJSONとしてパースできませんでした。プロンプトやデータ量を見直してください。: {json_err}"
                )
                if "response" in locals() and hasattr(response, "text"):
                    with st.expander("APIからの生の応答データ"):
                        st.code(response.text)
            except Exception as e:
                st.error(f"クレンジング処理中に予期せぬエラーが発生しました: {e}")

    # 11. 整形後のデータを表示（セッション状態にデータがある場合）
    if st.session_state.cleaned_df is not None:
        st.markdown("---")
        st.subheader("📝 クレンジング済みデータ（手動修正が可能です）")

        # st.data_editor を使って画面上で手動修正を可能に
        edited_df = st.data_editor(
            st.session_state.cleaned_df,
            key="cleaned_data_editor",
            use_container_width=True,
        )

        # 12. ダウンロードボタンの配置とエラーハンドリング
        try:
            # 編集後のデータを cp932 でCSV文字列に変換
            csv_data = edited_df.to_csv(index=False, encoding="cp932")

            st.download_button(
                label="📥 クレンジング済みデータをダウンロード (CSV)",
                data=csv_data,
                file_name="cleaned_customer_list.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"ダウンロード用CSVの生成中にエラーが発生しました: {e}")
