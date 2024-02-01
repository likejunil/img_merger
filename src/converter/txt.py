import logging
import os

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def text2pdf(data, filename):
    def set_color(cv_, color_):
        r, g, b = 0, 0, 0
        if color_ == 'white':
            r, g, b = 0.99, 0.99, 0.99
        elif color_ == 'orange':
            # ff7f00
            r, g, b = 0xff / 0xff, 0x7f / 0xff, 0x00 / 0xff

        logging.info(f'텍스트 컬러 변경=|{r},{g},{b}|')
        cv_.setFillColorRGB(r, g, b)

    logging.info(f'텍스트 삽입=|{data}| 임시 파일=|{filename}|')
    size = list(data.get('size'))
    width, height = size
    logging.info(f'너비=|{width}| 높이=|{height}| 회전=|{data.get("rotate")}| '
                 f'폰트=|{data.get("font")}| 폰트_사이즈=|{data.get("font-size")}|')

    # 캔버스 생성
    c = canvas.Canvas(filename, pagesize=(width * mm, height * mm))
    # c.line(0, 0, width * mm, 0)
    # c.line(0, 0, 0, height * mm)
    # c.rect(0, 0, width * mm, height * mm)

    # 폰트 설정
    content = data.get('content')
    font = data.get('font')
    font_size = float(data.get('font-size'))
    if color := data.get('color'):
        set_color(c, color)

    # to = c.beginText()
    # to.setFont(font, font_size)
    c.setFont(font, font_size)

    # todo 2023.0829 by june1
    #  - 왜 1pt 가 0.3528 mm 가 아닌걸까?
    #  - ratio = 0.3528
    ratio = 0.25
    font_size_mm = font_size * ratio

    text_width = c.stringWidth(content, font, font_size) / 2.85
    logging.info(f'텍스트의 너비=|{text_width}| 텍스트박스의 너비=|{width}|')
    need_resize_flag = False
    old_width = width
    if text_width > width:
        """
        dec_step = -1.0
        tmp_name = get_tmp_name(pdf)
        logging.info(f'텍스트의 너비를 구하기 위한 임시파일=|{tmp_name}|')
        c_ = canvas.Canvas(tmp_name, pagesize=(width * mm, height * mm))
        to_ = c_.beginText()
        to_.setFont(font, font_size)
        to_.setCharSpace(dec_step)
        # to_.setHorizScale(90)
        # to_.setWordSpace(-2.5)
        to_.setTextOrigin(0, 0)
        to_.textLine(content)
        c_.drawText(to_)
        c_.save()
        text_width = get_text_width(tmp_name)
        # os.remove(tmp_name)
        logging.info(f'텍스트의 너비=|{text_width}| 텍스트박스의 너비=|{width}| 적용자간=|{dec_step}|')
        return text_width
        """
        need_resize_flag = True
        width = text_width
        c.setPageSize((width * mm, height * mm))

    # 텍스트 정렬
    align = data.get('align')
    valign = data.get('valign')
    logging.info(f'텍스트 정렬, 상하=|{valign}| 좌우=|{align}|')

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
        convert_scale(filename, tmp_name, (old_width, height))
        os.remove(filename)
        os.rename(tmp_name, filename)

    if degree := data.get('rotate'):
        logging.info(f'텍스트의 방향 전환')
        # c.rotate(degree)
        tmp_name = get_tmp_name(pdf)
        rotate_pdf(filename, tmp_name, degree)
        os.remove(filename)
        os.rename(tmp_name, filename)


def test():
    pass


if __name__ == '__main__':
    test()
