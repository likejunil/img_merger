import json
import logging
import os

import segno
from PIL import Image
from pylibdmtx.pylibdmtx import encode
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from conf.constant import pdf
from src.comm.log import console_log
from src.converter.core import convert_scale, get_tmp_name


def generate_upc(content, o_file):
    generate_ean(f'0{content}', o_file)


def generate_ean(content, o_file):
    # 바코드 생성
    barcode = eanbc.Ean13BarcodeWidget(content)

    # 바코드 속성 설정
    # barcode.barHeight = 20 * mm
    # barcode.fontSize = 11
    barcode.barHeight = 16 * mm
    barcode.fontSize = 8

    # 바코드 바운딩 박스의 크기를 얻어 Drawing 객체 크기 설정
    # 캔버스 생성
    bounds = barcode.getBounds()
    width = bounds[2] - bounds[0] + 2
    height = bounds[3] - bounds[1] + 2
    c = canvas.Canvas(o_file, pagesize=(width, height))
    d = Drawing(width, height)

    # 바코드 그리기
    d.add(barcode)
    renderPDF.draw(d, c, 1, 1)
    c.save()


def conv_bar(filename):
    with open(filename, 'rt', encoding='utf8') as f:
        data = json.load(f)
        logging.info(f'바코드 이미지 생성을 위한 정보=|{data}|')

        # 바코드의 종류
        kind = data.get('type_').lower()
        # 바코드의 이미지 크기
        size = data.get('size')
        # 바코드의 내용
        content = data.get('text')
        # 바코드 이미지 파일 이름
        o_name = data.get('name')

        # 바코드를 생성하고 임시 파일에 저장
        if kind == 'ean':
            generate_ean(content, o_name)
        elif kind == 'upc':
            generate_upc(content, o_name)
        else:
            logging.error(f'바코드 이미지 생성, 도달할 수 없는 코드')
            return

        # 스케일 조정
        convert_scale(o_name, size)
        return o_name


def conv_qr(filename):
    # https://www.keyence.co.kr/ss/products/auto_id/barcode_lecture/basic_2d/qr/
    with open(filename, 'rt', encoding='utf8') as f:
        data = json.load(f)
        logging.info(f'qr코드 생성을 위한 정보=|{data}|')

        # qr코드 크기
        size = data.get('size')
        # qr코드 내용
        content = data.get('content')
        # qr코드 이미지 파일 이름
        o_name = data.get('name')

        qr = segno.make(content)
        qr.save(o_name, kind="pdf")
        convert_scale(o_name, size)
        return o_name


def conv_dmx(filename):
    # https://www.keyence.co.kr/ss/products/auto_id/barcode_lecture/basic_2d/datamatrix/
    # ECC200은 최신 버전의 Data Matrix 코드
    # 코드 크기는 10 x 10셀에서 144 x 144셀까지 24가지(직사각형의 6가지 크기 포함).
    with open(filename, "rb") as f:
        data = json.load(f)
        logging.info(f'dmx 생성을 위한 정보=|{data}|')

        # dmx 크기
        size = data.get('size')
        # dmx 내용
        content = data.get('content')
        # dmx 파일 이름
        o_name = data.get('name')

        # dmx 이미지 생성
        dmx_code = encode(content.encode('utf8'))
        img = Image.frombytes('RGB', (dmx_code.width, dmx_code.height), dmx_code.pixels)
        img.save(o_name)
        convert_scale(o_name, size)
        return o_name


def test_ean(content=None):
    if not content:
        content = '8808563461533'
    o_file = os.path.join(conf.root_path, get_tmp_name(pdf))
    print(f'파일=|{o_file}| 내용=|{content}|')
    generate_ean(content, o_file)


def test_upc():
    content = '72527273070'
    content = f'0{content}'
    test_ean(content)


def test_qr():
    content = "https://www.hankooktire.com/kr/ko/home.html"
    o_file = os.path.join(conf.root_path, get_tmp_name(pdf))
    print(f'파일=|{o_file}| 내용=|{content}|')
    qr = segno.make(content)
    qr.save(o_file, kind="pdf")


def test_dmx():
    content = 'Flying car, To the moon~! 123.987'
    o_file = os.path.join(conf.root_path, get_tmp_name(pdf))
    print(f'파일=|{o_file}| 내용=|{content}|')
    dmx_code = encode(content.encode('utf8'))
    img = Image.frombytes('RGB', (dmx_code.width, dmx_code.height), dmx_code.pixels)
    img.save(o_file)


def test_gs1():
    from treepoem import generate_barcode
    from PIL import Image

    def generate_and_print(data, name):
        datamatrix = generate_barcode(
            barcode_type='gs1datamatrix',
            data=data,
            options={"parsefnc": True, "format": "square", "version": "26x26"})

        dm_size_px = (120, 120)
        datamatrix = datamatrix.resize(dm_size_px, Image.NEAREST)

        picture_size_px = (200, 200)
        picture = Image.new('L', picture_size_px, color='white')

        barcode_position_px = (40, 40)
        picture.paste(datamatrix, barcode_position_px)

        picture.save(name)

    # 0108808563401119215!QWEJ6ukaIky91EE0992UKD5BCPJLFg8QkHZvkKlk0U1VQGvykJTRdlt8NYJ524=
    content = "(01)08808563401119(21)5!QWEJ6ukaIky(91)EE09(92)UKD5BCPJLFg8QkHZvkKlk0U1VQGvykJTRdlt8NYJ524="
    o_file = os.path.join(conf.root_path, get_tmp_name(pdf))
    generate_and_print(content, o_file)


def test():
    # test_ean()
    # test_upc()
    # test_qr()
    # test_dmx()
    test_gs1()


if __name__ == '__main__':
    console_log()
    test()
