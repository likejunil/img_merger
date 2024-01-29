import asyncio as aio
import json
import logging
import os
import pprint
import subprocess
import threading
from collections import deque
from multiprocessing import Process, Queue
from queue import Full, Empty
from shutil import copy
from uuid import uuid4

from conf.conf import config as conf
from src.comm.comm import ready_cont, get_loop, ready_queue, tm
from src.comm.log import console_log
from src.converter.fonts import register_fonts
from src.converter.image import conv_jpg, conv_png, conv_eps, conv_pdf
from src.converter.qr import conv_bar, conv_qr, conv_dmtx
from src.converter.text import conv_txt
from src.converter.watcher import Watcher


def convert(filename):
    procs = {
        'jpg': conv_jpg,
        'jpeg': conv_jpg,
        'png': conv_png,
        'eps': conv_eps,
        'pdf': conv_pdf,
        'txt': conv_txt,
        'bar': conv_bar,
        'qr': conv_qr,
        'dmtx': conv_dmtx,
    }

    try:
        file_ext = os.path.splitext(filename)[1][1:].lower()
        if file_ext in conf.infile_ext:
            return procs[file_ext](filename)
        else:
            logging.error(f'|{filename}| 변환 미지원')
            return

    except Exception as e:
        logging.error(f'이미지 로드 실패 =|{e}|')


async def do_convert(watcher):
    ok = ready_cont()[2]
    while ok():
        b, r = watcher.get_ret()
        if b:
            logging.info(f'id =|{threading.get_ident()}| ret =|{r}|')
            # 무엇이든.. 하고 싶은 작업을 여기서 해라..
        await aio.sleep(0.5)
    watcher.stop_proc()


async def thread_main(path, proc):
    watcher = Watcher(path, proc)
    loop = get_loop()
    t1 = loop.create_task(watcher.run_proc())
    t2 = loop.create_task(do_convert(watcher))
    logging.info(f'태스크 생성 완료')

    ret = await aio.gather(t1, t2)
    logging.info(f'이벤트 루프 종료, 결과=|{ret}|')


def thread_proc(path, proc):
    aio.run(thread_main(path, proc))


async def run_converter(send_q, recv_q, jq):
    proc = convert
    in_path = os.path.join(conf.root_path, conf.in_path)

    # 메인 쓰레드만이 시그널 등록을 할 수 있음
    ok = ready_cont()[2]

    idx = 0
    path_list = []
    t_list = []
    logging.info(f'총 |{conf.path_count}|개의 디렉토리 모니터링')
    for i in range(conf.path_count):
        sub_path = os.path.join(in_path, str(i + 1))
        path_list.append(sub_path)
        t = Process(target=thread_proc, args=(sub_path, proc), daemon=True)
        t_list.append(t)
        t.start()

    def get_dst_path():
        nonlocal idx
        ret = path_list[idx]
        idx = (idx + 1) % conf.path_count
        return ret

    limit_cnt = 3
    while ok():
        if d := recv_q():
            d_dict = pprint.pformat(d)
            logging.info(f'스타터로부터 정보 수신=|{d_dict}|')

            i_dict = d.get('input', {})
            s_count = i_dict.get('count')
            s_key = i_dict.get('key')
            s_list = i_dict.get('src')
            fail_flag = False

            for s in s_list:
                # 이미지의 경우 원본 이미지를 목적 디렉토리로 복사
                if (t := s.get('type_', '').lower()) == 'image':
                    try:
                        src = s.get('name')
                        dst = f'{get_dst_path()}/{s_key}_{tm()}_{os.path.basename(s.get("name"))}'
                        logging.info(f'이미지 파일 복사, |{src}| => |{dst}|')
                        copy(src, dst)
                        continue
                    except FileNotFoundError as e:
                        logging.error(f'원본 파일 없음=|{e}|')
                    except PermissionError as e:
                        logging.error(f'파일 접근 권한 부족=|{e}|')
                    except IOError as e:
                        logging.error(f'입출력 오류 발생=|{e}|')
                    except Exception as e:
                        logging.error(f'복사 실패=|{e}|')
                    break

                # 텍스트의 경우 파일 이름을 임의로 생성하여
                elif t == 'text':
                    try:
                        f_name = f'{get_dst_path()}/{s_key}_{tm()}_{str(uuid4())[:4]}.txt'
                        with open(f_name, 'wt') as f:
                            json.dump(s, f, indent=4, ensure_ascii=False)
                            logging.info(f'텍스트 파일 생성=|{f_name}|')
                            continue
                    except IOError as e:
                        logging.error(f'파일 입출력 오류 발생=|{e}|')
                    except ValueError as e:
                        logging.error(f'데이터 인코딩 오류 발생=|{e}|')
                    except Exception as e:
                        logging.error(f'텍스트 파일 생성 실패=|{e}|')
                    break

                # 바코드
                elif t == 'barcode':
                    try:
                        pass
                    except Exception as e:
                        logging.error(f'바코드 파일 생성 실패=|{e}|')

                elif t == 'qrcode':
                    try:
                        pass
                    except Exception as e:
                        logging.error(f'QR코드 파일 생성 실패=|{e}|')

                elif t == 'dmx':
                    try:
                        pass
                    except Exception as e:
                        logging.error(f'DMX 파일 생성 실패=|{e}|')

                else:
                    logging.error(f'지원하지 않는 종류의 데이터=|{t}|')
                    fail_flag = True
                    break

            # 웹라벨 구성 요소를 pdf로 변환 실패
            if fail_flag or s_count:
                logging.error(f'웹라벨 생성 실패')
                try:
                    jq.put_nowait(s_key)
                except Exception as e:
                    logging.error(f'예외 발생=|{e}|')
                continue

            fail_cnt = 0
            while ok():
                if send_q(d):
                    logging.info(f'머저에게 정보 송신=|{d_dict}|')
                    break

                # 머저에게 데이터 송신 실패
                fail_cnt += 1
                if fail_cnt > limit_cnt:
                    logging.error(f'머저에게 정보 송신 실패(처리 필요), 데이터=|{d_dict}|')
                    break
                await aio.sleep(1)
            continue

        await aio.sleep(1)

    for t in t_list:
        t.terminate()
    for t in t_list:
        t.join()


