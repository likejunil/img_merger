import asyncio as aio
import logging
import pprint
import socket
import uuid
from multiprocessing import Queue
from queue import Full

import conf.constant as _
from src.comm.comm import ready_cont, get_loop, cache_func
from src.comm.db import get_connect, query_all, query_one, update
from src.comm.help import get_zip_path, get_pdf_path, make_zip_files
from src.comm.log import console_log
from src.comm.query import get_sql_lpas_group, get_sql_server_info, get_upd_lpas_group, get_sql_lpas_headers, \
    get_sql_lpas_items, get_upd_lpas_group_ret, get_upd_run_lpas_group, get_state_group_run, get_state_group_yes, \
    get_upd_err_lpas_group, get_col_lpas_items, get_state_header_yes, get_state_item_yes, \
    get_state_header_init, get_state_group_err


def get_my_info(hostname):
    ret_dict = {
        # 서버 이름
        'name': '',
        # 서버의 상태
        'status': _.standby,
        # 작업 대상
        'task': '',
    }

    sql, cols = get_sql_server_info(hostname)
    if server := query_one(sql):
        ret_dict['name'] = server[cols.server_name]
        ret_dict['status'] = server[cols.status]
        ret_dict['task'] = server[cols.newlb].strip() if server[cols.newlb] else ''

    return ret_dict


@cache_func
def server_status():
    # 서버 자신의 정보 읽기
    hostname = socket.gethostname()
    info = get_my_info(hostname)
    old_status = info["status"]
    logging.info(f'호스트=|{hostname}| 상태=|{old_status}| 태스크=|{info["task"]}|')

    def _get_info():
        return info

    def change():
        nonlocal info, old_status
        if info := get_my_info(hostname):
            status = info['status']
            if status != old_status:
                logging.info(f'서버 상태 변경 {old_status} => {status}')
                old_status = status

    def get_info():
        _info = _get_info()
        if _info['status'] == _.active:
            return _info

    return change, get_info


async def get_lpas_group():
    get_info = server_status()[1]
    ok = ready_cont()[2]
    while ok():
        # 서버의 상태가 active 가 될 때까지 1초 간격으로 폴링하여 확인
        # 실시간으로 서버의 상태를 감지하여 적용
        if not (info := get_info()):
            await aio.sleep(1)
            continue
        name = info['name']
        task = info['task']

        # g 테이블로부터 작업 시작
        # g 테이블에 해당 서버에게 맡겨진 작업이 있는지 확인
        sql, cols = get_sql_lpas_group(name)
        if g := query_one(sql):
            # 해당 작업을 진행하겠다고 표시
            update(get_upd_run_lpas_group(g[cols.mandt], g[cols.ebeln], g[cols.vbeln]))
            logging.debug(f'G 읽음=|{g}|')
            return g, cols

        # g 테이블에 해당 서버에게 맡길 작업이 없다면..
        # 주인 없는 작업을 찾아서 해당 서버에게 할당
        update(get_upd_lpas_group(name, task))
        await aio.sleep(1)


def get_lpas_headers(mandt, ebeln, vbeln):
    sql, cols = get_sql_lpas_headers(mandt, ebeln, vbeln)
    if h := query_all(sql):
        # logging.debug(f'H 읽음=|{h}|')
        return h, cols
    return [], []


def get_lpas_items(mandt, ebeln, vbeln, posnr, matnr):
    sql, cols = get_sql_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
    if h := query_all(sql):
        # logging.debug(f'I 읽음=|{h}|')
        return h, cols
    return [], []


