FROM python:3.8-alpine as base

# Requirements
FROM base as dep_builder
RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
RUN apk add --no-cache curl python3 pkgconfig python3-dev openssl-dev libffi-dev musl-dev make gcc
RUN pip3 install --prefix="/install" -r /requirements.txt


# Packer
FROM base as packer_builder
RUN mkdir /install
WORKDIR /install
ADD https://releases.hashicorp.com/packer/1.7.0/packer_1.7.0_linux_amd64.zip /tmp
RUN unzip /tmp/packer_1.7.0_linux_amd64.zip -d /install


# Final
FROM base
COPY --from=dep_builder /install /usr/local
COPY --from=packer_builder /install /usr/local
COPY . /app
WORKDIR /app 
LABEL maintainer="Nicolas Vogt <nicolas.vogt@monext.net>" \
      version="1.2"
CMD [ "python3", "./main.py"] 