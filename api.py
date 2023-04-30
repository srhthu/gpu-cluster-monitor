# coding=utf-8
# © 2023 SHUI Ruihao <shuirh2019@gmail.com>
# All rights reserved.
"""
API of server monitor.
"""
import os
import sys
import argparse
from flask import Flask, request, jsonify, make_response

from cluster import Cluster

PASSWD = '8888'

parser = argparse.ArgumentParser(description='GPU Cluster Monitor API')
parser.add_argument('-c', help = 'path of hostname or IP addresses file')
parser.add_argument('--port', type = int, default = 7070, help = 'Main node API port. (default: %(default)s)')
parser.add_argument('--node_port', type = int, default = 7080, help = 'API port of each node. (default: %(default)s)')
parser.add_argument('--node_wait', type = int, default = 4, help = 'Node referesh frequency (second)')
parser.add_argument('--node_expire_time', type = int, default = 60, help = 'Node expire time (second)')
args = parser.parse_args()

hosts = list(map(lambda k: k.strip(), open(args.c).readlines()))

next_server = Cluster(
    hosts,
    port = args.node_port,
    passwd = PASSWD,
    node_wait = 4,
    node_expire_time = 60,
)

#------------------------------
# Route
#------------------------------
app = Flask(__name__)
port = args.port

@app.route('/')
def homepage():
    with open('monitor_home.html', encoding='utf8') as f:
        page = f.read()
    return page

@app.route('/web/<fn>')
def get_web(fn):
    with open('./web/{}'.format(fn), encoding='utf8') as f:
        s = f.read()
    r = make_response(s)
    if fn.split('.')[-1] == 'css':
        r.mimetype = 'text/css'
    elif fn.split('.')[-1] == 'js':
        r.mimetype = 'application/javascript'
    return r

@app.route('/get-status', methods = ['GET'])
def report_gpu_cluster():
    data = next_server.get_status()
    return jsonify(data)


if __name__ == '__main__':
    app.run(host = '0.0.0.0', port=port, threaded = True)
