import logging
import os
from time import sleep

from PyPDF2 import PdfFileReader, PdfFileWriter, PageObject
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.comm import get_log_level, ready_cont
from src.comm.log import console_log
from src.comm.util import exec_command


def get_task_info():
    # 작업 정보는 데이터베이스 혹은 starter 로부터 수신
    # 작업 고유번호를 갖고.. 매번 새로운 작업 정보를 수신
    info = {
        'input': {
            'key': 'abcd',
            'count': 4,
            'src': [
                {
                    'name': '880856333945',
                    'coordi': (155, 35),
                    'size': (45, 15),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'name': 'JP_G1_warning',
                    'coordi': (205, 5),
                    'size': (33.20, 69.60),
                    'rotate': 0,
                    'priority': 3,
                },
                {
                    'name': 'G3_a',
                    'coordi': (0, 0),
                    'size': (240, 80),
                    'rotate': 0,
                    'priority': 1,
                },
                {
                    'name': 'HK_V S1 EVO2 SUV HRS_productName',
                    'coordi': (26, 32),
                    'size': (105, 15),
                    'rotate': 0,
                    'priority': 1,
                },
            ]
        },
        'output': {
            'name': 'HK_V S1 EVO2 SUV HRS',
            'size': (240, 80),
        }
    }
    return info


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
                    f'|{os.path.basename(src)}| 정보=|{info}| 페이지수=|{pages}| 크기=|{width, height}|'
                    f'미디어박스=|{page.mediaBox}| ')


def get_padding_name(src):
    b, e = os.path.splitext(src)
    return f'{b}__RESIZE__{e}'


def merge_pdf(file_list, out_file, size):
    # 너비와 높이를 포인트 단위로 지정
    width, height = size
    logging.info(f'높이=|{height}| 너비=|{width}| 밑바탕 생성')
    c = canvas.Canvas(out_file, pagesize=(width, height))
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


def add_margin(reader, l_margin, b_margin):
    # PDF 파일 읽기
    # 원본 페이지 크기 가져오기
    page = reader.getPage(0)
    orig_width = page.mediaBox.getWidth()
    orig_height = page.mediaBox.getHeight()

    # 새 페이지의 크기 (원본 크기 + 여백)
    new_width = orig_width + l_margin
    new_height = orig_height + b_margin

    # 원본 페이지 가져오기
    # 새 페이지 만들기 (비어있음)
    # 새 페이지 위에 원본 페이지 붙여넣기
    orig_page = reader.getPage(0)
    new_page = PageObject.createBlankPage(None, new_width, new_height)
    new_page.mergeTranslatedPage(orig_page, l_margin, b_margin)
    return new_page


def resize_data(src_list, info_list, size):
    # 전체 이미지의 크기
    width, height = size

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
                logging.error(f'파일이 정보에 존재하지 않음, 파일=|{pure}|')
                continue

            info = infos[0]
            # 사이즈 조정
            tobe_width, tobe_height = info['size']
            # 좌표
            x, y = info['coordi']
            logging.info(f'|{pure}| 위치해야 할 좌표=|{x, y}|')

            if reader := PdfFileReader(file):
                page = reader.getPage(0)

                # 스케일 조정
                ret = page.mediaBox.upperRight
                asis_width = float(ret[0])
                asis_height = float(ret[1])
                scale_x = round(tobe_width / asis_width, 4)
                scale_y = round(tobe_height / asis_height, 4)
                logging.info(f'|{pure}| 원래 크기=|{asis_width, asis_height}| '
                             f'목표 크기=|{tobe_width, tobe_height}| '
                             f'스케일=|{scale_x, scale_y}|')

                # 여백 주기
                l_margin = x
                b_margin = int(height - (tobe_height + y))
                logging.info(f'여백 주기, |{pure}| 좌=|{l_margin}| 하=|{b_margin}|')

                # 변환된 결과물 생성
                o_file = get_padding_name(src)
                command = [
                    'gs',
                    '-sDEVICE=pdfwrite',
                    '-o', o_file,
                    '-dFIXEDMEDIA',
                    f'-dDEVICEWIDTHPOINTS={width}',
                    f'-dDEVICEHEIGHTPOINTS={height}',
                    '-c',
                    f'<</BeginPage {{{scale_x} {scale_y} scale}} /PageOffset [{l_margin} {b_margin}]>> setpagedevice',
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
    merger_proc()
