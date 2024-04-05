import asyncio as aio
import logging
import os
import sys
from multiprocessing import Process, Queue
from multiprocessing import current_process
from signal import SIGTERM
from time import sleep

import schedule

from conf.config import config as conf
from src.comm.comm import ready_cont, get_loop, cache_func
from src.comm.log import init_log, get_log_level, manage_logfile
from src.converter.converter import converter_proc
from src.merger.merger import merger_proc
from src.starter.starter import starter_proc


async def check_parent(loop):
    ppid = os.getppid()
    logging.info(f'{current_process()}: 프로세스 시작, 부모 프로세스=|{ppid}|')
    ok = ready_cont()[2]
    while ok():
        if ppid != os.getppid():
            logging.critical(f'부모 프로세스 변경({ppid} => {os.getppid()}), 프로세스 종료')
            os.kill(os.getpid(), SIGTERM)
        await aio.sleep(1)

    await aio.sleep(3.0)
    logging.info(f'이벤트 루프 중지')
    loop.stop()


def async_child_process(coro):
    ready_cont()
    loop = get_loop()
    loop.create_task(check_parent(loop))
    loop.create_task(coro)
    logging.info(f'태스크 생성 완료')
    loop.run_forever()
    logging.info(f'이벤트 루프 종료')
    loop.close()


def child_proc(coro):
    init_log(get_log_level(), None, True)
    logging.info(f'프로세스 시작')
    async_child_process(coro)
    logging.critical(f'프로세스 종료')


def child_strategy_run(strategy, args):
    sleep(0.1)
    child_proc(strategy(*args))
    sys.exit(0)


@cache_func
def ready_children(get_procs):
    if (procs := get_procs()) is None:
        logging.error(f'실행할 프로세스가 없음')
        return
    p_list = []

    def start(i=None):
        nonlocal p_list
        if i is None:
            p_list = [Process(name=n, target=t, args=a) for n, t, a in procs]
            for p in p_list:
                p.start()
        elif 0 <= i < len(procs):
            n, t, a = procs[i]
            p_list[i] = Process(name=n, target=t, args=a)
            p_list[i].start()

    def stop():
        for p in p_list:
            logging.info(f'|{p.name}| 종료')
            p.terminate()

    def get():
        return p_list

    return start, stop, get


def proc(get_procs, schedule_proc, clean_proc):
    init_log(get_log_level(), 'monitor')
    logging.info(f'모니터링 프로세스 시작, 현재 디렉토리=|{os.getcwd()}|')

    # -----------------------------
    # 관리할 프로세스 목록 생성
    # -----------------------------
    if (ret := ready_children(get_procs)) is None:
        msg = f'자식 생성 실패, 종료'
        logging.error(msg)
        return

    start, stop, get = ret
    start()

    # -----------------------------
    # 스케줄 관리
    # -----------------------------
    schedule_proc()

    # -----------------------------
    # 모니터링
    # -----------------------------
    go_cont, _, is_cont = ready_cont()
    go_cont()
    while is_cont():
        sleep(1)
        schedule.run_pending()
        for i, p in enumerate(get()):
            # is_alive() 를 호출하는 순간, 해당 프로세스가 좀비일 경우 좀비 해제를 실행한다.
            # 따라서 굳이 join() 을 호출할 필요가 없다.
            if not p.is_alive():
                logging.error(f'pid=|{p.pid}| {p.name} 프로세스가 종료되었음, 다시 시작..')
                start(i)

    # -----------------------------
    # 자원 해제 및 자식 프로세스 종료
    # -----------------------------
    logging.critical(f'자원 정리 및 자식 프로세스 종료 시작')
    sleep(1)
    stop()

    # 자원 해제
    clean_proc()
    logging.critical(f'모니터링 프로세스 종료')


def main_proc():
    # cq 는 스타터 모듈이 컨버터 모듈에게 송신하는 큐
    # mq 는 컨버터 모듈이 머저 모듈에게 송신하는 큐
    cq, mq = Queue(), Queue()

    def get_procs():
        proc_list = [
            ('starter', child_strategy_run, (starter_proc, (cq,))),
            ('converter', child_strategy_run, (converter_proc, (cq, mq))),
            ('merger', child_strategy_run, (merger_proc, (mq,))),
        ]
        return proc_list

    def schedule_proc(func=None, tm_info=None, *args):
        # 매일 로그파일 관리
        logging.info(f'|{conf.log_time}| 로그 배치 예정')
        schedule.every().day.at(conf.log_time).do(manage_logfile)

        if func:
            if not tm_info:
                tm_info = "00:00"
            schedule.every().day.at(tm_info).do(func, *args)

    def clean_proc():
        cq.close()
        mq.close()

    proc(get_procs, schedule_proc, clean_proc)


if __name__ == '__main__':
    pass
