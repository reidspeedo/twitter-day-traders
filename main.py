import tweepy
import logging.config
import os
import time
import threading
import datetime
import alpaca_trade_api as tradeapi
from sys import platform

from services import services as svr
from configuration import logger

if platform == 'darwin':
    import caffeine
    caffeine.on(display=False)

# https://twitter.com/anyuser/status/1372075679941070850

def create_api():
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        # logger.info("authentication success")
    except Exception as e:
        # logger.error("Error creating API", exc_info=True)
        raise e
    # logger.info("API created")
    return api

def create_alpaca_api():
    alpaca_api_key = 'PKFH6HVRYFE9M8QAIHVW'
    alpaca_api_secret = 'zu8zScHNhRpMkxM37bOhRO2l9zmkgz1GTYoivw4l'
    alpaca_base_url = 'https://paper-api.alpaca.markets'
    alpaca_api = tradeapi.REST(alpaca_api_key, alpaca_api_secret, alpaca_base_url, api_version='v2')
    return alpaca_api

class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, api):
        self.api = api
        self.me = api.me()

    def on_status(self, tweet):
        clean_tweet, include_tweet, tickers = self.filter_extract_tickers(tweet)
        if include_tweet:
            new_row = self.format_tweet(tweet, tickers)
            svr.create_tweet(new_row)

    def on_error(self, status):
        logger.error(status)

    def filter_extract_tickers(self, tweet):
        unique_tickers = []
        if '$' in tweet.text:
            split_tweet = tweet.text.split()
            tickers = split_tweet.copy()
            for word in split_tweet:
                if '$' not in word:
                    tickers.remove(word)
                elif any(char.isdigit() for char in word):
                    tickers.remove(word)
                elif not any(char.isalpha() for char in word):
                    tickers.remove(word)
                else:
                    pass

            for i in tickers:
                tick = i.upper().replace('.','')
                if tick not in unique_tickers:
                    unique_tickers.append(tick.upper())

            if len(unique_tickers) > 0:
                include_tweet = True
            else:
                include_tweet = False
        else:
            logging.info(f'No ticker found in tweet: {tweet.id}')
            include_tweet = False
        return tweet, include_tweet, unique_tickers

    def format_tweet(self, tweet, tickers):
        df_new_row = \
            {
                'tweet_id': tweet.id_str,
                'create_at': tweet.created_at,
                'user_id': tweet.user.id_str,
                'user_name': tweet.user.screen_name,
                'tweet_text': tweet.text,
                'tickers': tickers
            }
        # logger.info(df_new_row)
        return df_new_row

def streamer(my_twitterid = '1369887486810353664'):
    api = create_api()
    friends = [my_twitterid]
    for follower in api.friends():
        friends.append(str(follower.id))
    tweets_listener = FavRetweetListener(api)

    while True:
        try:
            stream = tweepy.Stream(api.auth, tweets_listener)
            stream.filter(follow=friends)
        except:
            continue
    return api

