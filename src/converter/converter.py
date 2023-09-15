import asyncio as aio
import json
import logging
import os
import threading
from multiprocessing import Process
from time import sleep
from uuid import uuid4

import segno
from PIL import Image
from PyPDF2 import PdfFileReader
from pylibdmtx.pylibdmtx import encode
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from conf.constant import pdf, eps
from src.comm.comm import ready_cont, get_loop, get_log_level, tm
from src.comm.log import console_log
from src.comm.util import exec_command
from src.converter.watcher import Watcher


def register_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(conf.font_path, 'Helvetica-Light.ttf')
    pdfmetrics.registerFont(TTFont('Helvetica-Light', font_path))
    # font_path = os.path.join(conf.font_path, 'HankookTTFBold.ttf')
    # pdfmetrics.registerFont(TTFont('HankookTTFBold', font_path))
    # font_path = os.path.join(conf.font_path, 'HankookTTFLight.ttf')
    # pdfmetrics.registerFont(TTFont('HankookTTFLight', font_path))
    # font_path = os.path.join(conf.font_path, 'HankookTTFRegular.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFRegular', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFBold.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFBold', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFLight.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFLight', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFRegular.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFRegular', font_path))


register_font()


def change_ext(filename, ext=pdf):
    return f'{os.path.splitext(filename)[0]}{ext}'


def get_out_name(filename):
    filename = change_ext(filename, pdf)
    base = os.path.basename(filename)
    name, ext = os.path.splitext(base)
    return os.path.join(conf.root_path, conf.out_path, f'{name}_{tm()}{ext}')


def get_tmp_name(ext):
    tmp_path = os.path.join(conf.root_path, conf.data_path, 'tmp_files')
    # tmp_file = f'{tmp_path}/{str(uuid4())}{ext}'
    tmp_file = os.path.join(f'{tmp_path}', f'{str(uuid4())}{ext}')
    logging.info(f'이미지 생성을 위한 임시파일=|{tmp_file}|')
    return tmp_file


def to_pdf(src, dst):
    command = [
        'inkscape',
        src,
        f'--export-filename={dst}',
    ]
    exec_command(command)


def png2svg(src, dst):
    command = [
        'inkscape',
        src,
        '--export-type=svg',
        f'--export-filename={dst}'
    ]
    exec_command(command)


def fit_image_to_pdf(src, dst):
    command = [
        'gs',
        '-dNOPAUSE',
        '-dEPSCrop',
        '-sDEVICE=pdfwrite',
        '-o', dst,
        '-f', src
    ]
    exec_command(command)


def fit_image_to_eps(src, dst):
    # gs -dNOPAUSE -dBATCH -sDEVICE=eps2write -sOutputFile=output.eps input.pdf
    command = [
        'gs',
        '-dNOPAUSE',
        '-dEPSCrop',
        '-sDEVICE=eps2write',
        '-o', dst,
        '-f', src
    ]
    exec_command(command)


def convert_scale(src, dst, size, scale=mm):
    to_width, to_height = size
    to_width, to_height = to_width * scale, to_height * scale
    with open(src, 'rb') as file:
        if reader := PdfFileReader(file):
            page = reader.getPage(0)
            width, height = page.mediaBox.upperRight
            w_scale = (to_width / float(width))
            h_scale = (to_height / float(height))
            command = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dFIXEDMEDIA',
                f'-dDEVICEWIDTHPOINTS={to_width}',
                f'-dDEVICEHEIGHTPOINTS={to_height}',
                '-o', dst,
                '-c', f'<</BeginPage {{{w_scale} {h_scale} scale}}>> setpagedevice',
                '-f', src
            ]
            exec_command(command)