async def delete_files(jq):
    logging.info(f'파일 정리 시작')
    # 변환 작업에 실패한 구성요소들은 여기서 삭제를 해야한다.
    # 병합 모듈에서 할 수 없다.
    target_list = deque(maxlen=5)

    ok = ready_cont()[2]
    while ok():
        try:
            await aio.sleep(1)
            s_key = jq.get_nowait()
            target_list.append(s_key)
            if len(target_list) > 1:
                target_key = target_list.popleft()
                command = f"find {conf.data_path} -name '{target_key}_*' -exec rm -rf {{}} \\;"
                r = subprocess.run(command, shell=True, check=True)
                logging.info(f'웹라벨 생성 실패 파일들 삭제=|{target_key}| 결과=|{r}|')

        except Exception as e:
            logging.debug(f'예외 발생=|{e}|')

    logging.info(f'파일 정리 종료')


async def converter_proc(rq, wq):
    logging.info(f'컨버터 모듈 시작')
    register_fonts()
    send_q, recv_q, close_q = ready_queue(wq, rq)
    jq = aio.Queue()
    loop = get_loop()

    ok = ready_cont()[2]
    while ok():
        try:
            t1 = loop.create_task(run_converter(send_q, recv_q, jq))
            t2 = loop.create_task(delete_files(jq))
            ret = await aio.gather(t1, t2)
            logging.info(f'컨버터 모듈 종료, 재시작=|{ret}|')
            await aio.sleep(1)

        except Exception as e:
            logging.error(f'실시간 처리 예외 발생=|{e}|')
            await aio.sleep(1)

    logging.info(f'컨버터 모듈 종료')
    close_q()
    return 'ok'


# async def converter_proc(rq, wq):
#     logging.info(f'컨버터 모듈 시작')
#     register_fonts()
#     send_q, recv_q, close_q = ready_queue(wq, rq)
#     await run_converter(send_q, recv_q)
#     logging.info(f'컨버터 모듈 종료')
#     close_q()
#     return 'ok'


