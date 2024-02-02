import json
import logging

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from src.converter.core import convert_scale, rotate_pdf, get_out_name


def text2pdf(data, o_name):
    # 이미지 크기 정보 추출하여 캔버스 생성
    # 이미지의 크기를 point 에서 mm 단위로 변환
    width, height = data.get('size')
    c = canvas.Canvas(o_name, pagesize=(width * mm, height * mm))

    # 폰트 종류와 크기
    font = data.get('font')
    font_size = data.get('font_size')
    c.setFont(font, font_size)
    # todo 2024.0129 by june1
    #  - 폰트 사이즈를 mm 로 변환
    #  - 왜 0.25 를 곱하는가?
    #  - 폰트의 종류마다 달라지는거 아닌가?
    font_mm_rate = 0.25
    font_size_mm = font_size * font_mm_rate

    # 폰트 색깔
    font_color = data.get('font_color')
    if all(m for m in font_color):
        font_color = [m / 0xff for m in font_color]
        c.setFillColorRGB(*font_color)

    # 텍스트 내용
    content = data.get('text')

    # 텍스트의 너비
    # mm 단위를 point 로 변환하여 비교
    text_width = round(c.stringWidth(content, font, font_size) / mm, 2)
    logging.info(f'텍스트의 너비=|{text_width}| 텍스트박스의 너비=|{width}|')
    old_width = width

    # 만약 텍스트의 너비가 이미지의 너비보다 넓다면
    # 이미지의 너비를 텍스트의 너비만큼 확장
    # 이제 이미지의 너비는 텍스트의 너비
    need_resize_flag = False
    if text_width > width:
        need_resize_flag = True
        width = text_width
        # 페이지의 크기를 재조정 (텍스트의 너비 때문에)
        c.setPageSize((width * mm, height * mm))

    # 텍스트 정렬
    align = data.get('align').lower() if data.get('align') else 'center'
    valign = data.get('valign').lower() if data.get('valign') else 'top'
    logging.info(f'텍스트 정렬, 상하=|{valign}| 좌우=|{align}|')

    # 데카르트 좌표(좌하단, 즉 원점으로부터)
    # 상하 정렬
    if valign == 'top':
        y = height - font_size_mm
    elif valign == 'bottom':
        # 텍스트는 기본적으로 이미지의 바닥에 위치
        y = 0
    else:
        y = round(((height - font_size_mm) / 2), 2)

    # 좌우 정렬
    if align == 'center':
        c.drawCentredString(x=width / 2 * mm, y=y * mm, text=content)
    elif align == 'left':
        c.drawString(x=0, y=y * mm, text=content)
    elif align == 'right':
        c.drawRightString(x=width * mm, y=y * mm, text=content)

    # 텍스트 이미지 저장
    c.save()

    # 텍스트 이미지 축소
    if need_resize_flag:
        logging.info(f'텍스트의 폭 축소 적용')
        convert_scale(o_name, (old_width, height))

    # 텍스트 이미지 회전
    if degree := data.get('rotate'):
        logging.info(f'텍스트의 방향 전환')
        rotate_pdf(o_name, degree)


def conv_txt(filename):
    with open(filename, 'rt', encoding='utf8') as f:
        data = json.load(f)
        o_name = get_out_name(filename)
        logging.info(f'텍스트 이미지 생성을 위한 정보=|{data}|, 출력파일=|{o_name}|')
        # 텍스트를 생성하기 위한 정보와 pdf 출력 파일의 이름을 전달
        text2pdf(data, o_name)
        return o_name


def test():
    pass


if __name__ == '__main__':
    test()
