FROM saltstack/salt:2019.2.2

RUN mkdir -p /opt/salt/legion
WORKDIR /opt/salt/legion

COPY . .

ENTRYPOINT ["/usr/bin/python3", "/opt/salt/legion/legion/legion.py"]
