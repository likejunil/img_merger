import asyncio as aio
import glob
import logging
import os
import pprint
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from io import FileIO
from multiprocessing import Queue
from queue import Empty

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.comm import ready_cont, get_loop, cache_func
from src.comm.db import update
from src.comm.log import initialize_log, console_log
from src.comm.query import get_upd_yes_lpas_header, get_upd_err_lpas_header
from src.comm.util import exec_command


@cache_func
def ready_error():
    _err = 'E'

    def s(err):
        nonlocal _err
        _err = err

    def g():
        return _err

    return s, g


def get_padding_name(src):
    b, e = os.path.splitext(src)
    return f'{b}__RESIZE__{e}'


async def delete_files(src_list, key):
    # out 디렉토리
    for src in src_list:
        try:
            t = src.get('type_')
            t = t.lower() if t else ''
            if t in ('ean', 'upc', 'qr', 'dmx'):
                os.remove(src['resized'])
                logging.info(f'해당 파일은 삭제 제외=|{os.path.basename(src["name"])}|')
                continue
            else:
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
    try:
        # 최종 결과물을 담을 캔버스 생성
        width, height = size
        if not os.path.exists(dir_name := os.path.dirname(o_file)):
            os.makedirs(dir_name)
        c = canvas.Canvas(o_file, pagesize=(width * mm, height * mm))
        c.showPage()
        c.save()
        logging.info(f'최종 결과물 바탕 생성=|{o_file}|')

        # 구성 요소 이미지들을 병합
        fd_list = []
        result = PdfFileReader(o_file, 'rb').getPage(0)
        for src in sorted(src_list, key=lambda x: x['priority']):
            fd_list.append(fd := open(src['resized'], 'rb'))
            reader = PdfFileReader(fd)
            page = reader.getPage(0)
            result.mergePage(page)
            logging.info(f'최종 결과물에 구성 요소 병합=|{src["resized"]}|')

        out = PdfFileWriter()
        out.addPage(result)
        with FileIO(o_file, 'wb') as f:
            out.write(f)
            logging.info(f'최종 결과물 생성 완료=|{o_file}|')

        for fd in fd_list:
            fd.close()
        return True

    except FileNotFoundError as e:
        logging.error(f'원본 파일 없음=|{e}|')
    except PermissionError as e:
        logging.error(f'파일 접근 권한 부족=|{e}|')
    except IOError as e:
        logging.error(f'입출력 오류 발생=|{e}|')
    except Exception as e:
        logging.error(f'예외 발생=|{e}|')
    return False


async def resize_data(src_list, size):
    width, height = size

    def resize_proc(src):
        name = src['target']
        with open(name, 'rb') as f:
            if reader := PdfFileReader(f):
                page = reader.getPage(0)

                # 이미지가 담길 영역의 좌표(좌측 상단 기준)
                box_x, box_y = src['coordi']
                # 영역의 크기
                box_width, box_height = src['size']
                # 실제 현재 이미지의 크기
                is_width, is_height = page.mediaBox.upperRight
                is_width = float(is_width) / mm
                is_height = float(is_height) / mm
                # 스케일 적용
                rate = src['rate'] if src['rate'] else 100.0
                scale = round(rate / 100.0, 2)
                img_width = round(is_width * scale, 2)
                img_height = round(is_height * scale, 2)

                # 텍스트의 반시계방향 90 회전 경우
                if (src['rotate'] if src['rotate'] else 0) == 90:
                    box_y += (box_width - box_height)
                    src['position'] = 'lt'

                # 이미지가 위치할 좌표
                align = src['position'].lower() if src['position'] else 'cm'
                if align == 'lt':
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
                o_file = get_padding_name(name)
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
                    '-f', name
                ]

            if r := exec_command(command):
                logging.error(f'사이즈변환 gs 명령 실패=|{r}|')
                return False

            return True

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(resize_proc, src) for src in src_list]
        try:
            for future in as_completed(futures):
                if not future.result():
                    logging.error(f'사이즈 변환 실패')
                    return False
            return True

        except FileNotFoundError as e:
            logging.error(f'원본 파일 없음=|{e}|')
        except PermissionError as e:
            logging.error(f'파일 접근 권한 부족=|{e}|')
        except IOError as e:
            logging.error(f'입출력 오류 발생=|{e}|')
        except Exception as e:
            logging.error(f'예외 발생=|{e}|')
        return False


