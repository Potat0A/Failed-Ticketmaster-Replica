from wtforms import Form, StringField, validators, RadioField, SelectField
from wtforms.fields import EmailField
from wtforms.fields.datetime import DateField
from wtforms.fields.numeric import IntegerField, DecimalField
import datetime


# custom validator must begin with validate_
class PaymentForm(Form):

    def validate_expiry_date(form, field):
        expiry_date = field.data
        if expiry_date < datetime.date.today():
            raise validators.ValidationError("Card expired")

    payment_method = RadioField('Payment Method', choices=[('paynow', 'PayNow'),
                                                           ('paypal', 'PayPal'), ('card', 'Credit/Debit Card')])
    card_number = StringField('Card Number', [validators.DataRequired(),
                                              validators.Length(min=16, max=16,
                                                                message="Card number must be 16 digits")])
    expiry_date = DateField('Expiry Date (MM/YY)', [validators.DataRequired(), validate_expiry_date])
    cvv = IntegerField('CVV', [validators.DataRequired(), validators.NumberRange(min=100, max=9999,
                                                                                 message="Invalid CVV")])

    def get_card_number(self):
        return self.card_number

    def get_expiry_date(self):
        return self.expiry_date

    def get_cvv(self):
        return self.cvv

    def set_card_number(self, card_number):
        self.card_number = card_number

    def set_expiry_date(self, expiry_date):
        self.expiry_date = expiry_date

    def set_cvv(self, cvv):
        self.cvv = cvv


class TicketListing(Form):
    name = StringField("name", [validators.Length(min=1, max=50), validators.DataRequired()])
    seat_number = StringField("seat_number", [validators.NumberRange(1, 1000)])
    seat_row = StringField("seat_row", [validators.DataRequired()])
    seat_section = StringField("seat_section", [validators.DataRequired()])
    seat_type = SelectField("seat_type", [validators.DataRequired()])
    # ticket_number = SelectField("Number of tickets:", [validators.DataRequired(),
    #                                                    validators.NumberRange(min=1, max=4)])
    amount = RadioField('Types of sales:', choices=[('Mandatory', 'mandatory'), ('Auction', 'auction')])
    # sales_date = DateField('Date to list (DD/MM/YYYY)', [validators.DataRequired()])
    image = SelectField('image')