import logging
from time import sleep

import cx_Oracle

from conf.conf import config as conf
from src.comm.comm import cache_func
from src.comm.log import console_log


def get_auth_info():
    console_log()
    logging.info(f'오라클 접속 정보_계정:주소:포트:서비스=|{conf.user}:{conf.addr}:{conf.port}:{conf.db}:{conf.passwd}|')
    return conf.user, conf.passwd, conf.addr, conf.port, conf.db


@cache_func
def get_connect():
    user, passwd, host, port, service = get_auth_info()
    conn = cx_Oracle.connect(user, passwd, f'{host}:{port}/{service}', encoding="UTF-8")

    def check_conn():
        try:
            if conn:
                conn.ping()
                return True
        except cx_Oracle.DatabaseError as e:
            logging.error(f'데이터베이스와 연결이 끊어졌습니다. |{e}|')
            return False

    def connect(check=False):
        nonlocal conn

        if check:
            if not check_conn():
                conn = None

        while True:
            try:
                if not conn:
                    nonlocal user, passwd, host, port, service
                    user, passwd, host, port, service = get_auth_info()
                    conn = cx_Oracle.connect(user, passwd, f'{host}:{port}/{service}', encoding="UTF-8")
                break
            except Exception as e:
                logging.error(f'데이터베이스 연결 실패, {e}')
                sleep(1)

        return conn

    def close():
        if conn:
            logging.info(f'데이터베이스 연결 종료')
            conn.close()

    return connect, close


def get_cursor(check=False):
    return get_connect()[0](check).cursor()


def commit(check=False):
    get_connect()[0](check).commit()


def call_query(sql, *in_data):
    cursor = get_cursor()
    cursor.execute(sql, in_data)
    return cursor


def query_one_by_one(sql, *in_data):
    cursor = call_query(sql, *in_data)

    def get():
        if out_data := cursor.fetchone():
            return out_data
        cursor.close()

    return get


def query_one(sql, *in_data):
    cursor = call_query(sql, *in_data)
    out_data = cursor.fetchone()
    cursor.close()
    return out_data


def query_many(n, sql, *in_data):
    cursor = call_query(sql, *in_data)
    out_data = cursor.fetchmany(n)
    cursor.close()
    return out_data


def test(n):
    def get_test_query():
        return \
            """
            SELECT *
            FROM LPAS_ORDER_I
            WHERE MANDT = :1
              AND EBELN = :2
              AND EBELP = :3
              AND VBELN = :4
              AND POSNR = :5
              AND MATNR = :6
            """

    def get_test_args():
        mandt = '110'
        ebeln = '9999036431'
        ebelp = '00010'
        vbeln = '9999036431'
        posnr = '000010'
        matnr = '1024881'
        return [mandt, ebeln, ebelp, vbeln, posnr, matnr]

    def test_1():
        for row in query_many(10, get_test_query(), *get_test_args()):
            print(row)
        get_connect()[1]()

    def test_2():
        for _ in range(3):
            if row := query_one(get_test_query(), *get_test_args()):
                print(row)
                continue
            break
        get_connect()[1]()

    def test_3():
        get = query_one_by_one(get_test_query(), *get_test_args())
        while row := get():
            print(row)
        get_connect()[1]()

    func = [test_1, test_2, test_3]
    if 0 < n <= len(func):
        return func[n - 1]()


if __name__ == '__main__':
    test(3)
