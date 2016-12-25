import random


class WarrantyBase:
    def __init__(self):
        pass

    @staticmethod
    def error_msg(msg):
        print '\n[!] HTTP error. Message was: %s' % str(msg)

    @staticmethod
    def generate_random_order_no():
        order_no = ''
        for index in range(9):
            order_no += str(random.randint(0, 9))
        return order_no

    def run_warranty_check(self, inline_serials, retry=True):
        raise NotImplementedError

    def process_result(self, result, purchases):
        raise NotImplementedError
