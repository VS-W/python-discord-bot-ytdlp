FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

ARG USER_ID
ARG GROUP_ID

RUN addgroup --gid $GROUP_ID user
RUN adduser --disabled-password --gecos '' --uid $USER_ID --gid $GROUP_ID user

USER user

WORKDIR /app

COPY app/requirements.txt requirements.txt
COPY app/run.sh run.sh

RUN pip install --no-warn-script-location -r requirements.txt

CMD ["bash", "run.sh"]
