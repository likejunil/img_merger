import os
from datetime import datetime as dt

from conf.conf import config as conf


def get_zip_path():
    dst_dir = f'{conf.root_path}/{conf.done_path}/ZIP/{dt.now().strftime("%Y%m%d")}'
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    return dst_dir


def test():
    print(get_zip_path())


if __name__ == '__main__':
    test()
