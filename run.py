import asyncio
import asyncssh
from pathlib import Path
from terminaltables import AsciiTable


SEPARATOR = '<|>'
CMD = 'docker ps --format="{{.Image}}%s{{.Status}}%s{{.Ports}}%s{{.Names}}"' % (SEPARATOR, SEPARATOR, SEPARATOR)


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


async def container_info(host, user):
    try:
        conn = await asyncio.wait_for(asyncssh.connect(host, username=user), timeout=10)
        result = await asyncio.wait_for(conn.run(CMD, check=True), timeout=10)

        table_data = []
        lines = result.stdout.splitlines()
        line = [host] + lines[0].split(SEPARATOR)
        table_data.append(line)
        for line in lines[1:]:
            line = [''] + line.split(SEPARATOR)
            table_data.append(line)
        return table_data
    except Exception as e:
        print(e)
        print(host, user)
        return ['']


async def main():
    creds = get_creds_from_config('~/.ssh/config')
    table_data = [['Host', 'Image', 'Status', 'Ports', 'Names'], ]
    f = asyncio.gather(*[container_info(host, user) for host, user in creds])
    results = await asyncio.wait_for(f, None)
    for r in results:
        table_data.extend(r)
    table = AsciiTable(table_data)
    print(table.table)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
