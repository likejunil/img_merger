import asyncio as aio
import json
import logging
import os
import pprint
import threading
from multiprocessing import Process, Queue
from queue import Full, Empty
from uuid import uuid4

import segno
from PIL import Image
from PyPDF2 import PdfFileReader, PdfFileWriter
from pylibdmtx.pylibdmtx import encode
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from conf.constant import pdf, eps
from src.comm.comm import ready_cont, get_loop, ready_queue
from src.comm.log import console_log
from src.comm.util import exec_command
from src.converter.watcher import Watcher


def register_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(conf.font_path, 'Helvetica-Light.ttf')
    pdfmetrics.registerFont(TTFont('Helvetica-Light', font_path))
    font_path = os.path.join(conf.font_path, 'Helvetica-heavy.ttf')
    pdfmetrics.registerFont(TTFont('Helvetica-heavy', font_path))
    # font_path = os.path.join(conf.font_path, 'HankookTTFBold.ttf')
    # pdfmetrics.registerFont(TTFont('HankookTTFBold', font_path))
    # font_path = os.path.join(conf.font_path, 'HankookTTFLight.ttf')
    # pdfmetrics.registerFont(TTFont('HankookTTFLight', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFRegular.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFRegular', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFBold.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFBold', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFLight.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFLight', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFMediumOblique.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFMediumOblique', font_path))
    font_path = os.path.join(conf.font_path, 'HankookTTFSemiboldOblique.ttf')
    pdfmetrics.registerFont(TTFont('HankookTTFSemiboldOblique', font_path))


register_font()


def get_tmp_name(ext):
    tmp_path = os.path.join(conf.root_path, conf.data_path, 'tmp_files')
    # tmp_file = f'{tmp_path}/{str(uuid4())}{ext}'
    tmp_file = os.path.join(f'{tmp_path}', f'{str(uuid4())}{ext}')
    logging.info(f'이미지 생성을 위한 임시파일=|{tmp_file}|')
    return tmp_file


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


def rotate_pdf(input_file, output_file, rotation_angle):
    with open(input_file, 'rb') as file:
        reader = PdfFileReader(file)
        writer = PdfFileWriter()

        for page_num in range(reader.numPages):
            page = reader.getPage(page_num)
            page.rotateClockwise(-1 * rotation_angle)
            writer.addPage(page)

        with open(output_file, 'wb') as output:
            writer.write(output)


def generate_pdf(data, filename):
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


def conv_text(filename):
    with open(filename, "rt") as f:
        data = json.load(f)
        out_file = get_out_name(filename)
        generate_pdf(data, out_file)
        return out_file


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
    ok = ready_cont()[2]
    while ok():
        b, r = watcher.get_ret()
        if b:
            logging.info(f'id =|{threading.get_ident()}| ret =|{r}|')
            # 무엇이든.. 하고 싶은 작업을 여기서 해라..
        await aio.sleep(0.5)
    watcher.stop_proc()


async def thread_main(path, proc):
    watcher = Watcher(path, proc)
    loop = get_loop()
    t1 = loop.create_task(watcher.run_proc())
    t2 = loop.create_task(do_convert(watcher))
    logging.info(f'태스크 생성 완료')

    ret = await aio.gather(t1, t2)
    logging.info(f'이벤트 루프 종료, 결과=|{ret}|')


def thread_proc(path, proc):
    aio.run(thread_main(path, proc))


async def run_converter(send_q, recv_q):
    proc = convert
    in_path = os.path.join(conf.root_path, conf.in_path)

    # 메인 쓰레드만이 시그널 등록을 할 수 있음
    ok = ready_cont()[2]

    t_list = []
    logging.info(f'총 |{conf.path_count}|개의 디렉토리 모니터링')
    for i in range(conf.path_count):
        sub_path = os.path.join(in_path, str(i + 1))
        t = Process(target=thread_proc, args=(sub_path, proc), daemon=True)
        t_list.append(t)
        t.start()

    limit_cnt = 3
    while ok():
        if d := recv_q():
            d_msg = pprint.pformat(d)
            logging.info(f'스타터로부터 정보 수신=|{d_msg}|')
            # todo 2024.0123 by june1
            #   - jpg, png, eps, pdf 이미지를 pdf 로 변환
            #       . 수신한 데이터를 바탕으로 이미지 파일을 찾아서 in_files 하위 디렉토리에 복사
            #       . 각 프로세스에 차례대로 분배
            #   -

            fail_cnt = 0
            while ok():
                if send_q(d):
                    logging.info(f'머저에게 정보 송신=|{d_msg}|')
                    break

                # 머저에게 데이터 송신 실패
                fail_cnt += 1
                if fail_cnt > limit_cnt:
                    logging.error(f'머저에게 정보 송신 실패(처리 필요), 데이터=|{d_msg}|')
                    break
                await aio.sleep(1)
            continue

        await aio.sleep(1)

    for t in t_list:
        t.terminate()
    for t in t_list:
        t.join()


async def converter_proc(rq, wq):
    logging.info(f'컨버터 모듈 시작')
    send_q, recv_q, close_q = ready_queue(wq, rq)
    await run_converter(send_q, recv_q)
    logging.info(f'컨버터 모듈 종료')
    close_q()
    return 'ok'


