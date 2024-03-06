FROM lsiobase/alpine:3.19 as base

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
	    wheel \
	    lz4

COPY . .

RUN \
    pip3 install /usr/src/app


EXPOSE 8080
WORKDIR /data

ENTRYPOINT python3 -m signalGPT.web
