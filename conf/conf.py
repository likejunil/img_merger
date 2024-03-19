import os
from collections import namedtuple

import yaml
from dotenv import load_dotenv

import conf.constant as _


def ready_conf():
    conf_dict = dict()

    # -----------------------
    # .env 파일로부터..
    # -----------------------
    load_dotenv()

    root_path = os.getenv("LPAS_ROOT")
    conf_dict[_.root_path] = root_path
    conf_dict[_.conf_path] = os.path.join(root_path, 'conf')
    conf_dict[_.src_path] = os.path.join(root_path, 'src')
    conf_dict[_.log_path] = os.path.join(root_path, 'log')
    conf_dict[_.data_path] = os.path.join(root_path, 'data')
    conf_dict[_.pid_path] = os.path.join(root_path, 'pid')
    conf_dict[_.font_path] = os.path.join(root_path, 'fonts')
    conf_dict[_.lib_path] = os.path.join(root_path, 'lib')
    conf_dict[_.bin_path] = os.path.join(root_path, 'bin')
    conf_dict[_.yaml_file] = os.getenv(_.yaml_file.upper())
    conf_dict[_.passwd] = os.getenv(_.passwd.upper())

    # -----------------------
    # yaml 파일로부터..
    # -----------------------
    yaml_file = os.path.join(conf_dict[_.conf_path], conf_dict[_.yaml_file])
    with open(yaml_file, "rt", encoding='utf8') as f:
        yml_conf = yaml.load(f, Loader=yaml.FullLoader)

    if not yml_conf:
        raise Exception(f'|{_.yaml_file}|로부터 정보를 읽지 못했습니다.')

    # 공통
    comm = yml_conf[_.comm]

    # 로그
    log = comm[_.log]
    conf_dict[_.debug] = log[_.debug]
    conf_dict[_.log_time] = log[_.log_time]

    # 데이터베이스
    dbms = comm[_.db_name][_.db_dbms]
    conf_dict[_.user] = dbms[_.user]
    conf_dict[_.addr] = dbms[_.addr]
    conf_dict[_.port] = dbms[_.port]
    conf_dict[_.db] = dbms[_.db]

    # 파일 패스 관련
    path_info = yml_conf[_.path]
    conf_dict[_.in_path] = path_info[_.in_data][_.path]
    conf_dict[_.infile_ext] = path_info[_.in_data][_.ext]
    conf_dict[_.path_count] = path_info[_.in_data][_.path_count]
    conf_dict[_.out_path] = path_info[_.out_data][_.path]
    conf_dict[_.done_path] = path_info[_.done_data][_.path]
    conf_dict[_.merged_path] = path_info[_.merged_data][_.path]
    conf_dict[_.tmp_path] = path_info[_.tmp_data][_.path]

    # 바코드 관련
    converter = yml_conf[_.converter]
    conf_dict[_.bar_addr] = converter[_.bar_addr]
    conf_dict[_.bar_port] = converter[_.bar_port]
    conf_dict[_.bar_url] = converter[_.bar_url]

    # -----------------------
    # namedtuple 로 변환하여 반환
    # -----------------------
    return namedtuple('Config', conf_dict.keys())(**conf_dict)


config = ready_conf()
