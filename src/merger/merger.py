import asyncio as aio
import logging
import os
import pprint
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Queue
from queue import Empty
from time import sleep

import PyPDF2
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.comm import ready_cont, get_loop
from src.comm.log import console_log
from src.comm.util import exec_command


def r(d):
    return round(d, 2)


"""
이미지 박스 내에 이미지가 위치하는 방법
coordi 성분의 3번째 값
만약 생략되었다면 디폴트 5
+---------+
| 1     2 |
|    5    |
| 4     3 |
+---------+
"""


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
                    'priority': 0,
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
    info3 = {
        'input': {
            'key': 'appl',
            'count': 13,
            'src': [
                {
                    'type_': 'img',
                    'name': 'EU_기본도면_2',
                    'coordi': (0, 0),
                    'size': (86, 173),
                    'rotate': 0,
                    'priority': 0,
                },
                {
                    'type_': 'img',
                    'name': 'EU_HK_TH31+_productName',
                    'coordi': (4, 18.5),
                    'size': (78, 12.6),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'type_': 'text',
                    'name': 'Size_spec',
                    'coordi': (29.05, 33.2),
                    'size': (53.1, 6.9),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Product_code',
                    'coordi': (3.46, 33.2),
                    'size': (22, 6.8),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_S_head',
                    'coordi': (21.7, 41),
                    'size': (5.5, 5.73),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_S',
                    'coordi': (27, 41),
                    'size': (21.8, 5.73),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_A_head',
                    'coordi': (55, 52),
                    'size': (5.5, 5.73),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_A',
                    'coordi': (60.45, 52),
                    'size': (21.8, 5.73),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'text',
                    'name': 'Form',
                    'coordi': (4.3, 167.4),
                    'size': (25, 4.25),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    # 바코드의 경우 이미지 박스가 아닌 이미지 자체의 크기와 좌표를 사용
                    'type_': 'bar',
                    'name': '880856333945',
                    'coordi': (22, 46.3),
                    'size': (24, 9.5),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    # 바코드의 경우 이미지 박스가 아닌 이미지 자체의 크기와 좌표를 사용
                    'type_': 'bar',
                    'name': '880856333946',
                    'coordi': (55, 41.5),
                    'size': (24, 9.5),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'img',
                    'name': 'eugrade',
                    'coordi': (4, 57.044),
                    'size': (78, 110),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'type_': 'qr',
                    'name': 'qr_eu_a',
                    'coordi': (4.7, 42),
                    'size': (10.6, 10.6),
                    'rotate': 0,
                    'priority': 3,
                },
            ]
        },
        'output': {
            'name': 'EU_HK',
            'size': (86, 173),
        },
    }
    info4 = {
        'input': {
            'key': 'yell',
            'count': 20,
            'src': [
                {
                    'type_': 'img',
                    'name': 'GLB_G3',
                    'coordi': (0, 0),
                    'size': (240, 80),
                    'rotate': 0,
                    'priority': 0,
                },
                {
                    'type_': 'img',
                    'name': 'HK_K127B_productName',
                    'coordi': (38.37, 30),
                    'size': (144, 27),
                    'rotate': 0,
                    'rate': 130.0,
                    'priority': 99,
                },
                {
                    'type_': 'img',
                    'name': 'HK_K127B_image1',
                    'coordi': (35, 21),
                    'size': (75, 40.5),
                    'rotate': 0,
                    'rate': 83.0,
                    'priority': 1,
                },
                {
                    'type_': 'img',
                    'name': 'HK_K127B_image2',
                    'coordi': (35, 3, 3),
                    'size': (54.3, 18),
                    'rotate': 0,
                    'rate': 69.854,
                    'priority': 1,
                },
                {
                    'type_': 'img',
                    'name': 'HANKOOK_logo_hori',
                    'coordi': (87, 3),
                    'size': (95, 18),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'img',
                    'name': 'HANKOOK_logo_verti',
                    'coordi': (11, 3),
                    'size': (17, 74),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'img',
                    'name': 'GLP_G3_SPACE_1',
                    'coordi': (0.1, 0.1),
                    'size': (35, 21),
                    'rotate': 0,
                    'priority': 2,
                },
                {
                    'type_': 'img',
                    'name': 'GLP_G3_SPACE_2',
                    'coordi': (0, 0),
                    'size': (89.3, 3),
                    'rotate': 0,
                    'priority': 2,
                },
                {
                    'type_': 'img',
                    'name': 'LINE_hori',
                    'coordi': (35.1, 61.5),
                    'size': (147, 0.2),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'img',
                    'name': 'LINE_verti',
                    'coordi': (35.1, 21),
                    'size': (0.2, 56),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'img',
                    'name': 'HK_K127B_picto',
                    'coordi': (183.3, 3),
                    'size': (32.42, 40.94),
                    'rotate': 0,
                    'rate': 102.0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Size_spec_1',
                    'coordi': (37, 65.2),
                    'size': (140, 14),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Size_spec_2',
                    'coordi': (29.5, 4),
                    'size': (44.6, 5.85),
                    'rotate': 90,
                    'font_size': 16,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Head_copy',
                    'coordi': (39, 22),
                    'size': (140, 8.5),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Product_code',
                    'coordi': (29.3, 55.7),
                    'size': (21, 6.2),
                    'rotate': 90,
                    'font_size': 16,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_1',
                    'coordi': (182, 48.4),
                    'size': (34.6, 8.3),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'M_code_2',
                    'coordi': (3.6, 3.6),
                    'size': (44, 9.5),
                    'rotate': 90,
                    'font_size': 24,
                    'priority': 99,
                },
                {
                    'type_': 'bar',
                    'name': '880856333946',
                    'coordi': (178.8, 61.5),
                    # 'size': (31.4, 11.7),
                    'size': (40, 15.5),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Form',
                    'coordi': (185.3, 57.3),
                    'size': (27.7, 2.8),
                    'rotate': 0,
                    'priority': 99,
                },
                {
                    'type_': 'text',
                    'name': 'Jobinfo',
                    'coordi': (3.5, 56.5),
                    'size': (20.3, 1.85),
                    'rotate': 90,
                    'font_size': 5,
                    'priority': 99,
                },
            ]
        },
        'output': {
            'name': 'GLB_HK',
            'size': (240, 80),
        },
    }
    return info4


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


