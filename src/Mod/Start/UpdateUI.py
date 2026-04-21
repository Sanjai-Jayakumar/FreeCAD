# BNC CAD Update UI Components
# Notification banner and dialogs for updates

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui


class UpdateNotificationBanner(QtGui.QWidget):
    """VS Code-style update notification banner"""
    
    def __init__(self, update_info, parent=None):
        super(UpdateNotificationBanner, self).__init__(parent)
        self.update_info = update_info
        self.setup_ui()
        
    def setup_ui(self):
        """Create the banner UI"""
        self.setAutoFillBackground(True)
        
        # VS Code blue background color
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(15, 98, 254))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))
        self.setPalette(palette)
        
        # Main layout
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        # Icon
        icon_label = QtGui.QLabel()
        icon_pixmap = QtGui.QPixmap(16, 16)
        icon_pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(icon_pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        painter.drawEllipse(3, 3, 10, 10)
        painter.drawText(QtCore.QRect(0, 0, 16, 16), QtCore.Qt.AlignCenter, "!")
        painter.end()
        icon_label.setPixmap(icon_pixmap)
        layout.addWidget(icon_label)
        
        # Message text
        current_ver = self.update_info.get('current_version', '1.1.0')
        new_ver = self.update_info.get('new_version', '1.2.0')
        
        msg_label = QtGui.QLabel(
            f"<b>BNC CAD {new_ver}</b> is available. You are currently on version {current_ver}."
        )
        msg_label.setStyleSheet("color: white; font-size: 12px;")
        msg_label.setWordWrap(False)
        layout.addWidget(msg_label, 1)
        
        # Buttons
        btn_layout = QtGui.QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # Release Notes button
        self.notes_btn = QtGui.QPushButton("Release Notes")
        self.notes_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.35);
            }
        """)
        self.notes_btn.clicked.connect(self.show_release_notes)
        btn_layout.addWidget(self.notes_btn)
        
        # Download Update button
        self.download_btn = QtGui.QPushButton("Download Update")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #0F62FE;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.9);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.8);
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.download_btn)
        
        # Later button
        self.later_btn = QtGui.QPushButton("Later")
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                padding: 5px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.later_btn.clicked.connect(self.dismiss)
        btn_layout.addWidget(self.later_btn)
        
        layout.addLayout(btn_layout)
        
        # Close button
        close_btn = QtGui.QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-size: 18px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        # Set fixed height
        self.setFixedHeight(50)
    
    def show_release_notes(self):
        """Show release notes dialog"""
        dialog = ReleaseNotesDialog(self.update_info, self)
        dialog.exec_()
    
    def start_download(self):
        """Show download confirmation and start download"""
        dialog = DownloadUpdateDialog(self.update_info, self)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            # In mock mode, just show a message
            QtGui.QMessageBox.information(
                self,
                "Mock Mode",
                "Frontend-only demo: Download functionality will be enabled when backend is connected.\n\n"
                f"Would download from:\n{self.update_info.get('download_url', '')}"
            )
    
    def dismiss(self):
        """Hide and remove the banner"""
        self.hide()
        self.deleteLater()


class ReleaseNotesDialog(QtGui.QDialog):
    """Dialog showing release notes for the new version"""
    
    def __init__(self, update_info, parent=None):
        super(ReleaseNotesDialog, self).__init__(parent)
        self.update_info = update_info
        self.setup_ui()
    
    def setup_ui(self):
        """Create the dialog UI"""
        new_ver = self.update_info.get('new_version', '1.2.0')
        self.setWindowTitle(f"BNC CAD {new_ver} Release Notes")
        self.resize(600, 450)
        
        layout = QtGui.QVBoxLayout()
        
        # Header
        header_label = QtGui.QLabel(f"<h2>BNC CAD {new_ver}</h2>")
        layout.addWidget(header_label)
        
        # Release notes
        notes_text = QtGui.QTextEdit()
        notes_text.setReadOnly(True)
        notes_text.setMarkdown(self.update_info.get('release_notes', 'No release notes available.'))
        layout.addWidget(notes_text)
        
        # File size info
        file_size = self.update_info.get('file_size', 0)
        from UpdateChecker import get_update_checker
        checker = get_update_checker()
        size_str = checker.format_file_size(file_size)
        
        info_label = QtGui.QLabel(f"<i>Download size: {size_str}</i>")
        info_label.setStyleSheet("color: #666; margin-top: 10px;")
        layout.addWidget(info_label)
        
        # Buttons
        btn_layout = QtGui.QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QtGui.QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)


class DownloadUpdateDialog(QtGui.QDialog):
    """Dialog for confirming and downloading the update"""
    
    def __init__(self, update_info, parent=None):
        super(DownloadUpdateDialog, self).__init__(parent)
        self.update_info = update_info
        self.setup_ui()
    
    def setup_ui(self):
        """Create the dialog UI"""
        new_ver = self.update_info.get('new_version', '1.2.0')
        self.setWindowTitle(f"Download BNC CAD {new_ver}")
        self.resize(500, 200)
        
        layout = QtGui.QVBoxLayout()
        
        # Message
        msg_label = QtGui.QLabel(
            f"<h3>Download BNC CAD {new_ver}?</h3>"
            "<p>The update will be downloaded in the background. "
            "You can continue working while the download completes.</p>"
            "<p>When ready, you'll be prompted to install the update.</p>"
        )
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        
        # File size
        file_size = self.update_info.get('file_size', 0)
        from UpdateChecker import get_update_checker
        checker = get_update_checker()
        size_str = checker.format_file_size(file_size)
        
        size_label = QtGui.QLabel(f"Download size: <b>{size_str}</b>")
        layout.addWidget(size_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QtGui.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtGui.QPushButton("Cancel")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        download_btn = QtGui.QPushButton("Download")
        download_btn.setMinimumWidth(100)
        download_btn.setDefault(True)
        download_btn.clicked.connect(self.accept)
        btn_layout.addWidget(download_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)


def show_update_banner():
    """Show the update notification banner in FreeCAD main window"""
    try:
        from UpdateChecker import get_update_checker
        
        checker = get_update_checker()
        update_info = checker.check_for_updates()
        
        if not update_info.get('update_available', False):
            # No update available - show info message
            QtGui.QMessageBox.information(
                FreeCADGui.getMainWindow(),
                "No Updates Available",
                f"You are using the latest version of BNC CAD ({checker.CURRENT_VERSION})."
            )
            return
        
        # Get main window
        main_window = FreeCADGui.getMainWindow()
        
        # Remove any existing banner
        for child in main_window.findChildren(UpdateNotificationBanner):
            child.deleteLater()
        
        # Create banner
        banner = UpdateNotificationBanner(update_info, main_window)
        
        # Add banner as a toolbar at the top (best way for FreeCAD)
        # This ensures it appears at the very top of the window
        banner.setParent(main_window)
        
        # Position the banner at the top of the window
        # Get the menu bar height to position below it
        try:
            menu_bar = main_window.menuBar()
            if menu_bar:
                menu_height = menu_bar.height()
            else:
                menu_height = 30
        except:
            menu_height = 30
        
        # Set banner geometry to span the full width
        banner.setGeometry(0, menu_height, main_window.width(), 50)
        
        # Make banner stay on top
        banner.raise_()
        banner.show()
        
        # Connect to window resize to keep banner full width
        def on_resize():
            try:
                banner.setGeometry(0, menu_height, main_window.width(), 50)
            except:
                pass
        
        # Store resize handler
        if not hasattr(main_window, '_banner_resize_handler'):
            main_window._banner_resize_handler = on_resize
        
    except Exception as e:
        # Show error in message box for debugging
        QtGui.QMessageBox.critical(
            FreeCADGui.getMainWindow(),
            "Update Check Error",
            f"Could not show update banner: {str(e)}\n\nPlease report this error."
        )


def check_for_updates_menu():
    """Menu action: Check for updates"""
    show_update_banner()