async def check_src_list(src_list, lmt_sec=5):
    wait_sec = 0.0
    for src in src_list:
        while not os.path.exists(src['target']):
            wait_sec += 0.1
            if wait_sec > lmt_sec:
                logging.error(f'필요한 구성 파일이 존재하지 않음=|{src["target"]}|')
                return False
            await aio.sleep(0.1)

    logging.info(f'모든 구성요소 파일이 준비되었음')
    return True


async def task_proc(task):
    logging.info(f'컨버터로부터 데이터 수신=|{pprint.pformat(task)}|')

    # 출력 정보
    out_data = task.get('output')
    size = out_data['size']
    name = out_data['name']
    mandt = out_data['mandt']
    ebeln = out_data['ebeln']
    vbeln = out_data['vbeln']
    posnr = out_data['posnr']
    matnr = out_data['matnr']

    # 입력 정보
    in_data = task.get('input')
    src_list = in_data['src']
    key = in_data['key']

    try:
        if await check_src_list(src_list) and \
                await resize_data(src_list, size) and \
                await merge_data(src_list, name, size):
            update(get_upd_yes_lpas_header(mandt, ebeln, vbeln, posnr, matnr))
            # await delete_files(src_list, key)
            return True
        else:
            _, get_error = ready_error()
            update(get_upd_err_lpas_header(mandt, ebeln, vbeln, posnr, matnr, get_error()))
            # await delete_files(src_list, key)
            return False

    except Exception as e:
        logging.error(f'예외 발생=|{e}|')
        return False


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


async def main_proc(rq):
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


async def merger_proc(rq):
    logging.info(f'머저 모듈 시작')
    loop = get_loop()
    ok = ready_cont()[2]
    while ok():
        try:
            t1 = loop.create_task(main_proc(rq))
            t2 = loop.create_task(initialize_log())
            ret = await aio.gather(t1, t2)
            logging.info(f'머저 모듈 종료, 재시작=|{ret}|')

        except Exception as e:
            logging.error(f'실시간 처리 예외 발생=|{e}|')
            await aio.sleep(1)

    logging.info(f'머저 모듈 종료')
    return 'ok'


