import pwnagotchi
import pwnagotchi.plugins as plugins
import logging
import traceback
import os
from os import fdopen, remove
import shutil
from shutil import move, copymode
from tempfile import mkstemp
from PIL import Image
import json
import toml
import csv
import _thread
from pwnagotchi import restart
from pwnagotchi.utils import save_config
from flask import abort, render_template_string
import requests
import subprocess

import pwnagotchi.plugins as plugins
import pwnagotchi.plugins.cmd
from pwnagotchi.plugins import toggle_plugin
import inspect

pwny_path = pwnagotchi.__file__
pwny_path = os.path.dirname(pwny_path)
pwnagotchi.root_path = pwny_path

ROOT_PATH = pwny_path

#ROOT_PATH = '/usr/local/lib/python3.7/dist-packages/pwnagotchi'
FANCY_ROOT = os.path.dirname(os.path.realpath(__file__))
setattr(pwnagotchi, 'fancy_root', FANCY_ROOT)

with open('%s/fancytools/sys/index.html' % (FANCY_ROOT), 'r') as file:
    html_contents = file.read()
INDEX = html_contents

def load_config(file_path):
    try:
        with open(file_path, "r") as file:
            config_data = toml.load(file)
        return config_data
    except FileNotFoundError:
        print(f"Error: File not found - {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def scan_folder(root_folder):
    folder_dict = {}

    for folder_name in os.listdir(root_folder):
        folder_path = os.path.join(root_folder, folder_name)

        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, 'config.toml')
            
            if os.path.exists(config_path):
                config_data = load_config(config_path)
                
                if config_data:
                    folder_dict[folder_name] = config_data

    return folder_dict

def serializer(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError

def copy_with_backup(src_path, dest_path):
    # Check if the source file exists
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"The source file '{src_path}' does not exist.")

    # Check if the destination directory exists, create it if not
    dest_dir = os.path.dirname(dest_path)
    os.makedirs(dest_dir, exist_ok=True)

    # Check if the destination file already exists
    if os.path.exists(dest_path):
        # Check if a backup file with .original extension exists
        backup_path = dest_path + '.original'
        index = 1
        while os.path.exists(backup_path):
            backup_path = f"{dest_path}.original_{index}"
            index += 1

        # If no .original file found, create a backup with .original extension
        shutil.copy(dest_path, backup_path)

    # Copy the source file to the destination
    shutil.copy(src_path, dest_path)

# function to backup all actual modified files to make a new install update
def dev_backup(config, dest_fold):
    path_table = []
    if not config.get('pwnagotchi') and not config.get('system'):
        logging.warning('empty config files for dev backup')
    else:
        if config.get('pwnagotchi'):  
            for path in config['pwnagotchi']:
                target_path = ROOT_PATH + '/' + path
                back_path = '%s/%s' % (dest_fold, path)
                logging.warning(target_path + " >> " + back_path)
                copy_with_backup(target_path, back_path)

        if config.get('system'):
            for path in config['system']:
                target_path = path
                back_path = '%s%s' % (dest_fold, path)
                logging.warning(target_path + " >> " + back_path)
                copy_with_backup(target_path, back_path)

# function to verify if a new version is available
def check_update(vers, online):
    nofile = False
    online_version = ''
    if online:
        URL = "https://raw.githubusercontent.com/V0r-T3x/fancygotchi/main/fancygotchi.py"
        response = requests.get(URL)
        lines = str(response.content)
        lines = lines.split('\\n')
        count = 0
        for line in lines:
            if '__version__ =' in line:
                count += 1
                if count == 3:
                    online_version = line.split('= ')[-1]
                    online_version = online_version[2:-2]
    elif not online:
        URL = '%s/fancytools/update/fancygotchi-main/fancygotchi.py' % (FANCY_ROOT)
        if os.path.exists(URL):
            with open(URL, 'r') as f:
                lines = f.read()
            lines = lines.splitlines()
            count = 0
            for line in lines:
                if '__version__ =' in line:
                    count += 1
                    if count == 3:
                        online_version = line.split('= ')[-1]
                        online_version = online_version[1:-1]
        else:
            nofile = True

    if not nofile:
        online_v = online_version.split('.')
        local_v = vers.split('.')
        if online_v[0] > local_v[0]:
            upd = True
        elif online_v[0] == local_v[0]:
            if online_v[1] > local_v[1]:
                upd = True
            elif online_v[1] == local_v[1]:
                if online_v[2] > local_v[2]:
                    upd = True
                else: upd = False
            else: upd = False
        else: upd = False
    else:
        upd = 2

    return [upd, online_version]

