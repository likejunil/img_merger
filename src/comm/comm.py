import asyncio as aio
import logging
import sys
from datetime import datetime as dt
from signal import signal, SIGTERM, SIGINT
from time import time
from uuid import uuid4

import fcntl

from conf.conf import config as conf


def cache_func(func):
    uuid = uuid4()
    ret = uuid

    def wrapper(*args, **kwargs):
        nonlocal ret
        if ret == uuid:
            ret = func(*args, **kwargs)
        return ret

    return wrapper


@cache_func
def ready_cont(signo=None):
    cont = True
    logging.info(f'프로그램 제어 플래그 초기화')
    set_signal(signo)
    logging.info(f'시그널 핸들러 등록')

    def go_cont():
        nonlocal cont
        cont = True

    def stop_cont(func=None):
        nonlocal cont
        cont = False
        if func:
            func()

    def is_cont():
        return cont

    return go_cont, stop_cont, is_cont


def signal_handler(signum, frame):
    logging.critical(f'시그널 수신 =|{signum}|')
    logging.debug(f'프레임 =|{frame}|')
    _, stop_cont, _ = ready_cont()
    stop_cont()


def set_signal(signo):
    if not signo:
        signal(SIGTERM, signal_handler)
        signal(SIGINT, signal_handler)
    else:
        signal(signo, signal_handler)


def get_loop():
    try:
        loop = aio.get_running_loop()
    except Exception as e:
        logging.info(e)
        loop = aio.new_event_loop()
    return loop


def get_log_level():
    return logging.DEBUG if conf.debug else logging.INFO


def tm(t=None):
    if not t:
        t = time()
    return dt.fromtimestamp(t).strftime('%H%M%S.%f')[:-3]


def lock_run(proc_name=""):
    pid_file = f'.lock_{proc_name}.pid'
    import os
    lock_file = os.path.join(conf.pid_path, pid_file)

    try:
        # 파일을 읽기 전용 모드로 열기
        lock_fd = open(lock_file, 'r')
    except IOError:
        # 파일이 존재하지 않는다면, 쓰기 모드로 열기
        lock_fd = open(lock_file, 'w')

    try:
        # 파일 락 설정
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # ---------------------------------------------------------
        # 파일 락을 얻을 수 없다면 이미 다른 프로세스가 실행 중..
        # ---------------------------------------------------------
        msg = f'\n' \
              f'  **************************************\n' \
              f'      이미 프로세스가 실행 중입니다.\n' \
              f'  **************************************\n'
        logging.error(msg)
        if not sys.stdout.closed:
            print(msg)
        # sys.exit(-1)
        return
    except Exception as e:
        logging.error(e)
        # sys.exit(-2)
        return

    def f():
        # 파일 락 해제
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        # 파일 닫기
        lock_fd.close()

    return f
