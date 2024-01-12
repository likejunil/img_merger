import logging

from src.comm.comm import ready_cont


async def starter_proc(cq, mq):
    logging.info(f'스타터 모듈 시작')
    ok = ready_cont()[2]
    csq, crq = cq
    msq, mrq = mq
    while ok():
        try:
            while True:
                csq.put(crq.get(timeout=3))
                msq.put(mrq.get(timeout=3))
        except Exception as e:
            logging.debug(f'메시지 수신 예외 발생=|{e}|')
            pass
    logging.info(f'스타터 모듈 종료')


def test():
    pass


if __name__ == '__main__':
    test()
