import asyncio as aio
import filecmp
import logging
import os
import shutil
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from multiprocessing import current_process

from conf.conf import config as conf
from src.comm.comm import ready_cont

log_level = logging.DEBUG if conf.debug else logging.INFO


# todo 2023.0527 by june1
#  - 왜 다음 함수는 기대한 대로 작동하지 않을까?
def init_log1(level=logging.INFO, name=None):
    if not name:
        name = current_process().name

    # 로거
    logger = logging.getLogger(name)

    # 포맷터
    fmt = f'%(asctime)s - ' \
          f'[{name}:{os.getpid()}] - ' \
          f'%(levelname)s - ' \
          f'[%(filename)s:%(funcName)s:%(lineno)d] - ' \
          f'%(message)s'
    formatter = logging.Formatter(fmt)

    # 핸들러
    log_file = os.path.join(conf.log_path, f'{name}.log')
    handler = TimedRotatingFileHandler(filename=log_file, when='midnight', encoding='utf8')
    handler.suffix = "%Y%m%d"

    # 포맷터 추가
    handler.setFormatter(formatter)

    # 핸들러 추가
    logger.addHandler(handler)

    # 레벨
    logger.setLevel(level)

    logging.info(f'|{name}| 로그 초기화 완료')


def init_log(level=logging.INFO, name=None, change=False, middle=''):
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

    """
    fmt = f'%(asctime)s - ' \
          f'[{name}:{os.getpid()}] - ' \
          f'%(levelname)s - ' \
          f'[%(filename)s:%(funcName)s:%(lineno)d] - ' \
          f'%(message)s'
    """
    fmt = f'%(asctime)s - ' \
          f'%(levelname)s - ' \
          f'[%(filename)s:%(funcName)s:%(lineno)d] - ' \
          f'%(message)s'
    filename = f'{name}_{datetime.now().strftime("%Y%m%d")}.log'
    log_path = os.path.join(conf.log_path, middle)
    try:
        if not os.path.exists(log_path):
            os.makedirs(log_path)
    except FileExistsError:
        pass
    log_file = os.path.join(log_path, filename)

    if change:
        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    logging.basicConfig(
        filename=log_file,
        encoding='utf8',
        format=fmt,
        level=level,
    )


def console_log(level=logging.DEBUG):
    fmt = f'%(asctime)s - %(levelname)s - ' \
          f'[%(filename)s:%(funcName)s:%(lineno)d] - ' \
          f'%(message)s'
    logging.basicConfig(
        format=fmt,
        level=level,
        # datefmt=f'%H:%M:%S'
    )


def move_and_merge(src_file, dst_dir):
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)

    base_name = os.path.basename(src_file)
    dst_file = os.path.join(dst_dir, base_name)
    if os.path.exists(dst_file):
        if not filecmp.cmp(src_file, dst_file, False):
            with open(dst_file, 'at', encoding='utf8') as dst:
                with open(src_file, 'rt', encoding='utf8') as src:
                    logging.info(f'로그 파일 병합')
                    data = src.read()
                    dst.write(data)
    else:
        logging.info(f'로그 파일 단순 이동')
        shutil.move(src_file, dst_file)


def manage_logfile():
    def is_target(f_name):
        # 디렉토리는 제외한다.
        if os.path.isdir(f_name):
            logging.info(f'디렉토리 제외')
            return False, ''

        # 파일 이름이 "*_20230523.log" 와 같은 형식을 가져야 한다.
        if len(f_name) < 14 or not f_name.endswith('.log') or f_name[-13] != '_':
            logging.info(f'파일 이름 조건 충족 실패')
            return False, ''

        # 오늘 날짜의 로그는 대상에서 제외한다.
        dt = f_name[-12:-4]
        today = str(datetime.today().date()).replace('-', '')
        if today == dt:
            logging.info(f'오늘 날짜 파일 제외')
            return False, ''

        # 주어진 날짜 정보는 존재하는 날이어야 한다.
        year, month, day = dt[:4], dt[4:6], dt[6:]
        try:
            datetime(int(year), int(month), int(day))
            return True, f'{year}/{month}/{day}'
        except ValueError:
            logging.info(f'존재하지 않는 날짜 제외')
            return False, ''

    logging.info(f'로그 파일 정리 시작')
    for file in os.listdir(conf.log_path):
        # 로그 디렉토리의 파일들을 필터링한다.
        abs_file = os.path.join(conf.log_path, file)
        logging.info(f'대상 파일 =|{abs_file}|')
        ret, info = is_target(abs_file)
        if not ret:
            continue

        # 이동하고 병합한다.
        dst_dir = os.path.join(conf.log_path, info)
        move_and_merge(abs_file, dst_dir)

    init_log(get_log_level(), 'root', change=True)


async def initialize_log():
    changed_flag = False
    t1 = datetime.strptime("0000", "%M%S").time()
    t2 = datetime.strptime("0005", "%M%S").time()
    t3 = datetime.strptime("0010", "%M%S").time()

    ok = ready_cont()[2]
    while ok():
        await aio.sleep(1)
        if not changed_flag:
            if t1 <= datetime.now().time() < t2:
                init_log(get_log_level(), None, change=True)
                changed_flag = True
        else:
            if t2 <= datetime.now().time() < t3:
                changed_flag = False

    return 'ok'


def get_log_level():
    return log_level


def set_log_level(level):
    global log_level
    log_level = level


if __name__ == '__main__':
    console_log()
    manage_logfile()
