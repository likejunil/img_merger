import logging
import os
from time import sleep, time

import PyPDF2
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.comm import get_log_level, ready_cont
from src.comm.log import console_log
from src.comm.util import exec_command


def r(d):
    return round(d, 2)


def get_task_info():
    # 작업 정보는 데이터베이스 혹은 starter 로부터 수신
    # 작업 고유번호를 갖고.. 매번 새로운 작업 정보를 수신
    info1 = {
        'input': {
            'key': 'abcd',
            'count': 7,
            'src': [
                {
                    'name': 'G3_aaaa',
                    'coordi': (0, 0),
                    'size': (240, 80),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'name': 'G3_warning',
                    'coordi': (217.596, 3.841),
                    'size': (18.344, 72.319),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'name': 'HK_K135_a_productName',
                    'coordi': (22.7, 29.5),
                    'size': (130, 20),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'name': '880856333945',
                    'coordi': (161.643, 32.108),
                    'size': (42.596, 21.641),
                    'rotate': 0,
                    'priority': 3,
                    # EAN13 의 경우 바코드 우측 숫자가 없으므로 좌측으로 조금 이동 필요..
                    'left_move': 5,
                },
                {
                    'name': 'Size_spec',
                    'coordi': (23.101, 63.678),
                    # 'size': (149.301, 12.667),
                    'size': (178, 18.203),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'name': 'M_code',
                    'coordi': (168.541, 29.58),
                    # 'size': (27.972, 5.365),
                    'size': (32, 8),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'name': 'jabinfo',
                    'coordi': (213.336, 52.504),
                    # 'size': (1.619, 23.858),
                    'size': (2.269, 24),
                    'rotate': 90,
                    'priority': 3,
                },
            ]
        },
        'output': {
            'name': 'HK_V S1 EVO2 SUV HRS',
            'size': (240, 80),
        }
    }
    info2 = {
        'input': {
            'key': 'afkn',
            'count': 13,
            'src': [
                {
                    'type_': 'img',
                    'name': 'RU_기본도면',
                    'coordi': (0, 0),
                    'size': (120, 100),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'type_': 'img',
                    'name': 'ProductName',
                    'coordi': (3, 50.5),
                    'size': (70, 10),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'type_': 'text',
                    'name': 'Size_spec',
                    'coordi': (5.5, 5.92),
                    'size': (109, 13.4),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Head_copy',
                    'coordi': (4.3, 60.5),
                    'size': (67.4, 7.3),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'M_code',
                    'coordi': (79.5, 29.7),
                    'size': (35, 9),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Product_code',
                    'coordi': (6.2, 72.83),
                    'size': (19, 4.63),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Seq',
                    'coordi': (57, 71.5),
                    'size': (15, 3.5),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Sales',
                    'coordi': (53, 76),
                    'size': (18.8, 3),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Form',
                    'coordi': (84.8, 42.7),
                    'size': (25, 4.25),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    # 바코드의 경우 이미지 박스가 아닌 이미지 자체의 크기와 좌표를 사용
                    'type_': 'bar',
                    'name': '880856333945',
                    'coordi': (34.3, 26.4),
                    'size': (34, 13.5),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'dmtx',
                    'name': 'dmtx_russia_a',
                    'coordi': (5.17, 24),
                    'size': (21, 21),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'dmtx',
                    'name': 'dmtx_russia_b',
                    'coordi': (95.5, 52.84),
                    'size': (21, 21),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'qr',
                    'name': 'qr_russia_a',
                    'coordi': (76.75, 52.7),
                    'size': (16, 21),
                    'rotate': 0,
                    'priority': 3,
                },
            ]
        },
        'output': {
            'name': 'RU_HK',
            'size': (120, 100),
        }

    }
    return info2


def get_src_list(prefix, count):
    out_list = []
    out_path = os.path.join(conf.root_path, conf.out_path)

    wait_time = 1
    limit_time = 10
    total_time = 0

    _, _, ok = ready_cont()
    while ok():
        for name in os.listdir(out_path):
            if not name.startswith(prefix):
                continue

            target = os.path.join(out_path, name)
            if not os.path.isfile(target):
                continue

            if target not in out_list:
                out_list.append(target)

        if len(out_list) == count:
            return out_list

        if total_time >= limit_time:
            return out_list
        sleep(wait_time)
        total_time += wait_time


def data_info(src_list):
    for src in src_list:
        with open(src, 'rb') as file:
            if pdf := PdfFileReader(file):
                info = pdf.getDocumentInfo()
                pages = pdf.getNumPages()
                page = pdf.getPage(0)
                width, height = page.mediaBox.upperRight
                logging.info(
                    f'|{os.path.basename(src)}| 정보=|{info}| 페이지수=|{pages}| 크기=|{width, height}| '
                    f'미디어박스=|{page.mediaBox}| ')


def get_padding_name(src):
    b, e = os.path.splitext(src)
    return f'{b}__RESIZE__{e}'


