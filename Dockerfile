# TA-Lib's Python wheel needs the underlying C library, which isn't
# available on Render's native Python buildpack. Building via Docker
# lets us compile it ourselves in one clean step.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential wget \
    && wget -q https://sourceforge.net/projects/ta-lib/files/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make -s \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz \
    && apt-get purge -y wget \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "uvicorn admin.server:app --host 0.0.0.0 --port ${PORT}"]
