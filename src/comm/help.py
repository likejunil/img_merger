import logging
import os
import zipfile
from datetime import datetime as dt

from conf.conf import config as conf


def get_zip_path(date_str=None):
    if not date_str:
        date_str = dt.now().strftime("%Y%m%d")
    dst_dir = f'{conf.root_path}/{conf.done_path}/ZIP/{date_str}'
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    return dst_dir


def get_pdf_path(date_str=None):
    if not date_str:
        date_str = dt.now().strftime("%Y%m%d")
    dst_dir = f'{conf.root_path}/{conf.done_path}/PDF/{date_str}'
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    return dst_dir


def make_zip_files(o_file, src_dir, s_pattern, e_pattern):
    logging.info(f'압축 파일 생성 시작=|{o_file}|')
    # 대소문자 무시 비교
    s_pattern = s_pattern.lower()
    e_pattern = e_pattern.lower()

    # 기존의 파일을 무시하고 덮어씀
    count = 0
    with zipfile.ZipFile(o_file, 'w') as f:
        for path, folders, files in os.walk(src_dir):
            for file in files:
                # 대소문자 무시 비교
                t = file.lower()
                if t.startswith(s_pattern) and t.endswith(e_pattern):
                    f.write(os.path.join(path, file), file)
                    count += 1
                    logging.info(f'압축 파일 추가({count})=|{file}|')

    logging.info(f'압축 파일 생성 완료(총 {count}개)=|{o_file}|')


def test():
    print(get_zip_path())


if __name__ == '__main__':
    test()
