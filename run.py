import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from itertools import chain
from ipaddress import IPv4Network
from collections import defaultdict
from terminaltables import AsciiTable
from containers import get_containers


FWD_NETWORK = IPv4Network('127.0.0.0/24')
TIMEOUT = 60
CONN_TIMEOUT = 10
CONFIG_FILE = '~/.ssh/config'


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


# def forward_containers(hu_pairs, client_keys=()):
#
#     async def _forward(ci, fwd_host):
#         connection = await asyncio.wait_for(asyncssh.connect(host, username=user, client_keys=client_keys),
#                                             timeout=CONN_TIMEOUT)
#
#         listener = await asyncio.wait_for(connection.forward_local_path(ux_socket, '/var/run/docker.sock'),
#                                           timeout=CONN_TIMEOUT)
#
#             listener = await asyncio.wait_for(ci.connection.forward_local_port(str(fwd_host), ci.public_port,
#                                                                                ci.public_host, ci.public_port),
#                                               timeout=CONN_TIMEOUT)
#             await listener.wait_closed()
#         except:
#             logging.exception('')
#
#     hosts = FWD_NETWORK.hosts()
#     def set_host():
#         return next(hosts)
#
#     fwd_hosts = defaultdict(set_host)
#     for ci in ci_list:
#         if not ci.public_host or ci.public_host == '0.0.0.0':
#             continue
#
#         fwd_host = fwd_hosts[ci.host]
#         asyncio.ensure_future(_forward(ci, fwd_host))


def forward_docker_sockets(hu_pairs, client_keys=()):

    async def _forward(host, user, client_keys=()):
        ux_socket = host + '.sock'
        logging.info('forward ' + ux_socket)
        connection = await asyncio.wait_for(asyncssh.connect(host, username=user, client_keys=client_keys), timeout=CONN_TIMEOUT)

        listener = await asyncio.wait_for(connection.forward_local_path(ux_socket, '/var/run/docker.sock'), timeout=CONN_TIMEOUT)
        return host, user, listener
        # await listener.wait_closed()

    tasks = []
    for host, user in hu_pairs:
        tasks.append(asyncio.ensure_future(_forward(host, user, client_keys)))

    return tasks

#
# async def forward_containers(hu_pairs, client_keys=()):
#     connections = {}
#     done, pending = await asyncio.wait([asyncssh.connect(host, username=user, client_keys=client_keys)
#                                         for host, user in hu_pairs],
#                                        timeout=CONN_TIMEOUT)
#     for t in done:
#         conn = t.result()
#         connections[conn._host] = conn
#
#     return connections


# class FwdRegister(dict):



async def main(config_file, all_states=False, client_keys=(), port_forward=False, timeout=TIMEOUT):
    hu_pairs = get_host_user_pairs(config_file)

    docker_socket_tasks = forward_docker_sockets(hu_pairs, client_keys)
    logging.info('sockets forwarded')

    done, pending = await asyncio.wait(docker_socket_tasks, timeout=TIMEOUT+2)

    forwardeds = []
    for task in done:
        if task.exception():
            continue
        host, user, listener = task.result()
        containers = await get_containers(host, all_states=all_states)
        forwardeds.append({'host': host, 'user': user, 'docker_listener': listener, 'containers': containers})

    # await asyncio.wait([fwd['docker_listener'].wait_closed() for fwd in forwardeds])

    while True:
        print("\n")
        table_header = ('Host', 'Names', 'State', 'Status', 'Ports', 'Image')
        table_data = [table_header]

        # (name=c_info['Names'][0],
        # state=c_info['State'],
        # status=c_info['Status'],
        # image=c_info['Image'],
        # public_host=network_info.get('IP', None),
        # public_port = network_info.get('PublicPort', None),
        #               private_port = network_info.get('PrivatePort', None))
        # if port_forward:
        #     forward_containers(chain(*ci_batches))
        #     port_forward = False  # разовое установление перенаправления
        for f in forwardeds:
            table_data.extend( tuple((f['host'], c.name, c.state, c.status, c.ports, c.image) for c in f['containers']) )

        # if all_states:
        #     table_data.append(['', '', '', '', ''])
        #     table_data.append(['', '', '', '', ''])
        #     f = asyncio.gather(*[ContainerInfo.get_all(host, user, only_running=True) for host, user in hu_pairs])
        #     ci_batches = await asyncio.wait_for(f, None)
        #     for r in ci_batches:
        #         table_data.extend(r)

        table = AsciiTable(table_data)

        print(table.table)
        await asyncio.sleep(timeout)


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
