FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# The CPU wheel: the default torch wheel pulls in gigabytes of CUDA libraries this app never uses.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
