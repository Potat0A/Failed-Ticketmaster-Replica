from datetime import datetime, timedelta


def calculate_date_range_data(days=7):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    total_orders = 0
    total_revenue = 0
    new_customers = 0

    try:
        # Get orders data
        with shelve.open('orders.db') as db:
            orders = db.get('orders', [])
            for order in orders:
                order_date = datetime.strptime(order.get('date', ''), "%Y-%m-%d %H:%M:%S")
                if start_date <= order_date <= end_date:
                    total_orders += 1
                    total_revenue += float(order.get('total_amount', 0))

        # Get customer registration data
        with shelve.open('users.db') as db:
            users = [user for user in db.values() if isinstance(user, dict)]
            new_customers = sum(
                1 for user in users
                if user.get('role') == 'customer'
                and start_date <= datetime.strptime(user.get('registration_date', ''), "%Y-%m-%d %H:%M:%S") <= end_date
            )

    except Exception as e:
        print(f"Error calculating metrics: {str(e)}")

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'new_customers': new_customers
    }