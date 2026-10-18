"""The desktop preview's small, shared visual palette."""

BACKGROUND = "#F3F5F7"
INK = "#182735"
TEAL = "#0F766E"
RED = "#D85B59"
BLUE = "#427BB4"

STYLESHEET = """
QMainWindow, QWidget#root { background: #F3F5F7; }
QWidget { color: #182735; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QLabel { background: transparent; }
QFrame#card { background: white; border: 1px solid #E1E6E9; border-radius: 16px; }
QLabel#brandMark { background: #182735; color: #FFF; border-radius: 12px;
    font-family: "Segoe UI"; font-size: 25px; font-weight: 700; }
QLabel#brand { font-family: "Segoe UI"; font-size: 25px; font-weight: 700; }
QLabel#brandChinese { font-size: 13px; color: #657582; }
QLabel#eyebrow { font-family: "Segoe UI"; color: #73838F; font-size: 10px;
    font-weight: 700; letter-spacing: 1.6px; }
QLabel#sectionTitle { font-size: 17px; font-weight: 700; }
QLabel#muted { color: #74828D; font-size: 12px; }
QLabel#badge { background: #E3EFEC; color: #0F766E; border-radius: 11px;
    padding: 5px 12px; font-size: 11px; }
QLabel#turn { font-size: 22px; font-weight: 700; }
QLabel#recommendation { font-size: 16px; font-weight: 600; }
QLabel#status { font-size: 11px; color: #687A85; }
QPushButton { background: white; border: 1px solid #DCE3E7; border-radius: 8px;
    padding: 8px 14px; min-height: 18px; font-weight: 500; }
QPushButton:hover { background: #F0F6F5; border-color: #83B9B2; }
QPushButton:pressed { background: #DEEDEA; }
QPushButton:disabled { color: #9AA7B0; background: #F6F8F9; border-color: #E8EDEF; }
QPushButton#primary { background: #0F766E; border-color: #0F766E; color: white; }
QPushButton#primary:hover { background: #106A64; }
QPushButton#primary:disabled { background: #CFDFDD; color: #F7FAFA; border-color: #CFDFDD; }
QPushButton#dice { padding: 0; min-height: 38px; font-size: 18px; font-weight: 700; }
QPushButton#dice:checked { background: #0F766E; border-color: #0F766E; color: white; }
QPushButton#quiet { color: #0F766E; border: 0; background: transparent; padding: 3px 0; }
QPushButton#quiet:disabled { color: #AAB5BB; }
QComboBox { background: #F8FAFB; border: 1px solid #DCE3E7; border-radius: 8px;
    padding: 8px 12px; min-height: 20px; }
QComboBox:disabled { color: #9AA7B0; }
QComboBox::drop-down { border: 0; width: 25px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #DCEEEA; }
QTableWidget { border: 0; background: white; gridline-color: #F0F3F5;
    selection-background-color: #E5F2EE; selection-color: #182735; }
QHeaderView::section { border: 0; border-bottom: 1px solid #E9EEF0;
    background: white; color: #84919A; font-size: 11px; padding: 5px; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #CCD7DC; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { color: #182735; background: #FFFFFF; border: 1px solid #DCE3E7; padding: 6px; }
"""
