import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from itertools import chain
from ipaddress import IPv4Network
from collections import defaultdict
from terminaltables import AsciiTable
from containers import ContainerInfo


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
                if not pass_ and user == 'root':
                    host_user_pairs.append((host, user))

    return host_user_pairs


async def _listen_forwaded(ci, fwd_host):
    try:
        listener = await asyncio.wait_for(ci.connection.forward_local_port(str(fwd_host), ci.public_port,
                                                                           ci.public_host, ci.public_port),
                                          timeout=CONN_TIMEOUT)
        await listener.wait_closed()
    except:
        logging.exception('')


def start_forwarding(ci_list):

    hosts = FWD_NETWORK.hosts()
    def set_host():
        return next(hosts)

    fwd_hosts = defaultdict(set_host)
    for ci in ci_list:
        if not ci.public_host or ci.public_host == '0.0.0.0':
            continue

        fwd_host = fwd_hosts[ci.host]
        asyncio.ensure_future(_listen_forwaded(ci, fwd_host))


async def make_connections(hu_pairs, client_keys=()):
    connections = {}
    done, pending = await asyncio.wait([asyncssh.connect(host, username=user, client_keys=client_keys)
                                        for host, user in hu_pairs],
                                       timeout=CONN_TIMEOUT)
    for t in done:
        conn = t.result()
        connections[conn._host] = conn

    return connections


async def main(config_file, all_=False, client_keys=(), port_forward=False, timeout=TIMEOUT):
    hu_pairs = get_host_user_pairs(config_file)

    connections = await make_connections(hu_pairs, client_keys)

    while True:
        print("\033c")

        f = asyncio.gather(*[ContainerInfo.get_all(host, conn) for host, conn in connections.items()])
        ci_batches = await asyncio.wait_for(f, None)

        table_data = [['Host', 'Names', 'Ports', 'Status', 'Image'], ]
        table_data.extend((ci.host, ci.name, ci.ports, ci.status, ci.image) for ci in chain(*ci_batches))

        if port_forward:
            start_forwarding(chain(*ci_batches))
            port_forward = False  # разовое установление перенаправления

        if all_:
            table_data.append(['', '', '', '', ''])
            table_data.append(['', '', '', '', ''])
            f = asyncio.gather(*[ContainerInfo.get_all(host, user, others=True) for host, user in hu_pairs])
            ci_batches = await asyncio.wait_for(f, None)
            for r in ci_batches:
                table_data.extend(r)

        table = AsciiTable(table_data)

        print(table.table)
        await asyncio.sleep(timeout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config-file',  default=CONFIG_FILE)
    parser.add_argument('-pk', '--private-key')
    parser.add_argument('--all', action='store_true', dest='all')
    parser.add_argument('--fwd', action='store_true', dest='port_forward')
    parser.add_argument('--timeout', type=int, default=TIMEOUT)
    args = parser.parse_args()
    logging.basicConfig()
    asyncio.get_event_loop().run_until_complete(main(args.config_file, args.all, [args.private_key],
                                                     args.port_forward, args.timeout))
