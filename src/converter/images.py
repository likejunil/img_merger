from src.comm.util import exec_command


def to_pdf(src, dst):
    command = [
        'inkscape',
        src,
        f'--export-filename={dst}',
    ]
    exec_command(command)


def png2svg(src, dst):
    command = [
        'inkscape',
        src,
        '--export-type=svg',
        f'--export-filename={dst}'
    ]
    exec_command(command)


def fit_image_to_pdf(src, dst):
    command = [
        'gs',
        '-dNOPAUSE',
        '-dEPSCrop',
        '-sDEVICE=pdfwrite',
        '-o', dst,
        '-f', src
    ]
    exec_command(command)


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
    exec_command(command)
