#! /usr/bin/python3

import sys
import subprocess
import pkg_resources
import importlib

# Ruta en Linux / MAC de carpeta GRASS
# CONFIG_GRASS_PATH = '/usr/lib/grass78'  # ejemplo: /usr/lib/grass78
CONFIG_GRASS_PATH = subprocess.check_output(["grass78", "--config", "path"]).decode("utf-8").strip()

# Paquetes usados en la aplicacion
PACKAGES = {
    'python-cli-ui': {
        'version': '0.7.5',
        'module': 'ui'
    },
    'grass-session': {
            'version': '0.5',
            'module': 'grass-session'
        },
    'flopy': {
            'version': '3.3.1',
            'module': 'flopy'
        },
    'anytree': {
            'version': '2.8.0',
            'module': 'anytree'
        },
    'pyshp': {
            'version': '2.1.2',
            'module': 'pyshp'
        },
}


# LD_LIBRARY_PATH=$(grass78 --config path)/lib
# os.putenv("LD_LIBRARY_PATH", "123")

process_lines = {}
package_lines = {}


def add_grass_path():
    # Necesario para poder encontrar librerias de GRASS
    sys.path.append(CONFIG_GRASS_PATH + '/etc/python')
    sys.path.append(CONFIG_GRASS_PATH + '/lib')


def add_process_msg(package, msg, status, info=None):
    line = {
        'msg': msg,
        'status': status,
        'info': info
    }

    if package in process_lines:
        process_lines[package].append(line)
    else:
        process_lines[package] = [line]


def import_package(package):
    module = PACKAGES[package]['module']
    version = PACKAGES[package]['version']

    msg_search = 'Searching package: [{}]'.format(package)
    msg_install = 'Installing package: [{}] v{}'.format(package, version)

    try:
        importlib.import_module(module)
        add_process_msg(package=package, msg=msg_search, status='FOUND')
    except ModuleNotFoundError:
        add_process_msg(package=package, msg=msg_search, status='NOT FOUND')
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", '{}=={}'.format(package, version)])
            add_process_msg(package=package, msg=msg_install, status='INSTALLED')
        except subprocess.CalledProcessError:
            msg_info = 'Need to be manually installed: pip3 install {}=={}'.format(package, version)
            add_process_msg(package=package, msg=msg_install, status='NOT INSTALLED', info=msg_info)


def show_msg_info_without_ui(msg_info, is_subtask=False, is_title=False):
    task_token = '::'
    subtask_token = '    =>'
    title_len = len(msg_info) if len(msg_info) > 80 else 80

    if is_title:
        print('\n')
        print('-' * (title_len + 2))
        print(msg_info)
        print('-' * (title_len + 2))
    elif is_subtask:
        print('{} {}'.format(subtask_token, msg_info))
    else:
        print('{} {}'.format(task_token, msg_info))


def check_packages():
    required = PACKAGES.keys()
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = required - installed

    for package in required:
        if package in installed:
            package_lines[package] = '[FOUND]'
        else:
            package_lines[package] = '[NOT FOUND]'

    if missing:
        for package in missing:
            import_package(package)


def check_ui():
    ret = False

    package = 'python-cli-ui'
    module = PACKAGES[package]['module']
    try:
        importlib.import_module(module)
        ret = True
    except ModuleNotFoundError:
        ret = False

    return ret


def print_summary_ui():
    import ui

    ui.info_section('STATUS')
    for package in package_lines:
        ui.info(ui.bold, '{}: '.format(package), ui.faint, ui.darkred, '{}'.format(package_lines[package]))
    print('\n')

    for package in process_lines:
        line = process_lines[package]
        ui.info_section(package)

        if line['info'] is not None:
            ui.info('\n\r', ui.bold, ui.red, '    => ', ui.reset, '{}: '.format(line['msg']),
                    ui.bold, ui.darkred, '[{}]'.format(line['status']), ui.reset, ' ({})'.format(line['info']))
        else:
            ui.info('\n\r', ui.bold, ui.red, '    => ', ui.reset, '{}: '.format(line['msg']),
                    ui.bold, ui.darkred, '[{}]'.format(line['status']))
    print('\n')


def setup_app():
    add_grass_path()
    check_packages()

    # with_ui = check_ui()
    with_ui = False
    if not with_ui:
        msg_title = 'STATUS'
        show_msg_info_without_ui(msg_info=msg_title, is_title=True)

        for package in package_lines:
            msg_info = '{}: {}'.format(package, package_lines[package])
            print('    {}'.format(msg_info))
        print('\n')

        for package in process_lines:
            line = process_lines[package]
            show_msg_info_without_ui(msg_info=package)

            if line['info'] is not None:
                msg_info = '{}: [{}] ({})'.format(line['msg'], line['status'], line['info'])
            else:
                msg_info = '{}: [{}]'.format(line['msg'], line['status'])
            show_msg_info_without_ui(msg_info=msg_info, is_subtask=True)
        print('\n')
    else:
        print_summary_ui()


if __name__ == '__main__':
    setup_app()
