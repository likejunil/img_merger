import logging
import os
import time
from threading import Thread

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
        self.filename = None
        self.observer = Observer()
        self._ok = True
        self._ret = []

    def filtering(self, filename):
        if filename.endswith(tuple(conf.recv_ext)):
            logging.info(f'|{filename}| 처리 대상 필터 통과')
            self.filename = filename
            return True

    def on_created(self, event):
        logging.info(f'|{event.src_path}| 파일 감지')
        if event.is_directory:
            return

        if self.filtering(event.src_path):
            logging.info(f'|{self.filename}| 처리 프로세스 시작')
            self._ret.append(self.proc(self.filename))

    def on_moved(self, event):
        logging.debug(f'|{event.src_path}| 이동 이벤트 발생')

    def on_modified(self, event):
        logging.debug(f'|{event.src_path}| 수정 이벤트 발생')

    def on_deleted(self, event):
        logging.debug(f'|{event.src_path}| 삭제 이벤트 발생')

    def get_ret(self):
        _, _, ok = ready_cont()
        while ok():
            if len(self._ret) > 0:
                return self._ret.pop(0)
            time.sleep(0.2)

    def run_proc(self):
        logging.info(f'모니터 스케줄 시작 =|{self.src_dir}|')
        self.observer.schedule(self, self.src_dir, recursive=True)
        self.observer.start()
        while self._ok:
            time.sleep(1)

    def stop_proc(self):
        self._ok = False
        self.observer.stop()
        self.observer.join()
        logging.info(f'모니터 스케줄 종료 =|{self.src_dir}|')

    def __del__(self):
        # self.stop_proc()
        pass


def receiver_proc(proc, path=None):
    root_path = os.path.join(conf.root_path, conf.recv_path)
    if path:
        path = os.path.join(root_path, path)
    logging.info(f'입력 디렉토리 =|{path}|')

    receiver = Receiver(path, proc)
    t1 = Thread(target=receiver.run_proc, args=(), daemon=True)
    t1.start()
    return receiver


if __name__ == '__main__':
    def show(filename):
        import matplotlib.pyplot as plt
        img = Image.open(filename)
        plt.imshow(img)
        plt.show()
        time.sleep(1)
        plt.close()
        return filename


    def info(filename):
        img = Image.open(filename)
        logging.info(f'파일 이름 =|{os.path.basename(filename)}|')
        logging.info(f'형식 =|{img.format}|')
        logging.info(f'높이 =|{img.height}|')
        logging.info(f'너비 =|{img.width}|')
        logging.info(f'크기 =|{img.size}|')
        return filename


    console_log(logging.INFO)
    r1 = receiver_proc(info, '1')
    r2 = receiver_proc(show, '2')

    logging.info(r1.get_ret())
    logging.info(r2.get_ret())
    logging.info(r1.get_ret())

    r1.stop_proc()
    r2.stop_proc()
