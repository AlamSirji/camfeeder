FROM alexxit/go2rtc:latest

RUN apk add --no-cache py3-yaml

WORKDIR /app
COPY app/ /app/
COPY go2rtc/base.yaml /app/go2rtc/base.yaml

ENV CAMERAS_CONFIG=/config/cameras.yml \
    DASHBOARD_PORT=200

EXPOSE 200

ENTRYPOINT ["/usr/bin/python3", "/app/entrypoint.py"]
