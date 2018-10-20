import logging
import asyncssh
import aiohttp


CONTAINER_API_URL = 'http://localhost/containers/json'


class Container:

    def __init__(self, name, image, state, status, ports, net_settings):
        self.name = name
        self.image = image
        self.state = state
        self.status = status
        self.fwd_host = None
        self._ports = ports
        self._ports_info = self._ports[0] if self._ports else {}
        self._net_settings = net_settings

    @property
    def ports(self):
        ports = ''
        if self._ports_info:
            ports = '{p_h}:{p_p}:{pr_p}'.format(p_h=self.public_host, p_p=self.public_port or '', pr_p=self.private_port or '')
        return ports

    @property
    def public_host(self):
        return self._ports_info.get('IP', '')

    @property
    def public_port(self):
        return int(self._ports_info.get('PublicPort', 0))

    @property
    def private_port(self):
        return int(self._ports_info.get('PrivatePort', 0))

    @property
    def private_host(self):
        ifss = self._net_settings.get('Networks', {})
        try:
            ifs = ifss.popitem()[1]
        except KeyError:
            ifs = {}
        host = ifs.get('IPAddress', '')
        return host

    async def forward(self, host, user, fwd_host, client_keys):
        logging.info('forward container')
        connection = await asyncssh.connect(host, username=user, client_keys=client_keys)

        listener = await connection.forward_local_port(str(fwd_host), self.private_port,self.private_host,
                                                       self.private_port)
        self.fwd_host = fwd_host
        return listener

    def __repr__(self):
        return f'<Container(name={self.name}, image={self.image}, state={self.state}, status={self.status}, ' \
               f'public_host={self.public_host}, public_port={self.public_port}, private_host={self.private_host},' \
               f'private_port={self.private_port})>'


async def get_containers(host, all_states=False, timeout=5.0):
    ux_socket = host + '.sock'
    connector = aiohttp.UnixConnector(path=ux_socket)
    async with aiohttp.ClientSession(connector=connector, raise_for_status=True, ) as session:
        async with session.get(CONTAINER_API_URL, params={'all': 'true' if all_states else 'false'}, timeout=timeout) as resp:
            data = await resp.json()

    containers = []
    for info in data:
        containers.append(Container(info['Names'][0], info['Image'], info['State'], info['Status'],
                                    info.get('Ports', list()), info.get('NetworkSettings', dict())))

    return containers
