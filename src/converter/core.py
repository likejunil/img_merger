import logging
import os
from io import FileIO
from uuid import uuid4

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.units import mm

from conf.conf import config as conf
from conf.constant import pdf
from src.comm.util import exec_command


def get_tmp_name(ext):
    tmp_file = os.path.join(f'{conf.tmp_path}', f'{str(uuid4())}{ext}')
    logging.info(f'이미지 생성을 위한 임시파일=|{tmp_file}|')
    return tmp_file


def change_ext(filename, ext=pdf):
    return f'{os.path.splitext(filename)[0]}{ext}'


def get_out_name(filename):
    # 확장자를 ".pdf" 로 바꾸고
    filename = change_ext(filename, pdf)
    # 파일 이름만을 추출하고
    base = os.path.basename(filename)
    # 이름과 확장자를 분리한 후
    name, ext = os.path.splitext(base)
    # 출력 디렉토리로 장소를 바꾸어 저장
    return os.path.join(conf.root_path, conf.out_path, f'{name}{ext}')


def convert_scale(src, size, scale=mm):
    dst = os.path.join(conf.root_path, get_tmp_name(pdf))
    to_width, to_height = size
    to_width, to_height = to_width * scale, to_height * scale
    with open(src, 'rb') as file:
        if reader := PdfFileReader(file):
            for page_num in range(reader.numPages):
                page = reader.getPage(page_num)
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
                # 첫번째 페이지만..
                os.remove(src)
                os.rename(dst, src)
                break


def rotate_pdf(src, angle):
    dst = os.path.join(conf.root_path, get_tmp_name(pdf))
    with open(src, 'rb') as file:
        if reader := PdfFileReader(file):
            if writer := PdfFileWriter():
                for page_num in range(reader.numPages):
                    page = reader.getPage(page_num)
                    page.rotateClockwise(-1 * angle)
                    writer.addPage(page)
                    # 첫번째 페이지만..
                    break

                with FileIO(dst, 'wb') as output:
                    writer.write(output)
                os.remove(src)
                os.rename(dst, src)


def to_pdf(src, dst):
    command = [
        'inkscape',
        src,
        f'--export-pdf={dst}',
    ]
    return exec_command(command)


def png2svg(src, dst):
    command = [
        'inkscape',
        src,
        '--export-type=svg',
        f'--export-filename={dst}'
    ]
    return exec_command(command)


def fit_image_to_pdf(src, dst):
    command = [
        'gs',
        '-dNOPAUSE',
        '-dEPSCrop',
        '-sDEVICE=pdfwrite',
        '-o', dst,
        '-f', src
    ]
    return exec_command(command)


def fit_image_to_eps(src, dst):
    # -dNOPAUSE: Ghostscript가 각 페이지를 처리한 후 사용자의 입력을 기다리지 않음
    # -dBATCH; 모든 파일을 처리한 후 Ghostscript가 자동으로 종료
    # -dEPSCrop: EPS 파일의 내용 중 실제로 중요한 부분만을 추출 (불필요한 여백 삭제)
    # -sDEVICE=eps2write: EPS 파일로 변환
    command = [
        'gs',
        '-dNOPAUSE',
        '-dEPSCrop',
        '-sDEVICE=eps2write',
        '-o', dst,
        '-f', src
    ]
    return exec_command(command)


def test():
    filename = '/apple/fruite/123.txt'
    ret = get_out_name(filename)
    print(ret)


if __name__ == '__main__':
    test()
