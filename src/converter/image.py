import logging
import os

from PIL import Image
from reportlab.pdfgen import canvas

from src.converter.core import get_out_name, fit_image_to_pdf


def conv_pdf(filename):
    o_name = get_out_name(filename)
    os.rename(filename, o_name)
    return o_name


def conv_eps(filename):
    # Ghostscript를 사용하여 EPS 파일을 PDF로 변환
    # Ghostscript("-sDEVICE=pdfwrite", "-dEPSCrop", "-o", o_name, filename)
    o_name = get_out_name(filename)
    if r := fit_image_to_pdf(filename, o_name):
        logging.error(f'eps 를 pdf 로 변환하는 명령 결과=|{r}|')
    return o_name


def conv_png(filename):
    img = Image.open(filename)
    o_name = get_out_name(filename)
    # 이미지의 품질을 유지하기 위해 canvas 사용
    out = canvas.Canvas(o_name, pagesize=(img.width, img.height))
    out.drawImage(filename, 0, 0, img.width, img.height)
    out.save()
    return o_name


def conv_jpg(filename):
    # jpg 포맷은 이미 비트맵 형식이므로 벡터 형식으로 변환할 수 없다.
    # Image 패키지를 사용하여 pdf 로 변환한다.
    img = Image.open(filename)
    o_name = get_out_name(filename)
    img.save(o_name)
    return o_name


def test():
    pass


if __name__ == '__main__':
    test()
