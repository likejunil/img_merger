import logging
from signal import signal, SIGTERM, SIGINT
from uuid import uuid4


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
