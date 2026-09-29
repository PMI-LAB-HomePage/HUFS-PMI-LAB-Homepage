# PMI Lab 홈페이지 — Django + Gunicorn
# 데이터(SQLite·media)는 이미지에 넣지 않는다. compose가 볼륨으로 붙인다.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# requirements를 먼저 복사해야 코드만 바뀔 때 pip 레이어를 다시 받지 않는다
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 루트로 돌리지 않는다. /data와 staticfiles에 쓸 수 있어야 한다.
# --create-home 필수: 홈이 없으면 gunicorn이 기동할 때마다 Permission denied를 로그에 남긴다.
RUN useradd --system --uid 10001 --create-home --home-dir /home/pmilab pmilab \
 && mkdir -p /data/media /app/staticfiles \
 && chown -R pmilab:pmilab /data /app/staticfiles /home/pmilab
USER pmilab
ENV HOME=/home/pmilab

EXPOSE 8000
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3"]