def conv_jpg(filename):
    """
    JPEG는 Joint Photographic Experts Group의 줄임말로, 이미지를 압축하여 저장하는 파일 형식입니다.
    JPEG 파일 형식의 주요 특징은 손실 압축(lossy compression), 품질 조절(quality control) 그리고 애니메이션 미지원이라는 점입니다.
    1. 손실 압축(Lossy compression): JPEG는 이미지를 압축할 때 '손실 압축'이라는 기술을 사용합니다.
        - 이 기술은 원본 이미지의 일부 정보를 버리고, 그 대신 파일 크기를 크게 줄이는 방법입니다.
        - 즉, 이미지의 크기를 줄이기 위해 일부 세부사항을 희생합니다.
        - 그래서 JPEG로 저장하면 원본 이미지와 비교했을 때 화질이 떨어질 수 있습니다.
        - 이러한 이유로, JPEG 형식은 사진이나 그림 등의 세부사항이 많이 없는 이미지에 적합합니다.
    2. 품질 조절(Quality control): JPEG 파일을 저장할 때 품질 수준을 조절할 수 있습니다.
        - 높은 품질의 이미지를 원하면, 파일 크기가 커질 것입니다.
        - 반면에 파일 크기를 줄이고 싶다면, 이미지 품질이 떨어질 것입니다.
        - 이렇게 품질과 파일 크기 사이에서 선택할 수 있기 때문에 JPEG는 웹사이트에서 많이 사용되는 이미지 형식입니다.
    3. 애니메이션 미지원: JPEG는 PNG처럼 투명성을 지원하지 않고, GIF처럼 애니메이션을 지원하지 않습니다.
        - JPEG는 정적인 이미지를 표현하는 데 주로 사용됩니다.
    4. 색상 깊이(Color Depth): JPEG는 수백만 가지의 색상을 표현할 수 있습니다.
        - 이를 통해 사진처럼 다양한 색상을 가진 이미지를 표현하는 데 적합합니다.
    5. 파일 크기: JPEG는 품질을 조절하여 파일 크기를 줄일 수 있는 능력 덕분에, 웹에서 많이 사용되는 이미지 형식입니다.
        - 동일한 이미지를 PNG와 비교하면 JPEG는 일반적으로 파일 크기가 더 작습니다.
    """

    img = Image.open(filename).convert('RGB')
    out = get_out_name(filename)
    img.save(out)
    return out


def conv_png(filename):
    """
    PNG는 Portable Network Graphics의 약자로, 이미지를 압축하여 저장하는 파일 형식입니다.
    PNG 파일 형식은 투명성을 지원하며, 이미지의 손실 없는 압축을 지원하는 두 가지 주요한 특징이 있습니다.
    1. 손실 없는 압축(Lossless compression): PNG는 이미지를 압축하되 원래의 이미지 정보를 모두 보존합니다.
        - 이를 '손실 없는 압축'이라고 합니다.
        - 이것은 어떤 의미일까요? 흔히 우리가 사용하는 ZIP 파일과 비슷하다고 생각하면 됩니다.
        - ZIP 파일로 여러 파일을 묶어서 압축하면 파일 크기가 작아지지만, 다시 압축을 풀면 원래의 파일들이 그대로 복구되죠.
        - PNG도 비슷한 원리로 동작합니다.
        - PNG 파일을 열면, 압축되어 저장된 이미지 정보가 원래대로 복구되어 화면에 표시됩니다.
        - 그래서 PNG는 이미지의 세부 정보를 중요하게 생각하는 디지털 아트, 웹 디자인 등의 분야에서 많이 사용됩니다.
    2. 투명성(Transparency): PNG 파일 형식은 투명성을 지원합니다.
        - 웹페이지에서 로고 이미지를 표시하고 싶은데, 로고가 원형이고 배경은 투명하게 하고 싶다면 PNG 형식의 이미지를 사용하면 됩니다.
        - PNG 이미지는 특정 부분을 투명하게 만들 수 있어, 웹페이지의 배경과 잘 어울릴 수 있습니다.
        - 이처럼 투명성은 이미지를 다른 요소 위에 덮어씌울 때 유용합니다.
    3. 색상 깊이(Color depth): PNG는 다양한 색상 깊이를 지원합니다.
        - 색상 깊이란 한 픽셀이 표현할 수 있는 색상의 수를 의미하는데, PNG는 흑백(2색), 256색, 심지어 수백만 가지 색상을 표현할 수 있습니다.
        - 이 때문에 다양한 색상을 가진 이미지를 표현하는데 PNG가 적합합니다.
    4. 애니메이션 지원 안 함: GIF 파일과 달리 PNG는 애니메이션을 지원하지 않습니다.
        - 따라서 동적인 이미지를 표현하려면 다른 형식을 사용해야 합니다.
    5. 파일 크기: PNG는 품질을 중요시하기 때문에, 같은 크기의 이미지를 JPEG와 비교하면 PNG 파일이 더 크다는 단점이 있습니다.
        - 그러나, 고해상도의 이미지를 웹에서 사용하거나 출력물을 만드는 데에는 PNG가 적합합니다.
    """

    # 이미지의 품질을 유지하기 위해 canvas 사용
    img = Image.open(filename)
    out_name = get_out_name(filename)
    out = canvas.Canvas(out_name, pagesize=(img.width, img.height))
    out.drawImage(filename, 0, 0, img.width, img.height)
    out.save()
    return out_name


