import logging
import os

from PIL import Image

from conf.conf import config as conf
from src.comm.log import console_log


def show_info(img):
    logging.info(f'파일 이름 =|{img.filename}|')
    logging.info(f'형식 =|{img.format}|')
    logging.info(f'높이 =|{img.height}|')
    logging.info(f'너비 =|{img.width}|')
    logging.info(f'크기 =|{img.size}|')


def save_pdf_file(path, img):
    ext = 'pdf'
    file_name = os.path.basename(img.filename)
    base_name = os.path.splitext(file_name)[0]
    name = os.path.join(path, f'{base_name}.{ext}')
    img.save(name, ext)
    logging.info(f'|{name}| 이미지 변환 저장 완료')


def sender_proc(img_list):
    path = os.path.join(conf.root_path, conf.sender_path)
    logging.info(f'출력 디렉토리 =|{path}|')

    for data in img_list:
        if data:
            show_info(data)
            save_pdf_file(path, data)


if __name__ == '__main__':
    console_log(logging.INFO)

    filename1 = '/Users/june1/Downloads/기타/cat.jpg'
    filename2 = '/Users/june1/Downloads/기타/dog.jpeg'

    i1 = Image.open(filename1)
    i2 = Image.open(filename2)
    sender_proc((i1, i2))
