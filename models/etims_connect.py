import json

import requests
from datetime import datetime
import logging
from odoo.exceptions import UserError, ValidationError
import datetime

_logger = logging.getLogger(__name__)


class ETIMSConnect:
    tin = None
    bhfId = None
    cmcKey = None
    env = None

    # create a constructor
    def __init__(self, tin, bhfId):
        self.tin = tin
        if not bhfId:
            self.bhfId = '00'
        else:
            self.bhfId = bhfId

    def save_item_composition(self, payload):
        url = 'items/saveItemComposition'
        return self.send_request(url, payload).json()
    def notice_search(self):
        url = 'notices/selectNotices'
        payload = json.dumps({
            "tin": self.tin,
            "bhfId": self.bhfId,
            "lastReqDt": "20180520000000"
        })
        return self.send_request(url, payload).json()

    def get_code_list(self):
        url = 'code/selectCodes'
        payload = json.dumps({
            "lastReqDt": "20180218191141",
            "tin": self.tin,
            "bhfId": self.bhfId,
        })
        return self.send_request(url, payload).json()

    def get_item_classification_list(self):
        url = 'itemClass/selectItemsClass'
        payload = json.dumps({
            "tin": self.tin,
            "bhfId": self.bhfId,
            "lastReqDt": "20180520000000"
        })
        return self.send_request(url, payload).json()

    def get_branch_list(self):
        url = 'branches/selectBranches'
        payload = json.dumps({
            "tin": self.tin,
            "bhfId": "00",
            "lastReqDt": "20180520000000"
        })
        return self.send_request(url, payload).json()

    def get_imports(self):
        url = 'imports/selectImportItems'
        payload = json.dumps({
            "tin": self.tin,
            "bhfId": self.bhfId,
            "lastReqDt": "20180520000000"
        })
        return self.send_request(url, payload).json()

    def get_purchases(self):
        url = 'trnsPurchase/selectTrnsPurchaseSales'
        last_req_date = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

        payload = json.dumps({
            "tin": self.tin,
            "bhfId": self.bhfId,
            "lastReqDt": "20180520000000"
            # "lastReqDt": f"{last_req_date}",
        })
        return self.send_request(url, payload).json()


    def get_stock_movement_list(self):
        url = '/stock/selectStockItems'
        last_req_date = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

        payload = json.dumps({
            "tin": self.tin,
            "bhfId": self.bhfId,
            "lastReqDt": "20180524000000"
            # "lastReqDt": f"{last_req_date}",
        })
        return self.send_request(url, payload).json()

    def save_customer(self, payload):
        url = 'branches/saveBrancheCustomers'
        return self.send_request(url, payload).json()

    def initialize_etims(self, payload):
        url = '/initializer/selectInitInfo'
        return self.send_request(url, payload).json()

    def save_item(self, payload):
        url = 'items/saveItems'
        return self.send_request(url, payload).json()

    def save_insurance(self, payload):
        url = 'branches/saveBrancheInsurances'
        return self.send_request(url, payload).json()

    def save_move(self, payload):
        url = 'trnsSales/saveSales'
        return self.send_request(url, payload).json()

    def save_user(self, payload):
        url = 'branches/saveBrancheUsers'
        return self.send_request(url, payload).json()

    def get_import_item(self, payload):
        url = ''
        return self.send_request(url, payload).json()

    def move_master_update(self, payload):
        url = 'stockMaster/saveStockMaster'
        return self.send_request(url, payload).json()

    def send_converted_imports(self, payload):
        url = 'imports/updateImportItems'
        return self.send_request(url, payload).json()

    def send_converted_purchase(self, payload):
        url = 'trnsPurchase/savePurchases'
        return self.send_request(url, payload).json()

    def move_stock(self, payload):
        url = 'stock/saveStockItems'
        return self.send_request(url, payload).json()


    def select_items(self, payload):
        url = 'items/selectItems'
        return self.send_request(url, payload).json()

    def search_customer(self, payload):
        url = 'selectCustomer'
        return self.send_request(url, payload).json()

    def send_request(self, url, payload):

        headers = {
            'Content-Type': 'application/json',
        }

        base_url = 'http://84.247.169.33:8088/'

        url = base_url + url

        try:
            _logger.info('==========================etims-header==========================')
            _logger.info(headers)
            _logger.info(url)

            _logger.info('******************end-etims-headers******************')
            _logger.info('==========================etims-request==========================')
            _logger.info(payload)

            _logger.info('******************end-etims-request******************')

            response = requests.request("POST", url, data=payload, headers=headers)  # stop sending headers
            _logger.info('==========================etims-response==========================')
            _logger.info(response.text)
            _logger.info('******************end-etims-response******************')

            response_data = response.json()
            _logger.info(response.request.headers)
            _logger.info(response.request.body)

            if response_data.get('resultCd') != '000':
                _logger.error(response_data.get('resultMsg'))
                # raise ValidationError(f"API Error: {response_data.get('resultMsg')}")

            return response
        except Exception as e:
            _logger.error(e)
            return None
