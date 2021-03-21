import alpaca_trade_api as tradeapi
import datetime
import os

#Credentials
alpaca_api_key = os.getenv('ALPACA_CLIENT_ID')
alpaca_api_secret = os.getenv('ALPACA_CLIENT_SECRET')
alpaca_base_url = 'https://paper-api.alpaca.markets'

alpaca_api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, alpaca_base_url, api_version='v2')

today = datetime.datetime.today().date()
from_day = today
to_day = today


#ba_bars = alpaca_api.get_quotes('BA', start=from_day, end=to_day, limit=1)
ba_bars = alpaca_api.get_barset('BA', '1Min', limit=1) #Current Price = h
account_balance = alpaca_api.get_account() #buying power
account_assets = alpaca_api.list_positions() #all positions

print(account_assets)

# buy_ccvi = alpaca_api.submit_order('CCIV',)

