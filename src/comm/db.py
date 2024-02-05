import logging
from time import sleep

import cx_Oracle

from conf.conf import config as conf
from src.comm.comm import cache_func


def get_auth_info():
    logging.info(f'오라클 접속 정보_계정:주소:포트:서비스=|{conf.user}:{conf.addr}:{conf.port}:{conf.db}:{conf.passwd}|')
    return conf.user, conf.passwd, conf.addr, conf.port, conf.db


@cache_func
def get_connect():
    user, passwd, host, port, service = get_auth_info()
    conn = cx_Oracle.connect(user, passwd, f'{host}:{port}/{service}', encoding="UTF-8")

    def check_conn(conn_):
        # 인자로 주어진 커넥션이 유효한가에 대해서만 기능한다.
        try:
            if conn_:
                conn_.ping()
                return True
        except cx_Oracle.DatabaseError as e:
            logging.error(f'데이터베이스와 연결이 끊어졌습니다. |{e}|')
            return False

    def connect():
        nonlocal conn

        if check_conn(conn):
            return conn

        f_count = 0
        conn = None
        while True:
            try:
                if not conn:
                    nonlocal user, passwd, host, port, service
                    user, passwd, host, port, service = get_auth_info()
                    conn = cx_Oracle.connect(user, passwd, f'{host}:{port}/{service}', encoding="UTF-8")
                    return conn

            except Exception as e:
                f_count += 1
                logging.error(f'데이터베이스 연결 실패(횟수={f_count}), {e}')
                sleep(1)

    def close():
        nonlocal conn
        if conn:
            logging.info(f'데이터베이스 연결 종료')
            conn.close()
            conn = None

    return connect, close


def _get_cursor():
    return get_connect()[0]().cursor()


def _call_query(sql, *in_data):
    cursor = _get_cursor()
    cursor.execute(sql, in_data) if in_data else cursor.execute(sql)
    return cursor


def query_one_by_one(sql, *in_data):
    try:
        cursor = _call_query(sql, *in_data)

        def get():
            if out_data := cursor.fetchone():
                return out_data
            cursor.close()

        return get

    except Exception as e:
        logging.error(f'에러발생 =|{e}|')


def query_one(sql, *in_data):
    try:
        cursor = _call_query(sql, *in_data)
        out_data = cursor.fetchone()
        cursor.close()
        return out_data
    except Exception as e:
        logging.error(f'에러발생 =|{e}|')


def query_all(sql, *in_data):
    try:
        cursor = _call_query(sql, *in_data)
        out_data = cursor.fetchall()
        cursor.close()
        return out_data
    except Exception as e:
        logging.error(f'에러발생 =|{e}|')


def query_many(n, sql, *in_data):
    try:
        cursor = _call_query(sql, *in_data)
        out_data = cursor.fetchmany(n)
        cursor.close()
        return out_data
    except Exception as e:
        logging.error(f'에러발생 =|{e}|')


def commit():
    get_connect()[0]().commit()


def update(sql, *in_data):
    try:
        cursor = _call_query(sql, *in_data)
        commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f'에러발생 =|{e}|')


def test_1(n):
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

    def test_11():
        sql = get_test_query()
        args = get_test_args()
        for row in query_many(10, sql, *args):
            print(row)
        get_connect()[1]()

    def test_12():
        for _ in range(3):
            if row := query_one(get_test_query(), *get_test_args()):
                print(row)
                continue
            break
        get_connect()[1]()

    def test_13():
        get = query_one_by_one(get_test_query(), *get_test_args())
        while row := get():
            print(row)
        get_connect()[1]()

    func = [test_11, test_12, test_13]
    if 0 < n <= len(func):
        return func[n - 1]()


if __name__ == '__main__':
    test_1(1)
