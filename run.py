import argparse
import asyncio
import asyncssh
from pathlib import Path
from terminaltables import AsciiTable


SEPARATOR = '<|>'
STS_RUNNNING = ' -f "status=running"'
STS_OTHERS = ' -f "status=created" -f "status=restarting" -f "status=removing" -f "status=paused" -f "status=exited"' \
             ' -f "status=dead"'
CMD = 'docker ps --format="{{.Names}}%s{{.Ports}}%s{{.Status}}%s{{.Image}}"' % (SEPARATOR, SEPARATOR, SEPARATOR)


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
                if user == 'root' and not pass_:
                    creds.append((host, user))
    return creds


async def container_info(host, user, others=False):
    table_data = []
    try:
        cmd = CMD + STS_RUNNNING
        if others:
            cmd = CMD + STS_OTHERS

        conn = await asyncio.wait_for(asyncssh.connect(host, username=user), timeout=10)
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
        print(e)
        print(host, user)

    return table_data


async def main(all_=False):
    creds = get_creds_from_config('~/.ssh/config')
    table_data = [['Host', 'Status', 'Names', 'Ports', 'Image'], ]

    f = asyncio.gather(*[container_info(host, user) for host, user in creds])
    results = await asyncio.wait_for(f, None)
    for r in results:
        table_data.extend(r)

    if all_:
        table_data.append(['', '', '', '', ''])
        table_data.append(['', '', '', '', ''])
        f = asyncio.gather(*[container_info(host, user, others=True) for host, user in creds])
        results = await asyncio.wait_for(f, None)
        for r in results:
            table_data.extend(r)

    table = AsciiTable(table_data)
    print(table.table)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', dest='all')
    args = parser.parse_args()
    asyncio.get_event_loop().run_until_complete(main(args.all))
