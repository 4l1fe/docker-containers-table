from pathlib import Path


def get_host_user_pairs(config_file):
    host_user_pairs = []
    with open(Path(config_file).expanduser().as_posix(), 'r') as file:
        for line in file.readlines():
            if not line.strip(): continue

            stmnt, value = line.split()
            if stmnt == 'Host':
                pass_ = not value.endswith('_')
            elif line.startswith('HostName'):
                host = line.split()[1]
            elif line.startswith('User'):
                user = line.split()[1]
                if not pass_ and user in ('root', 'dkrasnov'):
                    host_user_pairs.append((host, user))

    return host_user_pairs