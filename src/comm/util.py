import logging
import subprocess
from time import time

import requests


def exec_command(command):
    st = time()
    ret = subprocess.run(command, check=True)
    et = time()
    logging.info(f'명령=|{command}| 결과=|{ret.returncode}| 소요시간=|{et - st}초|')
    return ret.returncode


def req_post(url, req):
    try:
        headers = {'Content-Type': 'application/json'}
        res = requests.post(url, json=req, headers=headers)
        if res.status_code == 200:
            return res.json()

    except Exception as e:
        logging.error(f'예외 발생=||{e}')


def test():
    from conf.config import config as conf
    url = f'{conf.bar_addr}:{conf.bar_port}{conf.bar_url}'
    # url = 'http://localhost:33456/barcode'
    req_upc = {
        'type': 'upc',
        'content': '725272730706',
        'file': '/LPAS/lpas/data/tmp_files/upc.png',
    }
    req_ean = {
        'type': 'ean',
        'content': '8808563461533',
        'file': '/LPAS/lpas/data/tmp_files/ean.png',
    }
    req_post(url, req_ean)


if __name__ == '__main__':
    test()