class GraphTickers():
    def __init__(self):
        self.last_datetime = ''
        self.graph_data = {}
        self.watchlist_dict = {}
        self.current_positions = {}
        self.orders = []
        self.cannot_buy = {}
        self.buy_orders = {}
        self.sell_orders = {}
        self.cannot_sell = {}

    def percentage_change(self,original, current):
        diff = ((current - original) / original) * 100
        return round(diff,2)

    def logging_function(self, refresh=5, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                logger.info(f'----------------sleeping until trading opens-----------------')
                break
            else:
                cp_string = ''
                total_percentage = 0
                logger.info('\n-------------------------------------------------------------')
                logger.info(f'Ticker Watchlist: {self.watchlist_dict}')
                for key, value in self.current_positions.items():
                    percentage = self.percentage_change(float(value['avg_entry_price']), float(value['current_price']))
                    total_percentage = total_percentage + percentage
                    cp_string = cp_string + f" {key}: {percentage}%"

                logger.info(f'Current Positions: {round(total_percentage,2)}% / {cp_string}')
                logger.info(f'Orders Pending: {self.orders}')
                logger.info(f'Successfully initiated BUY for: {self.buy_orders}')
                logger.info(f'Successfully initiated SELL for: {self.sell_orders}')
                logger.info(f'Error selling for: {self.cannot_sell}')
                logger.info(f'Error buying for: {self.cannot_buy}')
                logger.info('-------------------------------------------------------------')

    def refresh_graph_data(self, start_date=datetime.datetime.today().date(), refresh=5, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            if self.last_datetime == '':
                self.last_datetime = datetime.datetime.combine(start_date, datetime.time(0, 0))

            self.last_datetime, delta_graph_data = svr.retrieve_tweets(self.last_datetime, self.last_datetime)
            for key, value in delta_graph_data.items():
                if key in self.graph_data.keys():
                    self.graph_data[key] += value
                else:
                    self.graph_data[key] = value
            time.sleep(refresh)

    def watchlist(self, refresh=5, count=5, end_hour=13, end_minute=0):
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            self.watchlist_dict = {}
            for i, (k, v) in enumerate(sorted(self.graph_data.items(), key=lambda item: item[1], reverse=True)):
                if len(self.watchlist_dict) < (count+1) and (k not in self.cannot_buy.keys()):
                    self.watchlist_dict[k] = v
            time.sleep(refresh)

    def alpca_buy_ticker(self, alpaca_api, refresh=5, end_hour=13, end_minute=0):
        time.sleep(10)
        while True:
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break

            for ticker in self.watchlist_dict.keys():
                if ticker not in self.current_positions.keys() and ticker not in self.orders:
                    try:
                        alpaca_api.submit_order(symbol=ticker.replace('$',''), qty=100, side='buy', type='market', time_in_force='day')
                        self.buy_orders[ticker] = datetime.datetime.now()
                    except Exception as e:
                        self.cannot_buy[ticker] = (e, datetime.datetime.now())

            time.sleep(refresh)
    def alpaca_monitor_and_sell(self, alpaca_api, refresh = 5, max_diff = 10, diff = 2, end_hour=13, end_minute=0):
        while True:
            temp_current_position = {}
            if datetime.datetime.today().hour >= end_hour and datetime.datetime.today().minute >= end_minute:
                break
            all_position_details = alpaca_api.list_positions()
            all_order_details = alpaca_api.list_orders()
            for position in all_position_details:
                ticker = f'${position.symbol}'
                temp_dict = dict(current_price=position.current_price,avg_entry_price=position.avg_entry_price,qty=position.qty)
                temp_current_position[ticker] = temp_dict
                self.current_positions = temp_current_position

                #Retrieve High Price into repository:
                ticker_high_price = svr.retrieve_highest_price(ticker)
                if ticker_high_price == '':
                    ticker_high_price = float(svr.create_highest_price({'ticker': ticker, 'high_price': position.current_price}))
                else:
                    ticker_high_price = float(ticker_high_price)
                    current_price = float(position.current_price)
                    buy_price = float(position.avg_entry_price)
                    if current_price > ticker_high_price: #if you are positive - how positive?
                        current_diff = ((current_price/buy_price)-1)*100
                        if current_diff > max_diff: #If you've made 30% profit then sell
                            try:
                                alpaca_api.submit_order(symbol=ticker.replace('$',''), qty=100, side='sell', type='market', time_in_force='day')
                                self.sell_orders[ticker] = datetime.datetime.now()
                                svr.remove_highest_price(ticker)
                            except Exception as e:
                                self.cannot_sell[ticker] = (e, datetime.datetime.now())
                        else: #If <30% then just update the highest price
                            svr.update_highest_price({'ticker': ticker, 'high_price': position.current_price})
                    else: #if you are negative - how negative?
                        current_diff = (1-(current_price/ticker_high_price))*100
                        if current_diff > diff:
                            try:
                                alpaca_api.submit_order(symbol=ticker.replace('$',''), qty=100, side='sell', type='market', time_in_force='day')
                                self.sell_orders[ticker] = datetime.datetime.now()
                                svr.remove_highest_price(ticker)
                            except Exception as e:
                                self.cannot_sell[ticker] = (e, datetime.datetime.now())

            self.orders = [f'${order.symbol}' for order in all_order_details]
            time.sleep(refresh)

def main(start_hour=6, start_minute=35, end_hour=13, end_minute=0):
    alpaca_api = create_alpaca_api()
    grapher = GraphTickers()
    stream_object = threading.Thread(target=streamer)
    stream_object.start()

    for i in range(0, 365):
        t = datetime.datetime.today()
        future = datetime.datetime(t.year, t.month, t.day, start_hour, start_minute)
        if t.hour > start_hour:
            future += datetime.timedelta(days=1)
        elif t.hour == start_hour and t.minute > start_minute:
            future += datetime.timedelta(days=1)
        else:
            pass
        wait = (future - t).total_seconds()
        logging.info(f'...Paused for {wait/60} minutes until next runtime...')
        time.sleep(wait)

        logging_function_object = threading.Thread(target=grapher.logging_function, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        watchlist_object = threading.Thread(target=grapher.watchlist, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        graphing_object = threading.Thread(target=grapher.refresh_graph_data, kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        alpaca_object = threading.Thread(target=grapher.alpaca_monitor_and_sell, args=(alpaca_api,), kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        alpaca_buy = threading.Thread(target=grapher.alpca_buy_ticker, args=(alpaca_api,), kwargs={'end_hour':end_hour, 'end_minute':end_minute})
        logging_function_object.start()
        watchlist_object.start()
        graphing_object.start()
        alpaca_object.start()
        alpaca_buy.start()
        logging_function_object.join()
        watchlist_object.join()
        graphing_object.join()
        alpaca_object.join()
        alpaca_buy.join()


if __name__ == '__main__':
    # alpaca_api.cancel_all_orders()
    # alpaca_api = create_alpaca_api()
    # print(alpaca_api.list_positions())
     main(start_hour=13, start_minute=6, end_hour=13, end_minute=7)












