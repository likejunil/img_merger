import asyncio as aio
import glob
import logging
import os
import pprint
from concurrent.futures import ProcessPoolExecutor
from io import FileIO
from multiprocessing import Queue
from queue import Empty

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.comm import ready_cont, get_loop
from src.comm.db import update
from src.comm.log import console_log
from src.comm.query import get_upd_yes_lpas_header
from src.comm.util import exec_command


def get_padding_name(src):
    b, e = os.path.splitext(src)
    return f'{b}__RESIZE__{e}'


async def delete_files(src_list, key):
    # out 디렉토리
    for src in src_list:
        try:
            # out 디렉토리
            os.remove(src['target'])
            os.remove(src['resized'])
        except Exception as e:
            logging.error(f'예외 발생=|{e}|')

    # in 디렉토리
    pattern = os.path.join(conf.root_path, conf.in_path, '**', f'{key}*')
    files = glob.glob(pattern, recursive=True)
    for file in files:
        try:
            os.remove(file)
        except Exception as e:
            logging.error(f'예외 발생=|{e}|')


async def merge_data(src_list, o_file, size):
    # 최종 결과물을 담을 캔버스 생성
    width, height = size
    canvas.Canvas(o_file, pagesize=(width * mm, height * mm)).save()
    logging.info(f'최종 결과물 바탕 생성=|{o_file}|')

    # 구성 요소 이미지들을 병합
    result = PdfFileReader(o_file, 'rb').getPage(0)
    for src in sorted(src_list, key=lambda x: x['priority']):
        with open(src['resized'], 'rb') as f:
            reader = PdfFileReader(f)
            page = reader.getPage(0)
            result.mergePage(page)
            logging.info(f'최종 결과물에 구성 요소 병합=|{src["resized"]}|')

    out = PdfFileWriter()
    out.addPage(result)
    with FileIO(o_file, 'wb') as f:
        out.write(f)
        logging.info(f'최종 결과물 생성 완료=|{o_file}|')


async def resize_data(src_list, size):
    width, height = size
    for src in src_list:
        with open(f_name := src['target'], 'rb') as f:
            if reader := PdfFileReader(f):
                page = reader.getPage(0)

                # 이미지가 담길 영역의 좌표(좌측 상단 기준)
                box_x, box_y = src['coordi']
                # 영역의 크기
                box_width, box_height = src['size']
                # 실제 현재 이미지의 크기
                is_width, is_height = page.mediaBox.upperRight
                is_width /= mm
                is_height /= mm
                # 스케일 적용
                scale = round(src.get('rate', 100) / 100.0, 3)
                img_width = round(is_width * scale, 2)
                img_height = round(is_height * scale, 2)

                # 영역에서 이미지의 정렬
                # 이미지가 위치할 좌표
                if align := src.get('position', 'cm').lower() == 'lt':
                    img_x = box_x
                    img_y = box_y
                elif align == 'lm':
                    img_x = box_x
                    img_y = box_y + (box_height - img_height) / 2
                elif align == 'lb':
                    img_x = box_x
                    img_y = box_y + box_height - img_height
                elif align == 'ct':
                    img_x = box_x + (box_width - img_width) / 2
                    img_y = box_y
                elif align == 'cm':
                    img_x = box_x + (box_width - img_width) / 2
                    img_y = box_y + (box_height - img_height) / 2
                elif align == 'cb':
                    img_x = box_x + (box_width - img_width) / 2
                    img_y = box_y + (box_height - img_height)
                elif align == 'rt':
                    img_x = box_x + (box_width - img_width)
                    img_y = box_y
                elif align == 'rm':
                    img_x = box_x + (box_width - img_width)
                    img_y = box_y + (box_height - img_height) / 2
                elif align == 'rb':
                    img_x = box_x + (box_width - img_width)
                    img_y = box_y + (box_height - img_height)
                else:
                    img_x = box_x + (box_width - img_width) / 2
                    img_y = box_y + (box_height - img_height) / 2

                # 마진 계산
                l_margin = img_x
                b_margin = height - (img_y + img_height)

                # 변환된 파일 이름
                o_file = get_padding_name(f_name)
                src['resized'] = o_file

                command = [
                    'gs',
                    '-sDEVICE=pdfwrite',
                    '-o', o_file,
                    '-dFIXEDMEDIA',
                    f'-dDEVICEWIDTHPOINTS={width * mm}',
                    f'-dDEVICEHEIGHTPOINTS={height * mm}',
                    '-c', f'<</PageOffset [{l_margin * mm} {b_margin * mm}] '
                          f'/BeginPage {{{scale} {scale} scale}}>> setpagedevice',
                    '-f', f_name
                ]
                exec_command(command)


async def check_src_list(src_list, lmt_sec):
    wait_sec = 0
    for src in src_list:
        if not os.path.exists(src['target']):
            wait_sec += 1
            if wait_sec > lmt_sec:
                logging.error(f'필요한 구성 파일이 존재하지 않음=|{src["target"]}|')
                return False
            await aio.sleep(0.1)

    logging.info(f'모든 구성요소 파일이 준비되었음')
    return True


