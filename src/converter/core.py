import os

from PIL import Image
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from conf.constant import pdf
from src.comm.comm import tm
from src.converter.images import fit_image_to_pdf


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
    # 파일 이름에 시각 정보 추가 (시2분2초2밀리초3)
    return os.path.join(conf.root_path, conf.out_path, f'{name}_{tm()}{ext}')


def conv_pdf(filename):
    o_name = get_out_name(filename)
    os.rename(filename, o_name)
    return o_name


def conv_eps(filename):
    # Ghostscript를 사용하여 EPS 파일을 PDF로 변환
    # Ghostscript("-sDEVICE=pdfwrite", "-dEPSCrop", "-o", o_name, filename)
    o_name = get_out_name(filename)
    fit_image_to_pdf(filename, o_name)
    return o_name


def conv_png(filename):
    img = Image.open(filename)
    o_name = get_out_name(filename)
    # 이미지의 품질을 유지하기 위해 canvas 사용
    out = canvas.Canvas(o_name, pagesize=(img.width, img.height))
    out.drawImage(filename, 0, 0, img.width, img.height)
    out.save()
    return o_name


def conv_jpg(filename):
    # jpg 포맷은 이미 비트맵 형식이므로 벡터 형식으로 변환할 수 없다.
    # Image 패키지를 사용하여 pdf 로 변환한다.
    img = Image.open(filename)
    o_name = get_out_name(filename)
    img.save(o_name)
    return o_name


def test():
    filename = '/apple/fruite/123.txt'
    ret = get_out_name(filename)
    print(ret)


if __name__ == '__main__':
    test()
