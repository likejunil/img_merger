import io
import logging
import os
from uuid import uuid4

from PyPDF2 import PdfFileReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from conf.conf import config as conf
from src.comm.log import console_log


def get_output():
    name = f'{uuid4()}.pdf'
    ret = os.path.join(conf.sender_path, name)
    logging.info(f'출력파일 =|{ret}|')
    return ret


def sender_proc(pdf_file_list):
    # 각 PDF 파일의 위치
    positions = [(0, 0), (0, 2000), (0, 4000)]
    pdf_files = pdf_file_list

    # 새로운 PDF 파일을 위한 캔버스 생성
    c = canvas.Canvas(get_output(), pagesize=letter)

    # 각 PDF 파일을 불러와서 지정한 위치에 추가
    for pdf_file, position in zip(pdf_files, positions):
        # PDF 파일 읽기
        reader = PdfFileReader(pdf_file)

        # 첫 번째 페이지 가져오기
        page = reader.getPage(0)

        # 페이지를 이미지로 변환
        packet = io.BytesIO()
        packet_img = canvas.Canvas(packet, pagesize=letter)
        packet_img.drawImage(pdf_file, position[0], position[1])
        packet_img.showPage()
        packet_img.save()

        # BytesIO 오브젝트를 다시 읽어서 새 페이지를 만듭니다
        packet.seek(0)
        new_pdf = PdfFileReader(packet)
        page.mergePage(new_pdf.getPage(0))

        # 새 페이지를 최종 PDF 파일에 추가
        c.showPage()
        c.save()

    # PDF 파일 닫기
    c.save()


if __name__ == '__main__':
    console_log(logging.INFO)

    filename1 = '/Users/june1/Downloads/기타/cat.jpg'
    filename2 = '/Users/june1/Downloads/기타/dog.jpeg'
    sender_proc((filename1, filename2))
