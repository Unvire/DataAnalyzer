import os
from typing import Sequence

from PySide6.QtCore import QDir, QModelIndex, Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileSystemModel, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSplitter, QTreeView, QVBoxLayout,
)


class FolderBrowserDialog(QDialog):
    def __init__(self, title:str='Select logs folder', initialDir:str='', extensions:Sequence[str]|None=None,
        includeSubfoldersHint: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(920, 560)
        self.setMinimumSize(680, 420)

        self._extensions = self._normalizeExtensions(extensions)
        self._includeSubfoldersHint = includeSubfoldersHint
        self._currentPath = self._resolveInitialDir(initialDir)
        self._matchingFileCount = 0
        self._subfolderCount = 0

        self._buildModels()
        self._buildUi()
        self._bindEvents()
        self._navigateTo(self._currentPath, force=True)

    @staticmethod
    def _normalizeExtensions(extensions:Sequence[str]|None) -> list[str]:
        if not extensions:
            return []
        
        cleaned: list[str] = []
        for ext in extensions:
            norm = ext.strip().lstrip('.').lower()
            if norm and norm not in cleaned:
                cleaned.append(norm)
        return cleaned

    @staticmethod
    def _resolveInitialDir(initialDir: str) -> str:
        if initialDir and os.path.isdir(initialDir):
            return os.path.abspath(initialDir)
        
        homeDir = QDir.homePath()
        if os.path.isdir(homeDir):
            return os.path.abspath(homeDir)
        return os.path.abspath(os.getcwd())

    def _buildModels(self):
        self._dirModel = QFileSystemModel(self)
        self._dirModel.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self._dirModel.setRootPath('')

        self._fileModel = QFileSystemModel(self)
        self._fileModel.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self._fileModel.setNameFilterDisables(False)
        self._applyExtensionFilter(bool(self._extensions))

    def _buildUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top navigation bar
        navRow = QHBoxLayout()
        navRow.setSpacing(6)

        self.upButton = QPushButton('Up')
        self.upButton.setToolTip('Go to parent folder')
        self.upButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.homeButton = QPushButton('Home')
        self.homeButton.setToolTip('Go to user home folder')
        self.homeButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText('Enter or paste folder path and press Enter...')

        self.goButton = QPushButton('Go')
        self.goButton.setCursor(Qt.CursorShape.PointingHandCursor)

        navRow.addWidget(self.upButton)
        navRow.addWidget(self.homeButton)
        navRow.addWidget(self.pathEdit, 1)
        navRow.addWidget(self.goButton)

        # Filter bar
        filterRow = QHBoxLayout()
        filterRow.setSpacing(8)

        extLabel = ', '.join(f'*.{ext}' for ext in self._extensions) if self._extensions else 'all files'
        self.filterExtensionsCheckBox = QCheckBox(f'Show only matching log files ({extLabel})')
        self.filterExtensionsCheckBox.setChecked(bool(self._extensions))
        self.filterExtensionsCheckBox.setEnabled(bool(self._extensions))

        self.fileStatsLabel = QLabel('')
        self.fileStatsLabel.setStyleSheet('color: #9da0a8;')

        filterRow.addWidget(self.filterExtensionsCheckBox)
        filterRow.addStretch(1)
        filterRow.addWidget(self.fileStatsLabel)

        # Main dual-pane browser
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        self.dirTreeView = QTreeView()
        self.dirTreeView.setModel(self._dirModel)
        self.dirTreeView.setHeaderHidden(True)
        self.dirTreeView.setAnimated(False)
        self.dirTreeView.setSortingEnabled(True)
        self.dirTreeView.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for col in (1, 2, 3):
            self.dirTreeView.hideColumn(col)

        self.fileTreeView = QTreeView()
        self.fileTreeView.setModel(self._fileModel)
        self.fileTreeView.setRootIsDecorated(False)
        self.fileTreeView.setItemsExpandable(False)
        self.fileTreeView.setAlternatingRowColors(True)
        self.fileTreeView.setSortingEnabled(True)
        self.fileTreeView.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.fileTreeView.hideColumn(2)  # Hide verbose OS "Type" column

        header = self.fileTreeView.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.splitter.addWidget(self.dirTreeView)
        self.splitter.addWidget(self.fileTreeView)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([280, 620])

        # Bottom selection & buttons row
        bottomRow = QHBoxLayout()
        bottomRow.setSpacing(8)

        self.selectedPathLabel = QLabel('')
        self.selectedPathLabel.setStyleSheet('color: #bcbec4;')
        self.selectedPathLabel.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setCursor(Qt.CursorShape.PointingHandCursor)

        self.selectButton = QPushButton('Select folder')
        self.selectButton.setProperty('accent', True)
        self.selectButton.setDefault(True)
        self.selectButton.setCursor(Qt.CursorShape.PointingHandCursor)

        bottomRow.addWidget(self.selectedPathLabel, 1)
        bottomRow.addWidget(self.cancelButton)
        bottomRow.addWidget(self.selectButton)

        layout.addLayout(navRow)
        layout.addLayout(filterRow)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(bottomRow)

    def _bindEvents(self):
        self.upButton.clicked.connect(self._goUp)
        self.homeButton.clicked.connect(self._goHome)
        self.goButton.clicked.connect(self._onPathSubmitted)
        self.pathEdit.returnPressed.connect(self._onPathSubmitted)
        self.filterExtensionsCheckBox.toggled.connect(self._onFilterToggled)
        self.dirTreeView.clicked.connect(self._onDirTreeClicked)
        self.fileTreeView.doubleClicked.connect(self._onFileViewDoubleClicked)
        self.cancelButton.clicked.connect(self.reject)
        self.selectButton.clicked.connect(self.accept)

    def _applyExtensionFilter(self, onlyMatching: bool):
        if onlyMatching and self._extensions:
            patterns = [f'*.{ext}' for ext in self._extensions]
            self._fileModel.setNameFilters(patterns)
        else:
            self._fileModel.setNameFilters([])

    def _onFilterToggled(self, checked: bool):
        self._applyExtensionFilter(checked)

    def _onDirTreeClicked(self, index: QModelIndex):
        path = self._dirModel.filePath(index)
        if path and os.path.isdir(path):
            self._navigateTo(path)

    def _onFileViewDoubleClicked(self, index: QModelIndex):
        if self._fileModel.isDir(index):
            path = self._fileModel.filePath(index)
            if path and os.path.isdir(path):
                self._navigateTo(path)

    def _onPathSubmitted(self):
        candidate = self.pathEdit.text().strip().strip('"')
        if candidate and os.path.isdir(candidate):
            self.pathEdit.setStyleSheet('')
            self._navigateTo(candidate)
        else:
            self.pathEdit.setStyleSheet('border: 1px solid #d9534f;')

    def _goUp(self):
        parentDir = os.path.dirname(os.path.normpath(self._currentPath))
        if parentDir and os.path.isdir(parentDir) and parentDir != self._currentPath:
            self._navigateTo(parentDir)

    def _goHome(self):
        homeDir = QDir.homePath()
        if os.path.isdir(homeDir):
            self._navigateTo(homeDir)

    def _navigateTo(self, path: str, force: bool = False):
        normPath = os.path.abspath(path)
        if not os.path.isdir(normPath):
            return
        if not force and os.path.normcase(normPath) == os.path.normcase(self._currentPath):
            return

        self._currentPath = normPath
        self.pathEdit.setStyleSheet('')
        self.pathEdit.setText(normPath)
        self.selectedPathLabel.setText(f'Selected: {normPath}')

        parentDir = os.path.dirname(normPath)
        self.upButton.setEnabled(bool(parentDir) and parentDir != normPath)

        fileRootIdx = self._fileModel.setRootPath(normPath)
        self.fileTreeView.setRootIndex(fileRootIdx)

        dirIdx = self._dirModel.index(normPath)
        if dirIdx.isValid():
            self.dirTreeView.setCurrentIndex(dirIdx)
            self.dirTreeView.expand(dirIdx)
            self.dirTreeView.scrollTo(dirIdx)

        self._updateFolderStats(normPath)

    def _updateFolderStats(self, folderPath: str):
        matchingFiles = 0
        totalFiles = 0
        subfolders = 0
        extSet = set(self._extensions)

        try:
            with os.scandir(folderPath) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        subfolders += 1
                    elif entry.is_file(follow_symlinks=False):
                        totalFiles += 1
                        if not extSet:
                            matchingFiles += 1
                        else:
                            _, dotExt = os.path.splitext(entry.name)
                            if dotExt.lstrip('.').lower() in extSet:
                                matchingFiles += 1
        except OSError:
            self._matchingFileCount = 0
            self._subfolderCount = 0
            self.fileStatsLabel.setText('Cannot read folder contents')
            return

        self._matchingFileCount = matchingFiles
        self._subfolderCount = subfolders

        if extSet:
            extText = '/'.join(f'.{e}' for e in self._extensions)
            summary = f'Matching ({extText}): {matchingFiles:,}  |  All files: {totalFiles:,}  |  Subfolders: {subfolders:,}'
        else:
            summary = f'Files: {totalFiles:,}  |  Subfolders: {subfolders:,}'

        if self._includeSubfoldersHint and subfolders > 0 and matchingFiles == 0:
            summary += '  (subfolders will be scanned)'

        self.fileStatsLabel.setText(summary)

    def selectedFolder(self) -> str:
        return self._currentPath

    def matchingFileCount(self) -> int:
        return self._matchingFileCount

    def subfolderCount(self) -> int:
        return self._subfolderCount

    @classmethod
    def getExistingDirectory(cls, parent=None, title:str='Select logs folder', initialDir:str='', extensions:Sequence[str]|None = None,
            includeSubfoldersHint:bool=True) -> str:
        
        dialog = cls(
            title=title,
            initialDir=initialDir,
            extensions=extensions,
            includeSubfoldersHint=includeSubfoldersHint,
            parent=parent,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selectedFolder()
        return ''