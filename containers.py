import logging
import asyncio


SEPARATOR = '<|>'
STS_RUNNNING = ' -f "status=running"'
STS_OTHERS = ' -f "status=created" -f "status=restarting" -f "status=removing" -f "status=paused" -f "status=exited"' \
             ' -f "status=dead"'
CMD = 'docker ps --format="{{.Names}}%s{{.Ports}}%s{{.Status}}%s{{.Image}}"' % (SEPARATOR, SEPARATOR, SEPARATOR)
#--format='{{(index .Spec.EndpointSpec.Ports 0).PublishedPort}}'


class ContainerInfo:

    def __init__(self, name, status, image, ports, public_host, public_port, host):
        self.name = name
        self.image = image
        self.status = status
        self.ports = ports
        self.public_host = public_host
        self.public_port = public_port
        self.host = host

    @staticmethod
    async def get_all(host, conn, others=False):
        cons_info = []
        try:
            cmd = CMD + STS_RUNNNING
            if others:
                cmd = CMD + STS_OTHERS

            result = await asyncio.wait_for(conn.run(cmd, check=True), timeout=10)

            lines = result.stdout.splitlines()
            if not lines:
                return cons_info

            for line in lines[1:]:
                name, ports, status, image = line.split(SEPARATOR)
                hp_str = ports.split('->')[0]
                pub_host, pub_port = '', ''
                if ':' in hp_str:
                    pub_host, pub_port = hp_str.split(':')
                ci = ContainerInfo(name, status, image, ports, pub_host, pub_port, host)
                cons_info.append(ci)
        except Exception:
            logging.exception('')

        return cons_info