def update(online):
    logging.info('[FANCYGOTCHI] The updater is starting, is online: %s' % (online))
    path_upd = '%s/fancygotchi/update' % (FANCY_ROOT)
    if online:#<-- Download from the Git & define the update path
        URL = "https://github.com/V0r-T3x/fancygotchi/archive/refs/heads/main.zip"
        response = requests.get(URL)
        filename = '%s/%s' % (path_upd, URL.split('/')[-1])
        os.system('mkdir %s' % (path_upd))
        with open(filename,'wb') as output_file:
            output_file.write(response.content)
        shutil.unpack_archive(filename, path_upd)
    path_upd += '/fancygotchi-main'
    
    logging.info('[FANCYGOTCHI] %s/fancygotchi.py ====> %s/fancygotchi.py' % (path_upd, FANCY_ROOT))
    shutil.copyfile('%s/fancygotchi.py' % (path_upd), '%s/fancygotchi.py' % (FANCY_ROOT))
    
    uninstall(True)
    mod_path = '%s/fancytools/mod' % (FANCY_ROOT)
    logging.info('[FANCYGOTCHI] removing mod folder: %s' % (mod_path))
    os.system('rm -R %s' % (mod_path))
    deftheme_path = '%s/fancygotchi/theme/.default' % (FANCY_ROOT)
    logging.info('[FANCYGOTCHI] removing theme folder: %s' % (deftheme_path))
    os.system('rm -R %s' % (deftheme_path))
    sys_path = '%s/fancytools/sys' % (FANCY_ROOT)
    logging.info('[FANCYGOTCHI] removing sys folder: %s' % (sys_path))
    os.system('rm -R %s' % (sys_path))
    
    path_upd += '/fancygotchi'
    for root, dirs, files in os.walk(path_upd):
        for name in files:
            if not name in ['README.md', 'readme.md']:
                src_file = os.path.join(root, name)
                dst_path = '%s/%s' % (FANCY_ROOT, root.split('fancygotchi-main/')[-1])
                dst_file = '%s/%s' % (dst_path, name)
                logging.info('[FANCYGOTCHI] %s ~~~~> %s' % (src_file, dst_file))
                
                if not os.path.exists(dst_path):
                    os.makedirs(dst_path)
                shutil.copyfile(src_file, dst_file)
            
                # Check if the destination path exists and create it if it doesn't
                if not os.path.exists(dst_path):
                    os.makedirs(dst_path)

                # Copy the file to the destination path
                shutil.copyfile(src_file, dst_file)
    if online:
        path_upd = '%s/fancytools/update' % (FANCY_ROOT)
        logging.info('[FANCYGOTCHI] removing the update temporary folder: %s' % (path_upd))
        os.system('rm -R %s' % (path_upd))

def uninstall(soft=False):
    logging.info('uninstall function start')

def verify_config_files(config, ext=''): 
    logging.warning('starting files verification')
    missing = []
    total_files = 0

    if not config.get('pwnagotchi') and not config.get('system'):
    # Skip verification if both sections are empty
        return missing, total_files

    if config.get('pwnagotchi'):  
        for path in config['pwnagotchi']:
            total_files += 1
            target_path = ROOT_PATH + '/' + path + ext
            if not os.path.exists(target_path):
                missing.append(target_path)

    if config.get('system'):
        for path in config['system']:
            total_files += 1  
            target_path = path + ext
            if not os.path.exists(target_path):
                missing.append(target_path)

    return missing, total_files

def verify_subprocess(subp):
    is_installed = 0
    try:
        subprocess.check_output(['which', subp])
        logging.warning('subprocess is installed')
        is_installed = 1
    except subprocess.CalledProcessError:
        logging.warning(subp+' is not installed')
    return is_installed

def verify_fancygotchi_status(config):
    logging.warning(config['fancygotchi']['info']['version'])
    missing_files, total_files = verify_config_files(config['fancygotchi']['files'])
    logging.warning('missing files: '+str(len(missing_files))+'/'+str(total_files))
    missing_backup, total_files = verify_config_files(config['fancygotchi']['files'], '.original')
    logging.warning('missing backup: '+str(len(missing_backup))+'/'+str(total_files))

    fancy_status = 0

    if len(missing_files) == total_files:
        logging.warning('Fancygotchi is not installed')
        fancy_status = 0
    elif len(missing_files) == 0 and len(missing_backup) == total_files:
        logging.warning('Fancygotchi is installed and is embedded')
        fancy_status = 1
    elif len(missing_files) == 0 and len(missing_backup) != total_files:
        logging.warning('Fancygotchi is installed manually')
        fancy_status = 2
    #logging.warning(str(fancy_status))
    return fancy_status

def verify_tool_status(config):
    missing, total = verify_config_files(config['files'])
    logging.warning(str(len(missing))+'/'+str(total))
    subp = config['info']['subprocess']
    if subp:
        logging.warning('verify if '+subp+' subprocess is installed')
        subp_status = verify_subprocess(subp)
    else:
        logging.warning('no subprocess')
        subp_status = 2

    if total == 0 and subp_status == 2:
        logging.warning('this tool cannot be installed')
    else:
        if total == 0:
            logging.warning('no files needed for the tool')
            if subp_status == 0:
                logging.warning('no subprocess installed')
            elif subp_status == 1:
                logging.warning(subp+' subprocess is installed')
                is_installed = 1
        else:
            logging.warning('files needed for the tool')
            if len(missing) == 0 and subp_status == 1:
                logging.warning('all files are install')
                logging.warning(subp+' subprocess is installed')
                is_installed = 1
            elif len(missing) == 0 and subp_status == 0:
                logging.warning('all files are install')
                logging.warning('no subprocess is installed')
                is_installed = 0
            elif len(missing) != 0 and subp_status ==1:
                logging.warning('not all files are installed')
                logging.warning(subp+' subprocess is installed')
                is_installed = 0
    return is_installed

