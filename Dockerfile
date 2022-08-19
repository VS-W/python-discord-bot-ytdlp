FROM python:3.10-bullseye

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

COPY . .

CMD ["bash", "run.sh"]