def merge_pdf(file_list, out_file, size, info):
    # 너비와 높이를 포인트 단위로 지정
    width, height = size
    logging.info(f'높이=|{height}| 너비=|{width}| 밑바탕 생성')
    c = canvas.Canvas(out_file, pagesize=(width * mm, height * mm))
    c.showPage()
    c.save()

    base_reader = PdfFileReader(out_file, "rb")
    base_page = base_reader.getPage(0)

    # 정렬 작업부터..
    src_list = info.get('input').get('src')

    def find_priority(name):
        for src_dict in src_list:
            if src_dict.get('name') in name:
                return src_dict.get('priority')
        return 99

    files = [{'name': file, 'priority': find_priority(file)} for file in file_list]

    for f_dict in sorted(files, key=lambda x: x['priority']):
        f = f_dict.get('name')
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

    out_list = []
    for src in src_list:
        with (open(src, 'rb') as file):
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
            logging.info(f'|{pure}| 박스 크기정보, |{r(box_width), r(box_height)}|')

            # 좌표
            if len(info['coordi']) == 2:
                (box_x, box_y), coordi = info['coordi'], 5
            elif len(info['coordi']) == 3:
                box_x, box_y, coordi = info['coordi']
            else:
                logging.error(f'좌표 정보 부정확, |{info["coordi"]}|')
                continue
            if (rotate := info.get('rotate', 0)) == 90:
                if vlign := info.get('vlign', 'top'):
                    font_size = info.get('font_size', 0) * 0.25
                    move = (box_height - font_size) / 2
                    if vlign == 'top':
                        box_x -= move
                    elif vlign == 'bottom':
                        box_x += move
                    else:
                        pass
                box_y += (box_width - box_height)
                coordi = 1
            logging.info(f'|{pure}| 박스 좌표정보, |{r(box_x), r(box_y), coordi}|')

            # 스케일
            scale = round(info.get('rate', 100) / 100.0, 2)
            logging.info(f'|{pure}| 확대축소 정보, |{scale}|')

            if reader := PdfFileReader(file):
                page = reader.getPage(0)

                # 스케일 조정
                ret = page.mediaBox.upperRight
                img_width = r(float(ret[0]) / mm) * scale
                img_height = r(float(ret[1]) / mm) * scale
                if coordi == 5:
                    img_x = box_x + (box_width - img_width) / 2
                    img_y = box_y + (box_height - img_height) / 2
                elif coordi == 1:
                    img_x = box_x
                    img_y = box_y
                elif coordi == 2:
                    img_x = box_x + box_width - img_width
                    img_y = box_y
                elif coordi == 3:
                    img_x = box_x + box_width - img_width
                    img_y = box_y + box_height - img_height
                elif coordi == 4:
                    img_x = box_x
                    img_y = box_y + box_height - img_height
                logging.info(
                    f'|{pure}| 크기정보, '
                    f'실제로 불러온 이미지의 크기=|{img_width},{img_height}| '
                    f'이미지박스의 크기=|{box_width},{box_height}| '
                    f'실제로 이미지가 위치하는 좌표=|{img_x},{img_y}|')

                # 여백 주기, 회전
                l_margin = img_x
                b_margin = r(float(height - img_y - img_height))
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
                    '-c', f'<</PageOffset [{l_margin * mm} {b_margin * mm}] '
                          f'/BeginPage {{{scale} {scale} scale}}>> setpagedevice',
                    '-f', src
                ]
                exec_command(command)
                out_list.append(o_file)

    return out_list


