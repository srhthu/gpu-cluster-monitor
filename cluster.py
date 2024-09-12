# coding=utf-8
# © 2023 SHUI Ruihao <shuirh2019@gmail.com>
# All rights reserved.
"""
Class of GPU cluster status.
"""

from typing import Optional, Union, Dict, Any, Tuple, List
import json
from collections import OrderedDict,defaultdict
import time
import re
from datetime import date, datetime
from threading import Thread, Lock
import requests


class Cluster:
    """
    Hold status of all servers and check user book legality.
    
    Data structure
        {
            "Nodes": [
                {
                    "hostname": "xxx"
                    "last_update": "2022-09-10T22:40:09.304060"
                    "ips": List[Tuple[str, str]] where tuple is of interface and ip addr
                    "gpus": list of gpu status
                    *"version": gpu brand
                    *"status": `bool`
                },
                ...
            ]
        }
    """

    def __init__(
            self,
            hosts: List[str],
            port = 7080,
            passwd = None,
            node_wait = 4,
            node_expire_time = 60,
        ):
        self.hosts = hosts
        self.port = port
        self.passwd = passwd

        self.node_wait = node_wait
        self.node_expire_time = node_expire_time

        self._cluster_stat = {}

        self.lock = Lock()
        
        self.nodes: Dict[str, Dict] = {h:None for h in self.hosts} # map from hostname to Node data
        
        self.init_fetch_thread()
        self.start_threads(self._node_threads)

    def init_fetch_thread(self):
        self._node_threads = [Thread(target = self.daemon_fetch_node,
                                     args = (h, ),
                                     name = f'fetch {h}')
                                for h in self.hosts]
        
    def start_threads(self, threads):
        for th in threads:
            th.start()

    def daemon_fetch_node(self, host):
        while True:
            url = f'http://{host}:{self.port}/get-status'
            try:
                res = requests.post(url, json = {'passwd': self.passwd})
                data = res.json()
                print(f'Fetch {url}: successful')
            except:
                print(f'Fetch {url}: no response')
                data = None
            self.lock.acquire()
            if data is not None:
                data['status'] = True
                self.nodes[host] = data
            elif self.nodes[host] is not None:
                q_time = datetime.fromisoformat(self.nodes[host]['last_update'])
                dur = (datetime.now() - q_time).total_seconds()
                self.nodes[host]['status'] = (dur <= self.node_expire_time)
            self.lock.release()
            time.sleep(self.node_wait)

    def _psudo_node(self, host):
        # get host gpu number from booking
        return {'hostname': host, 'status': False, 'gpus': []}

    def assemble(self):
        """
        Assemble node status and booking information.
        Return cluster status dict.
        """
        status = OrderedDict()
        status['Nodes'] = []

        for host in self.hosts:
            node = self.nodes[host] or self._psudo_node(host)
            gpu_names = [gpu['name'] for gpu in node['gpus']] if node['gpus'] else []
            node['version'] = gpu_names
            status['Nodes'].append(node)
        
        return status


        
    def get_status(self):
        """
        Return clauster status in JSON to frontend.
        """
        return self.assemble()
                    


if __name__ == '__main__':
    hosts = ['xxx', 'xxx'] # configure your node ip
    c = Cluster(hosts, passwd = '8888')
    time.sleep(8)
    print(json.dumps(c.get_status(), indent = 4))
    time.sleep(10)
    print(json.dumps(c.get_status(), indent = 4))
    exit()