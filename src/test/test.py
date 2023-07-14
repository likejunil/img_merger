import qrcode


def main():
    # QR 코드에 삽입할 데이터
    data = "https://www.google.com"

    # QR 코드 생성
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)

    # 이미지 파일로 저장
    img = qr.make_image(fill='black', back_color='white')
    img.save('qrcode.png')
    pass


if __name__ == '__main__':
    main()
