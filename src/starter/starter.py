import asyncio as aio
import logging
import socket
from multiprocessing import Queue
from time import sleep

import conf.constant as _
from src.comm.comm import ready_cont, get_loop, cache_func
from src.comm.db import get_connect, query_all, query_one, update
from src.comm.log import console_log
from src.starter.query import get_sql_lpas_group, get_sql_server_info, get_upd_lpas_group, get_sql_lpas_headers, \
    get_sql_lpas_items, get_upd_lpas_headers_ret, get_upd_lpas_group_ret


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
    logging.info(f'호스트=|{hostname}| 시작 상태=|{old_status}|')

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


async def update_status(period=1):
    logging.info(f'서버 상태 갱신 시작')
    change = server_status()[0]

    ok = ready_cont()[2]
    while ok():
        await aio.sleep(period)
        change()

    logging.info(f'서버 상태 갱신 종료')


def get_lpas_group(name, task):
    ok = ready_cont()[2]
    while ok():
        sql, cols = get_sql_lpas_group(name, task)
        if g := query_one(sql):
            # ('110', '9999036431', '9999036432', None)
            logging.info(f'g 를 읽음=|{g}|')
            return g, cols

        update(get_upd_lpas_group(name, task))
        sleep(0.01)


def get_lpas_headers(mandt, ebeln, vbeln):
    sql, cols = get_sql_lpas_headers(mandt, ebeln, vbeln)
    if h := query_all(sql):
        logging.info(f'h 를 읽음=|{h}|')
        return h, cols
    return [], []


def get_lpas_items(mandt, ebeln, vbeln, posnr, matnr):
    sql, cols = get_sql_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
    if h := query_all(sql):
        logging.info(f'i 를 읽음=|{h}|')
        return h, cols
    return [], []


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

        # LPAS_ORDER_G 로부터 작업 조회
        name = info['name']
        task = info['task']
        sql, g_cols = get_sql_lpas_group(name, task)
        if not (g := query_one(sql)):
            continue
        mandt = g[g_cols.mandt]
        ebeln = g[g_cols.ebeln]
        vbeln = g[g_cols.vbeln]

        # LPAS_ORDER_H 로부터 작업 조회
        h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
        if not len(h_list):
            update(get_upd_lpas_group_ret(mandt, ebeln, vbeln, 'E'))
            continue

        g_ret = 'Y'
        h_ret = 'Y'
        for h in h_list:
            posnr = h[h_cols.posnr]
            matnr = h[h_cols.matnr]
            i_cnt = h[h_cols.image_cnt]

            # LPAS_ORDER_I 로부터 작업 조회
            i_list, i_cols = get_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
            if not i_cnt or i_cnt != len(i_list):
                update(get_upd_lpas_headers_ret(mandt, ebeln, vbeln, posnr, matnr, 'E'))
                continue

            for i in i_list:
                if i[i_cols.zimgc].upper() != 'Y':
                    g_ret = 'E'
                    h_ret = 'E'
                    break
            update(get_upd_lpas_headers_ret(mandt, ebeln, vbeln, posnr, matnr, h_ret))
        update(get_upd_lpas_group_ret(mandt, ebeln, vbeln, g_ret))

    logging.info(f'작업 결과 갱신 종료')


def next_job():
    ret = True
    ok = ready_cont()[2]
    while ok():
        info = yield ret
        logging.info(f'작업을 읽기 위한 서버 정보 수신=|{info}|')
        task = info['task']
        name = info['name']

        # LPAS_ORDER_G 로부터 작업 조회
        g, g_cols = get_lpas_group(name, task)
        if not ok():
            break
        mandt = g[g_cols.mandt]
        ebeln = g[g_cols.ebeln]
        vbeln = g[g_cols.vbeln]

        ret = []
        # LPAS_ORDER_H 로부터 작업 조회
        h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
        for h in h_list:
            # LPAS_ORDER_I 로부터 작업 조회
            posnr = h[h_cols.posnr]
            matnr = h[h_cols.matnr]
            i_cnt = h[h_cols.image_cnt]
            i_list, i_cols = get_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
            if i_cnt != len(i_list):
                break
            ret = i_list


async def get_job(job_q):
    logging.info(f'작업 지시 시작')
    get_info = server_status()[1]
    g = next_job()
    r = next(g)
    logging.info(f'작업을 읽기 위한 제너레이터 생성=|{r}|')

    _, stop, ok = ready_cont()
    while ok():
        info = {}
        while ok():
            if not (info := get_info()):
                logging.debug(f'서버정보 획득 실패')
                await aio.sleep(1)
                continue
            break

        logging.info(f'서버정보 전달=|{info}|')
        if not (task := g.send(info)):
            continue
        logging.info(f'작업을 읽음=|{task}|')
        while ok():
            try:
                job_q.put(task)
                logging.info(f'작업을 전달=|{task}|')
                break
            except Exception as e:
                logging.error(f'작업 지시 실패=|{e}|')
                await aio.sleep(1)

        await aio.sleep(0.1)

    get_connect()[1]()
    logging.info(f'작업 지시 종료')
    stop()


async def proc_job(cq, mq, jq):
    logging.info(f'작업 진행 시작')

    _, stop, ok = ready_cont()
    while ok():
        try:
            job = jq.get()
            logging.info(f'작업 수신=|{job}|')
            # ...
            # 작업 진행
            # ...

        except Exception as e:
            logging.error(f'큐에서 작업 읽기 실패=|{e}|')
            await aio.sleep(1)

    logging.info(f'작업 진행 종료')
    stop()


async def starter_proc(cq, mq):
    logging.info(f'스타터 모듈 시작')
    jq = Queue()
    loop = get_loop()

    ok = ready_cont()[2]
    while ok():
        try:
            # 서버의 상태를 읽고 갱신
            t1 = loop.create_task(update_status())
            # 작업의 결과를 갱신
            # t2 = loop.create_task(update_result())
            # 데이터베이스 연결 및 job 을 읽어서 jq에 송신
            # t3 = loop.create_task(get_job(jq))
            # jq에서 job을 수신하여 다른 프로세스에게 전달 및 제어
            # t4 = loop.create_task(proc_job(cq, mq, jq))
            # ret = await aio.gather(t1, t2, t3, t4)
            ret = await aio.gather(t1)
            logging.info(f'스타터 모듈 종료, 재시작=|{ret}|')
            await aio.sleep(1)

        except Exception as e:
            logging.error(f'실시간 처리 예외 발생=|{e}|')
            await aio.sleep(1)

    logging.info(f'스타터 모듈 종료')


def test():
    console_log()
    aio.run(starter_proc(None, None))


if __name__ == '__main__':
    test()
