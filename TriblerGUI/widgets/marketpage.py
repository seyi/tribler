from urllib import urlencode

import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QTreeWidgetItem
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import PAGE_MARKET_TRANSACTIONS, PAGE_MARKET_WALLETS, PAGE_MARKET_ORDERS
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.dialogs.iom_input_dialog import IomInputDialog
from TriblerGUI.dialogs.newmarketorderdialog import NewMarketOrderDialog
from TriblerGUI.tribler_action_menu import TriblerActionMenu
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path
from TriblerGUI.widgets.marketcurrencybox import MarketCurrencyBox
from TriblerGUI.widgets.tickwidgetitem import TickWidgetItem


class MarketPage(QWidget):
    """
    This page displays the decentralized market in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.request_mgr = None
        self.asks_request_mgr = None
        self.bids_request_mgr = None
        self.dialog = None
        self.initialized = False
        self.wallets = []
        self.chosen_wallets = None
        self.wallet_widgets = {}

        self.bids = []
        self.asks = []

    def initialize_market_page(self):

        if not self.initialized:
            self.window().market_back_button.setIcon(QIcon(get_image_path('page_back.png')))

            self.window().core_manager.events_manager.received_market_ask.connect(self.on_ask)
            self.window().core_manager.events_manager.received_market_bid.connect(self.on_bid)
            self.window().core_manager.events_manager.expired_market_ask.connect(self.on_ask_timeout)
            self.window().core_manager.events_manager.expired_market_bid.connect(self.on_bid_timeout)
            self.window().core_manager.events_manager.market_payment_received.connect(self.on_payment)
            self.window().core_manager.events_manager.market_payment_sent.connect(self.on_payment)
            self.window().core_manager.events_manager.market_transaction_complete.connect(self.on_transaction_complete)
            self.window().core_manager.events_manager.market_iom_input_required.connect(self.on_iom_input_required)

            self.window().create_ask_button.clicked.connect(self.on_create_ask_clicked)
            self.window().create_bid_button.clicked.connect(self.on_create_bid_clicked)
            self.window().market_currency_type_button.clicked.connect(self.on_currency_type_clicked)
            self.window().market_transactions_button.clicked.connect(self.on_transactions_button_clicked)
            self.window().market_wallets_button.clicked.connect(self.on_wallets_button_clicked)
            self.window().market_orders_button.clicked.connect(self.on_orders_button_clicked)
            self.window().market_create_wallet_button.clicked.connect(self.on_wallets_button_clicked)

            # Sort asks ascending and bids descending
            self.window().asks_list.sortItems(2, Qt.AscendingOrder)
            self.window().bids_list.sortItems(2, Qt.DescendingOrder)

            self.window().asks_list.itemSelectionChanged.connect(
                lambda: self.on_tick_item_clicked(self.window().asks_list))
            self.window().bids_list.itemSelectionChanged.connect(
                lambda: self.on_tick_item_clicked(self.window().bids_list))

            self.window().tick_detail_container.hide()
            self.window().market_create_wallet_button.hide()

            self.initialized = True

        self.load_wallets()

    def load_wallets(self):
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("wallets", self.on_wallets)

    def on_wallets(self, wallets):
        wallets = wallets["wallets"]

        currency_wallets = ['BTC']
        total_currency_wallets = 0
        for wallet_id in wallets.keys():
            if wallet_id in currency_wallets:
                total_currency_wallets += 1

        if currency_wallets == 0:
            self.window().market_create_wallet_button.show()
            self.window().create_ask_button.hide()
            self.window().create_bid_button.hide()

        self.wallets = []
        for wallet_id in wallets.keys():
            self.wallets.append(wallet_id)

        if self.chosen_wallets is None and len(self.wallets) >= 2:
            self.chosen_wallets = (self.wallets[0], self.wallets[1])
            self.update_button_texts()

        for wallet_id, wallet in wallets.iteritems():
            if not wallet['created'] or not wallet['unlocked']:
                continue

            if wallet_id not in self.wallet_widgets:
                wallet_widget = MarketCurrencyBox(self.window().market_header_widget, wallets[wallet_id]['name'])
                self.window().market_header_widget.layout().insertWidget(4, wallet_widget)
                wallet_widget.setFixedWidth(100)
                wallet_widget.setFixedHeight(34)
                wallet_widget.show()
                self.wallet_widgets[wallet_id] = wallet_widget

                spacer = QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.window().market_header_widget.layout().insertSpacerItem(5, spacer)

            # The total balance keys might be different between wallet
            balance_amount = wallet['balance']['available']
            balance_currency = None

            if wallet_id == 'PP' or wallet_id == 'ABNA' or wallet_id == 'RABO':
                balance_currency = wallet['balance']['currency']

            self.wallet_widgets[wallet_id].update_with_amount(balance_amount, balance_currency)

        self.load_asks()
        self.load_bids()

    def update_button_texts(self):
        self.window().market_currency_type_button.setText("%s / %s" % (self.chosen_wallets[0], self.chosen_wallets[1]))
        self.window().create_ask_button.setText("Sell %s for %s" % (self.chosen_wallets[0], self.chosen_wallets[1]))
        self.window().create_bid_button.setText("Buy %s for %s" % (self.chosen_wallets[0], self.chosen_wallets[1]))

    def create_widget_item_from_tick(self, tick_list, tick, is_ask=True):
        tick["type"] = "ask" if is_ask else "bid"
        item = TickWidgetItem(tick_list, tick)
        item.setText(0, "%s %s" % (tick["quantity"], tick["quantity_type"]))
        item.setText(1, "%s %s" % (tick["price"], tick["price_type"]))
        return item

    def load_asks(self):
        self.asks_request_mgr = TriblerRequestManager()
        self.asks_request_mgr.perform_request("market/asks", self.on_received_asks)

    def on_received_asks(self, asks):
        self.asks = asks["asks"]
        self.update_filter_asks_list()

    def update_filter_asks_list(self):
        self.window().asks_list.clear()

        ticks = None
        for price_level_info in self.asks:
            if (price_level_info['quantity_type'], price_level_info['price_type']) == self.chosen_wallets:
                ticks = price_level_info["ticks"]
                break

        if ticks:
            for ask in ticks:
                self.window().asks_list.addTopLevelItem(
                    self.create_widget_item_from_tick(self.window().asks_list, ask, is_ask=True))

    def load_bids(self):
        self.bids_request_mgr = TriblerRequestManager()
        self.bids_request_mgr.perform_request("market/bids", self.on_received_bids)

    def on_received_bids(self, bids):
        self.bids = bids["bids"]
        self.update_filter_bids_list()

    def update_filter_bids_list(self):
        self.window().bids_list.clear()

        ticks = None
        for price_level_info in self.bids:
            if (price_level_info['quantity_type'], price_level_info['price_type']) == self.chosen_wallets:
                ticks = price_level_info["ticks"]
                break

        if ticks:
            for bid in ticks:
                self.window().bids_list.addTopLevelItem(
                    self.create_widget_item_from_tick(self.window().bids_list, bid, is_ask=False))

    def on_ask(self, ask):
        has_level = False
        for price_level_info in self.asks:
            if price_level_info['quantity_type'] == ask['quantity_type'] \
                    and price_level_info['price_type'] == ask['price_type']:
                price_level_info['ticks'].append(ask)
                has_level = True

        if not has_level:
            self.asks.append({'price_type': ask['price_type'], 'quantity_type': ask['quantity_type'], 'ticks': [ask]})

        self.update_filter_asks_list()

    def on_bid(self, bid):
        has_level = False
        for price_level_info in self.bids:
            if price_level_info['quantity_type'] == bid['quantity_type'] \
                    and price_level_info['price_type'] == bid['price_type']:
                price_level_info['ticks'].append(bid)

        if not has_level:
            self.bids.append({'price_type': bid['price_type'], 'quantity_type': bid['quantity_type'], 'ticks': [bid]})

        self.update_filter_bids_list()

    def on_transaction_complete(self, transaction):
        if transaction["mine"]:
            transaction = transaction["tx"]
            main_text = "Transaction with price %f %s and quantity %f %s completed." \
                        % (transaction["price"], transaction["price_type"],
                           transaction["quantity"], transaction["quantity_type"])
            self.window().tray_icon.showMessage("Transaction completed", main_text)
            self.window().hide_status_bar()

            # Reload wallets
            self.load_wallets()

            # Reload transactions
            self.window().market_transactions_page.load_transactions()
        else:
            self.load_asks()
            self.load_bids()

    def on_iom_input_required(self, event_dict):
        self.dialog = IomInputDialog(self.window().stackedWidget, event_dict['bank_name'], event_dict['input'])
        self.dialog.button_clicked.connect(self.on_iom_input)
        self.dialog.show()

    def on_iom_input(self, action):
        if action == 1:
            post_data = {'input_name': self.dialog.required_input['name']}
            for input_name, input_widget in self.dialog.input_widgets.iteritems():
                post_data[input_name] = input_widget.text()

            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("iominput", None, data=urlencode(post_data), method='POST')

        self.dialog.setParent(None)
        self.dialog = None

    def create_order(self, is_ask, price, price_type, quantity, quantity_type):
        post_data = str("price=%f&price_type=%s&quantity=%f&quantity_type=%s" %
                        (price, price_type, quantity, quantity_type))
        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("market/%s" % ('asks' if is_ask else 'bids'),
                                         lambda response: self.on_order_created(response, is_ask),
                                         data=post_data, method='PUT')

    def on_transactions_button_clicked(self):
        self.window().market_transactions_page.initialize_transactions_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET_TRANSACTIONS)

    def on_wallets_button_clicked(self):
        self.window().market_wallets_page.initialize_wallets_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET_WALLETS)

    def on_orders_button_clicked(self):
        self.window().market_orders_page.initialize_orders_page()
        self.window().navigation_stack.append(self.window().stackedWidget.currentIndex())
        self.window().stackedWidget.setCurrentIndex(PAGE_MARKET_ORDERS)

    def on_order_created(self, response, is_ask):
        if is_ask:
            self.load_asks()
        else:
            self.load_bids()

    def on_tick_item_clicked(self, tick_list):
        if len(tick_list.selectedItems()) == 0:
            return
        tick = tick_list.selectedItems()[0].tick

        if tick_list == self.window().asks_list:
            self.window().bids_list.clearSelection()
        else:
            self.window().asks_list.clearSelection()

        tick_time = datetime.datetime.fromtimestamp(int(tick["timestamp"])).strftime('%Y-%m-%d %H:%M:%S')
        self.window().market_detail_trader_id_label.setText(tick["trader_id"])
        self.window().market_detail_order_number_label.setText("%s" % tick["order_number"])
        self.window().market_detail_quantity_label.setText("%s %s" % (tick["quantity"], tick["quantity_type"]))
        self.window().market_detail_price_label.setText("%s %s" % (tick["price"], tick["price_type"]))
        self.window().market_detail_time_created_label.setText(tick_time)

        self.window().tick_detail_container.show()

    def on_create_ask_clicked(self):
        self.show_new_order_dialog(True)

    def on_create_bid_clicked(self):
        self.show_new_order_dialog(False)

    def on_currency_type_clicked(self):
        menu = TriblerActionMenu(self)

        for first_wallet_id in self.wallets:
            sub_menu = menu.addMenu(first_wallet_id)

            for second_wallet_id in self.wallets:
                if first_wallet_id == second_wallet_id:
                    continue

                wallet_action = QAction('%s / %s' % (first_wallet_id, second_wallet_id), self)
                wallet_action.triggered.connect(
                    lambda _, id1=first_wallet_id, id2=second_wallet_id: self.on_currency_type_changed(id1, id2))
                sub_menu.addAction(wallet_action)
        menu.exec_(QCursor.pos())

    def on_currency_type_changed(self, currency1, currency2):
        self.chosen_wallets = (currency1, currency2)
        self.update_button_texts()
        self.update_filter_asks_list()
        self.update_filter_bids_list()

    def show_new_order_dialog(self, is_ask):
        self.dialog = NewMarketOrderDialog(self.window().stackedWidget, is_ask, self.chosen_wallets[1], self.chosen_wallets[0])
        self.dialog.button_clicked.connect(self.on_new_order_action)
        self.dialog.show()

    def on_new_order_action(self, action):
        if action == 1:
            self.create_order(self.dialog.is_ask, self.dialog.price, self.dialog.price_type,
                              self.dialog.quantity, self.dialog.quantity_type)

        self.dialog.setParent(None)
        self.dialog = None

    def on_ask_timeout(self, ask):
        self.remove_tick_with_msg_id(self.window().asks_list, ask["message_id"])

    def on_bid_timeout(self, bid):
        self.remove_tick_with_msg_id(self.window().bids_list, bid["message_id"])

    def remove_tick_with_msg_id(self, tick_list, msg_id):
        index_to_remove = -1
        for ind in xrange(tick_list.topLevelItemCount()):
            item = tick_list.topLevelItem(ind)
            if item.tick["message_id"] == msg_id:
                index_to_remove = ind
                break

        if index_to_remove != -1:
            tick_list.takeTopLevelItem(index_to_remove)

    def on_payment(self, payment):
        if not payment["success"]:
            # Error occurred during payment
            main_text = "Transaction with id %s failed." % payment["transaction_number"]
            self.window().tray_icon.showMessage("Transaction failed", main_text)
            ConfirmationDialog.show_error(self.window(), "Transaction failed", main_text)
            self.window().hide_status_bar()
        else:
            self.window().show_status_bar("Transaction in process, please don't close Tribler.")
