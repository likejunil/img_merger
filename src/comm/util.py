import logging
import subprocess
from time import time


def exec_command(command):
    st = time()
    ret = subprocess.run(command, check=True)
    et = time()
    logging.info(f'명령=|{command}| 결과=|{ret.returncode}| 소요시간=|{et - st}초|')
    return ret.returncode
