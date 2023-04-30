# coding=utf-8
# © 2023 SHUI Ruihao <shuirh2019@gmail.com>
# All rights reserved.
"""
Provide node information via a port.

Data Format:
    hostname
    last_update
    ips: List[Tuple[str, str]] where tuple is of interface and ip addr
    gpus: List of gpu info in dict:
        index: int
        name: str
        use_mem: int
        tot_mem: int
        utilize: int, percent
        temp: int
        users: List of process info in dict:
            pid: int
            username: str
            mem(MiB): int
            command: str
"""

import os
import sys
import json
import socket
import psutil
from collections import OrderedDict
import time
from threading import Thread, Lock
from typing import List, Tuple, Dict, Any
from flask import Flask, request, jsonify, make_response, abort
from flask.logging import default_handler
from datetime import datetime
import pynvml as N
import subprocess
import pandas as pd
from copy import deepcopy
import argparse
import logging

PASSWD = '8888'

def create_gpu(index, name, used, tot, p, temp):
    d = OrderedDict([('index', int(index)),
                     ('name', name),
                     ('use_mem', int(used)),
                     ('tot_mem', int(tot)),
                     ('utilize', int(p)),
                     ('temp', temp),
                     ('users', [])]) # List[Dict[str, Any]]
    return d

class NodeStat:
    """
    Maintain the node status.
    """
    def __init__(self):
        self._status = {'hostname': None,
                        'last_update': None,
                        'ips': [],
                        'gpus': []}
        self._gpu_proc_status: Dict[str, List[Dict[str, Any]]] = {}

        self.interval = 4
        self.interval_proc = 10
        self.serial_map: Dict[str, int] = self.get_gpu_serial()

        self.th_referesh = Thread(target = self.daemon_func, name = 'th_referesh')
        self.th_proc = Thread(target = self.daemon_proc_func, name = 'th_proc')
    
    def start(self):
        self.th_referesh.start()
        self.th_proc.start()
    
    def stop(self):
        self.th_referesh.exit()
        self.th_proc.start()

    def get_gpu_serial(self):
        """map from serial to index(int)"""
        ser_map = {}
        N.nvmlInit()
        for gpu_idx in range(N.nvmlDeviceGetCount()):
            handle = N.nvmlDeviceGetHandleByIndex(gpu_idx)
            r = N.nvmlDeviceGetSerial(handle)
            if isinstance(r, bytes):
                r = r.decode()
            ser_map[r] = gpu_idx
        N.nvmlShutdown()
        return ser_map

    def get_hostname(self):
        host = socket.gethostname()  # next-gpu1 or next-dgx1-01
        return host

    def get_if_ip(self):
        if_ip_list: List[Tuple[str, str]] = []
        if2addrs = psutil.net_if_addrs()

        for ifname, ifstat in psutil.net_if_stats().items():
            if not ifstat.isup or any([k in ifname for k in ['lo', 'docker']]):
                continue
            # filter ipv4 address
            addrs = [k for k in if2addrs[ifname] if k.family == socket.AF_INET]
            if len(addrs) > 0:
                if_ip_list.append([ifname, addrs[0].address])
        if_ip_list.sort(key = lambda k: k[1])

        return if_ip_list

    def get_gpu_stat(self):
        gpus = []
        N.nvmlInit()
        for gpu_idx in range(N.nvmlDeviceGetCount()):
            handle = N.nvmlDeviceGetHandleByIndex(gpu_idx)
            
            gname = N.nvmlDeviceGetName(handle)
            if isinstance(gname, bytes):
                gname = gname.decode('utf-8')
            info = N.nvmlDeviceGetMemoryInfo(handle)
            use_mem = int(info.used / 1024 / 1024)
            tot_mem = int(info.total / 1024 / 1024)
            info = N.nvmlDeviceGetUtilizationRates(handle)
            utilize = int(info.gpu)
            temp = N.nvmlDeviceGetTemperature(handle, 0)
            
            gpu = create_gpu(gpu_idx, gname, use_mem, tot_mem, utilize, temp)
            
            gpus.append(gpu)
        
        N.nvmlShutdown()
        return gpus
    
    def get_gpu_process(self):
        command = 'nvidia-smi --query-compute-apps=gpu_serial,pid,used_memory --format=csv'
        p = subprocess.Popen(command, shell=True, close_fds=True, bufsize=-1,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        p.wait(10)
        df = pd.read_csv(p.stdout, dtype = str)
        # columns: gpu_serial, pid, used_gpu_memory [MiB]
        df.rename(lambda k: k.strip(), axis = 'columns', inplace = True)
        # print(df.columns)
        df['pid'] = df['pid'].astype(int)
        df['idx'] = df['gpu_serial'].apply(lambda k: self.serial_map[k])
        df['mem(MiB)'] = df['used_gpu_memory [MiB]'].apply(lambda k: int(k.split()[0]))

        gpu2procs = df.groupby('idx')[['pid', 'mem(MiB)']].apply(
                        lambda k: k.to_dict('records')).to_dict()
        for procs in gpu2procs.values():
            for proc in procs:
                proc['username'], proc['command'] = self.get_proc_info(proc['pid'])
        
        new_gpu2procs = {idx:[p for p in procs if p['username']] for idx,procs in gpu2procs.items()}

        return new_gpu2procs

    def get_proc_info(self, pid):
        pid = int(pid)
        try:
            pro = psutil.Process(pid)
            with pro.oneshot():
                username = pro.username()
                command = ' '.join(pro.cmdline())[:500]
        except:
            print('Unknown pid: {}'.format(pid))
            username = None
            command = None
        return username, command

    def referesh(self):
        self._status['hostname'] = self.get_hostname()
        self._status['last_update'] = datetime.now().isoformat()
        self._status['ips'] = self.get_if_ip()
        self._status['gpus'] = self.get_gpu_stat()
    
    def daemon_func(self):
        """THe daemon to periodically referesh device infomation"""
        print(f'Start monitor daemon')
        while True:
            self.referesh()
            time.sleep(self.interval)
    
    def daemon_proc_func(self):
        """The daemon to update process information"""
        print('Start process monitor daemon')
        while True:
            self._gpu_proc_status = self.get_gpu_process()
            time.sleep(self.interval_proc)    

    @property
    def status(self):
        """Return node status in dict"""
        status = deepcopy(self._status)
        for gpu in status['gpus']:
            idx = gpu['index']
            gpu['users'] = self._gpu_proc_status.get(idx, [])

        return status

def build_app(node: NodeStat):
    app = Flask(__name__)

    @app.route('/get-status', methods = ['POST'])
    def node_status():
        pw = request.json['passwd']
        if pw == PASSWD:
            return jsonify(node.status)
        else:
            abort(404)
    
    return app

def main(port, disable_log = False):
    ns = NodeStat()
    ns.start()

    app = build_app(ns)
    if disable_log:
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
    app.run(host = '0.0.0.0', port = port, threaded = True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Web app to display node status')
    parser.add_argument('--debug', action = 'store_true', 
                        help = 'Print the node status without starting the web app.')
    parser.add_argument('--port', type = int, default=7080, 
                        help = 'Port to access node status. (ip:port/get-status)')
    parser.add_argument('--disable_log', action = 'store_true', help = 'disable flask logging')

    args = parser.parse_args()
    if args.debug:
        ns = NodeStat()
        ns.start()
        time.sleep(3)
        print(json.dumps(ns.status, indent = 4, ensure_ascii=False))
    else:
        print('Start main....')
        main(port = args.port, disable_log=args.disable_log)

