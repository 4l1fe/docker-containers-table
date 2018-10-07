import aiohttp


class Container:

    def __init__(self, info):
        self.name = info['Names'][0]
        self.image = info['Image']
        self.state = info['State']
        self.status = info['Status']
        self._ports = info.get('Ports', list())
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

    def __repr__(self):
        return '<Container(name={c.name}, image={c.image}, state={c.state}, status={c.status}, ' \
               'public_host={c.public_host}, public_port={c.public_port}, ' \
               'private_port={c.private_port})>'.format(c=self)


async def get_containers(host, all_states=False, timeout=5):
    ux_socket = host + '.sock'
    connector = aiohttp.UnixConnector(path=ux_socket)
    async with aiohttp.ClientSession(connector=connector, raise_for_status=True) as session:
        async with session.get('http://localhost/containers/json',
                               params={'all': 'true' if all_states else 'false'}) as resp:
            data = await resp.json()

    containers = []
    for c_info in data:
        containers.append(Container(c_info))

    return containers
