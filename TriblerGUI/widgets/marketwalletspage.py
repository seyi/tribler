from PIL.ImageQt import ImageQt
from PyQt5 import QtGui, QtCore

from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QPushButton, QSizePolicy
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path, timestamp_to_time


class MarketWalletsPage(QWidget):
    """
    This page displays information about wallets.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.initialized = False
        self.wallets_to_create = []
        self.wallets = None
        self.active_wallet = None
        self.dialog = None

    def initialize_wallets_page(self):
        if not self.initialized:
            self.window().wallets_back_button.setIcon(QIcon(get_image_path('page_back.png')))
            self.window().wallet_btc_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('BTC', self.window().wallet_btc_overview_button))
            self.window().wallet_tbtc_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('TBTC', self.window().wallet_tbtc_overview_button))
            self.window().wallet_mc_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('MB', self.window().wallet_mc_overview_button))
            self.window().wallet_paypal_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('PP', self.window().wallet_paypal_overview_button))
            self.window().wallet_abn_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('ABNA', self.window().wallet_abn_overview_button))
            self.window().wallet_rabo_overview_button.clicked.connect(
                lambda: self.initialize_wallet_info('RABO', self.window().wallet_rabo_overview_button))
            self.window().add_wallet_button.clicked.connect(self.on_add_wallet_clicked)
            self.window().wallet_mc_overview_button.hide()
            self.window().wallet_btc_overview_button.hide()
            self.window().wallet_tbtc_overview_button.hide()
            self.window().wallet_paypal_overview_button.hide()
            self.window().wallet_abn_overview_button.hide()
            self.window().wallet_rabo_overview_button.hide()
            self.window().wallet_info_tabs.hide()

            self.window().wallet_info_tabs.currentChanged.connect(self.tab_changed)

            self.initialized = True

        self.load_wallets()

    def load_wallets(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets", self.on_wallets)

    def on_wallets(self, wallets):
        self.wallets = wallets["wallets"]

        if 'MB' in self.wallets and self.wallets["MB"]["created"]:
            self.window().wallet_mc_overview_button.show()

        if 'BTC' in self.wallets and self.wallets["BTC"]["created"]:
            self.window().wallet_btc_overview_button.show()

        if 'TBTC' in self.wallets and self.wallets["TBTC"]["created"]:
            self.window().wallet_tbtc_overview_button.show()

        if 'PP' in self.wallets and self.wallets["PP"]["created"]:
            self.window().wallet_paypal_overview_button.show()

        if 'ABNA' in self.wallets and self.wallets["ABNA"]["created"]:
            self.window().wallet_abn_overview_button.show()

        if 'RABO' in self.wallets and self.wallets["RABO"]["created"]:
            self.window().wallet_rabo_overview_button.show()

        # Find out which wallets we still can create
        self.wallets_to_create = []
        for identifier, wallet in self.wallets.iteritems():
            if not wallet["created"]:
                self.wallets_to_create.append(identifier)

        if len(self.wallets_to_create) > 0:
            self.window().add_wallet_button.setEnabled(True)
        else:
            self.window().add_wallet_button.hide()

    def tab_changed(self, index):
        if index == 1 and self.active_wallet:
            self.load_transactions(self.active_wallet)

    def initialize_wallet_info(self, wallet_id, pressed_button):
        # Show the tab again
        self.window().wallet_info_tabs.show()
        self.window().wallet_management_placeholder_widget.hide()

        # Clear the selection of all other buttons, except the pressed button
        for button in self.window().wallet_buttons_container.findChildren(QPushButton):
            if button != pressed_button:
                button.setChecked(False)

        self.active_wallet = wallet_id
        self.window().wallet_info_tabs.setCurrentIndex(0)
        self.window().wallet_address_label.setText(self.wallets[wallet_id]['address'])

        # Create a QR code of the wallet address
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=5,
            )
            qr.add_data(self.wallets[wallet_id]['address'])
            qr.make(fit=True)

            img = qr.make_image()  # PIL format

            qim = ImageQt(img)
            pixmap = QtGui.QPixmap.fromImage(qim).scaled(300, 300, QtCore.Qt.KeepAspectRatio)
            self.window().wallet_address_qr_label.setPixmap(pixmap)
        except ImportError:
            self.window().wallet_address_qr_label.setText("QR Code functionality not available!")

    def load_transactions(self, wallet_id):
        self.window().wallet_transactions_list.clear()
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets/%s/transactions" % wallet_id, self.on_transactions)

    def on_transactions(self, transactions):
        for transaction in transactions["transactions"]:
            item = QTreeWidgetItem(self.window().wallet_transactions_list)
            item.setText(0, "Sent" if transaction["outgoing"] else "Received")
            item.setText(1, transaction["from"])
            item.setText(2, transaction["to"])
            item.setText(3, "%g %s" % (transaction["amount"], transaction["currency"]))
            item.setText(4, "%g %s" % (transaction["fee_amount"], transaction["currency"]))
            item.setText(5, transaction["id"])
            timestamp = timestamp_to_time(float(transaction["timestamp"])) if transaction["timestamp"] != "False" else "-"
            item.setText(6, timestamp)
            self.window().wallet_transactions_list.addTopLevelItem(item)

    def on_add_wallet_clicked(self):
        menu = TriblerActionMenu(self)

        for wallet_id in self.wallets_to_create:
            wallet_action = QAction(self.wallets[wallet_id]['name'], self)
            wallet_action.triggered.connect(lambda _, wid=wallet_id: self.should_create_wallet(wid))
            menu.addAction(wallet_action)

        menu.exec_(QCursor.pos())

    def should_create_wallet(self, wallet_id):
        if wallet_id == 'BTC' or wallet_id == 'TBTC':
            self.dialog = ConfirmationDialog(self, "Create Bitcoin wallet",
                                             "Please enter the password of your Bitcoin wallet below:",
                                             [('CREATE', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                             show_input=True)
            self.dialog.dialog_widget.dialog_input.setPlaceholderText('Wallet password')
            self.dialog.button_clicked.connect(lambda action: self.on_create_btc_wallet_dialog_done(action, wallet_id))
            self.dialog.show()
        else:
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("wallets/%s" % wallet_id, self.on_wallet_created,
                                             method='PUT', data='')

    def on_create_btc_wallet_dialog_done(self, action, wallet_id):
        password = self.dialog.dialog_widget.dialog_input.text()

        if action == 1:  # Remove the dialog right now
            self.dialog.setParent(None)
            self.dialog = None
        elif action == 0:
            self.dialog.buttons[0].setEnabled(False)
            self.dialog.buttons[1].setEnabled(False)
            self.dialog.buttons[0].setText("CREATING...")
            self.request_mgr = TriblerRequestManager()
            post_data = str("password=%s" % password)
            self.request_mgr.perform_request("wallets/%s" % wallet_id, self.on_wallet_created,
                                             method='PUT', data=post_data)

    def on_wallet_created(self, response):
        if self.dialog:
            self.dialog.setParent(None)
            self.dialog = None
        self.load_wallets()