async def test_main():
    def get_data():
        def replace_values_in_dict(obj, fr, to):
            if isinstance(obj, dict):
                # 객체가 딕셔너리인 경우
                for k, v in obj.items():
                    obj[k] = replace_values_in_dict(v, fr, to)
            elif isinstance(obj, list):
                # 객체가 리스트인 경우
                obj = [replace_values_in_dict(item, fr, to) for item in obj]
            elif isinstance(obj, str):
                # 객체가 문자열인 경우
                obj = obj.replace(fr, to)
            return obj

        data = {
            'input': {
                'count': 20,
                'key': 'bbaf',
                'src': [
                    {'align': None,
                     'coordi': (0.0, 0.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/Template/HK/GLB_G3.pdf',
                     'position': 'CE',
                     'priority': 1,
                     'rate': 100,
                     'rotate': 0,
                     'size': (240.0, 80.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_267_GLB_G3.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (38.37, 30.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/productName/HK_K127B_productName.eps',
                     'position': 'CE',
                     'priority': 12,
                     'rate': 130,
                     'rotate': 0,
                     'size': (144.0, 27.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_268_HK_K127B_productName.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.0, 21.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/image1/HK_K127B_image1.eps',
                     'position': 'CM',
                     'priority': 2,
                     'rate': 83,
                     'rotate': 0,
                     'size': (75.0, 40.5),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_268_HK_K127B_image1.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.0, 3.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/image2/HK_K127B_image2.eps',
                     'position': 'RB',
                     'priority': 2,
                     'rate': 69,
                     'rotate': 0,
                     'size': (54.3, 18.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_270_HK_K127B_image2.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (87.0, 3.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_hori.eps',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 100,
                     'rotate': 0,
                     'size': (95.0, 18.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_271_HANKOOK_logo_hori.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (11.0, 3.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/logo/HANKOOK_logo_verti.eps',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 100,
                     'rotate': 0,
                     'size': (17.0, 74.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_271_HANKOOK_logo_verti.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (0.1, 0.1),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_1.eps',
                     'position': 'CM',
                     'priority': 3,
                     'rate': 100,
                     'rotate': 0,
                     'size': (35.0, 21.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_271_GLB_G3_SPACE_1.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (0.0, 0.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/GLB_G3_SPACE_2.eps',
                     'position': 'CM',
                     'priority': 3,
                     'rate': 100,
                     'rotate': 0,
                     'size': (89.3, 3.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_272_GLB_G3_SPACE_2.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.1, 61.5),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_hori.eps',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 100,
                     'rotate': 0,
                     'size': (147.0, 0.2),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_272_LINE_hori.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (35.1, 21.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/assist/LINE_verti.eps',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 100,
                     'rotate': 0,
                     'size': (0.2, 56.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_272_LINE_verti.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (183.3, 3.0),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/picto/HK_K127B_picto.eps',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 102,
                     'rotate': 0,
                     'size': (32.42, 40.94),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_273_HK_K127B_picto.pdf',
                     'text': None,
                     'type_': 'IMAGE',
                     'valign': None},
                    {'align': None,
                     'coordi': (178.8, 61.5),
                     'font': None,
                     'font_color': (None, None, None),
                     'font_size': None,
                     'name': '/lpas/Engine/data/src_files/images/HK/barcode/barcode1/8808563461533.pdf',
                     'position': 'CM',
                     'priority': 12,
                     'rate': 100,
                     'rotate': 0,
                     'size': (40.0, 15.5),
                     'target': '/lpas/Engine/data/src_files/images/HK/barcode/barcode1/8808563461533.pdf',
                     'text': '8808563461533',
                     'type_': 'EAN',
                     'valign': None},
                    {'align': 'center',
                     'coordi': (37.0, 65.2),
                     'font': 'Helvetica-Bold',
                     'font_color': (0, 0, 0),
                     'font_size': 39.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 0,
                     'size': (140.0, 14.0),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_273_494a7412.pdf',
                     'text': '235/65R18 91Y XL',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (29.5, 4.0),
                     'font': 'Helvetica',
                     'font_color': (0, 0, 0),
                     'font_size': 16.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 90,
                     'size': (44.6, 5.85),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_274_1d1aa3db.pdf',
                     'text': '235/65R18 91Y XL',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (39.0, 22.0),
                     'font': 'HankookTTFSemiboldOblique',
                     'font_color': (0, 0, 0),
                     'font_size': 9.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 0,
                     'size': (140.0, 8.5),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_274_3c38a279.pdf',
                     'text': 'Pleasure cross point between performance and '
                             'emotion',
                     'type_': 'TEXT',
                     'valign': 'middle'},
                    {'align': 'left',
                     'coordi': (29.3, 55.7),
                     'font': 'Helvetica-Bold',
                     'font_color': (0, 0, 0),
                     'font_size': 16.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 90,
                     'size': (21.0, 6.2),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_281_ced12844.pdf',
                     'text': 'K127B',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (182.0, 48.4),
                     'font': 'Helvetica-heavy',
                     'font_color': (0, 0, 0),
                     'font_size': 20.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 0,
                     'size': (34.6, 8.3),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_281_1ae5d5e6.pdf',
                     'text': '1234567',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'right',
                     'coordi': (3.6, 3.6),
                     'font': 'Helvetica-heavy',
                     'font_color': (0, 0, 0),
                     'font_size': 24.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 90,
                     'size': (44.0, 9.5),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_281_ad3523c5.pdf',
                     'text': '1234567',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'center',
                     'coordi': (185.3, 57.3),
                     'font': 'Helvetica',
                     'font_color': (0, 0, 0),
                     'font_size': 7.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 0,
                     'size': (27.7, 2.8),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_282_75955206.pdf',
                     'text': 'NOT FOR SALE IN JAPAN',
                     'type_': 'TEXT',
                     'valign': 'top'},
                    {'align': 'left',
                     'coordi': (3.5, 56.5),
                     'font': 'Helvetica',
                     'font_color': (0, 0, 0),
                     'font_size': 5.0,
                     'name': None,
                     'position': None,
                     'priority': 99,
                     'rate': None,
                     'rotate': 90,
                     'size': (20.3, 1.85),
                     'target': '/LPAS/lpas/data/out_files/bbaf_20240205_131537_282_5e98aaec.pdf',
                     'text': 'J-0001044483-230915',
                     'type_': 'TEXT',
                     'valign': 'top'}
                ]
            },
            'output': {
                'ebeln': '9999036431',
                'mandt': '110',
                'matnr': '1024881',
                'name': '/LPAS/lpas/data/done_files/PDF/20230901/110_9999036431_9999036431_000010_1024881.pdf',
                'posnr': '000010',
                'size': (240, 80),
                'vbeln': '9999036431'
            }
        }

        # 로컬에서 테스트 하기 위해..
        local_path = "/Users/june1/02.work/18/02/05.img_merger"
        data = replace_values_in_dict(data, "/LPAS/lpas", local_path)
        data = replace_values_in_dict(data, "/lpas/Engine", local_path)
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
