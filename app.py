import gradio as gr
from openai import OpenAI
import tempfile
from pydub import AudioSegment
from gtts import gTTS
import os

# セキュリティ対策：APIキーはRenderの管理画面から環境変数として読み込む
api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

INTERNAL_MANUAL = """
【コンベア異常停止対応マニュアル：VCA-007】
まずはメイン電源の非常停止ボタンが押されているか確認せよ。
次にコンベアのローラー部に異物（梱包テープの破片など）が巻き込まれていないか目視で確認せよ。
さらにモーターの温度を確認し、熱暴走している場合は冷却を待って再起動を試みよ。
解決しない場合は、直ちに保全担当の佐藤を呼び出し、勝手に分解修理を行ってはならない。
"""

def process_inside_dx_rag(audio_path):
    if not audio_path:
        return "マイクを確認できません。", None
    
    try:
        audio = AudioSegment.from_file(audio_path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            audio.export(tmp_wav.name, format="wav")
            clean_audio_path = tmp_wav.name

        with open(clean_audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=f, language="ja",
                prompt="ニックス、コンベア、異常、対応"
            )
        user_text = transcript.text.strip()
        
        if not any(target in user_text for target in ["ニックス", "ニクス", "ニック"]):
            error_msg = "ご用件は「ニックス」と呼びかけてからお話しください。"
            tts = gTTS(text=error_msg, lang='ja')
            tts.save("error.mp3")
            return error_msg, "error.mp3"

        system_prompt = f"""
        あなたは現場の職人をサポートするAIパートナーです。
        以下のマニュアル情報をもとに、箇条書きや番号付きリストは一切使わず、自然な話し言葉（です・ます調）の文章だけで回答してください。
        また、文章を強調するための太字や記号も一切使用しないでください。
        「まずは〜」「次に〜」のように、職人に隣で話しかけるような優しいトーンで説明してください。

        【社内マニュアル】
        {INTERNAL_MANUAL}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
        )
        reply = response.choices[0].message.content

        reply = reply.replace("*", "").replace("#", "")

        tts = gTTS(text=reply, lang='ja')
        tts.save("response.mp3")
        
        return f"認識: {user_text}\n\nEYES回答:\n{reply}", "response.mp3"

    except Exception as e:
        return f"エラー: {str(e)}", None

with gr.Blocks(theme=gr.themes.Soft()) as app:
    gr.Markdown("# Inside DX : 音声対話プロトタイプ")
    
    audio_in = gr.Audio(sources=["microphone"], type="filepath", label="マイク")
    out_text = gr.Markdown("待機中...")
    out_audio = gr.Audio(label="現場への回答", autoplay=True) 
    
    audio_in.stop_recording(
        fn=process_inside_dx_rag,
        inputs=[audio_in],
        outputs=[out_text, out_audio]
    )

# サーバー環境向けの設定（0.0.0.0でポート10000を開放）
if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=10000)
