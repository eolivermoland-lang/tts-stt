from __future__ import annotations

import html
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from api_client import ApiClient
import nest_player
from audio_engine import (
    PlaybackThread,
    Recorder,
    default_input_index,
    default_output_index,
    list_input_devices,
    list_output_devices,
    wav_bytes,
)
from settings_store import (
    DEFAULT_API_URL,
    DEFAULTS,
    load_settings,
    load_token,
    save_env,
    save_settings,
)
from workers import (
    ApiInfoWorker,
    PreviewWorker,
    ReloadVoicesWorker,
    TurnWorker,
)

PERSONALITY_PRESETS = {
    "Nysgjerrig valp": (
        "Du er Bingo, en nysgjerrig og vennlig robothund. "
        "Svar kort, morsomt og på norsk. Maks én kort setning, cirka 12 ord. "
        "Ikke bruk emoji."
    ),
    "Rolig hjelper": (
        "Du er Bingo, en rolig og hjelpsom robothund. "
        "Svar vennlig, tydelig og på norsk. Maks én kort setning, cirka 12 ord. "
        "Ikke bruk emoji."
    ),
    "Morsom og rampete": (
        "Du er Bingo, en morsom og litt rampete robothund. "
        "Svar kort, lekent og på norsk med en liten overraskelse. "
        "Maks én kort setning, cirka 12 ord. Ikke bruk emoji."
    ),
    "Kort og presis": (
        "Du er Bingo, en effektiv robothund. "
        "Svar på norsk med maks én kort setning, under 10 ord. "
        "Vær direkte og ikke bruk emoji."
    ),
    "Egendefinert": None,
}

VOICE_PRESETS = {
    "Nøytral": (0.50, 0.50, 0.80, 1.20, 1.00),
    "Rolig": (0.30, 0.60, 0.65, 1.25, 0.95),
    "Glad": (0.65, 0.40, 0.90, 1.15, 1.00),
    "Oppspilt": (0.85, 0.30, 1.05, 1.10, 1.00),
    "Dramatisk": (0.95, 0.70, 1.00, 1.10, 1.00),
    "Egendefinert": None,
}

MODELS = [
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
]

LANGUAGES = ["no", "en", "sv", "da", "de", "fr", "es", "it", "pt", "nl"]

APP_STYLE = """
QWidget {
    background: #111418;
    color: #e7edf4;
    font-size: 13px;
}
QMainWindow, QScrollArea, QWidget#transparent {
    background: #111418;
}
QLabel#appTitle {
    font-size: 26px;
    font-weight: 700;
    color: #f4f8fc;
}
QLabel#subtitle {
    color: #8b9aab;
    font-size: 12px;
}
QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #dbe6f2;
}
QLabel#muted, QLabel#note {
    color: #8b9aab;
    font-size: 11px;
}
QLabel#valueLabel {
    color: #b9c8d8;
    font-family: Menlo, monospace;
    font-size: 11px;
}
QLabel#statusLabel {
    color: #8b9aab;
    font-size: 12px;
}
QFrame#card {
    background: #181d23;
    border: 1px solid #29313a;
    border-radius: 12px;
}
QGroupBox {
    background: #181d23;
    border: 1px solid #29313a;
    border-radius: 10px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    color: #dbe6f2;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 4px;
    background: #181d23;
}
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox {
    background: #10151a;
    border: 1px solid #2d3843;
    border-radius: 7px;
    padding: 7px 9px;
    selection-background-color: #2b5d91;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus {
    border: 1px solid #4f9cf9;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #151b21;
    border: 1px solid #34414e;
    selection-background-color: #24415e;
    outline: none;
}
QPushButton {
    background: #222a33;
    border: 1px solid #35414c;
    border-radius: 8px;
    padding: 8px 13px;
    color: #dbe6f2;
    font-weight: 500;
}
QPushButton:hover {
    background: #2b3642;
    border-color: #4a5a69;
}
QPushButton:pressed {
    background: #1b2229;
}
QPushButton:disabled {
    color: #5d6b79;
    background: #191e24;
    border-color: #252d35;
}
QPushButton#primaryButton {
    background: #2f6fae;
    border-color: #3d85cb;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: #3b83c8;
}
QPushButton#recordButton {
    background: #2a2427;
    border-color: #5a3a42;
    color: #ffb3bd;
    font-weight: 600;
}
QPushButton#recordButton:hover {
    background: #352b2f;
}
QPushButton#recordButton[recording="true"] {
    background: #8f2d3c;
    border-color: #d65368;
    color: #ffffff;
}
QPushButton#dangerButton {
    color: #ff9aa6;
    border-color: #5a333a;
}
QPushButton#ghostButton {
    background: transparent;
    border-color: transparent;
    color: #8b9aab;
    padding: 5px 8px;
}
QPushButton#ghostButton:hover {
    background: #1f262e;
    color: #dbe6f2;
}
QTabWidget::pane {
    border: 1px solid #29313a;
    border-radius: 10px;
    background: #151a20;
    top: -1px;
}
QTabBar::tab {
    background: #151a20;
    color: #8b9aab;
    padding: 9px 13px;
    margin-right: 2px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    color: #eaf2fb;
    background: #1d242c;
    border-color: #29313a;
}
QTabBar::tab:hover {
    color: #dbe6f2;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #2a333d;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #4f9cf9;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #d7e9ff;
    border: 2px solid #4f9cf9;
    width: 15px;
    height: 15px;
    margin: -6px 0;
    border-radius: 8px;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #42515f;
    background: #10151a;
}
QCheckBox::indicator:checked {
    background: #4f9cf9;
    border-color: #4f9cf9;
}
QProgressBar {
    background: #222a33;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background: #4f9cf9;
    border-radius: 4px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #35414c;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #495866;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QToolTip {
    background: #1d242c;
    color: #e7edf4;
    border: 1px solid #42515f;
    padding: 5px;
}
QSplitter::handle {
    background: transparent;
    width: 8px;
}
"""


