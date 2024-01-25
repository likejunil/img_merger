import json
import logging
import os
from time import sleep

from conf.conf import config as conf
from src.comm.comm import ready_cont
from src.starter.starter import server_status


def main():
    """
    filename = 'jabinfo.text'
    data = {
        'font': 'Helvetica',
        'size': '6',
        'bold': False,
        'italic': False,
        'align': 'left',
        'rotate': 90,
        'letter-space': 0,
        'content': 'D-0000100664-221006',
        'coordi_x': 214.607,
        'coordi_y': 64.94,
        'width': 2.269,
        'height': 24,
    }
    """
    filename = 'Size_spec.text'
    data = {
        'font': 'Helvetica',
        'size': '48',
        'bold': True,
        'italic': False,
        'align': 'center',
        'rotate': 0,
        'letter-space': 0,
        'content': '205/50R17 93W XL',
        'coordi_x': 111.685,
        'coordi_y': 63.678,
        'width': 178,
        'height': 18.203,
    }
    """
    filename = 'M_code.text'
    data = {
        'font': 'Helvetica',
        'size': '21.1',
        'bold': True,
        'italic': False,
        'align': 'center',
        'rotate': 0,
        'letter-space': 0,
        'content': '1014070',
        'coordi_x': 182.683,
        'coordi_y': 32.488,
        'width': 32,
        'height': 8,
    }
    """
    in_path = os.path.join(conf.root_path, conf.in_path)
    output = os.path.join(in_path, filename)
    with open(output, mode='wt', encoding='utf8') as f:
        json.dump(data, f)


def test_1():
    import subprocess

    print(f'현재 디렉토리=|{os.getcwd()}|')
    print(f'{conf.root_path}')
    base = conf.root_path
    i_file = f'{base}/data/RU_HK_v8.pdf'
    o_file = f'{base}/data/out.png'

    # Ghostscript 명령 예시: PDF 파일을 PNG 이미지로 변환
    command = ["gs", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-r300",
               f"-sOutputFile={o_file}", f"{i_file}"]

    # subprocess를 사용하여 명령 실행
    subprocess.run(command)


def loop_test(sq, rq):
    count = 0
    ok = ready_cont()[2]
    while ok():
        msg = f'{os.getpid()} 현재 카운트=|{count}|'
        sq(msg)
        logging.info(f'송신=|{msg}|')
        msg = rq()
        logging.info(f'수신=|{msg}|')
        count += 1
        sleep(1)


def test_2():
    update, get_info = server_status()
    info = get_info()
    print(info)
    update()
    info = get_info()
    print(info)


def test_3():
    from datetime import datetime as dt
    ret = dt.now().strftime('%Y%m%d')
    print(ret)


if __name__ == '__main__':
    test_3()
