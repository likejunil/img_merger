from collections import namedtuple


############################
#
############################
def get_state_group_run():
    return 'R'


def get_state_group_yes():
    return 'Y'


def get_state_group_err():
    return 'E'


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
        f" AND TRIM(ZIMGC) IS NULL " \
        f" AND TRIM(SERVER) IS NULL " \
        f" {newlb_sql} "
    return sql


def get_upd_lpas_group_ret(mandt, ebeln, vbeln, zimgc):
    sql = \
        f" UPDATE LPAS_ORDER_G " \
        f" SET ZIMGC = '{zimgc}' " \
        f" WHERE 1 = 1 " \
        f" AND TRIM(ZIMGC) IS NULL " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' "
    return sql


def get_upd_run_lpas_group(mandt, ebeln, vbeln):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, get_state_group_run())


def get_upd_yes_lpas_group(mandt, ebeln, vbeln):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, get_state_group_yes())


def get_upd_err_lpas_group(mandt, ebeln, vbeln):
    return get_upd_lpas_group_ret(mandt, ebeln, vbeln, get_state_group_err())


def get_upd_lpas_headers_ret(mandt, ebeln, vbeln, posnr, matnr, ret):
    sql = \
        f" UPDATE LPAS_ORDER_H " \
        f" SET ZIMGC = '{ret}' " \
        f" WHERE 1 = 1 " \
        f" AND TRIM(ZIMGC) IS NULL " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' " \
        f" AND POSNR = '{posnr}' " \
        f" AND MATNR = '{matnr}' "
    return sql


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


def get_sql_server_info(hostname):
    col_list = [
        'server_name',
        'status',
        'newlb',
    ]
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM ENGINE_SERVER " \
        f" WHERE HOSTNAME = '{hostname}' "

    return sql, cols_tpl


def get_sql_lpas_group(name=None, newlb=None, zimgc=None):
    col_list = [
        'mandt',
        'ebeln',
        'vbeln',
        'newlb',
    ]
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    zimgc_sql = f" AND ZIMGC = '{zimgc}' " if zimgc else " AND TRIM(ZIMGC) IS NULL "
    server_sql = f" AND SERVER = '{name}' " if name else ""
    newlb_sql = f" AND NEWLB = '{newlb}' " if newlb else ""
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_G " \
        f" WHERE 1 = 1 " \
        f" {zimgc_sql} " \
        f" {server_sql} " \
        f" {newlb_sql} "

    return sql, cols_tpl


def get_sql_lpas_headers(mandt, ebeln, vbeln):
    col_list = [
        'mandt',
        'ebeln',
        'vbeln',
        'posnr',
        'matnr',
        'zimgc',
        'i_cnt',
    ]
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_H " \
        f" WHERE 1 = 1 " \
        f" AND TRIM(ZIMGC) IS NULL " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' "

    return sql, cols_tpl


def get_sql_lpas_items(mandt, ebeln, vbeln, posnr, matnr):
    col_list = [
        'l_type',
        'l_pri',
        'l_coordi_x',
        'l_coordi_y',
        'l_rotate',
        'b_width',
        'b_height',
        'i_filename',
        'i_position',
        'i_rate',
        't_font',
        't_fontsize',
        't_font_r',
        't_font_g',
        't_font_b',
        't_text',
        't_align',
        't_valign',
        'zimgc',
    ]
    cols_sql, cols_tpl = get_sql_and_nt(col_list)
    sql = \
        f" SELECT {cols_sql} " \
        f" FROM LPAS_ORDER_I " \
        f" WHERE 1 = 1 " \
        f" AND TRIM(ZIMGC) = 'Y' " \
        f" AND MANDT = '{mandt}' " \
        f" AND EBELN = '{ebeln}' " \
        f" AND VBELN = '{vbeln}' " \
        f" AND POSNR = '{posnr}' " \
        f" AND MATNR = '{matnr}' "

    return sql, cols_tpl


def test():
    pass


if __name__ == '__main__':
    test()
