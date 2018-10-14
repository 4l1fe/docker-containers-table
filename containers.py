import logging
import asyncio
import asyncssh
import aiohttp
import constants as cnst


class Container:

    def __init__(self, name, image, state, status, ports):
        self.name = name
        self.image = image
        self.state = state
        self.status = status
        self.fwd_host = None
        self._ports = ports
        self._network_info = self._ports[0] if self._ports else {}

    @property
    def ports(self):
        ports = ''
        if self._network_info:
            ports = '{p_h}:{p_p}:{pr_p}'.format(p_h=self.public_host, p_p=self.public_port or '', pr_p=self.private_port or '')
        return ports

    @property
    def public_host(self):
        return self._network_info.get('IP', '')

    @property
    def public_port(self):
        return int(self._network_info.get('PublicPort', 0))

    @property
    def private_port(self):
        return int(self._network_info.get('PrivatePort', 0))

    async def forward(self, host, user, fwd_host, client_keys):
        logging.info('forward container')
        connection = await asyncssh.connect(host, username=user, client_keys=client_keys)

        listener = await connection.forward_local_port(str(fwd_host), self.public_port, self.public_host,
                                                       self.public_port)
        self.fwd_host = fwd_host
        return listener

    def get_forwarding_data(self, host):
        pass

    def __repr__(self):
        return f'<Container(name={self.name}, image={self.image}, state={self.state}, status={self.status}, ' \
               f'public_host={self.public_host}, public_port={self.public_port}, private_port={self.private_port})>'


async def get_containers(host, all_states=False, timeout=5.0):
    ux_socket = host + '.sock'
    connector = aiohttp.UnixConnector(path=ux_socket)
    async with aiohttp.ClientSession(connector=connector, raise_for_status=True, ) as session:
        async with session.get('http://localhost/containers/json',
                               params={'all': 'true' if all_states else 'false'}, timeout=timeout) as resp:
            data = await resp.json()

    containers = []
    for info in data:
        containers.append(Container(info['Names'][0], info['Image'], info['State'], info['Status'],
                                    info.get('Ports', list())))

    return containers