class ChatInput(QPlainTextEdit):
    send_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(
            "Skriv til Bingo …  (Enter sender, Shift+Enter gir ny linje)"
        )
        self.setMinimumHeight(54)
        self.setMaximumHeight(92)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class BingoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.token = load_token()
        self.client: ApiClient | None = None
        self._loading = True
        self._dirty = False

        self.history: list[dict[str, str]] = []
        self.transcript_lines: list[str] = []
        self.last_audio: bytes | None = None
        self.pending_user: str | None = None
        self.pending_reply: str | None = None
        self.stt_seconds: float | None = None
        self.chat_seconds: float | None = None
        self.tts_seconds: float | None = None

        self.turn_worker: TurnWorker | None = None
        self.info_worker: ApiInfoWorker | None = None
        self.preview_worker: PreviewWorker | None = None
        self.reload_worker: ReloadVoicesWorker | None = None
        self.player: PlaybackThread | None = None

        self.voice_dir = Path.home() / "voice-server" / "voices"
        self._voice_meta: dict[str, dict] = {}
        self._voice_select_pending: str | None = None
        self._test_mic_active = False
        self._slider_specs: dict[tuple[str, str], dict] = {}

        self.recorder = Recorder()
        self.recorder.signals.level.connect(self._on_recorder_level)
        self.recorder.signals.finished.connect(self._on_recorder_finished)
        self.recorder.signals.error.connect(self._on_recorder_error)

        self.setWindowTitle("Bingo Studio")
        self.resize(1240, 830)
        self.setMinimumSize(1000, 680)

        self._build_ui()
        self._load_ui_from_settings()
        self._loading = False
        self._populate_voices(
            {
                "voices": [
                    {
                        "name": self.settings["voice"]["profile"],
                        "label": self.settings["voice"]["profile"],
                        "duration": 0,
                        "sample_rate": 0,
                    }
                ],
                "default_voice": self.settings["voice"]["profile"],
                "voice_dir": str(self.voice_dir),
            }
        )
        self._update_client()
        self._append_system(
            "Klar. Trykk «Snakk» for å snakke, eller skriv en melding. "
            "Alt går via API-et og TTS-serveren på Mac-en."
        )
        self._log("Bingo Studio startet.")
        self._set_status("Klar")
        self._set_chip(self.api_chip, "API", None, "Sjekker …")
        self._set_chip(self.tts_chip, "TTS", None, "Sjekker …")
        self._set_chip(self.mic_chip, "Mic", None, "Sjekker …")
        self._refresh_devices()

        self.record_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.record_shortcut.activated.connect(self.toggle_record)
        self.escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.escape_shortcut.activated.connect(self._escape)

        self.refresh_api_info(show_errors=False, delay_ms=350)
        if self.nest_checkbox.isChecked():
            nest_player.forbered_i_bakgrunnen()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("transparent")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Bingo Studio")
        title.setObjectName("appTitle")
        subtitle = QLabel(
            "Robothund med din stemme · STT → LLM → TTS"
        )
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.api_chip = QLabel("API")
        self.tts_chip = QLabel("TTS")
        self.mic_chip = QLabel("Mic")
        for chip in (self.api_chip, self.tts_chip, self.mic_chip):
            chip.setObjectName("chip")
            chip.setMinimumWidth(62)
            header.addWidget(chip)

        self.save_button = QPushButton("Lagre")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_all)
        header.addWidget(self.save_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setObjectName("transparent")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        chat_card = QFrame()
        chat_card.setObjectName("card")
        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(14, 12, 14, 12)
        chat_layout.setSpacing(8)

        chat_header = QHBoxLayout()
        chat_title = QLabel("Samtale")
        chat_title.setObjectName("sectionTitle")
        chat_header.addWidget(chat_title)
        chat_header.addStretch(1)
        self.export_button = QPushButton("Eksporter")
        self.export_button.setObjectName("ghostButton")
        self.export_button.clicked.connect(self.export_transcript)
        self.reset_button = QPushButton("Ny samtale")
        self.reset_button.setObjectName("ghostButton")
        self.reset_button.clicked.connect(self.reset_conversation)
        chat_header.addWidget(self.export_button)
        chat_header.addWidget(self.reset_button)
        chat_layout.addLayout(chat_header)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chatView")
        self.chat.setOpenExternalLinks(False)
        self.chat.setMinimumHeight(300)
        self.chat.document().setDefaultStyleSheet(
            "body { color: #e7edf4; }"
        )
        chat_layout.addWidget(self.chat, 1)
        left_layout.addWidget(chat_card, 1)

        composer = QFrame()
        composer.setObjectName("card")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(14, 11, 14, 11)
        composer_layout.setSpacing(8)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Klar")
        self.status_label.setObjectName("statusLabel")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        self.level_meter = QProgressBar()
        self.level_meter.setRange(0, 100)
        self.level_meter.setValue(0)
        self.level_meter.setTextVisible(False)
        self.level_meter.setFixedHeight(8)
        self.level_meter.setFixedWidth(140)
        status_row.addWidget(self.level_meter)
        composer_layout.addLayout(status_row)

        self.input = ChatInput()
        self.input.send_requested.connect(self.send_text)
        self.input.setObjectName("chatInput")
        composer_layout.addWidget(self.input)

        button_row = QHBoxLayout()
        self.record_button = QPushButton("Snakk")
        self.record_button.setObjectName("recordButton")
        self.record_button.setMinimumWidth(112)
        self.record_button.clicked.connect(self.toggle_record)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primaryButton")
        self.send_button.setMinimumWidth(86)
        self.send_button.clicked.connect(self.send_text)
        self.stop_button = QPushButton("Stopp lyd")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_playback)
        self.replay_button = QPushButton("Spill av igjen")
        self.replay_button.setEnabled(False)
        self.replay_button.clicked.connect(self.replay_last)
        button_row.addWidget(self.record_button)
        button_row.addWidget(self.send_button)
        button_row.addSpacing(6)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.replay_button)
        button_row.addStretch(1)
        hint = QLabel("Ctrl+R = snakk · Esc = stopp")
        hint.setObjectName("note")
        button_row.addWidget(hint)
        composer_layout.addLayout(button_row)
        left_layout.addWidget(composer)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.setMinimumWidth(420)
        self.tabs.setMaximumWidth(520)

        self.tabs.addTab(self._scroll(self._build_bot_tab()), "Bingo")
        self.tabs.addTab(self._scroll(self._build_voice_tab()), "Stemme")
        self.tabs.addTab(self._scroll(self._build_audio_tab()), "Lyd")
        self.tabs.addTab(self._scroll(self._build_api_tab()), "API")
        self.tabs.addTab(self._scroll(self._build_log_tab()), "Logg")

        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([750, 450])
        root.addWidget(splitter, 1)

    def _scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _new_tab(self) -> tuple[QWidget, QVBoxLayout]:
        content = QWidget()
        content.setObjectName("transparent")
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        return content, layout

    def _build_bot_tab(self) -> QWidget:
        content, layout = self._new_tab()

        identity = QGroupBox("Identitet")
        form = QFormLayout(identity)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(
            lambda text: self._set_setting("bot", "name", text)
        )
        form.addRow("Navn", self.name_edit)

        self.personality_combo = QComboBox()
        self.personality_combo.addItems(list(PERSONALITY_PRESETS))
        self.personality_combo.currentTextChanged.connect(
            self._on_personality_changed
        )
        form.addRow("Personlighet", self.personality_combo)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setMinimumHeight(150)
        self.prompt_edit.setMinimumWidth(0)
        self.prompt_edit.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.prompt_edit.setPlaceholderText(
            "Beskriv hvordan Bingo skal oppføre seg og snakke …"
        )
        self.prompt_edit.textChanged.connect(self._on_prompt_changed)
        form.addRow("Prompt", self.prompt_edit)
        layout.addWidget(identity)

        model_group = QGroupBox("Modell og svar")
        model_form = QFormLayout(model_group)
        model_form.setLabelAlignment(Qt.AlignRight)
        model_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.model_combo.setMinimumContentsLength(8)
        self.model_combo.addItems(MODELS)
        self.model_combo.currentTextChanged.connect(
            lambda text: self._set_setting("bot", "model", text)
        )
        model_form.addRow("Modell", self.model_combo)

        self._add_slider(
            model_form,
            "Kreativitet",
            "bot",
            "temperature",
            0.0,
            2.0,
            0.05,
            2,
            "",
        )
        self._add_slider(
            model_form,
            "Maks tokens",
            "bot",
            "max_tokens",
            16,
            300,
            1,
            0,
            "",
        )
        self._add_slider(
            model_form,
            "Minne (runder)",
            "bot",
            "history_turns",
            0,
            12,
            1,
            0,
            "",
        )
        layout.addWidget(model_group)

        reset = QPushButton("Nullstill samtalen")
        reset.clicked.connect(self.reset_conversation)
        layout.addWidget(reset)

        note = QLabel(
            "Systemprompten sendes med hver forespørsel. Modellene er "
            "Cloudflare Workers AI; standardmodellen er rask og gratis."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return content

    def _build_voice_tab(self) -> QWidget:
        content, layout = self._new_tab()

        profile = QGroupBox("Stemmeprofil")
        form = QFormLayout(profile)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        self.voice_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.voice_combo.setMinimumContentsLength(8)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        self.refresh_voices_button = QPushButton("Oppdater")
        self.refresh_voices_button.clicked.connect(
            lambda: self.refresh_api_info(show_errors=True)
        )
        voice_row.addWidget(self.voice_combo, 1)
        voice_row.addWidget(self.refresh_voices_button)
        form.addRow("Profil", voice_row)

        voice_actions = QHBoxLayout()
        self.add_voice_button = QPushButton("Legg til …")
        self.add_voice_button.setToolTip("Legg til en WAV-fil som ny stemmeprofil")
        self.add_voice_button.clicked.connect(self.add_voice_file)
        self.open_voice_button = QPushButton("Mappe")
        self.open_voice_button.setToolTip("Åpne stemmemappen i Finder")
        self.open_voice_button.clicked.connect(self.open_voice_folder)
        self.reload_voices_button = QPushButton("Last inn")
        self.reload_voices_button.setToolTip("Les stemmefiler på nytt")
        self.reload_voices_button.clicked.connect(self.reload_voices)
        voice_actions.addWidget(self.add_voice_button)
        voice_actions.addWidget(self.open_voice_button)
        voice_actions.addWidget(self.reload_voices_button)
        form.addRow("", voice_actions)

        self.voice_info_label = QLabel("Ingen stemmeprofil lastet.")
        self.voice_info_label.setObjectName("note")
        self.voice_info_label.setWordWrap(True)
        form.addRow("Info", self.voice_info_label)
        layout.addWidget(profile)

        preview_group = QGroupBox("Hør stemmen")
        preview_form = QFormLayout(preview_group)
        self.preview_text = QLineEdit("Hei! Jeg er Bingo.")
        self.preview_text.setCursorPosition(0)
        preview_form.addRow("Testtekst", self.preview_text)
        self.preview_button = QPushButton("Spill av test")
        self.preview_button.setObjectName("primaryButton")
        self.preview_button.clicked.connect(self.preview_voice)
        preview_form.addRow("", self.preview_button)
        layout.addWidget(preview_group)

        style_group = QGroupBox("Hvordan Bingo snakker")
        style_form = QFormLayout(style_group)
        style_form.setLabelAlignment(Qt.AlignRight)
        style_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.voice_preset_combo = QComboBox()
        self.voice_preset_combo.addItems(list(VOICE_PRESETS))
        self.voice_preset_combo.currentTextChanged.connect(
            self._on_voice_preset_changed
        )
        style_form.addRow("Stil", self.voice_preset_combo)

        self._add_slider(
            style_form, "Exaggeration", "voice", "exaggeration",
            0.0, 1.0, 0.05, 2, "",
        )
        self._add_slider(
            style_form, "CFG-vekt", "voice", "cfg_weight",
            0.0, 1.0, 0.05, 2, "",
        )
        self._add_slider(
            style_form, "Temperatur", "voice", "temperature",
            0.1, 2.0, 0.05, 2, "",
        )
        self._add_slider(
            style_form, "Repetisjon", "voice", "repetition_penalty",
            1.0, 2.0, 0.05, 2, "",
        )
        self._add_slider(
            style_form, "Top-p", "voice", "top_p",
            0.1, 1.0, 0.05, 2, "",
        )

        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        self.language_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.language_combo.setMinimumContentsLength(5)
        self.language_combo.addItems(LANGUAGES)
        self.language_combo.currentTextChanged.connect(
            lambda text: self._set_setting("voice", "lang_code", text)
        )
        style_form.addRow("Språk", self.language_combo)
        layout.addWidget(style_group)

        note = QLabel(
            "Stemmen styres av referanseopptaket og parameterne over. "
            "Legg flere WAV-filer i stemmemappen for å lage egne profiler. "
            "Etter opplasting lastes de inn på nytt uten restart."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return content

    def _build_audio_tab(self) -> QWidget:
        content, layout = self._new_tab()

        devices = QGroupBox("Lydenheter")
        form = QFormLayout(devices)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.input_combo = QComboBox()
        self.input_combo.currentIndexChanged.connect(
            self._on_input_device_changed
        )
        form.addRow("Mikrofon", self.input_combo)

        self.output_combo = QComboBox()
        self.output_combo.currentIndexChanged.connect(
            self._on_output_device_changed
        )
        form.addRow("Høyttaler", self.output_combo)

        self.refresh_devices_button = QPushButton("Oppdater enheter")
        self.refresh_devices_button.clicked.connect(self._refresh_devices)
        form.addRow("", self.refresh_devices_button)
        layout.addWidget(devices)

        nest_group = QGroupBox("Google Nest Mini")
        nest_form = QFormLayout(nest_group)
        nest_form.setLabelAlignment(Qt.AlignRight)
        nest_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.nest_checkbox = QCheckBox("Spill svar på Nest Mini")
        self.nest_checkbox.setChecked(
            bool(nest_player.les_innstillinger().get("paa", False))
        )
        self.nest_checkbox.toggled.connect(self._on_nest_toggled)
        nest_form.addRow("", self.nest_checkbox)
        self.nest_name_edit = QLineEdit(nest_player.hent_navn())
        self.nest_name_edit.textChanged.connect(self._on_nest_name_changed)
        nest_form.addRow("Navn", self.nest_name_edit)
        layout.addWidget(nest_group)

        recording = QGroupBox("Opptak")
        rec_form = QFormLayout(recording)
        rec_form.setLabelAlignment(Qt.AlignRight)
        rec_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Automatisk (VAD)", "vad")
        self.mode_combo.addItem("Trykk for å snakke", "ptt")
        self.mode_combo.currentIndexChanged.connect(
            lambda: self._set_setting(
                "audio", "mode", self.mode_combo.currentData()
            )
        )
        rec_form.addRow("Modus", self.mode_combo)

        self._add_slider(
            rec_form, "Støygrense", "audio", "silence_threshold_db",
            -60, -20, 1, 0, " dB",
        )
        self._add_slider(
            rec_form, "Stillhet før stopp", "audio", "silence_ms",
            300, 2000, 50, 0, " ms",
        )
        self._add_slider(
            rec_form, "Maks opptak", "audio", "max_record_s",
            5, 60, 1, 0, " s",
        )
        self._add_slider(
            rec_form, "Pre-roll", "audio", "pre_roll_ms",
            0, 1000, 50, 0, " ms",
        )

        self.trim_checkbox = QCheckBox("Trim stillhet før STT")
        self.trim_checkbox.toggled.connect(
            lambda checked: self._set_setting(
                "audio", "trim_silence", bool(checked)
            )
        )
        rec_form.addRow("", self.trim_checkbox)

        self.test_mic_button = QPushButton("Test mikrofon (3 sek)")
        self.test_mic_button.clicked.connect(self.test_microphone)
        self.test_mic_status = QLabel("")
        self.test_mic_status.setObjectName("note")
        self.test_mic_status.setWordWrap(True)
        rec_form.addRow("", self.test_mic_button)
        rec_form.addRow("", self.test_mic_status)
        layout.addWidget(recording)

        note = QLabel(
            "VAD stopper automatisk når du har vært stille en stund. "
            "Senk støygrensen hvis den ikke hører deg, eller hev den hvis "
            "den starter på bakgrunnsstøy. PTT lar deg styre opptaket selv."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return content

    def _build_api_tab(self) -> QWidget:
        content, layout = self._new_tab()

        connection = QGroupBox("Tilkobling")
        form = QFormLayout(connection)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText(DEFAULT_API_URL)
        form.addRow("API-URL", self.api_url_edit)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("ROBOT_TOKEN")
        form.addRow("Robot-token", self.token_edit)

        self.show_token = QCheckBox("Vis token")
        self.show_token.toggled.connect(
            lambda checked: self.token_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        form.addRow("", self.show_token)

        self.test_button = QPushButton("Test tilkobling")
        self.test_button.setObjectName("primaryButton")
        self.test_button.clicked.connect(
            lambda: self.refresh_api_info(show_errors=True)
        )
        form.addRow("", self.test_button)

        self.api_status_label = QLabel("Ikke testet ennå.")
        self.api_status_label.setObjectName("note")
        self.api_status_label.setWordWrap(True)
        form.addRow("Status", self.api_status_label)
        layout.addWidget(connection)

        tts_group = QGroupBox("TTS og stemmer")
        tts_form = QFormLayout(tts_group)
        self.tts_info_label = QLabel("Ikke testet ennå.")
        self.tts_info_label.setObjectName("note")
        self.tts_info_label.setWordWrap(True)
        tts_form.addRow("Status", self.tts_info_label)

        tts_buttons = QHBoxLayout()
        self.api_refresh_voices = QPushButton("Oppdater stemmer")
        self.api_refresh_voices.clicked.connect(
            lambda: self.refresh_api_info(show_errors=True)
        )
        self.api_reload_voices = QPushButton("Last inn på nytt")
        self.api_reload_voices.clicked.connect(self.reload_voices)
        tts_buttons.addWidget(self.api_refresh_voices)
        tts_buttons.addWidget(self.api_reload_voices)
        tts_form.addRow("", tts_buttons)
        layout.addWidget(tts_group)

        save = QPushButton("Lagre innstillinger")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.save_all)
        layout.addWidget(save)

        note = QLabel(
            "Tokenet lagres i .env med filrettigheter kun for deg. "
            "API-URL og token må peke på samme Worker som ROBOT_TOKEN i "
            "Cloudflare. TTS krever at start.sh og tunnel.sh kjører på Mac-en."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return content

    def _build_log_tab(self) -> QWidget:
        content, layout = self._new_tab()
        title = QLabel("Hendelser")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2500)
        self.log_view.setMinimumHeight(420)
        layout.addWidget(self.log_view, 1)

        row = QHBoxLayout()
        clear = QPushButton("Tøm logg")
        clear.clicked.connect(self.log_view.clear)
        save = QPushButton("Lagre logg …")
        save.clicked.connect(self.save_log)
        row.addWidget(clear)
        row.addWidget(save)
        row.addStretch(1)
        layout.addLayout(row)
        return content

    def _add_slider(
        self,
        form: QFormLayout,
        label: str,
        section: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
        decimals: int,
        suffix: str,
    ) -> QSlider:
        container = QWidget()
        container.setObjectName("transparent")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, round((maximum - minimum) / step))
        slider.setPageStep(1)
        value_label = QLabel()
        value_label.setObjectName("valueLabel")
        value_label.setMinimumWidth(58)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        row.addWidget(slider, 1)
        row.addWidget(value_label)
        form.addRow(label, container)

        spec = {
            "slider": slider,
            "label": value_label,
            "minimum": minimum,
            "maximum": maximum,
            "step": step,
            "decimals": decimals,
            "suffix": suffix,
            "section": section,
            "key": key,
        }
        self._slider_specs[(section, key)] = spec
        slider.valueChanged.connect(
            lambda _value, s=section, k=key: self._on_slider_changed(s, k)
        )
        return slider

    def _on_slider_changed(self, section: str, key: str) -> None:
        spec = self._slider_specs[(section, key)]
        value = spec["minimum"] + spec["slider"].value() * spec["step"]
        if spec["decimals"] == 0:
            value = int(round(value))
        else:
            value = round(float(value), spec["decimals"])
        self.settings[section][key] = value
        self._update_slider_label(section, key)
        if not self._loading:
            self._dirty = True

    def _update_slider_label(self, section: str, key: str) -> None:
        spec = self._slider_specs[(section, key)]
        value = spec["minimum"] + spec["slider"].value() * spec["step"]
        if spec["decimals"] == 0:
            text = f"{int(round(value))}{spec['suffix']}"
        else:
            text = f"{value:.{spec['decimals']}f}{spec['suffix']}"
        spec["label"].setText(text)

    def _set_slider(self, section: str, key: str, value: float) -> None:
        spec = self._slider_specs[(section, key)]
        index = round((float(value) - spec["minimum"]) / spec["step"])
        with QSignalBlocker(spec["slider"]):
            spec["slider"].setValue(
                max(0, min(spec["slider"].maximum(), index))
            )
        self._update_slider_label(section, key)

    def _load_ui_from_settings(self) -> None:
        self._loading = True
        bot = self.settings["bot"]
        voice = self.settings["voice"]
        audio = self.settings["audio"]

        self.name_edit.setText(str(bot.get("name", "Bingo")))
        self.personality_combo.setCurrentText(
            str(bot.get("personality", "Nysgjerrig valp"))
        )
        self.prompt_edit.setPlainText(str(bot.get("system_prompt", "")))
        self.model_combo.setCurrentText(str(bot.get("model", MODELS[0])))

        for (section, key), _spec in self._slider_specs.items():
            self._set_slider(section, key, self.settings[section][key])

        self.voice_combo.clear()
        profile = str(voice.get("profile", "min_stemme"))
        self.voice_combo.addItem(profile, profile)

        preset_name = "Egendefinert"
        style_keys = (
            "exaggeration",
            "cfg_weight",
            "temperature",
            "repetition_penalty",
            "top_p",
        )
        for candidate, values in VOICE_PRESETS.items():
            if values and all(
                abs(float(voice.get(key, 0)) - value) < 1e-6
                for key, value in zip(style_keys, values)
            ):
                preset_name = candidate
                break
        with QSignalBlocker(self.voice_preset_combo):
            self.voice_preset_combo.setCurrentText(preset_name)

        self.language_combo.setCurrentText(str(voice.get("lang_code", "no")))

        self.mode_combo.setCurrentIndex(
            max(0, self.mode_combo.findData(audio.get("mode", "vad")))
        )
        self.trim_checkbox.setChecked(bool(audio.get("trim_silence", True)))

        self.api_url_edit.setText(
            str(self.settings["api"].get("base_url", DEFAULT_API_URL))
        )
        self.api_url_edit.setCursorPosition(0)
        self.token_edit.setText(self.token)
        self.token_edit.setCursorPosition(0)
        self._loading = False

    # -------------------------------------------------------------- settings
    def _set_setting(self, section: str, key: str, value) -> None:
        if self._loading:
            return
        self.settings[section][key] = value
        self._dirty = True

    def _on_personality_changed(self, name: str) -> None:
        if self._loading:
            return
        self.settings["bot"]["personality"] = name
        preset = PERSONALITY_PRESETS.get(name)
        if preset:
            with QSignalBlocker(self.prompt_edit):
                self.prompt_edit.setPlainText(preset)
            self.settings["bot"]["system_prompt"] = preset
        self._dirty = True

    def _on_prompt_changed(self) -> None:
        if self._loading:
            return
        text = self.prompt_edit.toPlainText()
        self.settings["bot"]["system_prompt"] = text
        current = self.personality_combo.currentText()
        preset = PERSONALITY_PRESETS.get(current)
        if preset is not None and text != preset:
            with QSignalBlocker(self.personality_combo):
                self.personality_combo.setCurrentText("Egendefinert")
            self.settings["bot"]["personality"] = "Egendefinert"
        self._dirty = True

    def _on_voice_preset_changed(self, name: str) -> None:
        if self._loading:
            return
        values = VOICE_PRESETS.get(name)
        if values:
            for key, value in zip(
                (
                    "exaggeration",
                    "cfg_weight",
                    "temperature",
                    "repetition_penalty",
                    "top_p",
                ),
                values,
            ):
                self._set_slider("voice", key, value)
                self.settings["voice"][key] = value
            self._dirty = True

    def _on_voice_changed(self) -> None:
        if self._loading:
            return
        name = self.voice_combo.currentData()
        if name:
            self.settings["voice"]["profile"] = str(name)
            self._dirty = True
            self._update_voice_info()

    def _on_nest_toggled(self, checked: bool) -> None:
        nest_player.lagre_innstillinger(checked, self.nest_name_edit.text())
        self._log("Nest Mini er " + ("på" if checked else "av"))
        if checked:
            nest_player.forbered_i_bakgrunnen()

    def _on_nest_name_changed(self, text: str) -> None:
        nest_player.lagre_innstillinger(self.nest_checkbox.isChecked(), text)

    def _on_input_device_changed(self) -> None:
        if self._loading:
            return
        self.settings["audio"]["input_device"] = self.input_combo.currentData()
        self._dirty = True

    def _on_output_device_changed(self) -> None:
        if self._loading:
            return
        self.settings["audio"]["output_device"] = self.output_combo.currentData()
        self._dirty = True

    def _update_client(self) -> None:
        base = self.api_url_edit.text().strip() or DEFAULT_API_URL
        token = self.token_edit.text().strip()
        self.client = ApiClient(base, token) if token else None

    def _client_from_ui(self) -> ApiClient:
        self._update_client()
        if not self.client or not self.client.token:
            raise RuntimeError(
                "ROBOT_TOKEN mangler. Legg tokenet inn i API-fanen."
            )
        return self.client

    def save_all(self, silent: bool = False) -> bool:
        base = self.api_url_edit.text().strip() or DEFAULT_API_URL
        token = self.token_edit.text().strip()
        if not base.startswith(("http://", "https://")):
            if not silent:
                QMessageBox.warning(
                    self, "Ugyldig API-URL", "URL-en må starte med http:// eller https://."
                )
            return False
        if not token:
            if not silent:
                QMessageBox.warning(
                    self,
                    "Mangler token",
                    "ROBOT_TOKEN må fylles ut i API-fanen.",
                )
            return False

        self.settings["api"]["base_url"] = base
        self.settings["bot"]["name"] = self.name_edit.text().strip() or "Bingo"
        self.settings["bot"]["personality"] = (
            self.personality_combo.currentText()
        )
        self.settings["bot"]["system_prompt"] = self.prompt_edit.toPlainText()
        self.settings["bot"]["model"] = self.model_combo.currentText().strip()
        self.settings["voice"]["profile"] = (
            self.voice_combo.currentData()
            or self.settings["voice"].get("profile", "min_stemme")
        )
        self.settings["voice"]["lang_code"] = (
            self.language_combo.currentText().strip() or "no"
        )
        self.settings["audio"]["mode"] = self.mode_combo.currentData()
        self.settings["audio"]["trim_silence"] = self.trim_checkbox.isChecked()
        self.settings["audio"]["input_device"] = self.input_combo.currentData()
        self.settings["audio"]["output_device"] = self.output_combo.currentData()

        try:
            save_settings(self.settings)
            save_env(base, token)
            self.token = token
            self._update_client()
            self._dirty = False
            self._set_status("Innstillinger lagret")
            self._log("Innstillinger lagret.")
            if not silent:
                QMessageBox.information(
                    self,
                    "Lagret",
                    "Innstillingene er lagret.\n\n"
                    "Tokenet ligger i .env med begrensede rettigheter.",
                )
            return True
        except Exception as exc:
            if not silent:
                QMessageBox.critical(self, "Kunne ikke lagre", str(exc))
            return False

    # --------------------------------------------------------------- devices
    def _refresh_devices(self) -> None:
        self._loading = True
        try:
            inputs = list_input_devices()
            outputs = list_output_devices()
            saved_in = self.settings["audio"].get("input_device")
            saved_out = self.settings["audio"].get("output_device")
            default_in = default_input_index()
            default_out = default_output_index()
            default_in_name = next(
                (d["name"] for d in inputs if d["index"] == default_in),
                inputs[0]["name"] if inputs else "ukjent",
            )
            default_out_name = next(
                (d["name"] for d in outputs if d["index"] == default_out),
                outputs[0]["name"] if outputs else "ukjent",
            )

            with QSignalBlocker(self.input_combo):
                self.input_combo.clear()
                self.input_combo.addItem(
                    f"Systemstandard ({default_in_name})", None
                )
                for dev in inputs:
                    self.input_combo.addItem(
                        f"{dev['index']}: {dev['name']}", dev["index"]
                    )
                index = self.input_combo.findData(saved_in)
                if index < 0:
                    index = 0
                self.input_combo.setCurrentIndex(index)

            with QSignalBlocker(self.output_combo):
                self.output_combo.clear()
                self.output_combo.addItem(
                    f"Systemstandard ({default_out_name})", None
                )
                for dev in outputs:
                    self.output_combo.addItem(
                        f"{dev['index']}: {dev['name']}", dev["index"]
                    )
                index = self.output_combo.findData(saved_out)
                if index < 0:
                    index = 0
                self.output_combo.setCurrentIndex(index)

            if inputs:
                self._set_chip(
                    self.mic_chip,
                    "Mic",
                    True,
                    f"{len(inputs)} innganger · standard: {default_in_name}",
                )
            else:
                self._set_chip(self.mic_chip, "Mic", False, "Ingen mikrofon funnet")
        finally:
            self._loading = False

    def _on_recorder_level(self, db: float) -> None:
        value = int(max(0, min(100, (db + 60.0) / 60.0 * 100.0)))
        self.level_meter.setValue(value)

    # --------------------------------------------------------------- voices
    def _populate_voices(self, payload: dict) -> None:
        voices = payload.get("voices") or []
        current = self.settings["voice"].get("profile", "min_stemme")
        self._voice_meta = {str(v.get("name")): v for v in voices}

        with QSignalBlocker(self.voice_combo):
            self.voice_combo.clear()
            for voice in voices:
                name = str(voice.get("name", ""))
                if not name:
                    continue
                label = str(voice.get("label") or name)
                duration = float(voice.get("duration") or 0)
                text = f"{label}"
                if duration:
                    text += f"  ·  {duration:.1f}s"
                self.voice_combo.addItem(text, name)

            if current and self.voice_combo.findData(current) < 0:
                self.voice_combo.addItem(current, current)

            index = self.voice_combo.findData(current)
            if index < 0:
                index = 0
            self.voice_combo.setCurrentIndex(index)

        self.voice_dir = Path(
            payload.get("voice_dir") or self.voice_dir
        ).expanduser()
        self._update_voice_info()

    def _update_voice_info(self) -> None:
        name = self.voice_combo.currentData()
        if not name:
            self.voice_info_label.setText("Ingen stemme valgt.")
            return
        meta = self._voice_meta.get(str(name), {})
        duration = float(meta.get("duration") or 0)
        sample_rate = int(meta.get("sample_rate") or 0)
        parts = [str(name)]
        if duration:
            parts.append(f"{duration:.1f} sek")
        if sample_rate:
            parts.append(f"{sample_rate / 1000:.0f} kHz")
        parts.append(f"mappe: {self.voice_dir}")
        self.voice_info_label.setText(" · ".join(parts))

    def _voice_payload(self) -> dict:
        voice = self.settings["voice"]
        return {
            "voice": self.voice_combo.currentData()
            or voice.get("profile", "min_stemme"),
            "exaggeration": float(voice.get("exaggeration", 0.5)),
            "cfg_weight": float(voice.get("cfg_weight", 0.5)),
            "temperature": float(voice.get("temperature", 0.8)),
            "repetition_penalty": float(
                voice.get("repetition_penalty", 1.2)
            ),
            "top_p": float(voice.get("top_p", 1.0)),
            "lang_code": self.language_combo.currentText().strip() or "no",
            "max_tokens": int(voice.get("max_tokens", 1000)),
        }

    def open_voice_folder(self) -> None:
        try:
            self.voice_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.voice_dir)))
        except Exception as exc:
            QMessageBox.warning(self, "Kunne ikke åpne mappe", str(exc))

    def add_voice_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Velg en WAV-fil med en stemme",
            str(Path.home()),
            "WAV-filer (*.wav)",
        )
        if not filename:
            return

        source = Path(filename)
        safe = "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in source.stem.lower()
        ).strip("_") or "stemme"
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        destination = self.voice_dir / f"{safe}.wav"

        if destination.exists():
            answer = QMessageBox.question(
                self,
                "Stemmen finnes",
                f"{destination.name} finnes allerede. Erstatt den?",
            )
            if answer != QMessageBox.Yes:
                return

        try:
            shutil.copy2(source, destination)
        except Exception as exc:
            QMessageBox.critical(self, "Kunne ikke kopiere", str(exc))
            return

        self._log(f"La til stemmefil: {destination}")
        self._voice_select_pending = safe
        self.reload_voices()

    def reload_voices(self) -> None:
        if self.reload_worker and self.reload_worker.isRunning():
            return
        try:
            client = self._client_from_ui()
        except Exception as exc:
            QMessageBox.warning(self, "Mangler API", str(exc))
            return

        self.reload_voices_button.setEnabled(False)
        self.api_reload_voices.setEnabled(False)
        self._set_status("Laster inn stemmer …")
        worker = ReloadVoicesWorker(client, self)
        self.reload_worker = worker
        worker.result.connect(self._on_voices_reloaded)
        worker.failed.connect(self._on_voices_reload_failed)
        worker.finished.connect(
            lambda w=worker: self._finish_reload_worker(w)
        )
        worker.start()

    def _finish_reload_worker(self, worker: ReloadVoicesWorker) -> None:
        if self.reload_worker is worker:
            self.reload_worker = None
        worker.deleteLater()
        self.reload_voices_button.setEnabled(True)
        self.api_reload_voices.setEnabled(True)

    def _on_voices_reloaded(self, result: dict) -> None:
        payload = result.get("voices") or {}
        if payload.get("ok"):
            self._populate_voices(payload)
        selected = self._voice_select_pending
        if selected:
            index = self.voice_combo.findData(selected)
            if index >= 0:
                self.voice_combo.setCurrentIndex(index)
            self._voice_select_pending = None
        errors = (result.get("reload") or {}).get("errors") or {}
        self._set_status("Stemmer lastet inn")
        self._log("Stemmer lastet inn på nytt.")
        if errors:
            QMessageBox.warning(
                self,
                "Noen stemmer feilet",
                "\n".join(f"{k}: {v}" for k, v in errors.items()),
            )

    def _on_voices_reload_failed(self, message: str) -> None:
        self._set_status("Kunne ikke laste stemmer")
        self._log(f"Stemmeinnlasting feilet: {message}")
        QMessageBox.warning(self, "Kunne ikke laste stemmer", message)

    # ------------------------------------------------------------------- API
    def refresh_api_info(
        self, show_errors: bool = False, delay_ms: int = 0
    ) -> None:
        if delay_ms:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(
                delay_ms,
                lambda: self.refresh_api_info(show_errors=show_errors),
            )
            return

        if self.info_worker and self.info_worker.isRunning():
            return
        try:
            client = self._client_from_ui()
        except Exception as exc:
            self._set_chip(self.api_chip, "API", False, str(exc))
            self._set_chip(self.tts_chip, "TTS", False, "Mangler token")
            self.api_status_label.setText(str(exc))
            if show_errors:
                QMessageBox.warning(self, "Mangler API", str(exc))
            return

        self.test_button.setEnabled(False)
        self.refresh_voices_button.setEnabled(False)
        worker = ApiInfoWorker(client, self)
        self.info_worker = worker
        worker.result.connect(
            lambda result, show=show_errors: self._on_api_info(result, show)
        )
        worker.finished.connect(
            lambda w=worker: self._finish_info_worker(w)
        )
        worker.start()

    def _finish_info_worker(self, worker: ApiInfoWorker) -> None:
        if self.info_worker is worker:
            self.info_worker = None
        worker.deleteLater()
        self.test_button.setEnabled(True)
        self.refresh_voices_button.setEnabled(True)

    def _on_api_info(self, result: dict, show_errors: bool) -> None:
        status = result.get("status")
        voices = result.get("voices")
        errors = result.get("errors") or []

        if status and status.get("ok"):
            self._set_chip(
                self.api_chip,
                "API",
                True,
                f"{status.get('service', 'API')} · {status.get('time', '')}",
            )
            self.api_status_label.setText("Tilkoblet.")
        else:
            self._set_chip(self.api_chip, "API", False, "Ingen kontakt")
            self.api_status_label.setText(
                errors[0] if errors else "Ingen kontakt med API-et."
            )

        if voices and voices.get("ok"):
            self._populate_voices(voices)
            n = len(voices.get("voices") or [])
            folder = voices.get("voice_dir", str(self.voice_dir))
            self._set_chip(
                self.tts_chip, "TTS", True, f"{n} stemmer · {folder}"
            )
            self.tts_info_label.setText(
                f"TTS er tilgjengelig med {n} stemmeprofil(er).\n"
                f"Mappe: {folder}"
            )
        else:
            self._set_chip(self.tts_chip, "TTS", False, "TTS er ikke tilgjengelig")
            tts_errors = [e for e in errors if e.startswith("Stemmer/TTS")]
            self.tts_info_label.setText(
                tts_errors[0]
                if tts_errors
                else "TTS-serveren eller tunnelen svarer ikke."
            )

        for error in errors:
            self._log(error)

        if show_errors and errors:
            QMessageBox.warning(
                self,
                "Tilkoblingsfeil",
                "\n\n".join(errors),
            )

    # ------------------------------------------------------------------ turn
    def send_text(self) -> None:
        if self.turn_worker and self.turn_worker.isRunning():
            return
        if self.recorder.is_running:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self.player and self.player.isRunning():
            self.stop_playback()
        self.input.clear()
        self._start_turn(text=text)

    def _start_turn(
        self, *, text: str | None = None, wav_data: bytes | None = None
    ) -> None:
        if self.turn_worker and self.turn_worker.isRunning():
            return
        try:
            client = self._client_from_ui()
        except Exception as exc:
            self._show_error(str(exc))
            return

        bot = self.settings["bot"]
        turns = int(bot.get("history_turns", 6))
        history = self.history[-turns * 2 :] if turns > 0 else []

        self.pending_user = text.strip() if text else None
        self.pending_reply = None
        self.stt_seconds = None
        self.chat_seconds = None
        self.tts_seconds = None

        if text:
            self._append_message("user", text)
            self._log(f"Du skrev: {text}")

        worker = TurnWorker(
            client,
            text=text,
            wav_data=wav_data,
            history=history,
            system=str(bot.get("system_prompt", "")),
            model=str(bot.get("model", MODELS[0])),
            temperature=float(bot.get("temperature", 0.8)),
            max_tokens=int(bot.get("max_tokens", 80)),
            voice=self._voice_payload(),
            parent=self,
        )
        self.turn_worker = worker
        worker.transcribed.connect(self._on_transcribed)
        worker.replied.connect(self._on_replied)
        worker.audio_ready.connect(self._on_audio_ready)
        worker.failed.connect(self._on_turn_failed)
        worker.finished.connect(
            lambda w=worker: self._finish_turn_worker(w)
        )

        self._set_busy(True)
        self._set_status("Bingo tenker …")
        self.level_meter.setValue(0)
        worker.start()

    def _on_transcribed(self, text: str, seconds: float) -> None:
        self.pending_user = text.strip()
        self.stt_seconds = seconds
        if not text.strip():
            self._log("STT returnerte tom tekst.")
            return
        self._append_message("user", text)
        self._log(f"STT: {text} ({seconds:.2f}s)")
        self._set_status("Bingo tenker …")

    def _on_replied(self, reply: str, seconds: float) -> None:
        self.pending_reply = reply.strip()
        self.chat_seconds = seconds
        if not reply.strip():
            self._log("Modellen returnerte tomt svar.")
            return
        self._append_message("assistant", reply)
        self._log(f"Bingo: {reply} ({seconds:.2f}s)")

        if self.pending_user:
            self.history.append(
                {"role": "user", "content": self.pending_user}
            )
            self.history.append(
                {"role": "assistant", "content": reply.strip()}
            )
            turns = int(self.settings["bot"].get("history_turns", 6))
            if turns <= 0:
                self.history.clear()
            else:
                self.history = self.history[-turns * 2 :]

        self._set_status("Lager tale …")

    def _on_audio_ready(self, audio: bytes, seconds: float) -> None:
        self.tts_seconds = seconds
        self.last_audio = audio
        self.replay_button.setEnabled(True)

        timing = []
        if self.stt_seconds is not None:
            timing.append(f"STT {self.stt_seconds:.2f}s")
        if self.chat_seconds is not None:
            timing.append(f"svar {self.chat_seconds:.2f}s")
        timing.append(f"tale {seconds:.2f}s")
        self._append_meta(" · ".join(timing))
        self._log("TTS: " + " · ".join(timing))
        self.play_audio(audio)

    def _on_turn_failed(self, message: str) -> None:
        self._log(f"Feil: {message}")
        self._append_message("error", message)
        self._set_status("Noe gikk galt")
        QMessageBox.warning(self, "Bingo-feil", message)

    def _finish_turn_worker(self, worker: TurnWorker) -> None:
        if self.turn_worker is worker:
            self.turn_worker = None
        worker.deleteLater()
        self._set_busy(False)
        if self.player and self.player.isRunning():
            self._set_status("Spiller av …")
        else:
            self._set_status("Klar")

    def _set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.record_button.setEnabled(not busy)
        self.preview_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)

    # ------------------------------------------------------------- recording
    def toggle_record(self) -> None:
        if self.recorder.is_running:
            self.recorder.stop()
            self._set_status("Stopper opptak …")
            return
        if self.turn_worker and self.turn_worker.isRunning():
            return
        if self.player and self.player.isRunning():
            self.stop_playback()
        self._test_mic_active = False
        self._start_recorder(
            mode=self.mode_combo.currentData() or "vad",
            max_seconds=float(self.settings["audio"].get("max_record_s", 20)),
            trim=bool(self.settings["audio"].get("trim_silence", True)),
        )

    def test_microphone(self) -> None:
        if self.recorder.is_running:
            self.recorder.stop()
            return
        if self.turn_worker and self.turn_worker.isRunning():
            return
        self._test_mic_active = True
        self.test_mic_status.setText("Spiller inn 3 sekunder …")
        self._start_recorder(mode="ptt", max_seconds=3.0, trim=False)

    def _start_recorder(
        self, *, mode: str, max_seconds: float, trim: bool
    ) -> None:
        audio = self.settings["audio"]
        device = self.input_combo.currentData()
        self._set_recording_ui(True)
        self._set_status(
            "Lytter … snakk nå"
            if mode == "vad"
            else "Spiller inn … trykk Stopp"
        )
        self._log(
            f"Opptak startet: modus={mode}, enhet={device}, "
            f"maks={max_seconds:.0f}s"
        )
        self.recorder.start(
            mode=mode,
            device=device,
            threshold_db=float(audio.get("silence_threshold_db", -40)),
            silence_ms=int(audio.get("silence_ms", 900)),
            max_seconds=max_seconds,
            pre_roll_ms=int(audio.get("pre_roll_ms", 300)),
            trim=trim,
        )

    def _on_recorder_finished(self, audio, reason: str) -> None:
        self._set_recording_ui(False)
        self.level_meter.setValue(0)

        if self._test_mic_active:
            self._test_mic_active = False
            if audio.size == 0:
                self.test_mic_status.setText("Ingen lyd fanget. Sjekk mikrofontilgang.")
                self._set_status("Ingen lyd")
                return
            self.test_mic_status.setText(
                f"Tok opp {len(audio) / 16000:.1f} sek. Spiller av …"
            )
            test_audio = wav_bytes(audio)
            self.last_audio = test_audio
            self.replay_button.setEnabled(True)
            self.play_audio(test_audio, local=True)
            return

        if audio.size == 0:
            if reason == "timeout":
                message = "Jeg hørte ingenting. Senk støygrensen eller bruk PTT."
            else:
                message = "Opptaket ble tomt. Prøv igjen."
            self._set_status(message)
            self._append_system(message)
            self._log(message)
            return

        duration = len(audio) / 16000
        if duration < 0.3:
            self._set_status("Opptaket ble for kort.")
            self._append_system("Opptaket ble for kort. Prøv igjen.")
            return

        self._log(f"Opptak ferdig: {duration:.1f}s ({reason})")
        self._set_status("Sender til STT …")
        self._start_turn(wav_data=wav_bytes(audio))

    def _on_recorder_error(self, message: str) -> None:
        self._set_recording_ui(False)
        self._test_mic_active = False
        self.level_meter.setValue(0)
        self._set_status("Mikrofonfeil")
        self._log(f"Mikrofonfeil: {message}")
        self._show_error(
            "Kunne ikke bruke mikrofonen.\n\n"
            f"{message}\n\n"
            "Sjekk Systeminnstillinger → Personvern og sikkerhet → Mikrofon."
        )

    def _set_recording_ui(self, active: bool) -> None:
        self.record_button.setText("Stopp" if active else "Snakk")
        self.record_button.setProperty("recording", active)
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.send_button.setEnabled(not active and not (
            self.turn_worker and self.turn_worker.isRunning()
        ))

    # --------------------------------------------------------------- playback
    def play_audio(self, data: bytes, local: bool = False) -> None:
        self.stop_playback()
        device = self.output_combo.currentData()
        if self.nest_checkbox.isChecked() and not local:
            player = nest_player.NestPlaybackThread(data, parent=self)
        else:
            player = PlaybackThread(data, device=device, parent=self)
        self.player = player
        player.finished_ok.connect(self._on_playback_finished)
        player.failed.connect(self._on_playback_failed)
        player.finished.connect(lambda p=player: self._cleanup_player(p))
        self.stop_button.setEnabled(True)
        self._set_status("Spiller av …")
        self._log(f"Avspilling startet ({len(data)} byte).")
        player.start()

    def _on_playback_finished(self) -> None:
        self._log("Avspilling ferdig.")
        if self.test_mic_status.text().endswith("Spiller av …"):
            self.test_mic_status.setText("Mikrofonen fungerer.")
        self._set_status("Klar")

    def _on_playback_failed(self, message: str) -> None:
        self._log(f"Avspilling feilet: {message}")
        self._set_status("Kunne ikke spille av")
        self._show_error(f"Kunne ikke spille av lyden:\n\n{message}")

    def _cleanup_player(self, player: PlaybackThread) -> None:
        if self.player is player:
            self.player = None
            self.stop_button.setEnabled(False)
            if not (self.turn_worker and self.turn_worker.isRunning()):
                self._set_status("Klar")
        player.deleteLater()

    def stop_playback(self) -> None:
        if self.player and self.player.isRunning():
            self.player.stop()
            self._set_status("Stopper avspilling …")
        self.stop_button.setEnabled(False)

    def replay_last(self) -> None:
        if self.last_audio:
            self.play_audio(self.last_audio)

    def _escape(self) -> None:
        if self.recorder.is_running:
            self.recorder.stop()
        elif self.player and self.player.isRunning():
            self.stop_playback()

    # --------------------------------------------------------------- preview
    def preview_voice(self) -> None:
        if self.preview_worker and self.preview_worker.isRunning():
            return
        try:
            client = self._client_from_ui()
        except Exception as exc:
            self._show_error(str(exc))
            return
        text = self.preview_text.text().strip()
        if not text:
            self._show_error("Skriv en testtekst først.")
            return
        if self.player and self.player.isRunning():
            self.stop_playback()
        self.preview_button.setEnabled(False)
        self._set_status("Lager stemmetest …")
        self._log(
            f"Stemmetest: {len(text)} tegn, profil={self.voice_combo.currentData()}"
        )
        worker = PreviewWorker(client, text, self._voice_payload(), self)
        self.preview_worker = worker
        worker.audio_ready.connect(self._on_preview_audio)
        worker.failed.connect(self._on_preview_failed)
        worker.finished.connect(lambda w=worker: self._finish_preview(w))
        worker.start()

    def _on_preview_audio(self, data: bytes) -> None:
        self.last_audio = data
        self.replay_button.setEnabled(True)
        self._log(f"Stemmetest klar: {len(data)} byte WAV.")
        self.play_audio(data)

    def _on_preview_failed(self, message: str) -> None:
        self._set_status("Stemmetest feilet")
        self._show_error(message)

    def _finish_preview(self, worker: PreviewWorker) -> None:
        if self.preview_worker is worker:
            self.preview_worker = None
        worker.deleteLater()
        self.preview_button.setEnabled(not (
            self.turn_worker and self.turn_worker.isRunning()
        ))

    # ------------------------------------------------------------------ chat
    def _append_message(self, role: str, text: str) -> None:
        if not text:
            return
        now = datetime.now().strftime("%H:%M")
        safe = html.escape(text).replace("\n", "<br>")
        if role == "user":
            name = "Du"
            color = "#69aefc"
            background = "#18232e"
        elif role == "assistant":
            name = str(self.settings["bot"].get("name", "Bingo"))
            color = "#49dba2"
            background = "#17251f"
        elif role == "error":
            name = "Feil"
            color = "#ff8794"
            background = "#281a1d"
        else:
            name = "System"
            color = "#9aa8b7"
            background = "#1a1f25"

        block = (
            f'<div style="margin:7px 0; padding:9px 11px; '
            f'background:{background}; border-left:3px solid {color};">'
            f'<span style="color:{color}; font-weight:600;">{name}</span> '
            f'<span style="color:#6f7e8e; font-size:10px;">{now}</span>'
            f'<br><span style="color:#e7edf4;">{safe}</span></div>'
        )
        self.chat.append(block)
        self._scroll_chat()
        self.transcript_lines.append(f"[{now}] {name}: {text}")

    def _append_system(self, text: str) -> None:
        now = datetime.now().strftime("%H:%M")
        safe = html.escape(text).replace("\n", "<br>")
        self.chat.append(
            f'<div style="margin:6px 0; color:#8b9aab; font-size:11px; '
            f'font-style:italic;">{safe} <span style="color:#5f6c79;">'
            f'{now}</span></div>'
        )
        self._scroll_chat()

    def _append_meta(self, text: str) -> None:
        safe = html.escape(text)
        self.chat.append(
            f'<div style="margin:2px 0 9px 4px; color:#6f7e8e; '
            f'font-size:10px;">{safe}</div>'
        )
        self._scroll_chat()

    def _scroll_chat(self) -> None:
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def reset_conversation(self) -> None:
        if self.turn_worker and self.turn_worker.isRunning():
            return
        self.history.clear()
        self.chat.clear()
        self.transcript_lines.append("\n--- Ny samtale ---\n")
        self._append_system("Samtalen er nullstilt.")
        self._log("Samtalen er nullstilt.")

    def export_transcript(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Eksporter samtale",
            str(Path.home() / "bingo-samtale.txt"),
            "Tekstfiler (*.txt)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(
                "\n".join(self.transcript_lines) + "\n", encoding="utf-8"
            )
            self._set_status("Samtalen er eksportert")
            self._log(f"Eksporterte samtale til {filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Kunne ikke eksportere", str(exc))

    # ------------------------------------------------------------------- log
    def _log(self, message: str) -> None:
        if not hasattr(self, "log_view"):
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{stamp}] {message}")
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def save_log(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Lagre logg",
            str(Path.home() / "bingo-logg.txt"),
            "Tekstfiler (*.txt)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(
                self.log_view.toPlainText() + "\n", encoding="utf-8"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Kunne ikke lagre logg", str(exc))

    # ------------------------------------------------------------------ misc
    def _set_status(self, text: str) -> None:
        if hasattr(self, "status_label"):
            self.status_label.setText(text)

    def _set_chip(
        self, chip: QLabel, name: str, ok: bool | None, detail: str
    ) -> None:
        if ok is True:
            color = "#49dba2"
            background = "#14251d"
            border = "#24543d"
            mark = "●"
        elif ok is False:
            color = "#ff8794"
            background = "#281a1d"
            border = "#5c2a33"
            mark = "●"
        else:
            color = "#d6b35a"
            background = "#272215"
            border = "#54472a"
            mark = "○"
        chip.setText(f"{mark} {name}")
        chip.setStyleSheet(
            f"color:{color}; background:{background}; border:1px solid "
            f"{border}; border-radius:9px; padding:5px 9px; "
            f"font-size:11px; font-weight:600;"
        )
        chip.setToolTip(detail)

    def _show_error(self, message: str) -> None:
        self._log(f"Feil: {message}")
        QMessageBox.warning(self, "Bingo", message)

    def closeEvent(self, event) -> None:
        if self.recorder.is_running:
            self.recorder.stop()
        self.stop_playback()
        for worker in (
            self.turn_worker,
            self.info_worker,
            self.preview_worker,
            self.reload_worker,
            self.player,
        ):
            if worker and worker.isRunning():
                worker.wait(1000)
        try:
            self.save_all(silent=True)
        except Exception:
            pass
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Bingo Studio")
    app.setApplicationDisplayName("Bingo Studio")
    app.setStyle("Fusion")
    font = QFont(app.font())
    font.setPointSize(13)
    app.setFont(font)
    app.setStyleSheet(APP_STYLE)
    window = BingoWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
