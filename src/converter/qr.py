import json
import logging
import os

import segno
from PIL import Image
from pylibdmtx.pylibdmtx import encode
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from conf.constant import pdf, svg, png
from src.comm.log import console_log
from src.comm.util import exec_command
from src.converter.core import convert_scale, get_tmp_name, to_pdf, change_ext, png2svg


def generate_upc(content, o_file):
    # generate_ean(f'0{content}', o_file)
    from barcode.upc import UPCA
    from barcode.writer import SVGWriter

    upc = UPCA(content, writer=SVGWriter())
    base = os.path.splitext(o_file)[0]
    upc.save(base)
    to_pdf(o_file, change_ext(o_file))
    os.remove(f'{base}{svg}')


def generate_ean(content, o_file):
    from reportlab.graphics.barcode import eanbc
    from reportlab.pdfgen import canvas
    from reportlab.graphics.shapes import Drawing

    # 바코드 생성
    barcode = eanbc.Ean13BarcodeWidget(content)

    # 바코드 속성 설정
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
        png_file = os.path.join(conf.root_path, get_tmp_name(png))
        command = ['java', '-jar', f'{conf.lib_path}/barcode.jar', f'{kind}', f'{content}', f'{png_file}', "10"]
        exec_command(command)

        img = Image.open(png_file)
        c = canvas.Canvas(o_name)
        c.setPageSize((img.width, img.height))
        c.drawInlineImage(png_file, 0, 0, img.width, img.height)
        c.save()
        os.remove(png_file)

        # 스케일 조정
        # convert_scale(o_name, size)
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
        # convert_scale(o_name, size)
        return o_name


def generate_dmx(data, o_file):
    jar = 'DataMatrixLib.jar'
    prog = 'gs1.DmxGs1'
    path = os.path.dirname(o_file)
    file = os.path.basename(o_file)
    command = [
        'java', '-cp', f'.:{conf.lib_path}/{jar}:{conf.bin_path}', f'{prog}', f'{data}', f'{path}/', f'{file}'
    ]
    if exec_command(command):
        logging.error(f'Data Matrix 생성 실패, 파일=|{o_file}|')
        return

    src = change_ext(o_file, png)
    dst = o_file
    png2svg(src, dst)


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

        # 일반 데이터 메트릭스
        # dmx_code = encode(content.encode('utf8'))
        # img = Image.frombytes('RGB', (dmx_code.width, dmx_code.height), dmx_code.pixels)
        # img.save(o_name)
        # GS1 데이터 메트릭스
        generate_dmx(content, o_name)
        # convert_scale(o_name, size)
        return o_name


def test_ean(content=None):
    if not content:
        content = '8808563461533'
    o_file = os.path.join(conf.root_path, get_tmp_name(pdf))
    print(f'파일=|{o_file}| 내용=|{content}|')
    generate_ean(content, o_file)


def test_upc():
    content = '725272730706'
    case = 2

    if case == 1:
        content = f'0{content}'
        test_ean(content)
        pass
    elif case == 2:
        o_file = os.path.join(conf.root_path, get_tmp_name(svg))
        print(f'파일=|{o_file}| 내용=|{content}|')
        generate_upc(content, o_file)
    else:
        pass


def test_convert(src, dst):
    from PIL import Image
    from reportlab.pdfgen import canvas

    img = Image.open(src)
    c = canvas.Canvas(dst)
    c.setPageSize((img.width, img.height))
    c.drawInlineImage(src, 0, 0, img.width, img.height)
    c.save()


def test_bar(kind, content):
    if kind in ['upc', 'ean']:
        png_file = os.path.join(conf.root_path, get_tmp_name(png))
        pdf_file = change_ext(png_file, pdf)
        print(f'파일=|{png_file}| 내용=|{content}|')
        command = ['java', '-jar', f'{conf.lib_path}/barcode.jar', f'{kind}', f'{content}', f'{png_file}', '10']
        if not exec_command(command):
            test_convert(png_file, pdf_file)


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
    content = '0108808563578569215!J!-=D_0"KeL91EE0992/qn8IuxUGoXEtgQ8Jn307wxRePzm/EqMI54CEJkzx2Y='
    o_file = os.path.join(conf.root_path, get_tmp_name())
    print(f'출력파일 =|{o_file}|')
    generate_dmx(content, o_file)


def test():
    # test_ean()
    # test_upc()
    # test_qr()
    # test_dmx()
    # test_gs1()
    test_bar('upc', '725272730706')
    test_bar('ean', '8808563461533')


def test_png2pdf(src, dst):
    from PIL import Image
    from reportlab.pdfgen import canvas

    png_file = src
    pdf_file = dst
    img = Image.open(png_file)
    c = canvas.Canvas(pdf_file, pagesize=(img.width, img.height))
    c.drawImage(png_file, 0, 0, width=img.width, height=img.height)
    c.save()


if __name__ == '__main__':
    console_log()
    test()
