import asyncio


SEPARATOR = '<|>'
STS_RUNNNING = ' -f "status=running"'
STS_OTHERS = ' -f "status=created" -f "status=restarting" -f "status=removing" -f "status=paused" -f "status=exited"' \
             ' -f "status=dead"'
CMD = 'docker ps --format="{{.Names}}%s{{.Ports}}%s{{.Status}}%s{{.Image}}"' % (SEPARATOR, SEPARATOR, SEPARATOR)
#--format='{{(index .Spec.EndpointSpec.Ports 0).PublishedPort}}'


class ContainerInfo:
    def __init__(self, name, status, image, public_host, public_port, host):
        self.name = name
        self.image = image
        self.status = status
        self.host = host
        self.public_host = public_host
        self.public_port = public_port

    @staticmethod
    async def get_all_from_host(host, conn, others=False):
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
                line = line.split(SEPARATOR)

                ci = ContainerInfo()
                cons_info.append(ci)
        except Exception:
            logging.exception('')

        return cons_info
