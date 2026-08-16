FROM alexxit/go2rtc:latest

RUN apk add --no-cache py3-yaml

WORKDIR /app
COPY app/ /app/
COPY go2rtc/base.yaml /app/go2rtc/base.yaml

EXPOSE 200
VOLUME ["/config"]

ENTRYPOINT ["/usr/bin/python3", "/app/entrypoint.py"]