async def test_sub1(q):
    def get_data():
        data = {
            'input': {
                'count': 20,
                'key': '4410',
                'src': [
                    {
                        'align': None,
                        'coordi': (None, None),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/Template/HK/GLB_G3.pdf',
                        'priotiry': 1,
                        'rotate': None,
                        'size': (240.0, 80.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (38.37, 38.37),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/productName/HK_127B_productName.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (144.0, 27.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None},
                    {
                        'align': None,
                        'coordi': (35.0, 35.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/image1/HK/HK_K127B_image1.eps',
                        'priotiry': 2,
                        'rotate': None,
                        'size': (75.0, 40.5),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.0, 35.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/image2/HK/HK_K127B_image2.eps',
                        'priotiry': 2,
                        'rotate': None,
                        'size': (54.3, 18.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (87.0, 87.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_hori.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (95.0, 18.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (11.0, 11.0),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_verti.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (17.0, 74.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (0.1, 0.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_1.eps',
                        'priotiry': 3,
                        'rotate': None,
                        'size': (35.0, 21.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (None, None),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_2.eps',
                        'priotiry': 3,
                        'rotate': None,
                        'size': (89.3, 3.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.1, 35.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_hori.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (147.0, 0.2),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (35.1, 35.1),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_verti.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (0.2, 56.0),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (183.3, 183.3),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/picto/HK_K127B_picto.eps',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (32.42, 40.94),
                        'text': None,
                        'type_': 'IMAGE',
                        'valign': None
                    },
                    {
                        'align': None,
                        'coordi': (178.8, 178.8),
                        'font': None,
                        'font_color': (None, None, None),
                        'font_size': None,
                        'name': '/lpas/Engine/data/src_files/images/HK/barcode/8808563461533.png',
                        'priotiry': 12,
                        'rotate': None,
                        'size': (40.0, 15.5),
                        'text': '8808563461533',
                        'type_': 'BARCODE',
                        'valign': None
                    },
                    {
                        'align': 'center',
                        'coordi': (37.0, 37.0),
                        'font': 'Helvetica-Bold',
                        'font_color': (None, None, None),
                        'font_size': 39.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (140.0, 14.0),
                        'text': '235/65R18 91Y XL',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'right',
                        'coordi': (29.5, 29.5),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 16.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (44.6, 5.85),
                        'text': '235/65R18 91Y XL',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (39.0, 39.0),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 9.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (140.0, 8.5),
                        'text': 'Pleasure cross point between performance and '
                                'emotion',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'left',
                        'coordi': (29.3, 29.3),
                        'font': 'Helvetica-Bold',
                        'font_color': (None, None, None),
                        'font_size': 16.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (21.0, 6.2),
                        'text': 'K127B',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (182.0, 182.0),
                        'font': 'Helvetica-heavy',
                        'font_color': (None, None, None),
                        'font_size': 20.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (34.6, 8.3),
                        'text': '1234567',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'right',
                        'coordi': (3.6, 3.6),
                        'font': 'Helvetica-heavy',
                        'font_color': (None, None, None),
                        'font_size': 24.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (44.0, 9.5),
                        'text': '1234567',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'center',
                        'coordi': (185.3, 185.3),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 7.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': None,
                        'size': (27.7, 2.8),
                        'text': 'NOT FOR SALE IN JAPAN',
                        'type_': 'TEXT',
                        'valign': 'top'
                    },
                    {
                        'align': 'left',
                        'coordi': (3.5, 3.5),
                        'font': 'Helvetica',
                        'font_color': (None, None, None),
                        'font_size': 5.0,
                        'name': None,
                        'priotiry': 99,
                        'rotate': 90,
                        'size': (20.3, 1.85),
                        'text': 'J-0001044483-230915',
                        'type_': 'TEXT',
                        'valign': 'top'
                    }
                ]
            },
            'output': {
                'name': '/LPAS/lpas/data/done_files/PDF/20230901/110_9999036431_9999036431_000010_1024881.pdf',
                'size': (80, 240)
            }
        }
        return data

    try:
        q.put_nowait(get_data())
    except Full:
        logging.debug(f'큐가 가득참')
    except Exception as e:
        logging.error(f'작업 송신 실패=|{e}|')
    return 'ok'


async def test_sub2(q):
    ok = ready_cont()[2]
    while ok():
        try:
            ret = q.get_nowait()
            logging.info(f'{pprint.pformat(ret)}')
        except Empty:
            logging.debug(f'큐가 비었음')
        except Exception as e:
            logging.error(f'결과 수신 실패=|{e}|')
        await aio.sleep(1)
    return 'ok'


async def test_main():
    sq, rq = Queue(), Queue()
    loop = get_loop()
    t1 = loop.create_task(converter_proc(rq, sq))
    t2 = loop.create_task(test_sub1(rq))
    t3 = loop.create_task(test_sub2(sq))
    ret = await aio.gather(t1, t2, t3)
    logging.info(f'테스트 결과=|{ret}|')


def test():
    aio.run(test_main())


if __name__ == '__main__':
    console_log()
    test()