async def run_merger2(rq):
    ok = ready_cont()[2]
    while ok():
        try:
            # 작업 정보 획득
            info = get_task_info(rq)

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
            merge_pdf(out_list, out_file, size, info)

            # todo 2023.0710 by june1
            #  - 지금은 오직 한 건만 진행..
            #  - 기능 구현 완료 후 무한 반복..
            break

        except Exception as e:
            logging.error(f'에러 =|{e}|')
            # 종료 여부는 추후 결정
            break


def task_proc(task):
    logging.debug(f'컨버터로부터 데이터 수신=|{pprint.pformat(task)}|')


async def run_merger(rq):
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        ok = ready_cont()[2]
        while ok():
            try:
                task = rq.get_nowait()
                executor.submit(task_proc, task)
                continue
            except Empty:
                logging.debug(f'큐가 비었음')
            except Exception as e:
                logging.error(e)
            await aio.sleep(1)


async def merger_proc(rq):
    logging.info(f'머저 모듈 시작')
    await run_merger(rq)
    logging.info(f'머저 모듈 종료')
    rq.close()


async def test_main():
    def get_data():
        data = {
            'input': {
                'count': 20,
                'key': 'ccf3',
                'src': [
                    {'align': None,
                     'coordi': (None, None),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/Template/HK/GLB_G3.pdf',
                     'priotiry': 1,
                     'rotate': None,
                     'size': (240.0, 80.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_194_GLB_G3.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (38.37, 38.37),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/productName/HK_K127B_productName.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (144.0, 27.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_194_HK_K127B_productName.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.0, 35.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/image1/HK_K127B_image1.eps',
                     'priotiry': 2,
                     'rotate': None,
                     'size': (75.0, 40.5),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_195_HK_K127B_image1.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.0, 35.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/image2/HK_K127B_image2.eps',
                     'priotiry': 2,
                     'rotate': None,
                     'size': (54.3, 18.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_196_HK_K127B_image2.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (87.0, 87.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_hori.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (95.0, 18.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_197_HANKOOK_logo_hori.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (11.0, 11.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_verti.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (17.0, 74.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_197_HANKOOK_logo_verti.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (0.1, 0.1),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_1.eps',
                     'priotiry': 3,
                     'rotate': None,
                     'size': (35.0, 21.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_197_GLB_G3_SPACE_1.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (None, None),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_2.eps',
                     'priotiry': 3,
                     'rotate': None,
                     'size': (89.3, 3.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_197_GLB_G3_SPACE_2.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.1, 35.1),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_hori.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (147.0, 0.2),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_198_LINE_hori.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.1, 35.1),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_verti.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (0.2, 56.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_198_LINE_verti.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (183.3, 183.3),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/picto/HK_K127B_picto.eps',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (32.42, 40.94),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_198_HK_K127B_picto.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (178.8, 178.8),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/barcode/barcode1/8808563461533.pdf',
                     'priotiry': 12,
                     'rotate': None,
                     'size': (40.0, 15.5),
                     'target': '/lpas/Engine/data/src_files/images/HK/barcode/barcode1/8808563461533.pdf',
                     'text': '8808563461533',
                     'type_': 'EAN',
                     'valign': None},
                    {'align': 'center',
                     'coordi': (37.0, 37.0),
                     'font': 'Helvetica-Bold',
                     'font_color': (None, None, None),
                     'font_size': 39.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': None,
                     'size': (140.0, 14.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_199_d473e118.pdf',
                     'text': '235/65R18 91Y XL',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (29.5, 29.5),
                     'font': 'Helvetica',
                     'font_color': (None, None, None),
                     'font_size': 16.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 90,
                     'size': (44.6, 5.85),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_205_5214c635.pdf',
                     'text': '235/65R18 91Y XL',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (39.0, 39.0),
                     'font': 'Helvetica',
                     'font_color': (None, None, None),
                     'font_size': 9.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': None,
                     'size': (140.0, 8.5),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_205_9e112c6b.pdf',
                     'text': 'Pleasure cross point between performance and '
                             'emotion',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'left',
                     'coordi': (29.3, 29.3),
                     'font': 'Helvetica-Bold',
                     'font_color': (None, None, None),
                     'font_size': 16.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 90,
                     'size': (21.0, 6.2),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_bdffe7cd.pdf',
                     'text': 'K127B',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (182.0, 182.0),
                     'font': 'Helvetica-heavy',
                     'font_color': (None, None, None),
                     'font_size': 20.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': None,
                     'size': (34.6, 8.3),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_0c335d81.pdf',
                     'text': '1234567',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (3.6, 3.6),
                     'font': 'Helvetica-heavy',
                     'font_color': (None, None, None),
                     'font_size': 24.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 90,
                     'size': (44.0, 9.5),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_79a50bae.pdf',
                     'text': '1234567',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (185.3, 185.3),
                     'font': 'Helvetica',
                     'font_color': (None, None, None),
                     'font_size': 7.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': None,
                     'size': (27.7, 2.8),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_898c6ed7.pdf',
                     'text': 'NOT FOR SALE IN JAPAN',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'left',
                     'coordi': (3.5, 3.5),
                     'font': 'Helvetica',
                     'font_color': (None, None, None),
                     'font_size': 5.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 90,
                     'size': (20.3, 1.85),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_07b75d78.pdf',
                     'text': 'J-0001044483-230915',
                     'type_': 'TEXT',
                     'valign': 'top'}
                ]
            },
            'output': {
                'name': '/LPAS/lpas/data/done_files/PDF/20230901/110_9999036431_9999036431_000010_1024881.pdf',
                'size': (80, 240)
            }
        }
        return data

    q = Queue()
    q.put(get_data())
    loop = get_loop()
    t1 = loop.create_task(merger_proc(q))
    ret = await aio.gather(t1)
    logging.info(f'테스트 결과=|{ret}|')


def test():
    aio.run(test_main())


if __name__ == '__main__':
    console_log()
    test()