async def next_job():
    ok = ready_cont()[2]
    while ok():
        try:
            ###################################
            # LPAS_ORDER_G 로부터 작업 조회
            # 작업을 조회할 때까지 대기
            ###################################
            ret = await get_lpas_group()
            if not ok():
                break
            g, g_cols = ret
            mandt = g[g_cols.mandt]
            ebeln = g[g_cols.ebeln]
            vbeln = g[g_cols.vbeln]
            lbpodat = g[g_cols.lbpodat]

            ###################################
            # LPAS_ORDER_H 로부터 작업 조회
            ###################################
            h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
            ret = True
            for h in h_list:
                zimgc = h[h_cols.zimgc]
                if zimgc and zimgc.upper() == 'Y':
                    continue
                posnr = h[h_cols.posnr]
                matnr = h[h_cols.matnr]
                l_size = h[h_cols.l_size].split('*')
                i_cnt = h[h_cols.i_cnt]

                ###################################
                # LPAS_ORDER_I 로부터 작업 조회
                ###################################
                i_list, i_cols = get_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
                if i_cnt != len(i_list):
                    logging.error(f'H 정보와 I 개수가 불일치 |{i_cnt}| != |{len(i_list)}|')
                    ret = False
                    break

                state = get_state_item_yes()
                if any([not i[i_cols.zimgc] or i[i_cols.zimgc].strip().upper() != state for i in i_list]):
                    logging.error(f'I 요소 불완전 |{zimgc.strip().upper()}|')
                    ret = False
                    break

                o_dict = {
                    'mandt': mandt,
                    'ebeln': ebeln,
                    'vbeln': vbeln,
                    'posnr': posnr,
                    'matnr': matnr,
                    'name': f'{get_pdf_path(lbpodat)}/{mandt}_{ebeln}_{vbeln}_{posnr}_{matnr}.pdf',
                    'size': (int(l_size[0]), int(l_size[1])),
                }
                yield i_list, o_dict

            if not ret:
                # 웹에서 관리자가 직접 다시 초기화를 해줘야..
                # 다시 웹라벨 생성 및 압축 파일을 만들 수 있음
                update(get_upd_run_lpas_group(mandt, ebeln, vbeln))
                logging.error(f'G 실패 기록 mandt=|{mandt}| ebeln=|{ebeln}| vbeln=|{vbeln}|')

        except Exception as e:
            logging.error(f'에러 발생=|{e}|')


async def update_status(period=1):
    logging.info(f'서버 상태 갱신 시작')
    change = server_status()[0]
    ok = ready_cont()[2]
    while ok():
        await aio.sleep(period)
        change()

    logging.info(f'서버 상태 갱신 종료')
    return 'ok'


# 함수 사용 예
def make_zip(mandt, ebeln, lbpodat):
    # ZIP/{yyyymmdd}/{mandt}_{ebeln}.zip
    zip_path = get_zip_path(lbpodat)
    zip_file = f'{zip_path}/{mandt}_{ebeln}.zip'
    # PDF/{yyyymmdd}/{mandt}_{ebeln}_{vbeln}_{posnr}_{matnr}.pdf
    pdf_path = get_pdf_path(lbpodat)
    make_zip_files(zip_file, pdf_path, f'{mandt}_{ebeln}', 'pdf')


async def update_result(period=1):
    logging.info(f'작업 결과 갱신 시작')
    get_info = server_status()[1]
    ok = ready_cont()[2]
    while ok():
        await aio.sleep(period)
        if not (info := get_info()):
            continue
        if info['status'] != _.active:
            continue

        ###################################
        # LPAS_ORDER_G 로부터 작업 조회
        ###################################
        name = info['name']
        sql, g_cols = get_sql_lpas_group(name, None, get_state_group_run())
        if not (g := query_one(sql)):
            continue
        mandt = g[g_cols.mandt]
        ebeln = g[g_cols.ebeln]
        vbeln = g[g_cols.vbeln]
        lbpodat = g[g_cols.lbpodat]

        ###################################
        # LPAS_ORDER_H 로부터 작업 조회
        ###################################
        h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
        if not len(h_list):
            update(get_upd_err_lpas_group(mandt, ebeln, vbeln))
            continue

        count = 0
        ret = ''
        for h in h_list:
            if zimgc := h[h_cols.zimgc]:
                # 웹라벨 생성 성공
                if (t := zimgc.strip().upper()) == get_state_header_yes():
                    count += 1
                # 웹라벨 생성 진행 중
                elif t in ('', get_state_header_init()):
                    pass
                # 웹라벨 생성 실패
                else:
                    ret = get_state_group_err()
                    break

        if count == len(h_list):
            make_zip(mandt, ebeln, lbpodat)
            ret = get_state_group_yes()

        if ret in (get_state_group_err(), get_state_group_yes()):
            update(get_upd_lpas_group_ret(mandt, ebeln, vbeln, ret))
            logging.info(f'G 갱신, mandt=|{mandt}| ebeln=|{ebeln}| vbeln=|{vbeln}| zimgc=|{ret}|')

    logging.info(f'작업 결과 갱신 종료')
    return 'ok'


