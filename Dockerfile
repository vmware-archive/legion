FROM saltstack/salt:3000

RUN apk --no-cache add git
RUN mkdir -p /opt/salt/legion
WORKDIR /opt/salt/legion

COPY . .
RUN python3 -m pip install .

ENTRYPOINT ["/usr/bin/legion"]
