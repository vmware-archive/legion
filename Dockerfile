FROM python:3.6-slim as builder

RUN mkdir /install
WORKDIR /install

COPY . .

RUN apt-get update && \
    apt-get install -y gcc && \
    pip install --prefix=/install -r requirements.txt && \
    pip install --prefix=/install .

FROM python:3.6-slim
COPY --from=builder /install /usr/local

ENTRYPOINT ["legion"]