def conv_eps(filename):
    """
    EPS는 Encapsulated PostScript의 줄임말로, 이미지, 텍스트, 그래픽 등을 포함할 수 있는 벡터 기반의 파일 형식입니다.
    EPS 파일 형식의 주요 특징은 벡터 기반, 텍스트 편집 가능, 임베딩 기능이라는 점입니다.
    1. 벡터 기반(Vector-based): 벡터 기반의 이미지 형식인 EPS는 점, 선, 곡선, 도형 등의 기하학적 구조를 사용해 이미지를 생성합니다.
        - 이런 벡터 이미지의 장점은 확대하거나 축소해도 이미지 품질이 저하되지 않는다는 것입니다.
        - 예를 들어, 도형이나 로고를 크게 확대하거나 축소해도 선들이 계속해서 매끄럽게 보입니다.
    2. 텍스트 편집 가능: EPS 파일 형식은 텍스트 편집을 지원합니다.
        - 즉, 파일에 포함된 텍스트를 일반 텍스트 편집기로 열어 변경할 수 있습니다.
        - 또한, 다양한 폰트와 스타일을 지원하여 유연성을 제공합니다.
    3. 임베딩 기능(Embedding): EPS 파일은 '임베딩'이라는 기능을 제공합니다.
        - 이는 다른 문서에 EPS 파일을 삽입하여 그래픽이나 이미지를 별도의 파일로 분리하지 않고 한 곳에서 관리할 수 있다는 것을 의미합니다.
        - 이 기능 덕분에, 그래픽 디자이너들은 인쇄물이나 웹 디자인 등에 EPS 파일을 직접 사용할 수 있습니다.
    4. 호환성: EPS는 많은 그래픽 디자인 소프트웨어에서 널리 지원되므로, 디자이너들 사이에서 인기가 많습니다.
        - Adobe Illustrator, Photoshop 등의 프로그램에서 EPS 파일을 쉽게 열고 편집할 수 있습니다.
    5. 크기: EPS 파일은 벡터 기반이므로, 이미지의 복잡성에 따라 파일 크기가 크게 변할 수 있습니다.
        - 간단한 도형은 매우 작은 크기로 저장될 수 있지만, 매우 복잡한 이미지는 큰 파일 크기를 가질 수 있습니다.

    결국, EPS 파일 형식은 그래픽 디자인, 로고, 아이콘, 일러스트 등의 작업에 주로 사용됩니다.
    그러나 웹에서는 사용되지 않습니다.
    왜냐하면 대부분의 웹 브라우저가 EPS 파일 형식을 직접 지원하지 않기 때문입니다.
    따라서 웹에 이미지를 게시하려면 EPS 파일을 JPEG, PNG 등의 래스터 형식으로 변환해야 합니다.
    """

    def convert_eps_to_pdf(eps_, pdf_):
        # Ghostscript를 사용하여 EPS 파일을 PDF로 변환
        # Ghostscript("-sDEVICE=pdfwrite", "-dEPSCrop", "-o", pdf_file, filename)
        fit_image_to_pdf(eps_, pdf_)

    pdf_file = get_out_name(filename)
    convert_eps_to_pdf(filename, pdf_file)
    return pdf_file


