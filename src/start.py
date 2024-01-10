import logging
import os
import sys

from src.comm.comm import lock_run
from src.comm.log import init_log


def main_proc():
    init_log(logging.INFO, 'img_merger')


def set_daemon():
    # ------------------
    # 새로운 프로세스 그룹 생성
    # ------------------
    os.setsid()

    # ------------------
    # 모든 파일디스크립터 닫음
    # ------------------
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()


def daemon(start):
    # lock_run() 호출에 대한 반환 함수는 변수에 담고 있어야 클로져가 유지된다.
    # 부모 프로세스는 종료되면서 자동으로 잠금을 해제한다.
    # 쉘 스크립트에게 본 프로세스의 잠금 상태 여부에 대한 결과값을 주려면 fork() 이전에..
    if not (stop := lock_run()):
        sys.exit(-1)

    pid = os.fork()
    # ------------------
    # 자식 프로세스
    # ------------------
    if pid == 0:
        set_daemon()
        start()
        stop()
    # ------------------
    # 부모 프로세스
    # ------------------
    else:
        sys.exit(0)


if __name__ == '__main__':
    # main_proc()
    daemon(main_proc)
