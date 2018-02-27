import argparse
import asyncio
import logging
import asyncssh
from pathlib import Path
from terminaltables import AsciiTable


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


async def containers_info(host, conn, others=False):
    table_data = []
    try:
        cmd = CMD + STS_RUNNNING
        if others:
            cmd = CMD + STS_OTHERS

        result = await asyncio.wait_for(conn.run(cmd, check=True), timeout=10)

        lines = result.stdout.splitlines()
        if not lines:
            return table_data

        line = [host] + lines[0].split(SEPARATOR)
        table_data.append(line)
        for line in lines[1:]:
            line = [''] + line.split(SEPARATOR)
            table_data.append(line)
    except Exception as e:
        logging.exception('')

    return table_data


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
        f = asyncio.gather(*[containers_info(host, conn) for host, conn in connections.items()])
        results = await asyncio.wait_for(f, None)
        for r in results:
            table_data.extend(r)
            fwd_info = r[2].split('->')[0]
            host, port = fwd_info.split(':')
            listener = await conn

        if all_:
            table_data.append(['', '', '', '', ''])
            table_data.append(['', '', '', '', ''])
            f = asyncio.gather(*[containers_info(host, user, others=True) for host, user in creds])
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
