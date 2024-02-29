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
from conf.constant import pdf
from src.comm.comm import ready_cont, get_loop, ready_queue, tm
from src.comm.db import update
from src.comm.log import console_log, initialize_log
from src.comm.query import get_upd_err_lpas_header
from src.converter.core import change_ext
from src.converter.fonts import register_fonts
from src.converter.image import conv_jpg, conv_png, conv_eps, conv_pdf
from src.converter.qr import conv_bar, conv_qr, conv_dmx
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
        'ean': conv_bar,
        'upc': conv_bar,
        'qr': conv_qr,
        'dmx': conv_dmx,
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
        await aio.sleep(0.1)
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

    o_path = f'{conf.root_path}/{conf.out_path}'
    limit_cnt = 3
    while ok():
        if d := recv_q():
            d_dict = pprint.pformat(d)
            logging.info(f'스타터로부터 정보 수신=|{d_dict}|')

            i_dict = d.get('input', {})
            s_count = i_dict.get('count')
            s_key = i_dict.get('key')
            s_list = i_dict.get('src')

            o_dict = d.get('output', {})
            mandt = o_dict.get('mandt')
            ebeln = o_dict.get('ebeln')
            vbeln = o_dict.get('vbeln')
            posnr = o_dict.get('posnr')
            matnr = o_dict.get('matnr')

            count = 0
            fail_flag = False
            for s in s_list:
                # 이미지의 경우 원본 이미지를 목적 디렉토리로 복사
                if (t := s.get('type_', '').lower()) == 'image':
                    try:
                        src = s.get('name')
                        i_name = f'{s_key}_{tm()}_{os.path.basename(src)}'
                        f_name = f'{get_dst_path()}/{i_name}'
                        s['target'] = change_ext(f'{o_path}/{i_name}', pdf)
                        logging.info(f'이미지 파일 복사, |{src}| => |{f_name}|')
                        copy(src, f_name)
                        logging.info(f'파일 복사 완료, |{src}| => |{f_name}|')
                        count += 1
                        continue

                    except FileNotFoundError as e:
                        logging.error(f'원본 파일 없음(i)=|{e}| 파일=|{src}|')
                    except PermissionError as e:
                        logging.error(f'파일 접근 권한 부족(i)=|{e}| 파일=|{src}| ')
                    except IOError as e:
                        logging.error(f'입출력 오류 발생(i)=|{e}| 파일=|{src}|')
                    except Exception as e:
                        logging.error(f'복사 실패(i)=|{e}| 파일=|{src}|')
                    fail_flag = True
                    break

                # 텍스트의 경우 파일 이름을 임의로 생성
                elif t == 'text':
                    try:
                        i_name = f'{s_key}_{tm()}_{str(uuid4())[:8]}.txt'
                        f_name = f'{get_dst_path()}/{i_name}'
                        s['target'] = change_ext(f'{o_path}/{i_name}', pdf)
                        with open(f_name, 'wt') as f:
                            json.dump(s, f, indent=4, ensure_ascii=False)
                            logging.info(f'텍스트 파일 생성=|{f_name}|')
                            count += 1
                            continue

                    except FileNotFoundError as e:
                        logging.error(f'원본 파일 없음(t)=|{e}|')
                    except IOError as e:
                        logging.error(f'파일 입출력 오류 발생(t)=|{e}|')
                    except ValueError as e:
                        logging.error(f'데이터 인코딩 오류 발생(t)=|{e}|')
                    except Exception as e:
                        logging.error(f'텍스트 파일 생성 실패(t)=|{e}|')
                    fail_flag = True
                    break

                # 바코드
                elif t in ('ean', 'upc', 'qr', 'dmx'):
                    try:
                        s['target'] = s.get('name')
                        if not os.path.exists(s.get('name')):
                            # 바코드 이미지가 존재하지 않는다면 생성 지시
                            f_name = f'{get_dst_path()}/{s_key}_{tm()}_{str(uuid4())[:8]}.{t}'
                            logging.info(f'바코드가 존재하지 않음, 새로 생성=|{f_name}|')
                            with open(f_name, 'wt') as f:
                                json.dump(s, f, indent=4, ensure_ascii=False)
                                logging.info(f'바코드 정보=|{s}|')
                                count += 1
                                continue
                        else:
                            logging.info(f'이미 바코드 이미지 존재=|{s.get("name")}|')
                            count += 1
                            continue

                    except IOError as e:
                        logging.error(f'파일 입출력 오류 발생=|{e}|')
                    except Exception as e:
                        logging.error(f'바코드 정보 파일 생성 실패=|{e}|')
                    fail_flag = True
                    break

                else:
                    logging.error(f'지원하지 않는 종류의 데이터=|{t}|')
                    fail_flag = True
                    break

            # 웹라벨 구성 요소를 pdf로 변환 실패
            if fail_flag or s_count != count:
                logging.error(f'웹라벨 생성 실패, 실패_플래그=|{fail_flag}| 구성요소=|{count}/{s_count}|')
                update(get_upd_err_lpas_header(mandt, ebeln, vbeln, posnr, matnr))

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

        await aio.sleep(0.1)

    for t in t_list:
        t.terminate()
    for t in t_list:
        t.join()
    return 'ok'


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
    return 'ok'


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
            t3 = loop.create_task(initialize_log())
            ret = await aio.gather(t1, t2, t3)
            logging.info(f'컨버터 모듈 종료, 재시작=|{ret}|')
            await aio.sleep(1)

        except Exception as e:
            logging.error(f'실시간 처리 예외 발생=|{e}|')
            await aio.sleep(1)

    logging.info(f'컨버터 모듈 종료')
    close_q()
    return 'ok'


async def test_sub1(q):
    def get_data():
        data = {

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
