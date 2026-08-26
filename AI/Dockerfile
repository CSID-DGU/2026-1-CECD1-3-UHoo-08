FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# CPU 전용 torch를 먼저 설치한다.
# FlagEmbedding이 끌어오는 기본 torch는 CUDA 빌드라 nvidia-* 패키지가 4~5GB 붙는데,
# EC2에 GPU가 없어 전혀 쓰이지 않는다. 아래에서 이미 만족되므로 재설치되지 않는다.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    torch

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]