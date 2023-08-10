import asyncio as aio
import logging
from time import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from conf.conf import config as conf


class Watcher(FileSystemEventHandler):
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
        if filename.endswith(tuple(conf.infile_ext)):
            logging.info(f'|{filename}| 처리 대상 필터 통과')
            self.filename = filename
            return True

    def on_created(self, event):
        logging.info(f'|{event.src_path}| 파일 감지')
        if event.is_directory:
            return

        if self.filtering(event.src_path):
            st = time()
            logging.info(f'|{self.filename}| 처리 프로세스 시작')
            self._ret.append(self.proc(self.filename))
            et = time()
            print(f'소요시간=|{et - st}|')

    def on_moved(self, event):
        logging.debug(f'|{event.src_path}| 이동 이벤트 발생')

    def on_modified(self, event):
        logging.debug(f'|{event.src_path}| 수정 이벤트 발생')

    def on_deleted(self, event):
        logging.debug(f'|{event.src_path}| 삭제 이벤트 발생')

    def get_ret(self):
        if len(self._ret) > 0:
            return True, self._ret.pop(0)
        return False, None

    async def run_proc(self):
        logging.info(f'모니터 스케줄 시작 =|{self.src_dir}|')
        self.observer.schedule(self, self.src_dir, recursive=True)
        self.observer.start()
        while self._ok:
            await aio.sleep(1)

    def stop_proc(self):
        self._ok = False
        self.observer.stop()
        self.observer.join()
        logging.info(f'모니터 스케줄 종료 =|{self.src_dir}|')

    def __del__(self):
        # self.stop_proc()
        pass
