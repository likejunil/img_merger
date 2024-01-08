import logging

import cx_Oracle

from conf.conf import config as conf
from src.comm.comm import cache_func


def show_db_info():
    print(conf.passwd)
    print(conf.user)
    print(conf.addr)
    print(conf.port)
    print(conf.db)


def get_db_info():
    user = conf.user
    addr = conf.addr
    port = conf.port
    db = conf.db
    passwd = conf.passwd
    return {
        'user': user,
        'passwd': passwd,
        'addr': addr,
        'port': port,
        'db': db,
    }


@cache_func
def get_db_conn():
    db_info = {}
    try:
        db_info = get_db_info()
        dsn = cx_Oracle.makedsn(db_info['addr'], db_info['port'], service_name=db_info['db'])
        conn = cx_Oracle.connect(db_info['user'], db_info['passwd'], dsn)
    except Exception as e:
        logging.error(
            f'데이터베이스 연결 실패, 에러=|{e}| \n'
            f'접속 정보 '
            f'user=|{db_info.get("user")}| '
            f'addr=|{db_info.get("addr")}| '
            f'port=|{db_info.get("port")}| '
            f'db=|{db_info.get("db")}| ')
        raise

    def get():
        return conn

    def close():
        conn.close()

    return get, close


def task(cur):
    for row in cur:
        print(row)


def query(conn, qsl, func):
    cur = conn.cursor()
    cur.execute(qsl)
    func(cur)
    cur.close()


def test():
    # show_db_info()
    get, close = get_db_conn()

    qsl = "SELECT * FROM LPAS_ORDER_I"
    query(get(), qsl, task)

    close()


if __name__ == '__main__':
    test()
