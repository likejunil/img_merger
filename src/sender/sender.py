import logging
import math
import os
from uuid import uuid4

from PIL import Image

from conf.conf import config as conf
from src.comm.log import console_log


def show_info(img):
    logging.info(f'파일 이름 =|{img.filename}|')
    logging.info(f'형식 =|{img.format}|')
    logging.info(f'높이 =|{img.height}|')
    logging.info(f'너비 =|{img.width}|')
    logging.info(f'크기 =|{img.size}|')


def save_pdf_file(path, img, name):
    ext = 'pdf'
    file_name = os.path.basename(name)
    base_name = os.path.splitext(file_name)[0]
    name = os.path.join(path, f'{base_name}.{ext}')
    img.save(name, ext)
    logging.info(f'|{name}| 이미지 변환 저장 완료')


def rotate_img(img, degree):
    return img.rotate(degree)


def resize_img(img):
    ratio = 1
    return img.resize((math.floor(img.width * ratio), math.floor(img.height * ratio)))


def merge_file(img, xy, new_image):
    new_image.paste(img, xy)


def get_filename():
    return f'{uuid4()}.tmp'


def get_merged_img(size):
    img = Image.new('RGB', size, (250, 250, 250))
    return img


def sender_proc(img_list):
    path = os.path.join(conf.root_path, conf.sender_path)
    logging.info(f'출력 디렉토리 =|{path}|')

    # 출력 이미지 크기
    height = 0
    width = 0
    for img in img_list:
        if not img:
            continue
        if img.width > width:
            width = img.width
        height += img.height
    logging.info(f'출력 이미지의 크기 height=|{height}| width=|{width}|')

    new_image = get_merged_img((width, height))
    name = get_filename()

    # 파일 병합
    h = 0
    for i, img in enumerate(img_list, 0):
        if not img:
            continue
        show_info(img)
        img = rotate_img(img, 0)
        img = resize_img(img)
        merge_file(img, (0, 0 + h), new_image)
        h += img.height

    save_pdf_file(path, new_image, name)


if __name__ == '__main__':
    console_log(logging.INFO)

    filename1 = '/Users/june1/Downloads/기타/cat.jpg'
    filename2 = '/Users/june1/Downloads/기타/dog.jpeg'

    i1 = Image.open(filename1)
    i2 = Image.open(filename2)
    sender_proc((i1, i2))
