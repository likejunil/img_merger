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

from conf.constant import eps, pdf
from src.converter.core import get_tmp_name, fit_image_to_eps, fit_image_to_pdf, get_out_name, convert_scale


def generate_barcode(number, kind, out_file):
    def generate_ean():
        width, height = 240, 120
        barcode = eanbc.Ean13BarcodeWidget(number)
        # 바코드 속성 설정
        barcode.barHeight = 20 * mm
        barcode.fontSize = 11

        c = canvas.Canvas(out_file, pagesize=(width, height))
        d = Drawing(width, height)
        d.add(barcode)
        renderPDF.draw(d, c, 10, 10)
        c.save()

    generate_ean()


def conv_bar(filename):
    def read_bar_info(f_name):
        try:
            with open(f_name, 'rt', encoding='utf8') as f:
                size_json = json.load(f)
                logging.info(f'|{filename}| 파일로부터 바코드 사이즈 정보 획득=|{size_json}|')
                # return size_json['width'], size_json['height']
                return size_json
        except Exception as e:
            logging.error(f'바코드 파일 에러 발생=|{e}|')

    base = os.path.basename(filename)
    ret = os.path.splitext(base)
    if len(ret) != 2:
        logging.error(f'바코드 파일 이름 에러 =|{filename}|')
        return
    name, ext = ret

    if not (bar_info := read_bar_info(filename)):
        logging.error(f'바코드 사이즈 획득 실패')
        return

    # 바코드의 종류
    kind = bar_info.get('kind', 'EAN')

    # 바코드의 크기
    size = bar_info['width'], bar_info['height']

    # 바코드를 생성할 숫자 (길이는 12자리)
    data = name[-12:]
    logging.info(f'바코드 생성, 번호=|{data}|')

    # 바코드를 생성하고 임시 파일에 저장
    tmp_file = get_tmp_name(pdf)
    generate_barcode(data, kind, tmp_file)

    # 상하좌우 여백 없애기
    tmp_eps = get_tmp_name(eps)
    tmp_pdf = get_tmp_name(pdf)
    fit_image_to_eps(tmp_file, tmp_eps)
    fit_image_to_pdf(tmp_eps, tmp_pdf)

    # 임시 파일을 읽어서 스케일 조정
    out_file = get_out_name(filename)
    convert_scale(tmp_pdf, out_file, size)

    # 임시 파일 삭제
    os.remove(tmp_file)
    os.remove(tmp_pdf)
    os.remove(tmp_eps)
    return filename


def conv_qr(filename):
    """
    # https://www.keyence.co.kr/ss/products/auto_id/barcode_lecture/basic_2d/qr/
    """
    with open(filename, "rt") as f:
        json_data = json.load(f)
        content = json_data.get('content')
        width, height = json_data.get('width'), json_data.get('height')
        logging.info(f'QR-코드 생성을 위한 정보=|{json_data}|')

        tmp_file = get_tmp_name(pdf)
        qr = segno.make(content)
        qr.save(tmp_file, kind="pdf")
        out_file = get_out_name(filename)
        convert_scale(tmp_file, out_file, (width, height))
        os.remove(tmp_file)
        return out_file


def conv_dmtx(filename):
    """
    # https://www.keyence.co.kr/ss/products/auto_id/barcode_lecture/basic_2d/datamatrix/
    # ECC200은 최신 버전의 Data Matrix 코드
    # 코드 크기는 10 x 10셀에서 144 x 144셀까지 24가지(직사각형의 6가지 크기 포함).
    """
    with open(filename, "rb") as f:
        # json_data = json.load(f)
        # width, height = json_data.get('width'), json_data.get('height')
        # logging.info(f'Data-Matrix 생성을 위한 정보=|{json_data}|')
        # encoded = encode(json_data.get('content').encode('utf8'))
        width, height = 22, 22
        # data = f.read()
        # data = b'\xe8' + f.read()
        # data = b'\f' + f.read()
        # data = b'\x0f' + f.read()
        data = b'\x1d' + f.read()
        encoded = encode(data)
        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)

        tmp_file = get_tmp_name(pdf)
        img.save(tmp_file)
        out_file = get_out_name(filename)
        convert_scale(tmp_file, out_file, (width, height))
        os.remove(tmp_file)
        return out_file


def test():
    pass


if __name__ == '__main__':
    test()
