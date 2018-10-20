import argparse
import asyncio
import logging
import asyncssh
import constants as cnst
from ipaddress import IPv4Network
from collections import defaultdict
from terminaltables import AsciiTable
from containers import get_containers
from utils.config_data import get_host_user_pairs


FWD_HOSTS = IPv4Network('127.0.0.0/24').hosts()
TIMEOUT = 60
CONFIG_FILE = '~/.ssh/config'
DOCKER_SOCKET = '/var/run/docker.sock'


def _set_host():
    return next(FWD_HOSTS)


def read_container_names(file_name):
    if not file_name:
        return []
    with open(file_name) as file:
        return [name.strip() for name  in file]


async def forward_docker_socket(host, user, client_keys=()):
    ux_socket = host + '.sock'
    logging.info('forward ' + ux_socket)
    connection = await asyncssh.connect(host, username=user, client_keys=client_keys)

    listener = await connection.forward_local_path(ux_socket, DOCKER_SOCKET)
    return host, user, listener


async def main(config_file, all_states=False, client_keys=(), fwd_containers_file='', timeout=TIMEOUT):
    hu_pairs = get_host_user_pairs(config_file)

    docker_socket_tasks = []
    for host, user in hu_pairs:
        task = asyncio.ensure_future(forward_docker_socket(host, user, client_keys))
        docker_socket_tasks.append(task)

    d_done, d_pending = await asyncio.wait(docker_socket_tasks, timeout=cnst.CONN_TIMEOUT+2)
    logging.info('sockets are forwarded: done {}, pending {}'.format(len(d_done), len(d_pending)))
    d_done = [t for t in d_done if not t.exception()]

    table_header = ['Host', 'Names', 'State', 'Status', 'Ports', 'Image']
    forwardings = []
    fwd_container_names = read_container_names(fwd_containers_file)
    def _filter_forwardings(containers):
        if not fwd_container_names:
            return containers

        filtered = []
        for c in containers:
            if any(name in c.name for name in fwd_container_names):
                filtered.append(c)
        return filtered

    for task in d_done:
        host, user, listener = task.result()
        containers = await get_containers(host, all_states=all_states)
        forwardings.append({'host': host, 'user': user,
                            'containers': containers})
        listener.close()

    listeners = []
    if fwd_container_names:
        table_header.append('Tunnel')
        container_tasks = []
        fwd_hosts = defaultdict(_set_host)
        for f in forwardings:
            fwd_host = fwd_hosts[f['host']]
            for c in _filter_forwardings(f['containers']):
                if not c.private_port: continue
                task = asyncio.ensure_future(c.forward(f['host'], f['user'], fwd_host, client_keys=client_keys))
                container_tasks.append(task)

        c_done, c_pending = await asyncio.wait(container_tasks, timeout=cnst.CONN_TIMEOUT+2)
        logging.info('containers are forwarded: done {}, pending {}'.format(len(c_done), len(c_pending)))
        c_done = [t for t in c_done if not t.exception()]
        listeners.extend(t.result() for t in c_done)

        # if all_states:
        #     table_data.append(['', '', '', '', ''])
        #     table_data.append(['', '', '', '', ''])
        #     f = asyncio.gather(*[ContainerInfo.get_all(host, user, only_running=True) for host, user in hu_pairs])
        #     ci_batches = await asyncio.wait_for(f, None)
        #     for r in ci_batches:
        #         table_data.extend(r)

    table_data = [table_header]
    for f in forwardings:
        for c in f['containers']:
            row = [f['host'], c.name, c.state, c.status, c.ports, c.image]
            if fwd_container_names and c.fwd_host:
                forward_repr = f'{c.fwd_host}:{c.public_port}:{c.private_host}:{c.private_port}'
                row.append(forward_repr)
            table_data.append(row)

    table = AsciiTable(table_data)
    print(table.table)

    if not fwd_container_names:
        for l in listeners:
            l.close()

    await asyncio.wait([l.wait_closed() for l in listeners])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('private_key')
    parser.add_argument('-cfg', '--config-file',  default=CONFIG_FILE)
    parser.add_argument('--all', action='store_true', dest='all')
    parser.add_argument('--fwd-file', dest='fwd_containers_file')
    parser.add_argument('--timeout', type=int, default=TIMEOUT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    asyncio.get_event_loop().run_until_complete(main(args.config_file, args.all, [args.private_key],
                                                     args.fwd_containers_file, args.timeout))
