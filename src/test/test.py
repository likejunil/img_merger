import json
import os

from conf.conf import config as conf


def main():
    """
    filename = 'jabinfo.text'
    data = {
        'font': 'Helvetica',
        'size': '6',
        'bold': False,
        'italic': False,
        'align': 'left',
        'rotate': 90,
        'letter-space': 0,
        'content': 'D-0000100664-221006',
        'coordi_x': 214.607,
        'coordi_y': 64.94,
        'width': 2.269,
        'height': 24,
    }
    """
    filename = 'Size_spec.text'
    data = {
        'font': 'Helvetica',
        'size': '48',
        'bold': True,
        'italic': False,
        'align': 'center',
        'rotate': 0,
        'letter-space': 0,
        'content': '205/50R17 93W XL',
        'coordi_x': 111.685,
        'coordi_y': 63.678,
        'width': 178,
        'height': 18.203,
    }
    """
    filename = 'M_code.text'
    data = {
        'font': 'Helvetica',
        'size': '21.1',
        'bold': True,
        'italic': False,
        'align': 'center',
        'rotate': 0,
        'letter-space': 0,
        'content': '1014070',
        'coordi_x': 182.683,
        'coordi_y': 32.488,
        'width': 32,
        'height': 8,
    }
    """
    in_path = os.path.join(conf.root_path, conf.in_path)
    output = os.path.join(in_path, filename)
    with open(output, mode='wt', encoding='utf8') as f:
        json.dump(data, f)


def test():
    filename = 'abcd_880856333945.bar'
    data = {
        'width': 42.596,
        'height': 21.641,
    }
    data_path = os.path.join(conf.root_path, conf.data_path, 'src_files')
    output = os.path.join(data_path, filename)
    with open(output, mode='wt', encoding='utf8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def test_1():
    path = "/System/Library/Fonts/Helvetica.ttc"

    pass


if __name__ == '__main__':
    # main()
    test_1()
