import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from itertools import chain
from terminaltables import AsciiTable
from containers import ContainerInfo


FWD_HOST = '127.0.0.1'
FWD_PORT_BASE = 10000
TIMEOUT = 60
CONN_TIMEOUT = 10
CONFIG_FILE = '~/.ssh/config'


def get_creds_from_config(file_name):
    creds = []
    with open(Path(file_name).expanduser().as_posix(), 'r') as file:
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
                    creds.append((host, user))
    return creds


async def start_forwarding(ci):
    pport = FWD_PORT_BASE + ci.public_port
    try:
        listener = await asyncio.wait_for(ci.connection.forward_local_port(FWD_HOST, pport, ci.public_host, ci.public_port),
                                          timeout=CONN_TIMEOUT)
        await listener.wait_closed()
    except:
        logging.exception('')


async def main(config_file, all_=False, client_keys=(), port_forward=False, timeout=TIMEOUT):
    creds = get_creds_from_config(config_file)
    done, pending = await asyncio.wait([asyncssh.connect(host, username=user, client_keys=client_keys)
                                        for host, user in creds],
                                       timeout=CONN_TIMEOUT)
    connections = {}
    for t in done:
        conn = t.result()
        connections[conn._host] = conn

    while True:
        print("\033c")
        table_data = [['Host', 'Names', 'Ports', 'Status', 'Image'], ]
        f = asyncio.gather(*[ContainerInfo.get_all(host, conn) for host, conn in connections.items()])
        results = await asyncio.wait_for(f, None)
        table_data.extend((ci.host, ci.name, ci.ports, ci.status, ci.image) for ci in chain(*results))

        if port_forward:
            for ci in chain(*results):
                if ci.public_host and ci.public_host != '0.0.0.0':
                    asyncio.ensure_future(start_forwarding(ci))
            port_forward = False  # разовое установление перенаправления

        if all_:
            table_data.append(['', '', '', '', ''])
            table_data.append(['', '', '', '', ''])
            f = asyncio.gather(*[ContainerInfo.get_all(host, user, others=True) for host, user in creds])
            results = await asyncio.wait_for(f, None)
            for r in results:
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
