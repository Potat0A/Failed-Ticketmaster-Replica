import shelve
from datetime import datetime, timedelta
import random


class TicketManager:
    def __init__(self, ticket_db_path='tickets.db', user_db_path='users.db'):
        self.ticket_db_path = ticket_db_path
        self.user_db_path = user_db_path

    def get_purchased_tickets(self, username):
        with shelve.open('tickets.db') as db:
            tickets = db.get('tickets', [])
            return [t for t in tickets if t.get('buyer') == username]

    def process_ticket_purchase(self, ticket_id, username):
        """
        Process a ticket purchase:
        1. Remove ticket from available tickets
        2. Add ticket to user's owned tickets
        3. Record the transaction
        """
        with shelve.open(self.ticket_db_path, writeback=True) as ticket_db, \
                shelve.open(self.user_db_path, writeback=True) as user_db:

            # Get all tickets
            tickets = ticket_db.get('tickets', [])

            # Find the ticket to purchase
            ticket_index = None
            purchased_ticket = None
            for idx, ticket in enumerate(tickets):
                if ticket['ticket_id'] == ticket_id:
                    ticket_index = idx
                    purchased_ticket = ticket.copy()  # Make a copy of the ticket
                    break

            if ticket_index is None:
                raise ValueError("Ticket not found")

            # Add ownership and purchase date to ticket
            purchase_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            purchased_ticket['owner'] = username
            purchased_ticket['purchase_date'] = purchase_time
            purchased_ticket['status'] = 'sold'

            # Assign a seat dynamically (for example purposes, we randomize it)
            purchased_ticket['seat_number'] = random.randint(1, 50)
            purchased_ticket['row'] = random.choice(['A', 'B', 'C', 'D', 'E'])
            purchased_ticket['section'] = random.choice(['North', 'South', 'East', 'West'])

            # Remove ticket from available tickets
            tickets.pop(ticket_index)
            ticket_db['tickets'] = tickets

            # Add to user's owned tickets
            if username in user_db:
                user_data = user_db[username]
                if 'owned_tickets' not in user_data:
                    user_data['owned_tickets'] = []
                user_data['owned_tickets'].append(purchased_ticket)
                user_db[username] = user_data

                return purchased_ticket
            else:
                raise ValueError("User not found")

    def get_user_owned_tickets(self, username):
        with shelve.open(self.user_db_path) as db:
            user_data = db.get(username, {})
            owned_tickets = user_data.get('owned_tickets', [])
        return owned_tickets

    def list_ticket_for_resale(self, ticket_id, username, listing_price, listing_type='mandatory'):
        """
        List a user's owned ticket for resale:
        1. Verify ticket ownership
        2. Create resale listing
        3. Add to available tickets
        """
        with shelve.open(self.user_db_path, writeback=True) as user_db, \
                shelve.open(self.ticket_db_path, writeback=True) as ticket_db:

            # Verify ownership
            user_data = user_db.get(username)
            if not user_data:
                raise ValueError("User not found")

            owned_tickets = user_data.get('owned_tickets', [])
            ticket_to_list = None
            ticket_index = None

            for idx, ticket in enumerate(owned_tickets):
                if ticket['ticket_id'] == ticket_id:
                    ticket_to_list = ticket.copy()
                    ticket_index = idx
                    break

            if not ticket_to_list:
                raise ValueError("Ticket not found in user's owned tickets")

            # Update ticket for resale
            listing_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ticket_to_list['original_owner'] = username
            ticket_to_list['resale_price'] = listing_price
            ticket_to_list['listing_type'] = listing_type
            ticket_to_list['listing_date'] = listing_time
            ticket_to_list['status'] = 'listed'

            # Add to available tickets
            tickets = ticket_db.get('tickets', [])
            tickets.append(ticket_to_list)
            ticket_db['tickets'] = tickets

            # Remove from user's owned tickets
            owned_tickets.pop(ticket_index)
            user_data['owned_tickets'] = owned_tickets
            user_db[username] = user_data

            return ticket_to_list