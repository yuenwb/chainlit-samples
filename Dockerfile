FROM python:3.13.3-slim-bookworm

WORKDIR /app

COPY requirements.txt ./
COPY chainlit.md ./
COPY main.py ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENTRYPOINT ["chainlit", "run", "-h", "--host=0.0.0.0", "--port=8080", "main.py"]