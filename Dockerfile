FROM python:3.11.6

WORKDIR /usr/src/logs_bot_py

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "./bot.py", "/access.log" ]
