import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from ipaddress import IPv4Network
from collections import defaultdict
from terminaltables import AsciiTable
from containers import get_containers


FWD_HOSTS = IPv4Network('127.0.0.0/24').hosts()
TIMEOUT = 60
CONN_TIMEOUT = 10
CONFIG_FILE = '~/.ssh/config'
DOCKER_SOCKET = '/var/run/docker.sock'


def _set_host():
    return next(FWD_HOSTS)


def get_host_user_pairs(config_file):
    host_user_pairs = []
    with open(Path(config_file).expanduser().as_posix(), 'r') as file:
        for line in file.readlines():
            if not line.strip(): continue

            stmnt, value = line.split()
            if stmnt == 'Host':
                pass_ = value.endswith('_')
            elif line.startswith('HostName'):
                host = line.split()[1]
            elif line.startswith('User'):
                user = line.split()[1]
                if not pass_ and user in ('root', 'dkrasnov'):
                    host_user_pairs.append((host, user))

    return host_user_pairs


def forward_containers(host, user, fwd_host, containers, client_keys=()):

    async def _forward(host, user, fwd_host, container):
        connection = await asyncio.wait_for(asyncssh.connect(host, username=user, client_keys=client_keys),
                                            timeout=CONN_TIMEOUT)

        listener = await asyncio.wait_for(connection.forward_local_port(str(fwd_host), container.public_port,
                                                                        container.public_host, container.public_port),
                                          timeout=CONN_TIMEOUT)
        return listener

    tasks = []
    for c in containers:
        if not c.public_host or c.public_host == '0.0.0.0':
            continue
        tasks.append(asyncio.ensure_future(_forward(host, user, fwd_host, c)))

    return tasks


def forward_docker_sockets(hu_pairs, client_keys=()):

    async def _forward(host, user, client_keys=()):
        ux_socket = host + '.sock'
        logging.info('forward ' + ux_socket)
        connection = await asyncio.wait_for(asyncssh.connect(host, username=user, client_keys=client_keys), timeout=CONN_TIMEOUT)

        listener = await asyncio.wait_for(connection.forward_local_path(ux_socket, DOCKER_SOCKET), timeout=CONN_TIMEOUT)
        return host, user, listener

    tasks = []
    for host, user in hu_pairs:
        tasks.append(asyncio.ensure_future(_forward(host, user, client_keys)))

    return tasks


async def main(config_file, all_states=False, client_keys=(), port_forward=False, timeout=TIMEOUT):
    listeners = []
    hu_pairs = get_host_user_pairs(config_file)

    docker_socket_tasks = forward_docker_sockets(hu_pairs, client_keys)
    logging.info('sockets are forwarded')

    d_done, d_pending = await asyncio.wait(docker_socket_tasks, timeout=CONN_TIMEOUT+2)
    print(d_pending, d_done)

    table_header = ['Host', 'Names', 'State', 'Status', 'Ports', 'Image']
    while True:
        print("\n")

        forwardings = []
        for task in d_done:
            if task.exception():
                logging.error('error')
                continue
            host, user, listener = task.result()
            containers = await get_containers(host, all_states=all_states)
            listeners.append(listener)
            forwardings.append({'host': host, 'user': user, 'containers': containers})

        if port_forward:
            port_forward = False  # разовое установление перенаправления
            table_header.append('Tunnel')
            container_tasks = []
            fwd_hosts = defaultdict(_set_host)
            for f in forwardings:
                fwd_host = fwd_hosts[f['host']]
                tasks = forward_containers(f['host'], f['user'], fwd_host, f['containers'], client_keys=client_keys)
                container_tasks.extend(tasks)
            logging.info('containers are forwarded')

            c_done, c_pending = await asyncio.wait(container_tasks, timeout=CONN_TIMEOUT+2)
            print(c_pending, c_done)

            for task in c_done:
                if task.exception():
                    logging.error('error')
                    continue
                listener = task.result()
                listeners.append(listener)

        # if all_states:
        #     table_data.append(['', '', '', '', ''])
        #     table_data.append(['', '', '', '', ''])
        #     f = asyncio.gather(*[ContainerInfo.get_all(host, user, only_running=True) for host, user in hu_pairs])
        #     ci_batches = await asyncio.wait_for(f, None)
        #     for r in ci_batches:
        #         table_data.extend(r)

        table_data = [table_header]
        for f in forwardings:
            table_data.extend([f['host'], c.name, c.state, c.status, c.ports, c.image] for c in f['containers'])
        table = AsciiTable(table_data)

        print(table.table)
        await asyncio.sleep(timeout)

    # logging.info('shutting down')
    # await asyncio.wait([l.wait_closed() for l in listeners])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('private_key')
    parser.add_argument('-c', '--config-file',  default=CONFIG_FILE)
    parser.add_argument('--all', action='store_true', dest='all')
    parser.add_argument('--fwd', action='store_true', dest='port_forward')
    parser.add_argument('--timeout', type=int, default=TIMEOUT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    asyncio.get_event_loop().run_until_complete(main(args.config_file, args.all, [args.private_key],
                                                     args.port_forward, args.timeout))
