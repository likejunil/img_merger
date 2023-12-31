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

    root_path = os.getenv(_.root_path.upper())
    conf_dict[_.root_path] = root_path
    conf_dict[_.conf_path] = os.path.join(root_path, 'conf')
    conf_dict[_.src_path] = os.path.join(root_path, 'src')
    conf_dict[_.log_path] = os.path.join(root_path, 'log')
    conf_dict[_.data_path] = os.path.join(root_path, 'data')
    conf_dict[_.pid_path] = os.path.join(root_path, 'pid')
    conf_dict[_.font_path] = os.path.join(root_path, 'fonts')
    conf_dict[_.yaml_file] = os.getenv(_.yaml_file.upper())

    # -----------------------
    # yaml 파일로부터..
    # -----------------------
    yaml_file = os.path.join(conf_dict[_.conf_path], conf_dict[_.yaml_file])
    with open(yaml_file, "rt", encoding='utf8') as f:
        yml_conf = yaml.load(f, Loader=yaml.FullLoader)

    if not yml_conf:
        raise Exception(f'|{_.yaml_file}|로부터 정보를 읽지 못했습니다.')

    conf_dict[_.debug] = yml_conf[_.debug]
    conf_dict[_.in_path] = yml_conf[_.in_data][_.path]
    conf_dict[_.infile_ext] = yml_conf[_.in_data][_.ext]
    conf_dict[_.path_count] = yml_conf[_.in_data][_.path_count]
    conf_dict[_.out_path] = yml_conf[_.out_data][_.path]
    conf_dict[_.done_path] = yml_conf[_.done_data][_.path]
    conf_dict[_.merged_path] = yml_conf[_.merged_data][_.path]

    conf_dict[_.bar_type] = yml_conf[_.barcode][_.bar]

    # -----------------------
    # namedtuple 로 변환하여 반환
    # -----------------------
    return namedtuple('Config', conf_dict.keys())(**conf_dict)


config = ready_conf()
