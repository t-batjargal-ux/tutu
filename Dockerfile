FROM python:3.10-slim

# 音声処理に必要なffmpegをインストール
RUN apt-get update && apt-get install -y ffmpeg

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . .

# ポートの開放
EXPOSE 10000

# アプリの起動
CMD ["python", "app.py"]
