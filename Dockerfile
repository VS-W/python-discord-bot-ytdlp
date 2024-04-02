FROM python:3.10-bullseye

RUN apt-get -y update
RUN apt-get install -y ffmpeg

ARG USER_ID
ARG GROUP_ID

RUN addgroup --gid $GROUP_ID user
RUN adduser --disabled-password --gecos '' --uid $USER_ID --gid $GROUP_ID user

USER user

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY options.json options.json
COPY run.sh run.sh
COPY bot.py bot.py

# COPY . .

CMD ["bash", "run.sh"]
