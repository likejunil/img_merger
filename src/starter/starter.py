import asyncio as aio
import logging
import socket

import conf.constant as _
from src.comm.comm import ready_cont, get_loop, cache_func
from src.comm.db import get_connect, query_all, query_one, update
from src.comm.log import console_log
from src.starter.query import get_sql_lpas_group, get_sql_server_info, get_upd_lpas_group, get_sql_lpas_headers, \
    get_sql_lpas_items, get_upd_lpas_group_ret, get_upd_run_lpas_group, get_state_group_run, get_state_group_yes, \
    get_state_group_err, get_upd_err_lpas_group


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


async def get_lpas_group(name, task):
    ok = ready_cont()[2]
    while ok():
        sql, cols = get_sql_lpas_group(name)
        if g := query_one(sql):
            update(get_upd_run_lpas_group(g[cols.mandt], g[cols.ebeln], g[cols.vbeln]))
            logging.debug(f'G 읽음=|{g}|')
            return g, cols

        update(get_upd_lpas_group(name, task))
        await aio.sleep(0.1)


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
    get_info = server_status()[1]
    ok = ready_cont()[2]
    while ok():
        try:
            if not (info := get_info()):
                logging.debug(f'서버정보 획득 실패')
                await aio.sleep(1)
                continue

            logging.info(f'작업을 읽기 위한 서버 정보 수신=|{info}|')
            task = info['task']
            name = info['name']

            # LPAS_ORDER_G 로부터 작업 조회
            ret = await get_lpas_group(name, task)
            if not ok():
                break
            g, g_cols = ret
            mandt = g[g_cols.mandt]
            ebeln = g[g_cols.ebeln]
            vbeln = g[g_cols.vbeln]

            # LPAS_ORDER_H 로부터 작업 조회
            h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
            for h in h_list:
                zimgc = h[h_cols.zimgc]
                if zimgc and zimgc.upper() == 'Y':
                    continue

                # LPAS_ORDER_I 로부터 작업 조회
                posnr = h[h_cols.posnr]
                matnr = h[h_cols.matnr]
                i_cnt = h[h_cols.i_cnt]
                i_list, i_cols = get_lpas_items(mandt, ebeln, vbeln, posnr, matnr)
                if i_cnt != len(i_list):
                    break
                for i in i_list:
                    zimgc = i[i_cols.zimgc]
                    if not zimgc or zimgc.strip().upper() != get_state_group_yes():
                        break

                yield i_list

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


async def update_result(period=0.1):
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
        sql, g_cols = get_sql_lpas_group(name, None, get_state_group_run())
        if not (g := query_one(sql)):
            continue
        mandt = g[g_cols.mandt]
        ebeln = g[g_cols.ebeln]
        vbeln = g[g_cols.vbeln]

        # LPAS_ORDER_H 로부터 작업 조회
        h_list, h_cols = get_lpas_headers(mandt, ebeln, vbeln)
        if not len(h_list):
            update(get_upd_err_lpas_group(mandt, ebeln, vbeln))
            continue

        yes_cnt = 0
        ret = ''
        for h in h_list:
            if zimgc := h[h_cols.zimgc]:
                if zimgc.strip().upper() == get_state_group_yes():
                    yes_cnt += 1
                elif zimgc.strip() != '':
                    ret = get_state_group_err()
                    break
        if yes_cnt == len(h_list):
            ret = get_state_group_yes()
        if ret:
            update(get_upd_lpas_group_ret(mandt, ebeln, vbeln, ret))
            logging.info(f'G 갱신, mandt=|{mandt}| ebeln=|{ebeln}| vbeln=|{vbeln}| zimgc=|{ret}|')

    logging.info(f'작업 결과 갱신 종료')
    return 'ok'


async def get_job(job_q):
    logging.info(f'작업 지시 시작')
    ok = ready_cont()[2]
    while ok():
        async for task in next_job():
            logging.info(f'작업을 읽음=|{task}|')
            while ok():
                try:
                    job_q.put_nowait(task)
                    logging.info(f'작업을 전달=|{task}|')
                    break
                except aio.QueueFull:
                    logging.error(f'큐가 가득참')
                    await aio.sleep(1.0)
                except Exception as e:
                    logging.error(f'작업 지시 실패=|{e}|')
                    await aio.sleep(1.0)

    logging.info(f'작업 지시 종료')
    return 'ok'


async def proc_job(cq, mq, jq):
    logging.info(f'작업 진행 시작')
    ok = ready_cont()[2]
    while ok():
        try:
            job = jq.get_nowait()
            logging.info(f'작업 수신=|{job}|')
            # ...
            # 작업 진행
            # ...
        except aio.QueueEmpty:
            await aio.sleep(1.0)
        except Exception as e:
            logging.error(f'큐에서 작업 읽기 실패=|{e}|')
            await aio.sleep(1.0)

    logging.info(f'작업 진행 종료')
    return 'ok'


async def starter_proc(cq, mq):
    logging.info(f'스타터 모듈 시작')
    jq = aio.Queue()
    loop = get_loop()

    ok = ready_cont()[2]
    while ok():
        try:
            # 서버의 상태를 읽고 갱신
            t1 = loop.create_task(update_status(1))
            # 작업의 결과를 갱신
            t2 = loop.create_task(update_result(1))
            # 데이터베이스 연결 및 job 을 읽어서 jq에 송신
            t3 = loop.create_task(get_job(jq))
            # jq에서 job을 수신하여 다른 프로세스에게 전달 및 제어
            t4 = loop.create_task(proc_job(cq, mq, jq))

            ret = await aio.gather(t1, t2, t3, t4)
            logging.info(f'스타터 모듈 종료, 재시작=|{ret}|')
            get_connect()[1]()
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
