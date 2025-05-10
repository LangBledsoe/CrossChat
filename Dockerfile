FROM python:3.10-slim
WORKDIR /app
COPY webhook.py requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8080
ENV FLASK_APP=webhook.py
CMD ["gunicorn", "-k", "gevent", "-b", "0.0.0.0:8080", "webhook:app"]