FROM lsiobase/alpine:3.17 as base

WORKDIR /usr/src/app

RUN \
	apk add --no-cache \
		python3 \
		python3-dev \
		py3-pip \
		gcc \
		musl-dev
RUN \
	python3 -m ensurepip && \
  pip3 install -U --no-cache-dir \
	  pip \
	  wheel

COPY . .

RUN \
  pip3 install /usr/src/app


EXPOSE 8080
WORKDIR /data

ENTRYPOINT python3 -m signalGPT.web