async def get_job(job_q):
    logging.info(f'작업 지시 시작')
    ok = ready_cont()[2]
    while ok():
        async for job in next_job():
            while ok():
                try:
                    job_q.put_nowait(job)
                    break
                except aio.QueueFull:
                    logging.debug(f'큐가 가득참')
                except Exception as e:
                    logging.error(f'작업 지시 실패=|{e}|')
                await aio.sleep(1.0)

    logging.info(f'작업 지시 종료')
    return 'ok'


async def proc_job(cq, jq):
    def _f(d):
        return float(d) if d is not None else None

    def _i(d):
        return int(d) if d is not None else None

    logging.info(f'작업 진행 시작')
    g_cols = get_col_lpas_items(True)
    ok = ready_cont()[2]
    while ok():
        try:
            src = []
            jobs, o_dict = jq.get_nowait()
            for job in jobs:
                src.append({
                    'type_': job[g_cols.l_type],
                    'name': job[g_cols.i_filename],
                    'coordi': (_f(job[g_cols.l_coordi_x]), _f(job[g_cols.l_coordi_y])),
                    'size': (_f(job[g_cols.b_width]), _f(job[g_cols.b_height])),
                    'position': job[g_cols.i_position],
                    'rotate': _i(job[g_cols.l_rotate]),
                    'rate': _i(job[g_cols.i_rate]),
                    'priotiry': _i(job[g_cols.l_pri]),
                    'font': job[g_cols.t_font],
                    'font_size': _f(job[g_cols.t_fontsize]),
                    'font_color': (_i(job[g_cols.t_font_r]), _i(job[g_cols.t_font_g]), _i(job[g_cols.t_font_b])),
                    'text': job[g_cols.t_text],
                    'align': job[g_cols.t_align].lower() if job[g_cols.t_align] else None,
                    'valign': job[g_cols.t_valign].lower() if job[g_cols.t_valign] else None,
                })

            while ok():
                try:
                    key = str(uuid.uuid4())[:4]
                    jobs_dict = {
                        'input': {
                            'key': key,
                            'count': len(src),
                            'src': src,
                        },
                        'output': o_dict,
                    }
                    cq.put_nowait(jobs_dict)
                    logging.info(f'변환 모듈에게 작업 송신\n{pprint.pformat(jobs_dict)}')
                    break

                except Full:
                    logging.debug(f'큐가 가득참')
                except Exception as e:
                    logging.error(e)
                await aio.sleep(1)
            continue

        except aio.QueueEmpty:
            pass
        except Exception as e:
            logging.error(f'큐에서 작업 읽기 실패=|{e}|')
        await aio.sleep(0.1)

    logging.info(f'작업 진행 종료')
    return 'ok'


async def starter_proc(cq):
    logging.info(f'스타터 모듈 시작')
    jq = aio.Queue()
    loop = get_loop()

    ok = ready_cont()[2]
    while ok():
        try:
            # 서버의 상태를 읽고 갱신
            t1 = loop.create_task(update_status())
            # 작업의 결과를 갱신
            t2 = loop.create_task(update_result())
            # 데이터베이스 연결 및 job 을 읽어서 jq에 송신
            t3 = loop.create_task(get_job(jq))
            # jq에서 job을 수신하여 다른 프로세스에게 전달 및 제어
            t4 = loop.create_task(proc_job(cq, jq))

            ret = await aio.gather(t1, t2, t3, t4)
            logging.info(f'스타터 모듈 종료, 재시작=|{ret}|')
            get_connect()[1]()
            await aio.sleep(1)

        except Exception as e:
            logging.error(f'실시간 처리 예외 발생=|{e}|')
            await aio.sleep(1)

    logging.info(f'스타터 모듈 종료')
    cq.close()
    return 'ok'


async def test_sub(q):
    from queue import Empty
    ok = ready_cont()[2]
    while ok():
        try:
            d = q.get_nowait()
            logging.info(f'데이터 수신=|{d}|')
        except Empty:
            logging.debug(f'Queue 가 비었음')
            await aio.sleep(1)
        except Exception as e:
            logging.error(e)
            await aio.sleep(1)
    return 'ok'


async def test_main():
    q = Queue()
    loop = get_loop()
    t1 = loop.create_task(starter_proc(q))
    t2 = loop.create_task(test_sub(q))
    ret = await aio.gather(t1, t2)
    logging.info(f'테스트 결과=|{ret}|')


def test():
    aio.run(test_main())


if __name__ == '__main__':
    console_log()
    test()
