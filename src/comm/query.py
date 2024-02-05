import logging
from collections import namedtuple


############################
# lpas_order_g,h,i 테이블의 zimgc 컬럼 상태값
############################
def get_state_group_init():
    # return 'I'
    return ''


def get_state_group_run():
    return 'R'


def get_state_group_yes():
    return 'Y'


def get_state_group_err():
    return 'E'


def get_state_header_init():
    # return 'I'
    return ''


def get_state_header_yes():
    return 'Y'


def get_state_header_err():
    return 'E'


def get_state_item_yes():
    return 'Y'


############################
# update
############################
def get_upd_lpas_group(name, newlb=None):
    newlb_sql = f" AND NEWLB = '{newlb}' " if newlb else ""
    sql = \
        f" UPDATE LPAS_ORDER_G " \
        f" SET SERVER = '{name}' " \
        f" WHERE 1 = 1 " \
        f" AND ROWNUM = 1 " \
        f" AND (TRIM(ZIMGC) IS NULL OR TRIM(ZIMGC) = '{get_state_group_init()}')" \
        f" AND TRIM(SERVER) IS NULL " \
        f" {newlb_sql} "
    logging.debug(f'{sql}')
    return sql


def get_upd_lpas_group_ret(mandt, ebeln, vbeln, zimgc):
    # zimgc 의 값을 R 으로 갱신하려면, zimgc 가 초기화 상태여야 한다.
    # zimgc 의 값을 R 이외의 값으로 갱신하려면, zimgc 가 R 상태여야 한다.
    zimgc_sql = f" AND (TRIM(ZIMGC) IS NULL OR TRIM(ZIMGC) = '{get_state_group_init()}')" \
        if zimgc == get_state_group_run() \
        else f" AND TRIM(ZIMGC) = '{get_state_group_run()}' "
    sql = \
        f" UPDATE LPAS_ORDER_G " \
        f" SET ZIMGC = '{zimgc}' " \
        f" WHERE 1 = 1 " \
        f"{zimgc_sql}" \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' "
    logging.debug(f'{sql}')
    return sql


def get_upd_run_lpas_group(mandt, ebeln, vbeln):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, get_state_group_run())


def get_upd_yes_lpas_group(mandt, ebeln, vbeln):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, get_state_group_yes())


def get_upd_err_lpas_group(mandt, ebeln, vbeln, err=None):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, err if err else get_state_group_err())


def get_upd_lpas_header_ret(mandt, ebeln, vbeln, posnr, matnr, ret):
    sql = \
        f" UPDATE LPAS_ORDER_H " \
        f" SET ZIMGC = '{ret}' " \
        f" WHERE 1 = 1 " \
        f" AND (TRIM(ZIMGC) IS NULL OR TRIM(ZIMGC) = '{get_state_header_init()}')" \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' " \
        f" AND POSNR = '{posnr}' " \
        f" AND MATNR = '{matnr}' "
    logging.debug(f'{sql}')
    return sql


def get_upd_yes_lpas_header(mandt, ebeln, vbeln, posnr, matnr):
    return get_upd_lpas_header_ret(mandt, ebeln, vbeln, posnr, matnr, get_state_header_yes())


def get_upd_err_lpas_header(mandt, ebeln, vbeln, posnr, matnr, err=None):
    return get_upd_lpas_header_ret(mandt, ebeln, vbeln, posnr, matnr, err if err else get_state_header_err())


############################
# query
############################
def get_sql_and_nt(col_list):
    cols_sql = ''
    for col in col_list:
        cols_sql = f'{cols_sql} {col},'
    cols_sql = cols_sql[:-1]
    cols_dict = {k: i for i, k in enumerate(col_list)}
    cols_tpl = namedtuple('Columns', cols_dict.keys())(**cols_dict)
    return cols_sql, cols_tpl


def get_col_server():
    return [
        'server_name',
        'status',
        'newlb',
    ]


def get_sql_server_info(hostname):
    col_list = get_col_server()
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM ENGINE_SERVER " \
        f" WHERE HOSTNAME = '{hostname}' "

    logging.debug(f'{sql}')
    return sql, cols_tpl


def get_cols(col_list, nt=False):
    if nt:
        cols_dict = {k: i for i, k in enumerate(col_list)}
        return namedtuple('Columns', cols_dict.keys())(**cols_dict)
    else:
        return col_list


def get_col_lpas_group(nt=False):
    col_list = [
        'mandt',
        'ebeln',
        'vbeln',
        'newlb',
        'lbpodat',
    ]
    return get_cols(col_list, nt)


def get_sql_lpas_group(name=None, newlb=None, zimgc=None):
    col_list = get_col_lpas_group()
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    zimgc_sql = f" AND ZIMGC = '{zimgc}' " if zimgc else f" AND (TRIM(ZIMGC) IS NULL OR TRIM(ZIMGC) = '{get_state_group_init()}') "
    server_sql = f" AND SERVER = '{name}' " if name else ""
    newlb_sql = f" AND NEWLB = '{newlb}' " if newlb else ""
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_G " \
        f" WHERE 1 = 1 " \
        f" {zimgc_sql} " \
        f" {server_sql} " \
        f" {newlb_sql} "

    logging.debug(f'{sql}')
    return sql, cols_tpl


def get_col_lpas_headers(nt=False):
    col_list = [
        'mandt',
        'ebeln',
        'vbeln',
        'posnr',
        'matnr',
        'zimgc',
        'i_cnt',
        'l_size',
    ]
    return get_cols(col_list, nt)


def get_sql_lpas_headers(mandt, ebeln, vbeln):
    col_list = get_col_lpas_headers()
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_H " \
        f" WHERE 1 = 1 " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' "

    logging.debug(f'{sql}')
    return sql, cols_tpl


def get_col_lpas_items(nt=False):
    col_list = [
        'l_type',
        # "IMAGE", "BARCODE", "TEXT", "QRCODE", "DMX",
        'l_pri',
        # 낮은 숫자가 먼저 밑에 그려져야 함
        'l_coordi_x',
        'l_coordi_y',
        # 좌측 위로부터 x, y 좌표
        'l_rotate',
        # 시계방향으로 회전
        'b_width',
        'b_height',
        'i_filename',
        'i_position',
        # (r)ight, (c)enter, (l)eft 와 (t)op, (m)iddle, (b)ottom 의 조합
        # rt, rm, rb, ct, cm, cb, lt, lm, lb
        'i_rate',
        't_font',
        't_fontsize',
        't_font_r',
        't_font_g',
        't_font_b',
        't_text',
        't_align',
        # "LEFT", "CENTER", "RIGHT"
        't_valign',
        # "TOP", "MIDDLE", "BOTTOM"
        'zimgc',
    ]
    return get_cols(col_list, nt)


def get_sql_lpas_items(mandt, ebeln, vbeln, posnr, matnr):
    col_list = get_col_lpas_items()
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_I " \
        f" WHERE 1 = 1 " \
        f" AND TRIM(ZIMGC) = '{get_state_item_yes()}' " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' " \
        f" AND POSNR = '{posnr}' " \
        f" AND MATNR = '{matnr}' "

    logging.debug(f'{sql}')
    return sql, cols_tpl


def test():
    pass


if __name__ == '__main__':
    test()