def rotate_text(src, dst, degree):
    # PDF 파일을 열고 페이지를 추출합니다.
    with open(src, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfFileReader(pdf_file)
        page = pdf_reader.getPage(0)

        # 페이지를 원하는 방향으로 회전합니다.
        rotated_page = page.rotateClockwise(degree)

        # 회전된 페이지를 새로운 PDF 파일로 저장합니다.
        pdf_writer = PyPDF2.PdfFileWriter()
        pdf_writer.addPage(rotated_page)
        with open(dst, 'wb') as pdf_output_file:
            pdf_writer.write(pdf_output_file)


def merge_pdf(file_list, out_file, size):
    # 너비와 높이를 포인트 단위로 지정
    scale = mm
    width, height = size
    # width *= scale
    # height *= scale
    logging.info(f'높이=|{height}| 너비=|{width}| 밑바탕 생성')
    c = canvas.Canvas(out_file, pagesize=(width * mm, height * mm))
    c.showPage()
    c.save()

    base_reader = PdfFileReader(out_file, "rb")
    base_page = base_reader.getPage(0)

    for f in file_list:
        reader = PdfFileReader(open(f, "rb"))
        page = reader.getPage(0)
        logging.info(f'|{f}| 너비=|{page.mediaBox.getWidth()}| 높이=|{page.mediaBox.getHeight()}|')
        base_page.mergePage(page)

    output = PdfFileWriter()
    output.addPage(base_page)
    with open(out_file, "wb") as f:
        output.write(f)


def resize_data(src_list, info_list, size):
    # 전체 이미지의 크기
    # 스케일 조정
    width, height = size
    logging.info(f'전체 바탕의 크기=|{width, height}|')
    # width *= scale
    # height *= scale

    out_list = []
    for src in src_list:
        with open(src, 'rb') as file:
            # src 의 형태
            # |_____|___________________________|___________|____|
            # |abcd_|HK_V S1 EVO2 SUV HRS_image1|_095805.964|.pdf|
            base = os.path.basename(src)
            start_pos = base.find('_') + 1
            end_pos = base.rfind('_')
            pure = base[start_pos:end_pos]

            infos = list(filter(lambda m: os.path.splitext(os.path.basename(m['name']))[0] == pure, info_list))
            if not infos:
                logging.error(f'파일 정보가 존재하지 않음, 파일=|{pure}|')
                continue

            info = infos[0]
            # 사이즈 조정
            box_width, box_height = info['size']
            # box_width *= scale
            # box_height *= scale
            logging.info(f'|{pure}| 박스 크기정보, |{r(box_width), r(box_height)}|')

            # 좌표
            box_x, box_y = info['coordi']
            # box_x *= scale
            # box_y *= scale
            logging.info(f'|{pure}| 박스 좌표정보, |{r(box_x), r(box_y)}|')

            if reader := PdfFileReader(file):
                page = reader.getPage(0)

                # 스케일 조정
                ret = page.mediaBox.upperRight
                img_width = r(float(ret[0]) / mm)
                img_height = r(float(ret[1]) / mm)
                img_x = box_x + (box_width - img_width) / 2
                img_y = box_y + (box_height - img_height) / 2
                logging.info(
                    f'|{pure}| 크기정보, '
                    f'실제로 불러온 이미지의 크기=|{img_width},{img_height}| '
                    f'이미지박스의 크기=|{box_width},{box_height}| '
                    f'실제로 이미지가 위치하는 좌표=|{img_x},{img_y}|')

                # 여백 주기, 회전
                l_margin = img_x
                b_margin = r(float(height - img_y - img_height))
                rotate = info.get('rotate', 0)
                logging.info(f'|{pure}| 여백주기, 좌=|{l_margin}| 하=|{b_margin}| 회전=|{rotate}|')

                # 변환된 결과물 생성
                o_file = get_padding_name(src)
                command = [
                    'gs',
                    '-sDEVICE=pdfwrite',
                    '-o', o_file,
                    '-dFIXEDMEDIA',
                    f'-dDEVICEWIDTHPOINTS={width * mm}',
                    f'-dDEVICEHEIGHTPOINTS={height * mm}',
                    '-c', f'<</PageOffset [{l_margin * mm} {b_margin * mm}]>> setpagedevice',
                    '-f', src
                ]
                exec_command(command)
                out_list.append(o_file)

    return out_list


def merger_proc():
    _, _, ok = ready_cont()
    while ok():
        try:
            # 작업 정보 획득
            info = get_task_info()

            # 출력 정보
            out_data = info.get('output')
            size = out_data['size']
            name = out_data['name']
            merged_path = os.path.join(conf.root_path, conf.merged_path)
            out_file = os.path.join(merged_path, f'{name}.pdf')
            logging.info(f'출력, 파일=|{name}| 크기=|{size}|')

            # 구성 이미지들 로딩
            in_data = info.get('input')
            prefix = in_data['key']
            count = in_data['count']
            info_list = in_data['src']
            logging.info(f'입력, 목록=|{info_list}|')
            src_list = get_src_list(prefix, count)
            if len(src_list) != count:
                # todo 2023.0710 by june1
                #  - 부품 이미지의 수가 부족할 때 어떻게 처리할 것인가?
                #  - 실패한 작업은 어떻게 저장하고 후처리 방법은 무엇인가?
                logging.error(f'입력 이미지 부족, 키=|{prefix}| 필요개수=|{count}| 현재개수=|{len(src_list)}|')
                continue

            # 이미지 정보 출력
            data_info(src_list)
            out_list = resize_data(src_list, info_list, size)
            merge_pdf(out_list, out_file, size)

            # todo 2023.0710 by june1
            #  - 지금은 오직 한 건만 진행..
            #  - 기능 구현 완료 후 무한 반복..
            break

        except Exception as e:
            logging.error(f'에러 =|{e}|')
            # 종료 여부는 추후 결정
            break


if __name__ == '__main__':
    console_log(get_log_level())
    st = time()
    merger_proc()
    et = time()
    print(f'경과시간=|{et - st}|')
