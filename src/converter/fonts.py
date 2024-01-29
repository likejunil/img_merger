import os

from conf.conf import config as conf


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def get_path(ttf):
        return os.path.join(conf.font_path, ttf)

    pdfmetrics.registerFont(TTFont('Helvetica-Light', get_path('Helvetica-Light.ttf')))
    pdfmetrics.registerFont(TTFont('Helvetica-heavy', get_path('Helvetica-heavy.ttf')))
    pdfmetrics.registerFont(TTFont('HankookTTFRegular', get_path('HankookTTFRegular.ttf')))
    pdfmetrics.registerFont(TTFont('HankookTTFBold', get_path('HankookTTFBold.ttf')))
    pdfmetrics.registerFont(TTFont('HankookTTFLight', get_path('HankookTTFLight.ttf')))
    pdfmetrics.registerFont(TTFont('HankookTTFMediumOblique', get_path('HankookTTFMediumOblique.ttf')))
    pdfmetrics.registerFont(TTFont('HankookTTFSemiboldOblique', get_path('HankookTTFSemiboldOblique.ttf')))


def register_fonts():
    _register_fonts()
