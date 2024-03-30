FROM python:alpine3.7

WORKDIR /app

RUN apk --no-cache add make
RUN pip install gunicorn
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000
CMD gunicorn -b 0.0.0.0:5000 --access-logfile - --error-logfile - 'app:create_app()'
# enable websockets
# CMD gunicorn -b 0.0.0.0:5000 --worker-class eventlet -w 1 --access-logfile - --error-logfile - 'app:create_socket_app()()'