class Fancytools(plugins.Plugin):
    __name__ = 'FancyTools'
    __author__ = '@V0rT3x https://github.com/V0r-T3x'
    __version__ = '2023.12.1'
    __license__ = 'GPL3'
    __description__ = 'Fancygotchi and additional debug/dev tools'


    def __init__(self):
        self.ready = False
        self.mode = 'MANU'

    def toggle_plugin(name, enable=True):
        logging.warning(toggle_plugin(name, enable))

    def on_config_changed(self, config):
        self.config = config
        self.ready = True

    def on_ready(self, agent):
        self.mode = 'MANU' if agent.mode == 'manual' else 'AUTO'

    def on_internet_available(self, agent):
        self.mode = 'MANU' if agent.mode == 'manual' else 'AUTO'

    def on_loaded(self):
        logging.info("[FANCYTOOLS] Beginning Fancytools load")
        # Fancytools cmd 
        os.system('chmod +x %s/fancytools/sys/fancytools.py' % (FANCY_ROOT))
        os.system('sudo ln -s %s/fancytools/sys/fancytools.py /usr/local/bin/fancytools' % (FANCY_ROOT))

        # Each tool folders should be scanned
        # Each sub-folder become the tool name ID
        # Each tool dict have a place for the mod files (this can be use to verify if this is already installed) this is including special install/uninstall commands

        deftool_path = '%s/fancytools/tools/default/' % (FANCY_ROOT)
        custool_path = '%s/fancytools/tools/custom/' % (FANCY_ROOT)

        self.deftools = scan_folder(deftool_path)
        self.custools = scan_folder(custool_path)
        logging.warning('='*20)
        for tool in self.deftools:
            logging.warning(tool+' tool')
            is_installed = 0
            if tool == 'fancygotchi':
                status = verify_fancygotchi_status(self.deftools)
                if status == 1 or status == 2:
                    is_installed = 1
                else:
                    is_installed = 0
            else:
                is_installed = verify_tool_status(self.deftools[tool])

            if is_installed == 0:
                logging.warning('tool not installed')
            else:
                logging.warning('tool installed')
            logging.warning('='*20)

        logging.info("[FANCYTOOLS] Ending Fancytools load")







    def on_unload(self, ui):
        os.system('rm /usr/local/bin/fancytools')
        #logging.warning('rm /usr/local/bin/fancytools')
        logging.info("[FANCYTOOLS] Fancytools unloaded")

    def on_webhook(self, path, request):
        logging.info(request.remote_addr)
        if not self.ready:
            return "Plugin not ready"

        if request.method == "GET":
            if path == "/" or not path:
                #pwnagotchi.fancy_change = True
                return render_template_string(INDEX)

        elif request.method == "POST":

            if path == "devbackup":
                try:
                    jreq = request.get_json()
                    folder = json.loads(json.dumps(jreq))
                    fancybu = '%s/fancybackup/' % (FANCY_ROOT)
                    dest = '%s%s' % (fancybu, str(folder["response"]))
                    if not os.path.exists(fancybu):
                        os.system('mkdir %s' % (dest))
                    if not os.path.exists(dest):
                        os.system('mkdir %s' % (dest))
                    dev_backup(self.deftools['fancygotchi']['files'], dest);
                    return "success"
                except Exception as ex:
                    logging.error(ex)
                    logging.error(traceback.format_exc())
                    return "dev backup error", 500

            elif path == "check_online_update":
                try:
                    is_update = check_update(self.__version__, True)
                    logging.info(is_update[1])
                    upd = '%s,%s' % (is_update[0], is_update[1])
                    return upd
                except Exception as ex:
                    logging.error(ex)
                    return "update check error, check internet connection", 500

            elif path == "online_update":
                try:
                    update(True)
                    _thread.start_new_thread(restart, (self.mode,))
                    logging.info(str(request.get_json()))
                    return "success"
                except Exception as ex:
                    logging.error(ex)
                    return "update error", 500
                    
            elif path == "check_local_update":
                try:
                    is_update = check_update(self.__version__, False)
                    logging.info(is_update)
                    #if upd == 2:
                    upd = '%s,%s' % (is_update[0], is_update[1])
                    logging.info(upd)
                    return upd
                except Exception as ex:
                    logging.error(ex)
                    return "update check error, check internet connection", 500

            elif path == "local_update":
                try:
                    update(False)
                    _thread.start_new_thread(restart, (self.mode,))
                    logging.info(str(request.get_json()))
                    return "success"
                except Exception as ex:
                    logging.error(ex)
                    return "update error", 500
        abort(404)
