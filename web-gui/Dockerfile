FROM python:3.10.6

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY flaskr flaskr
ENV FLASK_APP="flaskr"

CMD [ "flask", "run", "--host=0.0.0.0", "--port=80" ]
