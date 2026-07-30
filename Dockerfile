FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANGGRAPH_STRICT_MSGPACK=true

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY coach ./coach
COPY codebase ./codebase
COPY data/vlearn-pack/transcript ./data/vlearn-pack/transcript

USER app
EXPOSE 8000

CMD ["uvicorn", "coach.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
