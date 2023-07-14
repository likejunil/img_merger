import logging
import subprocess
from time import time


def exec_command(command):
    st = time()
    subprocess.run(command, check=True)
    et = time()
    logging.info(f'명령=|{command}| 소요시간=|{et - st}초|')
