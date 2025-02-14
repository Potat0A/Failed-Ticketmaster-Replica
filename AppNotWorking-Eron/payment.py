class Payment:
    def __init__(self, name, email, contact_number, payment_id, amount, payment_method):
        self.__name = name
        self.__email = email
        self.__contact_number = contact_number
        self.__payment_id = str(payment_id)
        self.__amount = amount
        self.__payment_method = payment_method

    def get_name(self):
        return self.__name

    def get_email(self):
        return self.__email

    def get_contact_number(self):
        return self.__contact_number

    def get_payment_id(self):
        return str(self.__payment_id)

    def get_amount(self):
        return self.__amount

    def get_payment_method(self):
        return self.__payment_method

    def set_name(self, name):
        self.__name = name

    def set_email(self, email):
        self.__email = email

    def set_contact_number(self, contact_number):
        self.__contact_number = contact_number

    def set_payment_id(self, payment_id):
        self.__payment_id = str(payment_id)

    def set_amount(self, amount):
        self.__amount = amount

    def set_payment_method(self, payment_method):
        self.__payment_method = payment_method


class PaymentMethod:
    def __init__(self, card_number, expiry_date, cvv):
        self.__card_number = card_number
        self.__expiry_date = expiry_date
        self.__cvv = cvv

    def get_card_number(self):
        return self.__card_number

    def get_expiry_date(self):
        return self.__expiry_date

    def get_cvv(self):
        return self.__cvv

    def set_card_number(self, card_number):
        self.__card_number = card_number

    def set_expiry_date(self, expiry_date):
        self.__expiry_date = expiry_date

    def set_cvv(self, cvv):
        self.__cvv = cvv


class Ticket:
    def __init__(self, name, seat_number, seat_row, seat_section, seat_type, amount, image):
        self.name = name
        self.seat_number = seat_number
        self.seat_row = seat_row
        self.seat_section = seat_section
        self.seat_type = seat_type
        self.amount = amount
        self.image = image

    def access_ticket(self):
        return {
            'name': self.name,
            'seat_number': self.seat_number,
            'seat_row': self.seat_row,
            'seat_section': self.seat_section,
            'seat_type': self.seat_type,
            'amount': self.amount,
            'image': self.image,
        }


class Amount:
    def __init__(self, base_price, GST, platform_fee, total):
        self.__base_price = base_price
        self.__platform_fee = platform_fee
        self.__GST = GST
        self.__total = total

    def get_base_price(self):
        return {'base_price': self.__base_price}

    def get_platform_fee(self):
        return {'platform_fee': self.__platform_fee}

    def get_GST(self):
        return {'GST': self.__GST}

    def get_total(self):
        return {'total': self.__total}

    def set_base_price(self, price, gst, platform_fee):
        return price - gst - platform_fee

    def set_platform_fee(self, price):
        return price * (2/100)

    def set_GST(self, price):
        return price * (9/100)

    def set_total(self, price):
        return price