async def test_sub1(q):
    def get_data():
        data = {
            'input': {
                # 'count': 20,
                'count': 11,
                'key': '4410',
                'src': [
                    {
                        'align': None,
                        'coordi': (None, None),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/Template/HK/GLB_G3.pdf',
                        'priotiry': 1,
                        'rotate': None,
                        'size': (240.0, 80.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (38.37, 38.37),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/productName/HK_127B_productName.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (144.0, 27.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None},
                    {
                        'align': None,
                        'coordi': (35.0, 35.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/image1/HK/HK_K127B_image1.eps',
                        'priotiry': 2,
                        'rotate': None,
                        'size': (75.0, 40.5),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.0, 35.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/image2/HK/HK_K127B_image2.eps',
                        'priotiry': 2,
                        'rotate': None,
                        'size': (54.3, 18.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (87.0, 87.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_hori.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (95.0, 18.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (11.0, 11.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_verti.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (17.0, 74.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (0.1, 0.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_1.eps',
                        'priotiry': 3,
                        'rotate': None,
                        'size': (35.0, 21.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (None, None),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_2.eps',
                        'priotiry': 3,
                        'rotate': None,
                        'size': (89.3, 3.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.1, 35.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_hori.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (147.0, 0.2),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.1, 35.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_verti.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (0.2, 56.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (183.3, 183.3),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/picto/HK_K127B_picto.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (32.42, 40.94),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    """
                    {
                        'align': None,
                        'coordi': (178.8, 178.8),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/barcode/8808563461533.png',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (40.0, 15.5),
                        'text': '8808563461533',
                        'type_': 'BARCODE',
                        'valign': None
                    },
                    {
                        'align': 'center',
                        'coordi': (37.0, 37.0),
                        'font': 'Helvetica-Bold',
                        'font_color': (None, None, None),
                        'font_size': 39.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (140.0, 14.0),
                        'text': '235/65R18 91Y XL',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'right',
                        'coordi': (29.5, 29.5),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 16.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (44.6, 5.85),
                        'text': '235/65R18 91Y XL',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (39.0, 39.0),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 9.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (140.0, 8.5),
                        'text': 'Pleasure cross point between performance and '
                                'emotion',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'left',
                        'coordi': (29.3, 29.3),
                        'font': 'Helvetica-Bold',
                        'font_color': (None, None, None),
                        'font_size': 16.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (21.0, 6.2),
                        'text': 'K127B',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (182.0, 182.0),
                        'font': 'Helvetica-heavy',
                        'font_color': (None, None, None),
                        'font_size': 20.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (34.6, 8.3),
                        'text': '1234567',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'right',
                        'coordi': (3.6, 3.6),
                        'font': 'Helvetica-heavy',
                        'font_color': (None, None, None),
                        'font_size': 24.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (44.0, 9.5),
                        'text': '1234567',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (185.3, 185.3),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 7.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (27.7, 2.8),
                        'text': 'NOT FOR SALE IN JAPAN',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'left',
                        'coordi': (3.5, 3.5),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 5.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (20.3, 1.85),
                        'text': 'J-0001044483-230915',
                        'type_': 'TEXT',
                        'valign': 'top'
                    }
                    """
                ]
            },
            'output': {
                'name': '/LPAS/lpas/data/done_files/PDF/20230901/110_9999036431_9999036431_000010_1024881.pdf',
                'size': (80, 240)
            }
        }
        return data

    try:
        q.put_nowait(get_data())
    except Full:
        logging.debug(f'큐가 가득참')
    except Exception as e:
        logging.error(f'작업 송신 실패=|{e}|')
    return 'ok'


async def test_sub2(q):
    ok = ready_cont()[2]
    while ok():
        try:
            ret = q.get_nowait()
            logging.info(f'{pprint.pformat(ret)}')
        except Empty:
            logging.debug(f'큐가 비었음')
        except Exception as e:
            logging.error(f'결과 수신 실패=|{e}|')
        await aio.sleep(1)
    return 'ok'


async def test_main():
    sq, rq = Queue(), Queue()
    loop = get_loop()
    t1 = loop.create_task(converter_proc(rq, sq))
    t2 = loop.create_task(test_sub1(rq))
    t3 = loop.create_task(test_sub2(sq))
    ret = await aio.gather(t1, t2, t3)
    logging.info(f'테스트 결과=|{ret}|')


def test():
    aio.run(test_main())


if __name__ == '__main__':
    console_log()
    test()
