import json
import logging
import os

from PyPDF2 import PdfFileReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.constant import pdf, eps
from src.converter.core import get_tmp_name, fit_image_to_eps, fit_image_to_pdf, convert_scale, rotate_pdf, get_out_name


def get_text_width(filename):
    tmp_eps = get_tmp_name(eps)
    fit_image_to_eps(filename, tmp_eps)
    tmp_pdf = get_tmp_name(pdf)
    fit_image_to_pdf(tmp_eps, tmp_pdf)
    # os.remove(tmp_eps)
    with open(tmp_pdf, 'rb') as f:
        if reader := PdfFileReader(f):
            page = reader.getPage(0)
            ret = page.mediaBox.upperRight
            img_width = round(float(ret[0]) / mm)
    # os.remove(tmp_pdf)
    return img_width


def text2pdf(data, o_name):
    # 이미지 크기 정보 추출하여 캔버스 생성
    # 이미지의 크기를 mm 단위로 변환
    width, height = data.get('size')
    c = canvas.Canvas(o_name, pagesize=(width * mm, height * mm))

    # 폰트 종류와 크기
    font = data.get('font')
    font_size = data.get('font_size')
    c.setFont(font, font_size)

    # 폰트 색깔
    font_color = data.get('font_color')
    if all(m for m in font_color):
        font_color = [m / 0xff for m in font_color]
        c.setFillColorRGB(*font_color)

    # 텍스트 내용
    content = data.get('text')

    # 텍스트의 너비
    # text_width = c.stringWidth(content, font, font_size) / 2.8346
    text_width = c.stringWidth(content, font, font_size) / mm
    logging.debug(f'텍스트의 너비=|{text_width}| 텍스트박스의 너비=|{width}|')
    old_width = width

    # 만약 텍스트의 너비가 이미지의 너비보다 넓다면
    # 이미지의 너비를 텍스트의 너비만큼 확장
    # 이제 이미지의 너비는 텍스트의 너비
    need_resize_flag = False
    if text_width > width:
        need_resize_flag = True
        width = text_width
        c.setPageSize((width * mm, height * mm))

    # 텍스트 정렬
    align = data.get('align')
    valign = data.get('valign')
    logging.info(f'텍스트 정렬, 상하=|{valign}| 좌우=|{align}|')

    font_size_mm = font_size * 0.25

    # 데카르트 좌표(좌하단, 즉 원점으로부터..)
    if valign == 'top':
        y = height - font_size_mm
    elif valign == 'bottom':
        y = 0
    else:
        y = round((height / 2) - (font_size_mm / 2), 2)

    if align == 'center':
        c.drawCentredString(round(width / 2, 2) * mm, y * mm, content)
        # to.setTextOrigin(round((width - text_width) / 2, 2) * mm, y * mm)
    elif align == 'left':
        c.drawString(x=0, y=y * mm, text=content)
        # to.setTextOrigin(0, y * mm)
    elif align == 'right':
        c.drawRightString(x=width * mm, y=y * mm, text=content)
        # to.setTextOrigin((width - text_width) * mm, y * mm)

    # to.textLine(content)
    # c.drawText(to)
    c.save()

    if need_resize_flag:
        logging.info(f'텍스트의 폭 축소 적용')
        tmp_name = get_tmp_name(pdf)
        convert_scale(o_name, tmp_name, (old_width, height))
        os.remove(o_name)
        os.rename(tmp_name, o_name)

    if degree := data.get('rotate'):
        logging.info(f'텍스트의 방향 전환')
        # c.rotate(degree)
        tmp_name = get_tmp_name(pdf)
        rotate_pdf(o_name, tmp_name, degree)
        os.remove(o_name)
        os.rename(tmp_name, o_name)


def conv_txt(filename):
    with open(filename, 'rt') as f:
        data = json.load(f)
        o_name = get_out_name(filename)
        logging.debug(f'텍스트 이미지 생성을 위한 정보=|{data}|, 출력파일=|{o_name}|')
        # 텍스트를 생성하기 위한 정보와 pdf 출력 파일의 이름을 전달
        # text2pdf(data, o_name)
        return o_name


def test():
    pass


if __name__ == '__main__':
    test()
