import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from terminaltables import AsciiTable
from containers import ContainerInfo


CLIENT_KEY = '/home/owner/.ssh/gitqpay'


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


async def main(all_=False, port_forward=False):
    creds = get_creds_from_config('~/.ssh/config')
    done, pending = await asyncio.wait([asyncssh.connect(host, username=user, client_keys=[CLIENT_KEY])
                                        for host, user in creds],
                                       timeout=10)
    connections = {}
    for t in done:
        conn = t.result()
        connections[conn._host] = conn

    while True:
        table_data = [['Host', 'Names', 'Ports', 'Status', 'Image'], ]
        f = asyncio.gather(*[ContainerInfo.get_all(host, conn) for host, conn in connections.items()])
        results = await asyncio.wait_for(f, None)
        for r in results:
            table_data.extend((ci.host, ci.name, ci.ports, ci.status, ci.image) for ci in r)

        if all_:
            table_data.append(['', '', '', '', ''])
            table_data.append(['', '', '', '', ''])
            f = asyncio.gather(*[ContainerInfo.get_all(host, user, others=True) for host, user in creds])
            results = await asyncio.wait_for(f, None)
            for r in results:
                table_data.extend(r)

        table = AsciiTable(table_data)
        print(table.table)
        await asyncio.sleep(60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', dest='all')
    parser.add_argument('--fwd', action='store_true', dest='port_forward')
    args = parser.parse_args()
    logging.basicConfig()
    asyncio.get_event_loop().run_until_complete(main(args.all, args.port_forward))