def conv_pdf(filename):
    pdf_file = get_out_name(filename)
    os.rename(filename, pdf_file)
    logging.info(f'pdf 파일 옮기기, 원본=|{filename}| 대상=|{pdf_file}|')
    return pdf_file


def generate_barcode(number, out_file):
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


def conv_bar(filename):
    def read_bar_info(f_name):
        try:
            with open(f_name, 'rt', encoding='utf8') as f:
                size_json = json.load(f)
                logging.info(f'|{filename}| 파일로부터 바코드 사이즈 정보 획득=|{size_json}|')
                return size_json['width'], size_json['height']
        except Exception as e:
            logging.error(f'바코드 파일 에러 발생=|{e}|')

    base = os.path.basename(filename)
    ret = os.path.splitext(base)
    if len(ret) != 2:
        logging.error(f'바코드 파일 이름 에러 =|{filename}|')
        return
    name, ext = ret

    if not (size := read_bar_info(filename)):
        logging.error(f'바코드 사이즈 획득 실패')
        return

    # 바코드를 생성할 숫자 (길이는 12자리)
    data = name[-12:]
    logging.info(f'바코드 생성, 번호=|{data}|')

    # 바코드를 생성하고 임시 파일에 저장
    tmp_file = get_tmp_name(pdf)
    generate_barcode(data, tmp_file)

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


def generate_pdf(data, filename):
    def set_color(cv_, color_):
        r, g, b = 0, 0, 0
        if color_ == 'white':
            r, g, b = 0.99, 0.99, 0.99
        elif color_ == 'orange':
            # ff7f00
            r, g, b = 0xff/0xff, 0x7f/0xff, 0x00/0xff

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

    to = c.beginText()
    to.setFont(font, font_size)
    # c.setFont(font, font_size)

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
    if degree := data.get('rotate'):
        c.rotate(degree)
        c.drawString(height / 2 * mm, -width * mm, content)
    else:
        if valign == 'top':
            y = height - font_size_mm
        elif valign == 'bottom':
            y = 0
        else:
            y = round((height / 2) - (font_size_mm / 2), 2)

        if align == 'center':
            # c.drawCentredString(round(width / 2, 2) * mm, y * mm, content)
            to.setTextOrigin(round((width - text_width) / 2, 2) * mm, y * mm)
        elif align == 'left':
            # c.drawString(x=0, y=y * mm, text=content)
            to.setTextOrigin(0, y * mm)
        elif align == 'right':
            # c.drawRightString(x=width * mm, y=y * mm, text=content)
            to.setTextOrigin((width - text_width) * mm, y * mm)

    to.textLine(content)
    c.drawText(to)
    c.save()

    if need_resize_flag:
        logging.info(f'텍스트의 폭 축소 적용')
        tmp_name = get_tmp_name(pdf)
        convert_scale(filename, tmp_name, (old_width, height))
        os.remove(filename)
        os.rename(tmp_name, filename)


def conv_text(filename):
    with open(filename, "rt") as f:
        data = json.load(f)
        out_file = get_out_name(filename)
        generate_pdf(data, out_file)
        return out_file


def info(filename):
    img = Image.open(filename)
    logging.info(f'파일 이름 =|{os.path.basename(filename)}|')
    logging.info(f'형식 =|{img.format}|')
    logging.info(f'높이 =|{img.height}|')
    logging.info(f'너비 =|{img.width}|')
    logging.info(f'크기 =|{img.size}|')
    return filename


