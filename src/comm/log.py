import logging
import os
from datetime import datetime
from multiprocessing import current_process

from conf.conf import config as conf


def init_log(level=logging.INFO, name=None):
    """
    로그 레벨의 종류는 총 6가지가 있다.
    1. CRITICAL (프로그램 중지 야기)
    2. ERROR (심각한 문제지만 프로그램 진행)
    3. WARNING (예측할 수 없는 결과 발생 가능)
    4. INFO (정보)
    5. DEBUG (디버깅)
    6. NOTSET (사용자 지정 로그 레벨)
    """

    if not name:
        name = current_process().name

    fmt = f'%(asctime)s - ' \
          f'[{name}:{os.getpid()}] - ' \
          f'%(levelname)s - ' \
          f'[%(filename)s:%(funcName)s:%(lineno)d] - ' \
          f'%(message)s'
    filename = f'{name}_{datetime.now().strftime("%Y%m%d")}.log'
    log_file = os.path.join(conf.log_path, filename)

    logging.basicConfig(
        filename=log_file,
        encoding='utf8',
        format=fmt,
        level=level,
    )


def console_log(level=logging.DEBUG):
    fmt = f'%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        format=fmt,
        level=level,
        # datefmt=f'%H:%M:%S'
    )
