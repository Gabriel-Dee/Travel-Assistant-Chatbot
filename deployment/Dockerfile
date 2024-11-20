FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9

COPY ./travel-assistant-chatbot /app

RUN pip install -r /app/requirements.txt

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