def convert(filename):
    procs = {
        'jpg': conv_jpg,
        'jpeg': conv_jpg,
        'png': conv_png,
        'eps': conv_eps,
        'pdf': conv_pdf,
        'bar': conv_bar,
        'qr': conv_qr,
        'dmtx': conv_dmtx,
        'text': conv_text,
    }

    try:
        file_ext = os.path.splitext(filename)[1][1:].lower()
        if file_ext in conf.infile_ext:
            return procs[file_ext](filename)
        else:
            logging.error(f'|{filename}| 변환 미지원')
            return

    except Exception as e:
        logging.error(f'이미지 로드 실패 =|{e}|')


async def do_convert(watcher):
    _, _, ok = ready_cont()
    while ok():
        b, r = watcher.get_ret()
        if b:
            logging.info(f'id =|{threading.get_ident()}| ret =|{r}|')
            # 무엇이든.. 하고 싶은 작업을 여기서 해라..

        await aio.sleep(0.5)
    watcher.stop_proc()


async def thread_main(path, proc):
    console_log(get_log_level())
    loop = get_loop()
    watcher = Watcher(path, proc)
    t1 = loop.create_task(watcher.run_proc())
    t2 = loop.create_task(do_convert(watcher))
    logging.info(f'태스크 생성 완료')

    ret = await aio.gather(t1, t2)
    logging.info(f'이벤트 루프 종료, 결과=|{ret}|')


def thread_proc(path, proc):
    aio.run(thread_main(path, proc))


def converter_proc(proc):
    in_path = os.path.join(conf.root_path, conf.in_path)
    logging.info(f'입력 디렉토리 =|{in_path}|')

    # 메인 쓰레드만이 시그널 등록을 할 수 있음
    ready_cont()
    t_list = []
    logging.info(f'총 |{conf.path_count}|개의 디렉토리 모니터링')
    for i in range(conf.path_count):
        sub_path = os.path.join(in_path, str(i + 1))
        t = Process(target=thread_proc, args=(sub_path, proc), daemon=True)
        t_list.append(t)
        t.start()

    _, _, ok = ready_cont()
    while ok():
        sleep(1)

    for t in t_list:
        t.terminate()
    for t in t_list:
        t.join()


def test():
    from treepoem import generate_barcode
    from PIL import Image

    # def generate_and_print(gtin_, serial_number_, expiry_date_, batch_number_):
    def generate_and_print(data_):
        # Generate datamatrix
        datamatrix = generate_barcode(
            barcode_type='gs1datamatrix',
            # data=f"(01){gtin_}(21){serial_number_}(17){expiry_date_}(10){batch_number_}",
            data=data_,
            options={"parsefnc": True, "format": "square", "version": "36x36"}
        )

        # Resize datamatrix to desired size
        dm_size_px = (120, 120)
        datamatrix = datamatrix.resize(dm_size_px, Image.NEAREST)

        # Create white picture
        picture_size_px = (200, 200)
        picture = Image.new('L', picture_size_px, color='white')

        # Position the datamatrix
        barcode_position_px = (40, 40)
        picture.paste(datamatrix, barcode_position_px)

        # Save the image
        picture.save("datamatrix.png")

    gtin = "01234567890128"
    serial_number = "01234567891011"
    expiry_date = "250731"
    batch_number = "DATAMATRIXTEST"
    data = "(01)08808563401119(21)5&4TOm5+.Uw'l(91)EE09(92)e/RE1wbSABu6LdbXkBRmOWB2rw1EU6NjEYshQQ2MiAs="

    # generate_and_print(gtin, serial_number, expiry_date, batch_number)
    generate_and_print(data)


def test_2():
    print('hi')


if __name__ == '__main__':
    console_log(get_log_level())
    converter_proc(convert)
