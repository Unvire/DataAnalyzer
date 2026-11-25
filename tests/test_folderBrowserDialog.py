import pytest
from PySide6.QtWidgets import QApplication

from src.ui.widgets.folderBrowserDialog import FolderBrowserDialog


@pytest.fixture(scope='module')
def qtApp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_folderBrowserDialog_countsMatchingFilesAndSubfolders(qtApp, tmp_path):
    (tmp_path / 'log_1.csv').write_text('a;b', encoding='utf-8')
    (tmp_path / 'log_2.CSV').write_text('a;b', encoding='utf-8')
    (tmp_path / 'notes.txt').write_text('ignore', encoding='utf-8')
    sub = tmp_path / 'batch_sub'
    sub.mkdir()
    (sub / 'nested.csv').write_text('a;b', encoding='utf-8')

    dialog = FolderBrowserDialog(
        title='Select FWK logs',
        initialDir=str(tmp_path),
        extensions=['csv'],
        includeSubfoldersHint=True,
    )

    assert dialog.selectedFolder() == str(tmp_path.resolve())
    assert dialog.matchingFileCount() == 2
    assert dialog.subfolderCount() == 1
    assert dialog.filterExtensionsCheckBox.isChecked() is True
    assert dialog._fileModel.nameFilters() == ['*.csv']


def test_folderBrowserDialog_navigationAndFilterToggle(qtApp, tmp_path):
    sub = tmp_path / 'spea_logs'
    sub.mkdir()
    (sub / 'sample1.txt').write_text('START;', encoding='utf-8')
    (sub / 'sample2.log').write_text('other', encoding='utf-8')

    dialog = FolderBrowserDialog(initialDir=str(tmp_path), extensions=['txt'])

    # Navigate via path input bar
    dialog.pathEdit.setText(str(sub))
    dialog._onPathSubmitted()
    assert dialog.selectedFolder() == str(sub.resolve())
    assert dialog.matchingFileCount() == 1

    # Toggle off extension filter
    dialog.filterExtensionsCheckBox.setChecked(False)
    assert dialog._fileModel.nameFilters() == []

    # Go up to parent directory
    dialog._goUp()
    assert dialog.selectedFolder() == str(tmp_path.resolve())