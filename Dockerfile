FROM python:3.11

RUN apt-get update && apt-get install -y libraqm0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
