from PySide2.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide2.QtWidgets import (
    QVBoxLayout,
    QMainWindow,
    QTableView,
    QAbstractItemView,
    QHeaderView,
    QWidget,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
)

from angrmanagement.plugins import BasePlugin
from angrmanagement.ui.views import BaseView
from angrmanagement.ui.workspace import Workspace

from .seed_table import SeedTable


class SeedTableModel(QAbstractTableModel):
    def __init__(self, workspace, table, dropdown):
        super(SeedTableModel, self).__init__()
        seed_table = SeedTable(workspace, seed_callback=self.add_seed)

        self.table = table
        self.workspace = workspace
        self.page_dropdown = dropdown
        self.headers = ["ID", "Input", "NC", "C", "NT", "L", "E"]
        self.seeds = seed_table.get_all_seeds()
        self.displayed_seeds = []

        # pagination support
        self.current_page = 1
        self.max_pages = 1
        self.entries_per_page = 50

        self.set_page(1)

    def rowCount(self, index=QModelIndex()):
        if not self.displayed_seeds:
            return 0
        return len(self.displayed_seeds)

    def columnCount(self, index=QModelIndex()):
        return len(self.headers)

    # probably not useful anymore. kept for not wanting to do it again.
    # def canFetchMore(self, index=QModelIndex()):
    #     return len(self.seeds) > self.num_loaded
    #
    # def fetchMore(self, index=QModelIndex()):
    #     num_to_fetch = min(len(self.seeds) - self.num_loaded, 50)
    #     self.beginInsertRows(QModelIndex(), self.num_loaded, self.num_loaded+num_to_fetch-1)
    #     self.num_loaded += num_to_fetch
    #     self.endInsertRows()
    #     self.table.resizeEvent(QResizeEvent(self.table.size(), QSize()))

    def set_page(self, pagenum):
        self.beginResetModel()
        if self.max_pages >= pagenum > 0:
            self.current_page = pagenum
        else:
            return False
        # load seeds for page
        min_index = (pagenum - 1) * self.entries_per_page
        max_index = min((pagenum * self.entries_per_page) - 1, len(self.seeds))
        # check to ensure we arent out of bounds
        if min_index > len(self.seeds):  # this should REALLY never happen.
            print("ERROR: Invalid page selected.")
            return False
        self.displayed_seeds = self.seeds[min_index:max_index]
        self.endResetModel()
        return True

    def add_seed(self, seed):
        self.beginResetModel()
        # more complex logic here.. probably
        if isinstance(seed, list):
            for s in seed:
                self.seeds.append(s)
        else:
            self.seeds.append(seed)
        # update our page
        self.max_pages = (len(self.seeds) // self.entries_per_page) + 1
        self.set_page(self.current_page)
        self.page_dropdown.clear()
        self.page_dropdown.addItems(list(map(str, range(1, self.max_pages))))
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        col = index.column()
        seed = self.displayed_seeds[index.row()]
        if role == Qt.DisplayRole:
            if col == 0:
                return f"ID{index.row() + ((self.current_page-1)*(self.entries_per_page - 1))}"
            elif col == 1:
                return str(seed.value)[:10]
            elif col == 2 and "non-crashing" in seed.tags:
                return "x"
            elif col == 3 and "crashing" in seed.tags:
                return "x"
            elif col == 4 and "non-terminating" in seed.tags:
                return "x"
            elif col == 5 and "leaking" in seed.tags:
                return "x"
            elif col == 6 and "exploit" in seed.tags:
                return "x"
            return None
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and section < len(self.headers):
            return self.headers[section]
        else:
            return None

    def go_next_page(self):
        if self.set_page(self.current_page + 1):
            self.page_dropdown.clear()
            self.page_dropdown.addItems(list(map(str, range(1, self.max_pages))))
            self.page_dropdown.setCurrentIndex(self.current_page - 1)

    def go_prev_page(self):
        if self.set_page(self.current_page - 1):
            self.page_dropdown.clear()
            self.page_dropdown.addItems(list(map(str, range(1, self.max_pages))))
            self.page_dropdown.setCurrentIndex(self.current_page-1)


class SeedTableWidget(QTableView):
    def __init__(self, parent, workspace):
        super().__init__(parent)
        self.workspace = workspace
        self._context_menu = None  # for now

    def refresh(self):
        self.viewport().update()

    def init_parameters(self):
        self.horizontalHeader().setVisible(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(18)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setHorizontalScrollMode(self.ScrollPerPixel)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)


class SeedTableView(BaseView):
    def __init__(self, workspace: Workspace, *args, **kwargs):
        super().__init__("SeedTableView", workspace, *args, **kwargs)
        self.base_caption = "Seed Table"
        self.workspace = workspace
        self.instance = workspace.instance
        workspace.instance.project.am_subscribe(self.on_project_load)
        self._init_widgets()

    def page_changed(self, i):
        self.table_data.set_page(self.page_dropdown.currentIndex()+1)

    def _init_widgets(self):
        self.main = QMainWindow()
        self.main.setWindowFlags(Qt.Widget)

        self.container = QWidget()  # create containing widget to keep things nice
        self.container.setLayout(QVBoxLayout())
        # create table
        self.page_dropdown = QComboBox()
        self.table = SeedTableWidget(self, self.workspace)
        self.table_data = SeedTableModel(self.workspace, self.table, self.page_dropdown)
        self.table.setModel(self.table_data)
        self.table.init_parameters()  # need to set table model before messing with column resizing
        self.container.layout().addWidget(self.table)

        self.table_data.add_seed("test")

        # create bottom section
        self.bottom_widget = QWidget()
        self.bottom_widget.setLayout(QHBoxLayout())
        # page buttons
        self.next_page_btn = QPushButton(">")
        self.next_page_btn.setMaximumWidth(40)
        self.next_page_btn.clicked.connect(self.table_data.go_next_page)
        self.prev_page_btn = QPushButton("<")
        self.prev_page_btn.setMaximumWidth(40)
        self.prev_page_btn.clicked.connect(self.table_data.go_prev_page)
        self.page_label = QLabel("Page:")
        # page dropdown
        self.page_dropdown.addItems(list(map(str, range(1,1))))  # test
        self.page_dropdown.setCurrentIndex(0)
        self.page_dropdown.activated.connect(self.page_changed)

        self.bottom_widget.layout().addStretch()
        self.bottom_widget.layout().addWidget(self.prev_page_btn)
        self.bottom_widget.layout().addWidget(self.page_label)
        self.bottom_widget.layout().addWidget(self.page_dropdown)
        self.bottom_widget.layout().addWidget(self.next_page_btn)

        self.container.layout().addWidget(self.bottom_widget)

        self.main.setCentralWidget(self.container)
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.main)
        self.setLayout(main_layout)

    def on_project_load(self, **kwargs):
        if self.instance.project.am_none:
            return
        pass


class SeedTablePlugin(BasePlugin):
    """
    Plugin loader
    """

    def __init__(self, workspace):
        super().__init__(workspace)
        self.seed_table_view = SeedTableView(workspace, "center")
        workspace.default_tabs += [self.seed_table_view]
        workspace.add_view(self.seed_table_view)