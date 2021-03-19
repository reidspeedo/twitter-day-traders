#V1

def alpca_buy_ticker(self, alpaca_api, refresh=5, end_hour=13, end_minute=0):
    time.sleep(10)
    while True:
        if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
            break

        for ticker in self.watchlist_dict.keys():
            if ticker not in self.current_positions.keys() and ticker not in self.orders:
                try:
                    alpaca_api.submit_order(symbol=ticker.replace('$', ''), qty=100, side='buy', type='market',
                                            time_in_force='day')
                    self.buy_orders[ticker] = datetime.datetime.now()
                except Exception as e:
                    self.cannot_buy[ticker] = (e, datetime.datetime.now())

        time.sleep(refresh)


def alpaca_monitor_and_sell(self, alpaca_api, refresh=5, max_diff=10, diff=2, end_hour=13, end_minute=0):
    while True:
        temp_current_position = {}
        if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
            break
        all_position_details = alpaca_api.list_positions()
        all_order_details = alpaca_api.list_orders()
        for position in all_position_details:
            ticker = f'${position.symbol}'
            temp_dict = dict(current_price=position.current_price, avg_entry_price=position.avg_entry_price,
                             qty=position.qty)
            temp_current_position[ticker] = temp_dict
            self.current_positions = temp_current_position

            # Sell Logic
            ticker_high_price = svr.retrieve_highest_price(ticker)
            if ticker_high_price == '':
                ticker_high_price = float(
                    svr.create_highest_price({'ticker': ticker, 'high_price': position.current_price}))
            else:
                ticker_high_price = float(ticker_high_price)
                current_price = float(position.current_price)
                buy_price = float(position.avg_entry_price)
                if current_price > ticker_high_price:  # if you are positive - how positive?
                    current_diff = ((current_price / buy_price) - 1) * 100
                    if current_diff > max_diff:  # If you've made 30% profit then sell
                        try:
                            alpaca_api.submit_order(symbol=ticker.replace('$', ''), qty=100, side='sell', type='market',
                                                    time_in_force='day')
                            self.sell_orders[ticker] = datetime.datetime.now()
                            svr.remove_highest_price(ticker)
                        except Exception as e:
                            self.cannot_sell[ticker] = (e, datetime.datetime.now())
                    else:  # If <30% then just update the highest price
                        svr.update_highest_price({'ticker': ticker, 'high_price': position.current_price})
                else:  # if you are negative - how negative?
                    current_diff = (1 - (current_price / ticker_high_price)) * 100
                    if current_diff > diff:
                        try:
                            alpaca_api.submit_order(symbol=ticker.replace('$', ''), qty=100, side='sell', type='market',
                                                    time_in_force='day')
                            self.sell_orders[ticker] = datetime.datetime.now()
                            svr.remove_highest_price(ticker)
                        except Exception as e:
                            self.cannot_sell[ticker] = (e, datetime.datetime.now())

        self.orders = [f'${order.symbol}' for order in all_order_details]
        time.sleep(refresh)