FROM --platform=linux/amd64 python:3.11

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    CELERY_BROKER_URL=sqs:// \
    CELERY_RESULT_BACKEND=db+sqlite:///results.sqlite

# Set working directory
WORKDIR /app

COPY . .

# Install dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]