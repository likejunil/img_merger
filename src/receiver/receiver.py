import logging
import os
import time

from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from conf.conf import config as conf
from src.comm.comm import ready_cont
from src.comm.log import console_log


class Receiver(FileSystemEventHandler):
    """
    특정 디렉토리를 관찰하다가 image 파일이 생성되면 해당 image 를 열어서 반환
    - 어떤 종류의 이미지를 대상으로 할 것인지 필터링 필요
    """

    def __init__(self, src_dir, proc):
        super().__init__()
        logging.info(f'|{src_dir}| 입력 디렉토리 모니터링 인스턴스 생성')
        self.src_dir = src_dir
        self.proc = proc
        self.target = None

    def filtering(self, target):
        if target.endswith(tuple(conf.recv_ext)):
            logging.info(f'|{target}| 처리 대상 필터 통과')
            self.target = target
            return True

    def on_created(self, event):
        logging.info(f'|{event.src_path}| 파일 감지')
        if event.is_directory:
            return

        if self.filtering(event.src_path):
            img = Image.open(self.target)
            logging.info(f'|{self.target}| 처리 프로세스 시작')
            self.proc(img)

    def on_moved(self, event):
        logging.info(f'|{event.src_path}| 이동 이벤트 발생')

    def on_modified(self, event):
        logging.info(f'|{event.src_path}| 수정 이벤트 발생')

    def on_deleted(self, event):
        logging.info(f'|{event.src_path}| 삭제 이벤트 발생')


def receiver_proc(proc):
    path = os.path.join(conf.root_path, conf.recv_path)
    logging.info(f'입력 디렉토리 =|{path}|')

    handler = Receiver(path, proc)
    observer = Observer()
    logging.info(f'모니터 스케줄 시작 =|{path}|')
    observer.schedule(handler, path, recursive=True)
    observer.start()

    _, _, ok = ready_cont()
    while ok():
        time.sleep(1)

    observer.stop()
    observer.join()
    logging.info(f'모니터 스케줄 종료 =|{path}|')


if __name__ == '__main__':
    def task(img):
        import matplotlib.pyplot as plt
        plt.imshow(img)
        plt.show()
        time.sleep(1)
        plt.close()


    console_log()
    receiver_proc(task)
