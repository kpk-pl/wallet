FROM python:3.7.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ .
ENV FLASK_APP="main.py"

CMD [ "flask", "run", "--host=0.0.0.0", "--port=80" ]