async def task_proc(task):
    logging.debug(f'컨버터로부터 데이터 수신=|{pprint.pformat(task)}|')

    # 출력 정보
    out_data = task.get('output')
    size = out_data['size']
    name = out_data['name']
    mandt = out_data['mandt']
    ebeln = out_data['ebeln']
    vbeln = out_data['vbeln']
    posnr = out_data['posnr']
    matnr = out_data['matnr']
    merged_file = os.path.join(conf.root_path, conf.merged_path, os.path.basename(name))

    # 입력 정보
    in_data = task.get('input')
    key = in_data['key']
    src_list = in_data['src']

    # 모든 입력 파일이 준비될 때까지 기다림
    ok = ready_cont()[2]
    while ok():
        try:
            # 구성요소 이미지 파일들이 모두 존재하는지 확인
            if not await check_src_list(src_list, 3):
                logging.error(f'결과물 생성 실패')
                break

            # 구성요소 이미지들의 크기를 재조정
            await resize_data(src_list, size)

            # 크기가 재조정된 파일들을 병합
            await merge_data(src_list, merged_file, size)

            # 결과를 데이터베이스에 반영
            update(get_upd_yes_lpas_header(mandt, ebeln, vbeln, posnr, matnr))

            # 작업이 완료된 파일들을 정리
            await delete_files(src_list, key)

        except Exception as e:
            logging.error(f'예외 발생=|{e}|')
            break


async def thread_main(*args):
    loop = get_loop()
    t1 = loop.create_task(task_proc(*args))
    # t2 = loop.create_task(...)
    # t3 = loop.create_task(...)
    logging.info(f'태스크 생성 완료')

    ret = await aio.gather(t1)
    # ret = await aio.gather(t1, t2, t3)
    logging.info(f'이벤트 루프 종료, 결과=|{ret}|')


def thread_proc(*args):
    aio.run(thread_main(*args))


async def merger_proc(rq):
    logging.info(f'머저 모듈 시작')
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        ok = ready_cont()[2]
        while ok():
            try:
                task = rq.get_nowait()
                executor.submit(thread_proc, task)
                continue
            except Empty:
                logging.debug(f'큐가 비었음')
            except Exception as e:
                logging.error(e)
            await aio.sleep(1)

    logging.info(f'머저 모듈 종료')


async def test_main():
    def get_data():
        data = {
            'input': {
                'count': 20,
                'key': 'ccf3',
                'src': [
                    {'align': None,
                     'coordi': (0, 0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/Template/HK/GLB_G3.pdf',
                     'priotiry': 1,
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
                     'size': (35.0, 21.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_197_GLB_G3_SPACE_1.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (0, 0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_2.eps',
                     'priotiry': 3,
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
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
                     'rotate': 0,
                     'size': (40.0, 15.5),
                     'target': '/lpas/Engine/data/src_files/images/HK/barcode/barcode1/8808563461533.pdf',
                     'text': '8808563461533',
                     'type_': 'EAN',
                     'valign': None},
                    {'align': 'center',
                     'coordi': (37.0, 37.0),
                     'font': 'Helvetica-Bold',
                     'font_color': (0, 0, 0),
                     'font_size': 39.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 0,
                     'size': (140.0, 14.0),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_199_d473e118.pdf',
                     'text': '235/65R18 91Y XL',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (29.5, 29.5),
                     'font': 'Helvetica',
                     'font_color': (0, 0, 0),
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
                     'font_color': (0, 0, 0),
                     'font_size': 9.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 0,
                     'size': (140.0, 8.5),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_205_9e112c6b.pdf',
                     'text': 'Pleasure cross point between performance and '
                             'emotion',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'left',
                     'coordi': (29.3, 29.3),
                     'font': 'Helvetica-Bold',
                     'font_color': (0, 0, 0),
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
                     'font_color': (0, 0, 0),
                     'font_size': 20.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 0,
                     'size': (34.6, 8.3),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_0c335d81.pdf',
                     'text': '1234567',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (3.6, 3.6),
                     'font': 'Helvetica-heavy',
                     'font_color': (0, 0, 0),
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
                     'font_color': (0, 0, 0),
                     'font_size': 7.0,
                     'name': None,
                     'priotiry': 99,
                     'rotate': 0,
                     'size': (27.7, 2.8),
                     'target': '/LPAS/lpas/data/out_files/ccf3_20240130_160033_206_898c6ed7.pdf',
                     'text': 'NOT FOR SALE IN JAPAN',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'left',
                     'coordi': (3.5, 3.5),
                     'font': 'Helvetica',
                     'font_color': (0, 0, 0),
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

    q.close()


def test():
    aio.run(test_main())


if __name__ == '__main__':
    console_log()
    test()
